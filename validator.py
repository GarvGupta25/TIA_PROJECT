from database import get_connection, ensure_database, get_client_config


def lookup_by_emp_id(emp_id: str, client_code: str = None) -> dict:
    ensure_database()
    conn = get_connection()
    cur = conn.execute("SELECT * FROM employees WHERE UPPER(emp_id)=?", ((emp_id or "").strip().upper(),))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.close()
    if not row:
        return {"found": False, "emp": None, "flags": ["EMPLOYEE_NOT_FOUND"]}
    emp = dict(zip(cols, row))
    flags = []
    if str(emp.get("status", "")).lower() != "active":
        flags.append("INACTIVE_EMPLOYEE")
    if client_code and emp.get("client_code") != client_code:
        flags.append("CLIENT_MISMATCH")
    return {"found": True, "emp": emp, "flags": flags}


def lookup_by_name(full_name: str, client_code: str) -> dict:
    ensure_database()
    conn = get_connection()
    cur = conn.execute(
        "SELECT * FROM employees WHERE client_code=? AND LOWER(full_name) LIKE ?",
        (client_code, f"%{(full_name or '').strip().lower()}%"),
    )
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    if not rows:
        return {"found": False, "matches": [], "resolved": None, "flags": ["EMPLOYEE_NOT_FOUND"]}
    matches = [dict(zip(cols, row)) for row in rows]
    if len(matches) > 1:
        return {"found": True, "matches": matches, "resolved": None, "flags": ["AMBIGUOUS_EMPLOYEE"]}
    emp = matches[0]
    flags = []
    if str(emp.get("status", "")).lower() != "active":
        flags.append("INACTIVE_EMPLOYEE")
    return {"found": True, "matches": matches, "resolved": emp, "flags": flags}


def validate_record(record: dict, selected_client_code: str) -> dict:
    flags = list(record.get("anomaly_flags", []))
    emp_id = (record.get("emp_id") or "").strip()
    full_name = (record.get("full_name") or "").strip()

    if emp_id:
        result = lookup_by_emp_id(emp_id, selected_client_code)
        flags += result["flags"]
        record["resolved_emp"] = result["emp"] if result["found"] else None
        record["resolution_method"] = "id_direct" if result["found"] else "not_found"
        if result["found"] and full_name:
            db_name = result["emp"].get("full_name", "").lower()
            submitted = full_name.lower()
            if submitted not in db_name and db_name not in submitted:
                flags.append("ID_NAME_MISMATCH")
    elif full_name:
        result = lookup_by_name(full_name, selected_client_code)
        flags += result["flags"]
        if result["resolved"]:
            record["resolved_emp"] = result["resolved"]
            record["resolution_method"] = "name_unique"
        elif "AMBIGUOUS_EMPLOYEE" in result["flags"]:
            record["resolved_emp"] = None
            record["resolution_method"] = "name_ambiguous"
            record["ambiguous_candidates"] = result["matches"]
        else:
            record["resolved_emp"] = None
            record["resolution_method"] = "not_found"
    else:
        flags.append("MISSING_REQUIRED_FIELD")
        record["resolved_emp"] = None
        record["resolution_method"] = "not_found"

    days = float(record.get("working_days") or 0)
    if days > 26:
        flags.append("EXCESS_DAYS")
    for punch in record.get("punch_records", []) or []:
        if float(punch.get("hours_worked", 8) or 0) > 10:
            flags.append("DAILY_HOURS_EXCEEDED")
            break

    if record.get("iban") and record.get("resolved_emp") and record["iban"] != record["resolved_emp"].get("iban"):
        flags.append("IBAN_MISMATCH")

    reimbursements = record.get("reimbursements") or []
    for reimb in reimbursements:
        if not str(reimb.get("reason", "")).strip():
            flags.append("MISSING_REIMBURSEMENT_REASON")
    if record.get("resolved_emp") and reimbursements:
        basic = float(record["resolved_emp"].get("basic") or 0)
        reimb_sum = sum(float(r.get("amount") or 0) for r in reimbursements)
        if basic > 0 and reimb_sum > basic * 0.20:
            flags.append("REIMBURSEMENT_HIGH")

    if record.get("resolved_emp"):
        from payroll import calculate_payroll

        cfg = get_client_config(selected_client_code)
        calc = calculate_payroll(
            record["resolved_emp"],
            days,
            ot_hours=record.get("ot_hours", 0),
            reimbursements=reimbursements,
            markup_pct=cfg.get("markup_pct", 10.0),
        )
        record["payroll"] = calc
        submitted_total = record.get("submitted_total")
        if submitted_total:
            submitted = float(submitted_total)
            if submitted > 0:
                delta = abs(calc["final_total"] - submitted) / submitted * 100
                record["financial_match_pct"] = round(max(0, 100 - delta), 1)
                if delta > 5:
                    flags.append("INVOICE_AMOUNT_DEVIATION")

    record["anomaly_flags"] = sorted(set(flags))
    return record
