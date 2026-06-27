def _num(value, default=0.0):
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def calculate_payroll(emp: dict, working_days: float, ot_hours: float = 0, reimbursements=None, markup_pct: float = 10.0):
    reimbursements = reimbursements or []
    monthly_ctc = _num(emp.get("total_ctc")) or sum(_num(emp.get(k)) for k in ["basic", "housing", "transport", "food", "phone"])
    basic = _num(emp.get("basic"))
    working_days = max(0.0, min(_num(working_days), 31.0))
    daily_rate = monthly_ctc / 26 if monthly_ctc else 0
    gross_billable = round(daily_rate * working_days, 2)
    hourly_rate = basic / 26 / 8 if basic else 0
    ot_amount = round(hourly_rate * 1.25 * _num(ot_hours), 2)
    reimbursement_total = round(sum(_num(r.get("amount")) for r in reimbursements), 2)
    subtotal = gross_billable + ot_amount + reimbursement_total
    markup_amount = round(subtotal * _num(markup_pct) / 100, 2)
    invoice_amount = round(subtotal + markup_amount, 2)
    vat_amount = round(invoice_amount * 0.05, 2)
    final_total = round(invoice_amount + vat_amount, 2)
    return {
        "monthly_ctc": round(monthly_ctc, 2),
        "daily_rate": round(daily_rate, 2),
        "working_days_amount": gross_billable,
        "ot_amount": ot_amount,
        "reimbursement_total": reimbursement_total,
        "gross_billable": round(subtotal, 2),
        "markup_pct": _num(markup_pct),
        "markup_amount": markup_amount,
        "invoice_amount": invoice_amount,
        "vat_amount": vat_amount,
        "final_total": final_total,
    }
