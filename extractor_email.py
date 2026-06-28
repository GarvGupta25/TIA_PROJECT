import os
import re
from email import policy
from email.parser import BytesParser

from confidence import assign_status
from validator import validate_record


def _read_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".eml":
        with open(file_path, "rb") as handle:
            msg = BytesParser(policy=policy.default).parse(handle)
        parts = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    parts.append(part.get_content())
        else:
            parts.append(msg.get_content())
        return "\n".join(parts)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()


def extract_from_pdf(file_path: str, selected_client_code: str):
    try:
        from pdfminer.high_level import extract_text
    except ImportError as exc:
        raise RuntimeError("Install pdfminer.six to extract PDF text.") from exc
    return _extract_from_text(extract_text(file_path), selected_client_code, "pdf")


def extract_from_email(file_path: str, selected_client_code: str):
    return _extract_from_text(_read_text(file_path), selected_client_code, "email")


def _amount_after(label, text):
    match = re.search(r"(?:" + label + r")\s*[:\-]?\s*(?:AED)?\s*([\d,]+(?:\.\d+)?)", text, re.I)
    return float(match.group(1).replace(",", "")) if match else 0.0


def _extract_from_text(text: str, selected_client_code: str, source: str):
    chunks = re.split(r"\n\s*\n|(?=Employee\s*ID\s*:)", text or "", flags=re.I)
    records = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        emp_match = re.search(r"(?:Employee\s*ID|Emp\s*ID|ID)\s*[:\-]\s*([A-Z0-9\-]+)", chunk, re.I)
        name_match = re.search(r"(?:Full\s*Name|Employee\s*Name|Name)\s*[:\-]\s*([^\n\r]+)", chunk, re.I)
        if not emp_match and not name_match:
            continue
        reimb = _amount_after(r"Reimbursement|Expense", chunk)
        reimbursements = [{"amount": reimb, "reason": "Parsed from email/PDF"}] if reimb else []
        record = {
            "source": source,
            "emp_id": emp_match.group(1).strip() if emp_match else None,
            "full_name": name_match.group(1).strip() if name_match else None,
            "working_days": _amount_after(r"Working\s*Days|Days", chunk),
            "ot_hours": _amount_after(r"OT\s*Hours|Overtime", chunk),
            "submitted_total": _amount_after(r"Submitted\s*Total|Invoice\s*Amount|Total", chunk) or None,
            "iban": (re.search(r"\bAE\d{21}\b", chunk) or [None])[0],
            "reimbursements": reimbursements,
            "raw_input_snapshot": chunk.strip(),
            "anomaly_flags": [],
        }
        records.append(assign_status(validate_record(record, selected_client_code)))
    return records
