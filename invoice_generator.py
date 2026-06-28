import json
import os
import uuid
from datetime import datetime, timedelta

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
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


def _money(value, currency="AED"):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    return f"{currency} {number:,.2f}"


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _employee_name(record):
    return record.get("full_name") or (record.get("resolved_emp") or {}).get("full_name") or "-"


def _client_name(cfg, client_code):
    return cfg.get("client_name") or cfg.get("name") or client_code


def _amount_words(value, currency="AED"):
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def words_under_1000(number):
        parts = []
        if number >= 100:
            parts.append(f"{ones[number // 100]} Hundred")
            number %= 100
        if 10 <= number <= 19:
            parts.append(teens[number - 10])
        else:
            if number >= 20:
                parts.append(tens[number // 10])
                number %= 10
            if number:
                parts.append(ones[number])
        return " ".join(parts)

    number = int(round(_num(value)))
    if number == 0:
        return f"{currency} Zero Only"
    parts = []
    for scale, label in [(1_000_000, "Million"), (1_000, "Thousand"), (1, "")]:
        chunk = number // scale
        if chunk:
            parts.append(f"{words_under_1000(chunk)} {label}".strip())
            number %= scale
    return f"{currency} {' '.join(parts)} Only"


def _draw_page_frame(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#B8C2D1"))
    canvas.setLineWidth(0.8)
    canvas.rect(8 * mm, 8 * mm, A4[0] - 16 * mm, A4[1] - 16 * mm)
    canvas.restoreState()


def _section_title(text, style):
    return Paragraph(text, style)


def _kv_table(rows, col_widths, label_color="#111111", font_size=8.5, leading=11, padding=3):
    data = [[Paragraph(f"<b>{label}</b>", ParagraphStyle("kv-label", fontSize=font_size, leading=leading, textColor=colors.HexColor(label_color))), ":", value] for label, value in rows]
    table = Table(data, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", font_size),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ]
        )
    )
    return table


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
    cfg = get_client_config(client_code)
    invoice_id = persist_invoice(records, client_code, period)
    path = os.path.join(OUTPUT_DIR, f"{invoice_id}.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=16 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0B3978")
    light_blue = colors.HexColor("#EAF1FB")
    grid = colors.HexColor("#B8C2D1")
    title_style = ParagraphStyle("invoice-title", parent=styles["Title"], fontSize=31, leading=34, textColor=navy, alignment=2, spaceAfter=4)
    company_style = ParagraphStyle("company", parent=styles["Heading1"], fontSize=15, leading=18, textColor=navy, spaceAfter=4)
    normal = ParagraphStyle("invoice-normal", parent=styles["Normal"], fontSize=8, leading=10)
    small = ParagraphStyle("invoice-small", parent=styles["Normal"], fontSize=7.2, leading=9)
    section = ParagraphStyle("section", parent=styles["Heading3"], fontSize=9, leading=11, textColor=navy, spaceBefore=3, spaceAfter=3)
    client_display = _client_name(cfg, client_code)
    created = datetime.now()
    due = created + timedelta(days=14)
    total = sum(_num(record.get("payroll", {}).get("final_total")) for record in records)
    invoice_amount = sum(_num(record.get("payroll", {}).get("invoice_amount")) for record in records)
    vat_amount = sum(_num(record.get("payroll", {}).get("vat_amount")) for record in records)
    total_days = sum(_num(record.get("working_days")) for record in records)
    total_ot = sum(_num(record.get("ot_hours")) for record in records)
    avg_confidence = round(sum(_num(record.get("confidence_score")) for record in records) / len(records), 2) if records else 0
    first = records[0] if records else {}
    first_pay = first.get("payroll", {})

    logo = Table([["T", Paragraph("<b>TASC SOLUTIONS PVT. LTD.</b>", company_style)]], colWidths=[16 * mm, 82 * mm])
    logo.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 16),
                ("TEXTCOLOR", (0, 0), (0, 0), navy),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (0, 0), 1.4, navy),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    company_block = [
        logo,
        Paragraph("TASC Business Park, Sector 62", normal),
        Paragraph("Noida, Uttar Pradesh 201309, India", normal),
        Paragraph("Phone: +91 98765 43210  |  Email: finance@tasc.example", normal),
        Paragraph("GSTIN: 09TASCINVOICE01", normal),
    ]
    invoice_meta = _kv_table(
        [
            ("Invoice No.", invoice_id),
            ("Invoice Date", created.strftime("%d %b %Y")),
            ("Due Date", due.strftime("%d %b %Y")),
            ("PO / Ref No.", period),
            ("Place of Supply", "Uttar Pradesh (09)"),
        ],
        [28 * mm, 4 * mm, 44 * mm],
        font_size=8,
        leading=10,
        padding=2,
    )
    right_header = [Paragraph("INVOICE", title_style), invoice_meta]
    header = Table([[company_block, right_header]], colWidths=[100 * mm, 78 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    bill_to = [
        _section_title("BILL TO", section),
        Paragraph(f"<b>{client_display}</b>", normal),
        Paragraph(f"Client Code: {client_code}", normal),
        Paragraph("Payroll services billing", normal),
        Paragraph("GSTIN: -", normal),
    ]
    ship_to = [
        _section_title("SHIP TO", section),
        Paragraph(f"<b>{client_display}</b>", normal),
        Paragraph(f"Billing Period: {period}", normal),
        Paragraph("Processed by TASC payroll operations", normal),
    ]
    address_blocks = Table([[bill_to, ship_to]], colWidths=[89 * mm, 89 * mm])
    address_blocks.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.7, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.7, grid), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))

    details = _kv_table(
        [
            ("Client Code", client_code),
            ("Source", first.get("source") or "Payroll System"),
            ("Employee ID (Emp ID)", first.get("emp_id") or "Multiple employees"),
            ("Full Name", _employee_name(first) if len(records) == 1 else f"{len(records)} approved payroll rows"),
            ("Working Days", f"{total_days:g}"),
            ("OT Hours", f"{total_ot:g}"),
            ("Submitted Total", _money(sum(_num(r.get("submitted_total")) for r in records))),
            ("IBAN", first.get("iban") or (first.get("resolved_emp") or {}).get("iban") or "-"),
            ("Final Total", _money(total)),
            ("Confidence Score", f"{avg_confidence:g}%"),
            ("Status", "Approved"),
            ("Payroll Decision", "Approved"),
            ("Marked For Review", "No"),
            ("Review Reason", "-"),
            ("Anomaly Flags", "None"),
        ],
        [55 * mm, 4 * mm, 119 * mm],
        font_size=7.6,
        leading=9,
        padding=1.6,
    )
    details.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, grid),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7F9FC")),
            ]
        )
    )

    summary_rows = [["DESCRIPTION", "WORKING DAYS", "OT HOURS", "SUBMITTED TOTAL", "FINAL TOTAL"]]
    for record in records:
        pay = record.get("payroll", {})
        summary_rows.append(
            [
                Paragraph(_employee_name(record), small),
                f"{_num(record.get('working_days')):g}",
                f"{_num(record.get('ot_hours')):g}",
                _money(record.get("submitted_total") or pay.get("invoice_amount")),
                _money(pay.get("final_total")),
            ]
        )
    summary_rows.append(["TOTAL", f"{total_days:g}", f"{total_ot:g}", _money(invoice_amount), _money(total)])
    summary = Table(summary_rows, repeatRows=1, colWidths=[50 * mm, 31 * mm, 27 * mm, 35 * mm, 35 * mm])
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.6),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.35, grid),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 7.5),
                ("BACKGROUND", (0, -1), (-1, -1), light_blue),
                ("TEXTCOLOR", (0, -1), (-1, -1), navy),
                ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 7.6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    total_box = Table(
        [
            ["SUBTOTAL", _money(invoice_amount)],
            ["TAX (IF APPLICABLE)", _money(vat_amount)],
            ["TOTAL AMOUNT", _money(total)],
        ],
        colWidths=[40 * mm, 38 * mm],
    )
    total_box.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, grid),
                ("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 7.6),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BACKGROUND", (0, -1), (-1, -1), navy),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
            ]
        )
    )

    payment = [
        _section_title("PAYMENT INFORMATION", section),
        _kv_table(
            [
                ("Bank Name", "HDFC Bank"),
                ("Account Name", "TASC Solutions Pvt. Ltd."),
                ("Account No.", "50200012345678"),
                ("IFSC Code", "HDFC0001234"),
                ("Branch", "Noida Sector 62, Uttar Pradesh"),
                ("IBAN", "IN12ABCD12345678901234"),
            ],
            [24 * mm, 4 * mm, 55 * mm],
            font_size=7.5,
            leading=9,
            padding=1.5,
        ),
    ]
    terms = [
        _section_title("TERMS & CONDITIONS", section),
        Paragraph("1. Payment is due within 14 days from the invoice date.", normal),
        Paragraph("2. Late payment may attract interest @ 18% p.a.", normal),
        Paragraph("3. Please make all payments to the bank account mentioned.", normal),
        Paragraph("4. Approved payroll rows only are included in this invoice.", normal),
    ]
    footer_blocks = Table([[payment, terms]], colWidths=[89 * mm, 89 * mm])
    footer_blocks.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    story = [
        header,
        Spacer(1, 5),
        address_blocks,
        _section_title("PAYROLL / INVOICE DETAILS", section),
        details,
        _section_title("PAYROLL SUMMARY", section),
        summary,
        Spacer(1, 4),
        Table([[Paragraph("<b>AMOUNT IN WORDS</b>", section), total_box]], colWidths=[100 * mm, 78 * mm]),
        Paragraph(_amount_words(total), normal),
        Spacer(1, 5),
        footer_blocks,
        Spacer(1, 8),
        Table([["", Paragraph("<b>Thank you for your business!</b>", ParagraphStyle("thanks", parent=normal, textColor=navy, alignment=1)), ""]], colWidths=[61 * mm, 56 * mm, 61 * mm], style=[("LINEABOVE", (0, 0), (0, 0), 0.7, colors.black), ("LINEABOVE", (2, 0), (2, 0), 0.7, colors.black)]),
    ]
    doc.build(story, onFirstPage=_draw_page_frame, onLaterPages=_draw_page_frame)
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
