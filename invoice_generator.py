import json
import os
import uuid
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from database import get_client_config, get_connection, log_audit


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
ALL_COLUMNS = [
    "emp_id", "full_name", "working_days", "ot_hours", "gross_billable",
    "markup_pct", "invoice_amount", "vat_amount", "final_total",
    "confidence_score", "status", "review_reason", "anomaly_flags",
]


def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _value(record, column):
    if column in record:
        return record[column]
    if column in record.get("payroll", {}):
        return record["payroll"][column]
    if column in (record.get("resolved_emp") or {}):
        return record["resolved_emp"][column]
    if column == "anomaly_flags":
        return ", ".join(record.get("anomaly_flags", []))
    return ""


def persist_invoice(records, client_code: str, period: str):
    invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    total = sum(r.get("payroll", {}).get("final_total", 0) for r in records if r.get("status") != "REJECTED")
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO invoices(invoice_id,client_code,period,created_at,status,total_aed,record_count) VALUES(?,?,?,?,?,?,?)",
        (invoice_id, client_code, period, datetime.now().isoformat(timespec="seconds"), "DRAFT", total, len(records)),
    )
    for record in records:
        payroll = record.get("payroll", {})
        line_id = f"LIN-{uuid.uuid4().hex[:10].upper()}"
        conn.execute(
            """
            INSERT INTO invoice_lines(line_id,invoice_id,emp_id,full_name,working_days,ot_hours,ot_amount,
            reimbursements_json,gross_billable,markup_pct,invoice_amount,vat_amount,final_total,
            confidence_score,anomaly_flags,status,raw_input_snapshot)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                line_id, invoice_id, record.get("emp_id"), record.get("full_name"),
                record.get("working_days"), record.get("ot_hours"), payroll.get("ot_amount", 0),
                json.dumps(record.get("reimbursements", [])), payroll.get("gross_billable", 0),
                payroll.get("markup_pct", 0), payroll.get("invoice_amount", 0),
                payroll.get("vat_amount", 0), payroll.get("final_total", 0),
                record.get("confidence_score"), json.dumps(record.get("anomaly_flags", [])),
                record.get("status"), json.dumps(record.get("raw_input_snapshot", {}), default=str),
            ),
        )
    conn.commit()
    conn.close()
    log_audit("INVOICE_PERSISTED", invoice_id=invoice_id, notes=f"{client_code} {period}")
    return invoice_id


def generate_invoice_pdf(records, client_code: str, period: str, columns=None):
    _ensure_output_dir()
    columns = columns or ALL_COLUMNS[:10]
    cfg = get_client_config(client_code)
    invoice_id = persist_invoice(records, client_code, period)
    path = os.path.join(OUTPUT_DIR, f"{invoice_id}.pdf")
    doc = SimpleDocTemplate(path, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("TIA - Touchless Invoice Agent", styles["Title"]),
        Paragraph(f"Invoice {invoice_id} | {cfg.get('client_name', client_code)} | {period}", styles["Normal"]),
        Spacer(1, 12),
    ]
    data = [[c.replace("_", " ").title() for c in columns]]
    for record in records:
        data.append([str(_value(record, col)) for col in columns])
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#21262D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D7DE")),
                ("FONT", (0, 0), (-1, -1), "Helvetica", 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return path


def export_erp_excel(records, client_code: str, columns=None):
    _ensure_output_dir()
    columns = columns or ALL_COLUMNS
    rows = [{col: _value(record, col) for col in columns} for record in records]
    path = os.path.join(OUTPUT_DIR, f"ERP_{client_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def export_auto_approved_csv(records, client_code: str):
    _ensure_output_dir()
    auto_records = [record for record in records if record.get("status") == "AUTO_APPROVED"]
    if not auto_records:
        return None
    columns = ["emp_id", "full_name", "working_days", "ot_hours", "final_total", "confidence_score", "status", "review_reason"]
    rows = [{col: _value(record, col) for col in columns} for record in auto_records]
    path = os.path.join(OUTPUT_DIR, f"AUTO_APPROVED_{client_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    pd.DataFrame(rows).to_csv(path, index=False)
    return path
