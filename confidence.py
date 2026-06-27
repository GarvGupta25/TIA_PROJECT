HIGH_RISK_FLAGS = {"EMPLOYEE_NOT_FOUND", "CLIENT_MISMATCH", "AMBIGUOUS_EMPLOYEE", "ID_NAME_MISMATCH", "INVOICE_AMOUNT_DEVIATION"}
MEDIUM_RISK_FLAGS = {"EXCESS_DAYS", "DAILY_HOURS_EXCEEDED", "IBAN_MISMATCH", "REIMBURSEMENT_HIGH", "MISSING_REQUIRED_FIELD"}


def calculate_confidence(record: dict) -> int:
    score = 100
    flags = set(record.get("anomaly_flags", []))
    score -= 18 * len(flags & HIGH_RISK_FLAGS)
    score -= 10 * len(flags & MEDIUM_RISK_FLAGS)
    score -= 5 * len(flags - HIGH_RISK_FLAGS - MEDIUM_RISK_FLAGS)
    if record.get("resolution_method") == "name_unique":
        score -= 8
    if record.get("source") == "image":
        score -= 5
    return max(0, min(100, score))


def assign_status(record: dict) -> dict:
    score = calculate_confidence(record)
    record["confidence_score"] = score
    flags = set(record.get("anomaly_flags", []))
    if "EMPLOYEE_NOT_FOUND" in flags or "CLIENT_MISMATCH" in flags:
        record["status"] = "REJECTED"
    elif score >= 85 and not flags:
        record["status"] = "AUTO_APPROVED"
    else:
        record["status"] = "REVIEW_REQUIRED"
    record["review_reason"] = build_review_reason(record)
    return record


def _money(value):
    try:
        return f"AED {float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "AED 0.00"


def build_review_reason(record: dict) -> str:
    flags = set(record.get("anomaly_flags", []))
    if record.get("status") == "AUTO_APPROVED" and not flags:
        return "No review needed - all validation checks passed."

    reasons = []
    emp_id = record.get("emp_id") or "missing employee ID"
    name = record.get("full_name") or "missing employee name"

    if "INVOICE_AMOUNT_DEVIATION" in flags:
        submitted = record.get("submitted_total")
        calculated = record.get("payroll", {}).get("final_total", 0)
        try:
            submitted_float = float(submitted or 0)
            delta_pct = abs(calculated - submitted_float) / submitted_float * 100 if submitted_float else 0
        except (TypeError, ValueError):
            delta_pct = 0
        reasons.append(
            f"Submitted amount {_money(submitted)} differs from calculated invoice total "
            f"{_money(calculated)} by {delta_pct:.1f}%, which is above the 5% tolerance."
        )
    if "EMPLOYEE_NOT_FOUND" in flags:
        reasons.append(f"Employee could not be matched in the database using {emp_id} / {name}.")
    if "CLIENT_MISMATCH" in flags:
        actual = (record.get("resolved_emp") or {}).get("client_code", "another client")
        reasons.append(f"Employee belongs to {actual}, not the selected client.")
    if "AMBIGUOUS_EMPLOYEE" in flags:
        count = len(record.get("ambiguous_candidates", []))
        reasons.append(f"Name matched {count} employees for this client, so manual selection is required.")
    if "ID_NAME_MISMATCH" in flags:
        db_name = (record.get("resolved_emp") or {}).get("full_name", "database employee name")
        reasons.append(f"Submitted name '{name}' does not match database name '{db_name}' for {emp_id}.")
    if "INACTIVE_EMPLOYEE" in flags:
        reasons.append("Employee is not marked Active in the database.")
    if "MISSING_REQUIRED_FIELD" in flags:
        reasons.append("Required employee identifier is missing; provide an employee ID or employee name.")
    if "EXCESS_DAYS" in flags:
        reasons.append(f"Working days value {record.get('working_days', 0)} exceeds the 26-day monthly limit.")
    if "DAILY_HOURS_EXCEEDED" in flags:
        reasons.append("At least one punch record has more than 10 working hours in a day.")
    if "IBAN_MISMATCH" in flags:
        reasons.append("Submitted IBAN does not match the employee IBAN in the database.")
    if "MISSING_REIMBURSEMENT_REASON" in flags:
        reasons.append("A reimbursement amount was submitted without a reason.")
    if "REIMBURSEMENT_HIGH" in flags:
        reasons.append("Reimbursement total is more than 20% of basic salary.")

    if reasons:
        return " ".join(reasons)
    if record.get("status") == "REJECTED":
        return "Record failed validation and cannot be auto-approved."
    return "Review required because confidence score is below the auto-approval threshold."
