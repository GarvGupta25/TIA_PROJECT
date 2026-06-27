from collections import Counter
from datetime import datetime
import html
import json
import os
import shutil
import sqlite3
import uuid

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

from anomaly_detector import summarize_anomalies
from database import (
    ensure_database,
    get_all_clients,
    get_client_config,
    get_connection,
    log_audit,
    save_client_columns,
    save_client_markup,
)
from invoice_generator import ALL_COLUMNS, export_auto_approved_csv, export_erp_excel, generate_invoice_pdf
from router import process_file


BATCH = {"records": [], "client_code": None}
CLIENT_PORTAL_DB = os.path.join(os.path.dirname(__file__), "client-codebases", "backend", "client_portal.db")
EXCEPTION_COLUMNS = [
    "payroll_decision", "mark_for_review", "emp_id", "full_name", "working_days", "ot_hours",
    "final_total", "confidence_score", "status", "review_reason", "anomaly_flags", "source",
]
EXCEPTION_DISPLAY_COLUMNS = [
    "row_id", "emp_id", "full_name", "working_days", "ot_hours", "final_total",
    "confidence_score", "status", "review_reason", "anomaly_flags", "source",
]
FLAGGED_REVIEW_EXPORT_COLUMNS = [
    "client_code", "source", "emp_id", "full_name", "working_days", "ot_hours",
    "submitted_total", "iban", "final_total", "confidence_score", "status",
    "payroll_decision", "marked_for_review", "review_reason", "anomaly_flags",
]
CLIENT_MESSAGE_COLUMNS = ["client_id", "client_name", "company_name", "uploaded_files", "uploaded_at", "file_ids"]

CSS = """
body, .gradio-container { background:#0d1117 !important; color:#e6edf3 !important; }
.gradio-container { max-width: 1240px !important; }
.metric { border:1px solid #30363d; background:#161b22; border-radius:8px; padding:12px; }
.metric b { display:block; font-size:24px; color:#58a6ff; font-family:monospace; }
table { width:100%; border-collapse:collapse; }
th, td { border-bottom:1px solid #30363d; padding:8px; text-align:left; font-size:12px; }
th { color:#8b949e; background:#161b22; }
"""


def _client_choices():
    return [f"{c['code']} - {c['name']}" for c in get_all_clients()]


def _client_code(choice):
    return (choice or "").split(" - ")[0]


def _badge(status):
    colors = {"AUTO_APPROVED": "#238636", "APPROVED": "#238636", "REVIEW_REQUIRED": "#9e6a03", "REJECTED": "#da3633"}
    color = colors.get(status, "#6e7681")
    return f"<span style='background:{color};color:white;border-radius:4px;padding:2px 6px;font-size:11px'>{html.escape(str(status))}</span>"


def _records_table(records):
    if not records:
        return "<p style='color:#8b949e'>No records processed yet.</p>"
    rows = []
    for r in records:
        pay = r.get("payroll", {})
        flags = ", ".join(r.get("anomaly_flags", [])) or "None"
        reason = r.get("review_reason") or ""
        name = r.get("full_name") or (r.get("resolved_emp") or {}).get("full_name", "")
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('emp_id') or ''))}</td>"
            f"<td>{html.escape(str(name))}</td>"
            f"<td>{r.get('working_days', 0)}</td>"
            f"<td>{r.get('ot_hours', 0)}</td>"
            f"<td>AED {pay.get('final_total', 0):,.2f}</td>"
            f"<td>{r.get('confidence_score', 0)}</td>"
            f"<td>{_badge(r.get('status'))}</td>"
            f"<td>{html.escape(reason)}</td>"
            f"<td>{html.escape(flags)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Emp ID</th><th>Name</th><th>Days</th><th>OT</th>"
        "<th>Total</th><th>Score</th><th>Status</th><th>Review Reason</th><th>Flags</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _summary_cards(records):
    summary = summarize_anomalies(records)
    counts = summary["status_counts"]
    total = sum(r.get("payroll", {}).get("final_total", 0) for r in records if r.get("status") != "REJECTED")
    return f"""
    <div style='display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0'>
      <div class='metric'><b>{summary['total_records']}</b><span>Total records</span></div>
      <div class='metric'><b>{counts.get('AUTO_APPROVED',0)}</b><span>Auto approved</span></div>
      <div class='metric'><b>{counts.get('REVIEW_REQUIRED',0)}</b><span>Needs review</span></div>
      <div class='metric'><b>AED {total:,.0f}</b><span>Billable total</span></div>
    </div>
    """


def _json(value):
    return json.dumps(value or ([] if isinstance(value, list) else {}), default=str)


def _payroll_value(record, key):
    return (record.get("payroll") or {}).get(key, 0)


def _is_invoice_approved(record):
    return record.get("status") in {"AUTO_APPROVED", "APPROVED"}


def _approved_invoice_records():
    return [record for record in BATCH.get("records", []) if _is_invoice_approved(record)]


def _client_db_connection():
    return sqlite3.connect(CLIENT_PORTAL_DB)


def _client_messages_df():
    if not os.path.exists(CLIENT_PORTAL_DB):
        return pd.DataFrame(columns=CLIENT_MESSAGE_COLUMNS)
    conn = _client_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                u.id,
                u.name,
                COALESCE(u.company_name, u.name),
                GROUP_CONCAT(f.filename, ', '),
                MAX(f.uploaded_at),
                GROUP_CONCAT(f.id, ',')
            FROM uploaded_files f
            JOIN users u ON u.id = f.user_id
            WHERE COALESCE(f.processed_by_tasc, 0)=0
            GROUP BY u.id, u.name, u.company_name
            ORDER BY MAX(f.uploaded_at) DESC
            """
        ).fetchall()
    finally:
        conn.close()
    return pd.DataFrame(rows, columns=CLIENT_MESSAGE_COLUMNS)


def render_client_messages():
    df = _client_messages_df()
    choices = [
        f"{row.client_id} | {row.company_name} | {row.uploaded_files} | {row.uploaded_at}"
        for row in df.itertuples(index=False)
    ]
    return df, gr.update(choices=choices, value=choices[0] if choices else None)


def _selected_client_message_row(messages_df, selected_label=None):
    df = pd.DataFrame(messages_df, columns=CLIENT_MESSAGE_COLUMNS)
    if df.empty:
        return None
    if selected_label:
        try:
            client_id = int(str(selected_label).split("|", 1)[0].strip())
            matches = df[df["client_id"].astype(int) == client_id]
            if not matches.empty:
                return matches.iloc[0].to_dict()
        except (TypeError, ValueError):
            pass
    return df.iloc[0].to_dict()


def process_client_message_uploads(messages_df, selected_label, client_choice):
    if not client_choice:
        return "<p style='color:#f85149'>Select the TASC client mapping first.</p>", "", gr.update(visible=False)
    row = _selected_client_message_row(messages_df, selected_label)
    if not row:
        return "<p style='color:#f85149'>No client upload row available. Click Refresh Client Messages.</p>", "", gr.update(visible=False)

    code = _client_code(client_choice)
    file_ids = [int(value) for value in str(row.get("file_ids") or "").split(",") if value.strip()]
    if not file_ids:
        return "<p style='color:#f85149'>Selected client row has no files.</p>", "", gr.update(visible=False)

    placeholders = ",".join("?" for _ in file_ids)
    conn = _client_db_connection()
    try:
        files = conn.execute(f"SELECT id, filepath, filename FROM uploaded_files WHERE id IN ({placeholders})", file_ids).fetchall()
    finally:
        conn.close()

    all_records = []
    errors = []
    processed_file_ids = []
    for file_id, filepath, filename in files:
        path = os.path.join(os.path.dirname(CLIENT_PORTAL_DB), filepath)
        if not os.path.exists(path):
            errors.append(f"{filename}: file not found")
            continue
        try:
            records = process_file(path, code)
            if not records:
                errors.append(f"{filename}: no records extracted")
                continue
            for record in records:
                record["client_portal_user_id"] = int(row["client_id"])
                record["client_company_name"] = row["company_name"]
            all_records.extend(records)
            processed_file_ids.append(file_id)
        except Exception as exc:
            errors.append(f"{filename}: {exc}")

    BATCH["records"] = all_records
    BATCH["client_code"] = code
    BATCH["client_portal_user_id"] = int(row["client_id"])
    BATCH["client_company_name"] = row["company_name"]
    flagged_count = persist_flagged_reviews(all_records, code)

    if processed_file_ids:
        processed_placeholders = ",".join("?" for _ in processed_file_ids)
        conn = _client_db_connection()
        try:
            conn.execute(f"UPDATE uploaded_files SET processed_by_tasc=1 WHERE id IN ({processed_placeholders})", processed_file_ids)
            conn.commit()
        finally:
            conn.close()

    err_html = ""
    if errors:
        err_html = "<p style='color:#f85149'>" + "<br>".join(html.escape(e) for e in errors) + "</p>"
    if flagged_count:
        err_html += f"<p style='color:#d29922'>{flagged_count} flagged review record(s) stored in SQLite.</p>"
    csv_path = export_auto_approved_csv(all_records, code)
    return _summary_cards(all_records) + err_html, _records_table(all_records), gr.update(value=csv_path, visible=bool(csv_path))


def persist_flagged_reviews(records, client_code):
    flagged = [record for record in records if record.get("status") != "AUTO_APPROVED"]
    if not flagged:
        return 0

    batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    conn = get_connection()
    try:
        for record in flagged:
            conn.execute(
                """
                INSERT INTO flagged_reviews(
                    batch_id, client_code, source, emp_id, full_name, working_days, ot_hours,
                    submitted_total, iban, reimbursements_json, gross_billable, markup_pct,
                    invoice_amount, vat_amount, final_total, confidence_score, status,
                    review_reason, anomaly_flags, resolution_method, resolved_emp_json,
                    raw_input_snapshot, created_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    batch_id,
                    client_code,
                    record.get("source"),
                    record.get("emp_id"),
                    record.get("full_name") or (record.get("resolved_emp") or {}).get("full_name"),
                    record.get("working_days"),
                    record.get("ot_hours"),
                    record.get("submitted_total"),
                    record.get("iban"),
                    _json(record.get("reimbursements") or []),
                    _payroll_value(record, "gross_billable"),
                    _payroll_value(record, "markup_pct"),
                    _payroll_value(record, "invoice_amount"),
                    _payroll_value(record, "vat_amount"),
                    _payroll_value(record, "final_total"),
                    record.get("confidence_score"),
                    record.get("status"),
                    record.get("review_reason"),
                    _json(record.get("anomaly_flags") or []),
                    record.get("resolution_method"),
                    _json(record.get("resolved_emp") or {}),
                    _json(record.get("raw_input_snapshot") or {}),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return len(flagged)


def _exception_rows(records):
    rows = []
    for index, record in enumerate(records, start=1):
        pay = record.get("payroll", {})
        rows.append(
            {
                "row_id": index,
                "payroll_decision": "Accept Payroll",
                "mark_for_review": "No",
                "emp_id": record.get("emp_id") or "",
                "full_name": record.get("full_name") or (record.get("resolved_emp") or {}).get("full_name", ""),
                "working_days": record.get("working_days", 0),
                "ot_hours": record.get("ot_hours", 0),
                "final_total": pay.get("final_total", 0),
                "confidence_score": record.get("confidence_score", 0),
                "status": record.get("status") or "",
                "review_reason": record.get("review_reason") or "",
                "anomaly_flags": ", ".join(record.get("anomaly_flags", [])),
                "source": record.get("source") or "",
            }
        )
    return pd.DataFrame(rows, columns=EXCEPTION_COLUMNS)


def _exception_display_rows(records):
    rows = []
    for index, record in enumerate(records, start=1):
        pay = record.get("payroll", {})
        rows.append(
            {
                "row_id": index,
                "emp_id": record.get("emp_id") or "",
                "full_name": record.get("full_name") or (record.get("resolved_emp") or {}).get("full_name", ""),
                "working_days": record.get("working_days", 0),
                "ot_hours": record.get("ot_hours", 0),
                "final_total": pay.get("final_total", 0),
                "confidence_score": record.get("confidence_score", 0),
                "status": record.get("status") or "",
                "review_reason": record.get("review_reason") or "",
                "anomaly_flags": ", ".join(record.get("anomaly_flags", [])),
                "source": record.get("source") or "",
            }
        )
    return pd.DataFrame(rows, columns=EXCEPTION_DISPLAY_COLUMNS)


def _exception_label(index, record):
    emp_id = record.get("emp_id") or "Missing ID"
    name = record.get("full_name") or (record.get("resolved_emp") or {}).get("full_name", "Missing Name")
    status = record.get("status") or "UNKNOWN"
    reason = (record.get("review_reason") or "").strip()
    if len(reason) > 90:
        reason = reason[:87] + "..."
    return f"{index} | {emp_id} | {name} | {status} | {reason}"


def _row_ids_from_labels(labels):
    row_ids = set()
    for label in labels or []:
        try:
            row_ids.add(int(str(label).split("|", 1)[0].strip()))
        except (TypeError, ValueError):
            continue
    return row_ids


def process_upload(client_choice, files):
    if not client_choice:
        return "<p style='color:#f85149'>Select a client first.</p>", "", gr.update(visible=False)
    if not files:
        return "<p style='color:#f85149'>Upload at least one Excel, email, PDF, or image file.</p>", "", gr.update(visible=False)
    code = _client_code(client_choice)
    all_records = []
    errors = []
    for item in files:
        path = item.name if hasattr(item, "name") else item
        try:
            all_records.extend(process_file(path, code))
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    BATCH["records"] = all_records
    BATCH["client_code"] = code
    flagged_count = persist_flagged_reviews(all_records, code)
    log_audit("BATCH_PROCESSED", notes=f"{len(all_records)} records for {code}")
    err_html = ""
    if errors:
        err_html = "<p style='color:#f85149'>" + "<br>".join(html.escape(e) for e in errors) + "</p>"
    if flagged_count:
        err_html += f"<p style='color:#d29922'>{flagged_count} flagged review record(s) stored in SQLite.</p>"
    csv_path = export_auto_approved_csv(all_records, code)
    csv_update = gr.update(value=csv_path, visible=bool(csv_path))
    return _summary_cards(all_records) + err_html, _records_table(all_records), csv_update


def render_exception_queue():
    records = [r for r in BATCH.get("records", []) if not _is_invoice_approved(r) and r.get("status") != "REJECTED"]
    choices = [_exception_label(index, record) for index, record in enumerate(records, start=1)]
    message = "<p style='color:#8b949e'>No exception records in the current batch.</p>" if not records else ""
    return (
        _exception_display_rows(records),
        gr.update(choices=choices, value=[]),
        gr.update(choices=choices, value=[]),
        message,
        gr.update(visible=False),
    )


def export_marked_flagged_reviews(marked_labels, reject_labels):
    records = [r for r in BATCH.get("records", []) if not _is_invoice_approved(r) and r.get("status") != "REJECTED"]
    if not records:
        return "<p style='color:#f85149'>No exception queue available.</p>", gr.update(visible=False)

    marked_ids = _row_ids_from_labels(marked_labels)
    reject_ids = _row_ids_from_labels(reject_labels)
    selected_ids = marked_ids | reject_ids
    if not selected_ids:
        return "<p style='color:#f85149'>Select at least one row to approve or reject.</p>", gr.update(visible=False)

    export_rows = []
    approved_count = 0
    rejected_count = 0
    conn = get_connection()
    try:
        for row_id in sorted(selected_ids):
            if row_id < 1 or row_id > len(records):
                continue
            record = records[row_id - 1]
            emp_id = str(record.get("emp_id") or "")
            is_rejected = row_id in reject_ids
            decision = "Reject Payroll" if is_rejected else "Approved"
            if is_rejected:
                record["status"] = "REJECTED"
                record["payroll_decision"] = "Rejected"
                record["marked_for_review"] = "Yes"
                rejected_count += 1
            else:
                record["status"] = "APPROVED"
                record["payroll_decision"] = "Approved"
                record["marked_for_review"] = "No"
                record["review_reason"] = "Manually approved from inspection queue."
                approved_count += 1
            conn.execute(
                """
                UPDATE flagged_reviews
                SET payroll_decision=?, marked_for_review=?, status=?, review_reason=?
                WHERE client_code=? AND COALESCE(emp_id,'')=? AND exported_at IS NULL
                """,
                (
                    decision,
                    "Yes" if is_rejected else "No",
                    record["status"],
                    record.get("review_reason"),
                    BATCH.get("client_code"),
                    emp_id,
                ),
            )
            if is_rejected:
                export_rows.append(
                    {
                        "client_code": BATCH.get("client_code"),
                        "source": record.get("source"),
                        "emp_id": emp_id,
                        "full_name": record.get("full_name") or (record.get("resolved_emp") or {}).get("full_name", ""),
                        "working_days": record.get("working_days"),
                        "ot_hours": record.get("ot_hours"),
                        "submitted_total": record.get("submitted_total"),
                        "iban": record.get("iban"),
                        "final_total": _payroll_value(record, "final_total"),
                        "confidence_score": record.get("confidence_score"),
                        "status": record.get("status"),
                        "payroll_decision": decision,
                        "marked_for_review": "Yes",
                        "review_reason": record.get("review_reason"),
                        "anomaly_flags": ", ".join(record.get("anomaly_flags", [])),
                    }
                )
        if not export_rows:
            conn.commit()
            log_audit("INSPECTION_QUEUE_UPDATED", notes=f"{approved_count} approved, {rejected_count} rejected")
            return f"<p style='color:#3fb950'>{approved_count} row(s) approved for invoice. {rejected_count} row(s) rejected.</p>", gr.update(visible=False)
        conn.execute(
            "UPDATE flagged_reviews SET exported_at=? WHERE client_code=? AND marked_for_review='Yes' AND exported_at IS NULL",
            (datetime.now().isoformat(timespec="seconds"), BATCH.get("client_code")),
        )
        conn.commit()
    finally:
        conn.close()

    os.makedirs("outputs", exist_ok=True)
    path = os.path.join("outputs", f"FLAGGED_REVIEWS_{BATCH.get('client_code')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    pd.DataFrame(export_rows, columns=FLAGGED_REVIEW_EXPORT_COLUMNS).to_csv(path, index=False)
    send_note = ""
    client_user_id = BATCH.get("client_portal_user_id")
    if client_user_id and os.path.exists(CLIENT_PORTAL_DB):
        return_dir = os.path.join(os.path.dirname(CLIENT_PORTAL_DB), "returned")
        os.makedirs(return_dir, exist_ok=True)
        returned_path = os.path.join(return_dir, os.path.basename(path))
        shutil.copyfile(path, returned_path)
        conn = _client_db_connection()
        try:
            conn.execute(
                "INSERT INTO returned_files(user_id,filename,filepath,note,created_at) VALUES(?,?,?,?,?)",
                (
                    int(client_user_id),
                    os.path.basename(path),
                    returned_path,
                    "Flagged review CSV from TASC",
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
            send_note = " Rejected rows sent to client portal."
        finally:
            conn.close()
    log_audit("INSPECTION_QUEUE_UPDATED", notes=f"{approved_count} approved, {rejected_count} rejected")
    return f"<p style='color:#3fb950'>{approved_count} row(s) approved for invoice. {rejected_count} row(s) rejected.{send_note}</p>", gr.update(value=path, visible=True)


def generate_outputs(period):
    records = _approved_invoice_records()
    code = BATCH.get("client_code")
    if not records or not code:
        return "<p style='color:#f85149'>No approved records available for invoice generation.</p>", gr.update(visible=False), gr.update(visible=False)
    cfg = get_client_config(code)
    columns = cfg.get("output_columns") or ALL_COLUMNS[:10]
    pdf_path = generate_invoice_pdf(records, code, period or "Current Period", columns)
    xlsx_path = export_erp_excel(records, code, columns)
    log_audit("INVOICE_GENERATED", notes=f"{code} {period} approved_records={len(records)}")
    return _summary_cards(records), gr.update(value=pdf_path, visible=True), gr.update(value=xlsx_path, visible=True)


def render_charts():
    records = BATCH.get("records", [])
    layout = dict(paper_bgcolor="#161b22", plot_bgcolor="#0d1117", font={"color": "#e6edf3"}, margin=dict(l=30, r=20, t=40, b=30))
    if not records:
        empty = go.Figure().update_layout(**layout)
        return empty, empty, empty, empty
    statuses = Counter(r.get("status") for r in records)
    fig1 = go.Figure(go.Pie(labels=list(statuses), values=list(statuses.values()), hole=0.45)).update_layout(**layout, title="Status Distribution")
    scores = [r.get("confidence_score", 0) for r in records]
    fig2 = go.Figure(go.Histogram(x=scores, nbinsx=10, marker_color="#58a6ff")).update_layout(**layout, title="Confidence Scores")
    flags = Counter(f for r in records for f in r.get("anomaly_flags", []))
    fig3 = go.Figure(go.Bar(x=list(flags.values()), y=list(flags), orientation="h", marker_color="#f85149")).update_layout(**layout, title="Anomaly Frequency")
    names = [(r.get("full_name") or r.get("emp_id") or "?")[:18] for r in records]
    totals = [r.get("payroll", {}).get("final_total", 0) for r in records]
    fig4 = go.Figure(go.Bar(x=names, y=totals, marker_color="#d29922")).update_layout(**layout, title="Final Total per Employee")
    return fig1, fig2, fig3, fig4


def answer_query(question):
    q = (question or "").lower()
    if not q:
        return "<p style='color:#8b949e'>Enter a question.</p>"
    conn = get_connection()
    try:
        if "current" in q or "batch" in q:
            return _summary_cards(BATCH.get("records", []))
        if "how many" in q and "employee" in q:
            for client in get_all_clients():
                if client["name"].lower() in q or client["code"].lower() in q:
                    n = conn.execute("SELECT COUNT(*) FROM employees WHERE client_code=?", (client["code"],)).fetchone()[0]
                    return f"<p><b>{html.escape(client['name'])}</b> has <b>{n}</b> employees.</p>"
        import re

        match = re.search(r"(\d[\d,]*)", question or "")
        if match and any(word in q for word in ["salary", "earn", "ctc", "above", "more than"]):
            threshold = float(match.group(1).replace(",", ""))
            rows = conn.execute(
                "SELECT emp_id,full_name,client_name,total_ctc FROM employees WHERE total_ctc>? ORDER BY total_ctc DESC LIMIT 20",
                (threshold,),
            ).fetchall()
            body = "".join(f"<tr><td>{r[0]}</td><td>{html.escape(r[1])}</td><td>{html.escape(r[2])}</td><td>AED {r[3]:,.0f}</td></tr>" for r in rows)
            return "<table><tr><th>ID</th><th>Name</th><th>Client</th><th>CTC</th></tr>" + body + "</table>"
        for client in get_all_clients():
            if client["name"].lower() in q:
                rows = conn.execute("SELECT emp_id,full_name,job_title,total_ctc FROM employees WHERE client_code=? LIMIT 20", (client["code"],)).fetchall()
                body = "".join(f"<tr><td>{r[0]}</td><td>{html.escape(r[1])}</td><td>{html.escape(str(r[2]))}</td><td>AED {r[3]:,.0f}</td></tr>" for r in rows)
                return "<table><tr><th>ID</th><th>Name</th><th>Role</th><th>CTC</th></tr>" + body + "</table>"
        return "<p style='color:#8b949e'>Try asking about employee count, salary above an amount, or current batch.</p>"
    finally:
        conn.close()


def load_config(client_choice):
    if not client_choice:
        return [], 10.0
    cfg = get_client_config(_client_code(client_choice))
    return cfg.get("output_columns", []), cfg.get("markup_pct", 10.0)


def save_config(client_choice, columns, markup):
    if not client_choice:
        return "Select a client."
    code = _client_code(client_choice)
    save_client_columns(code, columns or [])
    save_client_markup(code, float(markup or 0))
    return f"Settings saved for {client_choice}."


def build_app():
    ensure_database()
    with gr.Blocks(title="TIA - Touchless Invoice Agent", css=CSS, theme=gr.themes.Base()) as app:
        gr.HTML(
            "<div style='display:flex;align-items:center;gap:12px;border-bottom:1px solid #30363d;padding:12px 0'>"
            "<div style='font-size:26px;font-weight:700;color:#e6edf3'>TIA</div>"
            "<div style='color:#8b949e'>Touchless Invoice Agent - TASC invoice validation and billing</div>"
            "<div style='margin-left:auto;color:#3fb950;font-family:monospace'>OFFLINE</div>"
            "</div>"
        )

        with gr.Tab("Submit Timesheets"):
            client = gr.Dropdown(choices=_client_choices(), label="Client")
            files = gr.File(label="Upload files", file_count="multiple", file_types=[".xlsx", ".xls", ".csv", ".tsv", ".eml", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".webp"])
            run = gr.Button("Process Batch", variant="primary")
            summary = gr.HTML()
            table = gr.HTML()
            auto_csv = gr.File(label="Auto-approved CSV", visible=False)
            run.click(process_upload, inputs=[client, files], outputs=[summary, table, auto_csv])

        with gr.Tab("Client Messages"):
            client_msg_client = gr.Dropdown(choices=_client_choices(), label="Map Client Upload To TASC Client")
            refresh_client_msgs = gr.Button("Refresh Client Messages")
            client_messages = gr.Dataframe(
                headers=CLIENT_MESSAGE_COLUMNS,
                datatype=["number", "str", "str", "str", "str", "str"],
                interactive=False,
                wrap=True,
                label="Client Uploads Waiting For TASC",
            )
            selected_client_message = gr.Radio(choices=[], label="Select Client Upload Row")
            process_client_files = gr.Button("Upload All", variant="primary")
            client_summary = gr.HTML()
            client_table = gr.HTML()
            client_auto_csv = gr.File(label="Auto-approved CSV", visible=False)
            refresh_client_msgs.click(render_client_messages, outputs=[client_messages, selected_client_message])
            process_client_files.click(
                process_client_message_uploads,
                inputs=[client_messages, selected_client_message, client_msg_client],
                outputs=[client_summary, client_table, client_auto_csv],
            )

        with gr.Tab("Exception Queue"):
            refresh = gr.Button("Refresh Queue")
            queue = gr.Dataframe(
                headers=EXCEPTION_DISPLAY_COLUMNS,
                datatype=["number", "str", "str", "number", "number", "number", "number", "str", "str", "str", "str"],
                interactive=False,
                wrap=True,
                label="Admin Exception Queue",
            )
            with gr.Row():
                reject_rows = gr.CheckboxGroup(
                    choices=[],
                    label="Reject Payroll",
                    interactive=True,
                )
                mark_rows = gr.CheckboxGroup(
                    choices=[],
                    label="Approve For Invoice",
                    interactive=True,
                )
            send_flagged = gr.Button("Apply Inspection Decisions", variant="primary")
            flagged_msg = gr.HTML()
            flagged_csv = gr.File(label="Flagged Reviews CSV", visible=False)
            refresh.click(render_exception_queue, outputs=[queue, reject_rows, mark_rows, flagged_msg, flagged_csv])
            send_flagged.click(export_marked_flagged_reviews, inputs=[mark_rows, reject_rows], outputs=[flagged_msg, flagged_csv])

        with gr.Tab("Invoice Output"):
            period = gr.Textbox(label="Billing Period", value="June 2026")
            generate = gr.Button("Generate PDF and ERP Excel", variant="primary")
            output_summary = gr.HTML()
            pdf_file = gr.File(label="Invoice PDF", visible=False)
            xlsx_file = gr.File(label="ERP Excel", visible=False)
            generate.click(generate_outputs, inputs=period, outputs=[output_summary, pdf_file, xlsx_file])

        with gr.Tab("Analytics"):
            refresh_charts = gr.Button("Refresh Charts")
            with gr.Row():
                pie = gr.Plot()
                hist = gr.Plot()
            with gr.Row():
                flags = gr.Plot()
                totals = gr.Plot()
            refresh_charts.click(render_charts, outputs=[pie, hist, flags, totals])

        with gr.Tab("Query Assistant"):
            question = gr.Textbox(label="Question", lines=2, placeholder="How many employees does Aldar Properties have?")
            ask = gr.Button("Ask", variant="primary")
            answer = gr.HTML()
            ask.click(answer_query, inputs=question, outputs=answer)

        with gr.Tab("Column Config"):
            cfg_client = gr.Dropdown(choices=_client_choices(), label="Client")
            cfg_columns = gr.CheckboxGroup(choices=ALL_COLUMNS, label="Invoice Output Columns")
            cfg_markup = gr.Number(label="TASC Markup %", minimum=0, maximum=50, step=0.5, value=10.0)
            save = gr.Button("Save Settings", variant="primary")
            msg = gr.Textbox(label="", interactive=False)
            cfg_client.change(load_config, inputs=cfg_client, outputs=[cfg_columns, cfg_markup])
            save.click(save_config, inputs=[cfg_client, cfg_columns, cfg_markup], outputs=msg)
    return app


def launch():
    build_app().queue().launch(server_name="127.0.0.1", server_port=7860, share=False, debug=True)


if __name__ == "__main__":
    launch()
