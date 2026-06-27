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
    return record
