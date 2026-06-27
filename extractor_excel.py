import os

import pandas as pd

from confidence import assign_status
from validator import validate_record


ALIASES = {
    "emp_id": ["emp_id", "employee id", "employee_id", "id", "employee code"],
    "full_name": ["full name", "employee name", "name", "full_name"],
    "working_days": ["working days", "days", "attendance days", "working_days"],
    "ot_hours": ["ot hours", "overtime", "overtime hours", "ot_hours"],
    "submitted_total": ["submitted total", "invoice amount", "amount", "total", "submitted_total"],
    "iban": ["iban", "bank iban"],
    "reimbursement_amount": ["reimbursement", "reimbursements", "reimbursement amount", "expenses"],
    "reimbursement_reason": ["reimbursement reason", "expense reason", "reason"],
}


def _clean(value):
    if pd.isna(value):
        return None
    return value


def _find(row, key):
    normalized = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in ALIASES[key]:
        if alias in normalized:
            return _clean(normalized[alias])
    return None


def _to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", ""))
    except ValueError:
        return default


def extract_from_excel(file_path: str, selected_client_code: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(file_path)
    elif ext == ".tsv":
        df = pd.read_csv(file_path, sep="\t")
    else:
        df = pd.read_excel(file_path)

    records = []
    for _, row in df.iterrows():
        reimb_amount = _to_float(_find(row, "reimbursement_amount"))
        reimbursements = []
        if reimb_amount:
            reimbursements.append({"amount": reimb_amount, "reason": _find(row, "reimbursement_reason") or ""})
        record = {
            "source": "excel",
            "emp_id": str(_find(row, "emp_id") or "").strip() or None,
            "full_name": str(_find(row, "full_name") or "").strip() or None,
            "working_days": _to_float(_find(row, "working_days")),
            "ot_hours": _to_float(_find(row, "ot_hours")),
            "submitted_total": _to_float(_find(row, "submitted_total"), None),
            "iban": str(_find(row, "iban") or "").strip() or None,
            "reimbursements": reimbursements,
            "raw_input_snapshot": row.to_dict(),
            "anomaly_flags": [],
        }
        records.append(assign_status(validate_record(record, selected_client_code)))
    return records
