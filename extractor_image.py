import json
import mimetypes
import os
import re
import tempfile
import uuid
from urllib import error, request

from confidence import assign_status
from validator import validate_record


REMOTE_EXTRACT_URL = os.getenv("IMAGE_EXTRACT_URL", "https://uncorrupt-lunar-imbecile.ngrok-free.dev/extract")
REMOTE_TIMEOUT_SECONDS = int(os.getenv("IMAGE_EXTRACT_TIMEOUT_SECONDS", "120"))


def _to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _parse_json_from_text(text):
    match = re.search(r"\{.*\}|\[.*\]", text or "", re.S)
    if not match:
        raise ValueError("Image model did not return JSON records.")
    return json.loads(match.group(0))


def _normalize_remote_payload(payload):
    if isinstance(payload, str):
        payload = _parse_json_from_text(payload)

    if isinstance(payload, dict) and str(payload.get("status", "")).lower() == "error":
        raise RuntimeError(payload.get("message") or "Image model returned an error.")

    if isinstance(payload, dict):
        for key in ("records", "data", "result", "results", "extracted_data", "items", "output"):
            if key in payload:
                return _normalize_remote_payload(payload[key])
        return [payload]

    if isinstance(payload, list):
        return payload

    raise ValueError("Image model returned an unsupported response shape.")


def _post_file_to_model(file_path):
    boundary = f"----TIAImageExtract{uuid.uuid4().hex}"
    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    with open(file_path, "rb") as handle:
        file_bytes = handle.read()

    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            file_bytes,
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    req = request.Request(
        REMOTE_EXTRACT_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "ngrok-skip-browser-warning": "true",
        },
    )

    try:
        with request.urlopen(req, timeout=REMOTE_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", "replace")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Image model request failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach image model at {REMOTE_EXTRACT_URL}: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _first_value(item, keys):
    for key in keys:
        if isinstance(item, dict) and item.get(key) not in (None, ""):
            return item.get(key)
    return None


def _normalize_reimbursements(value):
    if not value:
        return []
    if isinstance(value, (int, float, str)):
        amount = _to_float(value, None)
        return [{"amount": amount, "reason": ""}] if amount else []
    if isinstance(value, dict):
        value = [value]
    reimbursements = []
    for item in value:
        if not isinstance(item, dict):
            continue
        amount = _to_float(_first_value(item, ("amount", "reimbursement_amount", "expense_amount")), None)
        if amount:
            reimbursements.append({"amount": amount, "reason": _first_value(item, ("reason", "description", "expense_reason")) or ""})
    return reimbursements


def _records_from_model_file(file_path, selected_client_code, raw_source="image"):
    payload = _post_file_to_model(file_path)
    rows = _normalize_remote_payload(payload)
    records = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        record = {
            "source": "image",
            "emp_id": str(_first_value(item, ("emp_id", "employee_id", "employee_code", "id")) or "").strip() or None,
            "full_name": str(_first_value(item, ("full_name", "employee_name", "name")) or "").strip() or None,
            "working_days": _to_float(_first_value(item, ("working_days", "days", "attendance_days"))),
            "ot_hours": _to_float(_first_value(item, ("ot_hours", "overtime_hours", "overtime"))),
            "submitted_total": _to_float(_first_value(item, ("submitted_total", "invoice_amount", "amount", "total", "net_pay", "gross")), None),
            "iban": str(_first_value(item, ("iban", "bank_iban")) or "").strip() or None,
            "reimbursements": _normalize_reimbursements(
                _first_value(item, ("reimbursements", "reimbursement", "expenses", "reimbursement_amount"))
            ),
            "raw_input_snapshot": {"model_response": item, "source_file": os.path.basename(file_path), "raw_source": raw_source},
            "anomaly_flags": [],
        }
        records.append(assign_status(validate_record(record, selected_client_code)))
    return records


def _render_pdf_pages(file_path, output_dir):
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("Install pypdfium2 to route PDF pages through the image model.") from exc

    image_paths = []
    pdf = pdfium.PdfDocument(file_path)
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            pil_image = page.render(scale=2).to_pil().convert("RGB")
            image_path = os.path.join(output_dir, f"page_{index + 1}.png")
            pil_image.save(image_path)
            image_paths.append(image_path)
    finally:
        pdf.close()
    return image_paths


def extract_from_image(file_path: str, selected_client_code: str):
    return _records_from_model_file(file_path, selected_client_code, "image")


def extract_from_pdf_images(file_path: str, selected_client_code: str):
    records = []
    with tempfile.TemporaryDirectory(prefix="tia_pdf_pages_") as tmpdir:
        for image_path in _render_pdf_pages(file_path, tmpdir):
            records.extend(_records_from_model_file(image_path, selected_client_code, "pdf"))
    return records
