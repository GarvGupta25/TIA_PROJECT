from collections import Counter
from datetime import datetime
import html
import json
import os
import random
import shutil
import sqlite3
import string
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
    "Reject", "Mark for Review", "row_id", "emp_id", "full_name", "working_days", "ot_hours", "final_total",
    "confidence_score", "status", "review_reason", "anomaly_flags", "source",
]
FLAGGED_REVIEW_EXPORT_COLUMNS = [
    "client_code", "source", "emp_id", "full_name", "working_days", "ot_hours",
    "submitted_total", "iban", "final_total", "confidence_score", "status",
    "payroll_decision", "marked_for_review", "review_reason", "anomaly_flags",
]
CLIENT_MESSAGE_COLUMNS = ["client_id", "client_name", "company_name", "uploaded_files", "uploaded_at", "file_ids"]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
:root {
  --bg-base:#080B14;
  --bg-surface:#0D1117;
  --bg-elevated:#161B27;
  --border:#1E2D40;
  --border-accent:#2D4A6B;
  --primary:#3B82F6;
  --primary-hover:#2563EB;
  --primary-glow:rgba(59,130,246,.15);
  --secondary:#8B5CF6;
  --success:#10B981;
  --success-glow:rgba(16,185,129,.12);
  --warning:#F59E0B;
  --warning-glow:rgba(245,158,11,.12);
  --danger:#EF4444;
  --danger-glow:rgba(239,68,68,.12);
  --text-primary:#F1F5F9;
  --text-secondary:#94A3B8;
  --text-muted:#475569;
  --mono:'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --sans:'Inter', system-ui, -apple-system, Segoe UI, sans-serif;
}
* { box-sizing:border-box; }
html, body, .gradio-container {
  background:
    radial-gradient(circle at 8% -10%, rgba(59,130,246,.12), transparent 32%),
    radial-gradient(circle at 90% 4%, rgba(139,92,246,.10), transparent 28%),
    var(--bg-base) !important;
  color:var(--text-primary) !important;
  font-family:var(--sans) !important;
  letter-spacing:0 !important;
}
.gradio-container { max-width:1280px !important; padding:0 24px 32px !important; }
.gradio-container h1, .gradio-container h2, .gradio-container h3, .gradio-container label {
  color:var(--text-primary) !important;
  font-family:var(--sans) !important;
}
.tia-topbar {
  height:56px;
  display:flex;
  align-items:center;
  gap:16px;
  position:sticky;
  top:0;
  z-index:20;
  background:rgba(8,11,20,.95);
  backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
  margin:0 -24px 18px;
  padding:0 24px;
}
.tia-logo {
  color:#fff;
  font-size:20px;
  font-weight:800;
  letter-spacing:-.02em;
  position:relative;
}
.tia-logo:after {
  content:"";
  position:absolute;
  left:0;
  right:0;
  bottom:-5px;
  height:2px;
  background:var(--primary);
  border-radius:999px;
}
.tia-product { color:var(--text-secondary); font-size:13px; font-weight:500; }
.tia-status { margin-left:auto; display:flex; align-items:center; gap:9px; color:var(--text-secondary); font-size:12px; font-family:var(--mono); }
.tia-avatar { width:30px; height:30px; border-radius:50%; display:grid; place-items:center; background:rgba(139,92,246,.2); color:#fff; font-weight:800; position:relative; }
.tia-avatar:after { content:""; position:absolute; right:0; bottom:1px; width:8px; height:8px; border-radius:50%; background:var(--success); box-shadow:0 0 0 5px rgba(16,185,129,.08); animation:pulse-online 2s infinite; }
@keyframes pulse-online { 0%,100%{ box-shadow:0 0 0 3px rgba(16,185,129,.12);} 50%{ box-shadow:0 0 0 9px rgba(16,185,129,0);} }
@keyframes card-in { from{ opacity:0; transform:translateY(8px);} to{ opacity:1; transform:translateY(0);} }
@keyframes amber-pulse { 0%,100%{ box-shadow:0 0 0 0 rgba(245,158,11,.10);} 50%{ box-shadow:0 0 0 5px rgba(245,158,11,0);} }
.tabs, .tabitem, .form, .block, .panel, .gr-panel {
  background:transparent !important;
}
.tab-nav, .tabs > .tab-nav {
  min-height:56px !important;
  background:rgba(8,11,20,.78) !important;
  backdrop-filter:blur(20px) !important;
  border:1px solid var(--border) !important;
  border-radius:12px !important;
  padding:4px 8px !important;
  gap:6px !important;
}
.tab-nav button, .tab-nav .tabitem {
  color:var(--text-secondary) !important;
  border:0 !important;
  border-bottom:2px solid transparent !important;
  border-radius:8px !important;
  background:transparent !important;
  font-size:13px !important;
  font-weight:600 !important;
  transition:all 150ms ease !important;
}
.tab-nav button:hover, .tab-nav .tabitem:hover {
  color:var(--text-primary) !important;
  background:rgba(30,45,64,.5) !important;
}
.tab-nav button.selected, .tab-nav .selected {
  color:#fff !important;
  background:var(--primary-glow) !important;
  border-bottom-color:var(--primary) !important;
}
.gradio-container .gr-button, button {
  border-radius:8px !important;
  border:1px solid var(--border) !important;
  background:transparent !important;
  color:var(--text-primary) !important;
  padding:10px 20px !important;
  font-size:14px !important;
  font-weight:600 !important;
  letter-spacing:.01em !important;
  transition:all 150ms ease !important;
}
.gradio-container .gr-button:hover, button:hover {
  border-color:var(--primary) !important;
  color:var(--primary) !important;
  box-shadow:0 0 20px rgba(59,130,246,.24) !important;
}
.gradio-container .gr-button:active, button:active { transform:scale(.97) !important; }
.gradio-container .gr-button.primary, .gradio-container button.primary {
  background:var(--primary) !important;
  color:#fff !important;
  border-color:transparent !important;
}
.gradio-container .gr-button.primary:hover, .gradio-container button.primary:hover {
  background:var(--primary-hover) !important;
  color:#fff !important;
  box-shadow:0 0 20px rgba(59,130,246,.4) !important;
}
.gradio-container input, .gradio-container textarea, .gradio-container select, .gradio-container .gr-input, .gradio-container .gr-dropdown, .gradio-container .wrap {
  background:var(--bg-surface) !important;
  border-color:var(--border) !important;
  border-radius:8px !important;
  color:var(--text-primary) !important;
  font-size:14px !important;
  transition:all 150ms ease !important;
}
.gradio-container input:focus, .gradio-container textarea:focus, .gradio-container .wrap:focus-within {
  border-color:var(--primary) !important;
  box-shadow:0 0 0 3px rgba(59,130,246,.10) !important;
}
.gradio-container input[type="checkbox"], .gradio-container input[type="radio"] {
  accent-color:var(--success) !important;
  width:16px !important;
  height:16px !important;
}
.selection-summary {
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  margin:10px 0 4px;
}
.selection-pill {
  display:inline-flex;
  align-items:center;
  gap:7px;
  border:1px solid var(--border);
  border-radius:999px;
  background:rgba(16,185,129,.08);
  color:var(--text-primary);
  padding:7px 11px;
  font-size:12px;
  font-weight:700;
}
.selection-pill.reject { background:rgba(239,68,68,.08); }
.selection-pill.warn { background:rgba(245,158,11,.10); }
.selection-check { color:var(--success); font-weight:900; }
.gradio-container input::placeholder, .gradio-container textarea::placeholder { color:var(--text-muted) !important; }
.gradio-container .file-preview, .gradio-container .upload-container, .gradio-container .file-wrap, .gradio-container [data-testid='file'] {
  border:2px dashed var(--border) !important;
  border-radius:12px !important;
  background:rgba(13,17,23,.5) !important;
  min-height:160px !important;
  transition:all 150ms ease !important;
}
.gradio-container .file-preview:hover, .gradio-container .upload-container:hover, .gradio-container .file-wrap:hover {
  border-color:var(--primary) !important;
  background:rgba(59,130,246,.05) !important;
}
.gradio-container .block, .gradio-container .form, .gradio-container .panel {
  border-color:var(--border) !important;
}
.metric-row { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:14px 0; }
.metric {
  border:1px solid var(--border);
  border-top:2px solid var(--metric-accent, var(--primary));
  background:linear-gradient(180deg, rgba(255,255,255,.025), transparent), var(--bg-surface);
  border-radius:12px;
  padding:20px 20px 18px;
  position:relative;
  overflow:hidden;
  transition:border-color 200ms ease, box-shadow 200ms ease;
  animation:card-in 300ms ease both;
}
.metric:nth-child(2){ animation-delay:50ms; }
.metric:nth-child(3){ animation-delay:100ms; }
.metric:nth-child(4){ animation-delay:150ms; }
.metric:hover { border-color:var(--border-accent); box-shadow:0 0 0 1px rgba(59,130,246,.1); }
.metric b { display:block; font-size:40px; line-height:1; color:var(--text-primary); font-weight:800; font-variant-numeric:tabular-nums; }
.metric span { display:block; margin-top:10px; color:var(--text-secondary); font-size:13px; font-weight:500; }
.metric:after {
  content:attr(data-icon);
  position:absolute;
  top:16px;
  right:16px;
  width:36px;
  height:36px;
  border-radius:50%;
  display:grid;
  place-items:center;
  color:var(--metric-accent, var(--primary));
  background:color-mix(in srgb, var(--metric-accent, var(--primary)) 15%, transparent);
  font-size:17px;
}
.metric.total { --metric-accent:var(--primary); }
.metric.approved { --metric-accent:var(--success); }
.metric.review { --metric-accent:var(--warning); }
.metric.money { --metric-accent:var(--secondary); }
.metric.money b { color:var(--primary); font-size:28px; }
table { width:100%; border-collapse:collapse; background:transparent !important; }
th, td { border-bottom:1px solid var(--border) !important; padding:10px 12px !important; text-align:left; font-size:13px; color:var(--text-primary); }
th {
  color:var(--text-secondary) !important;
  background:var(--bg-surface) !important;
  font-size:11px !important;
  text-transform:uppercase;
  letter-spacing:.08em;
  font-weight:600 !important;
}
tr:hover td { background:rgba(30,45,64,.5) !important; }
.gr-dataframe, .dataframe, .table-wrap {
  border:1px solid var(--border) !important;
  border-radius:12px !important;
  background:var(--bg-surface) !important;
  overflow:hidden !important;
}
.badge {
  display:inline-flex;
  align-items:center;
  border-radius:999px;
  padding:3px 10px;
  font-size:12px;
  font-weight:600;
  border:1px solid rgba(148,163,184,.15);
  background:rgba(148,163,184,.08);
  color:var(--text-secondary);
}
.badge.ok { background:var(--success-glow); color:var(--success); border-color:rgba(16,185,129,.2); }
.badge.warn { background:var(--warning-glow); color:var(--warning); border-color:rgba(245,158,11,.2); animation:amber-pulse 2s infinite; }
.badge.danger { background:var(--danger-glow); color:var(--danger); border-color:rgba(239,68,68,.2); }
.confidence { display:inline-flex; flex-direction:column; gap:4px; min-width:72px; }
.confidence-pill { border-radius:999px; padding:2px 8px; font-size:12px; font-weight:700; width:max-content; }
.confidence-bar { height:3px; border-radius:999px; overflow:hidden; background:rgba(148,163,184,.12); }
.confidence-bar i { display:block; height:100%; border-radius:999px; }
.confidence.high .confidence-pill { color:var(--success); background:var(--success-glow); }
.confidence.high .confidence-bar i { background:var(--success); }
.confidence.mid .confidence-pill { color:var(--warning); background:var(--warning-glow); }
.confidence.mid .confidence-bar i { background:var(--warning); }
.confidence.low .confidence-pill { color:var(--danger); background:var(--danger-glow); }
.confidence.low .confidence-bar i { background:var(--danger); }
.gradio-container .plot-container, .gradio-container .js-plotly-plot {
  background:transparent !important;
  border:0 !important;
}
.gradio-container ::-webkit-scrollbar { width:8px; height:8px; }
.gradio-container ::-webkit-scrollbar-track { background:transparent; }
.gradio-container ::-webkit-scrollbar-thumb { background:var(--border-accent); border-radius:999px; }
.muted-note { color:var(--text-muted); font-size:12px; margin:8px 0 16px; }
footer, .footer, .built-with, .api-docs, [data-testid='footer'] {
  display:none !important;
  visibility:hidden !important;
  height:0 !important;
  min-height:0 !important;
  overflow:hidden !important;
}
"""


def _client_choices():
    return [f"{c['code']} - {c['name']}" for c in get_all_clients()]


def _client_code(choice):
    return (choice or "").split(" - ")[0]


def _badge(status):
    value = html.escape(str(status or "PENDING"))
    if status in {"AUTO_APPROVED", "APPROVED", "PASSED"}:
        klass = "ok"
    elif status in {"REVIEW_REQUIRED", "FLAGGED"}:
        klass = "warn"
    elif status == "REJECTED":
        klass = "danger"
    else:
        klass = ""
    return f"<span class='badge {klass}'>{value}</span>"


def _confidence_html(score):
    try:
        numeric = float(score or 0)
    except (TypeError, ValueError):
        numeric = 0
    tier = "high" if numeric >= 80 else "mid" if numeric >= 60 else "low"
    width = max(0, min(numeric, 100))
    return (
        f"<span class='confidence {tier}'>"
        f"<span class='confidence-pill'>{numeric:g}%</span>"
        f"<span class='confidence-bar'><i style='width:{width}%'></i></span>"
        "</span>"
    )


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
            f"<td>{_confidence_html(r.get('confidence_score', 0))}</td>"
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
    <div class='metric-row'>
      <div class='metric total' data-icon='Σ'><b>{summary['total_records']}</b><span>Total records</span></div>
      <div class='metric approved' data-icon='✓'><b>{counts.get('AUTO_APPROVED',0) + counts.get('APPROVED',0)}</b><span>Approved</span></div>
      <div class='metric review' data-icon='!'><b>{counts.get('REVIEW_REQUIRED',0)}</b><span>Needs review</span></div>
      <div class='metric money' data-icon='AED'><b>AED {total:,.0f}</b><span>Billable total</span></div>
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
            record["_flagged_batch_id"] = batch_id
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
                "Reject": False,
                "Mark for Review": False,
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
    records = [
        r for r in BATCH.get("records", [])
        if not _is_invoice_approved(r) and r.get("status") not in {"REJECTED", "SENT_FOR_REVIEW"}
    ]
    message = "<p style='color:#8b949e'>No exception records in the current batch.</p>" if not records else ""
    return (
        _exception_display_rows(records),
        message,
        gr.update(visible=False),
    )


def _is_checked(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y", "checked", "on"}


def export_marked_flagged_reviews(queue_df):
    records = [
        r for r in BATCH.get("records", [])
        if not _is_invoice_approved(r) and r.get("status") not in {"REJECTED", "SENT_FOR_REVIEW"}
    ]
    if not records:
        return "<p style='color:#f85149'>No exception queue available.</p>", gr.update(visible=False)

    marked_ids = set()
    reject_ids = set()
    
    if queue_df is not None:
        if isinstance(queue_df, dict):
            # Parse from Gradio dictionary format
            data = queue_df.get("data", [])
            headers = queue_df.get("headers", [])
            queue_df = pd.DataFrame(data, columns=headers)
            
        if not queue_df.empty:
            for _, row in queue_df.iterrows():
                try:
                    row_id = int(row["row_id"])
                    if _is_checked(row.get("Reject")):
                        reject_ids.add(row_id)
                    elif _is_checked(row.get("Mark for Review")):
                        marked_ids.add(row_id)
                except (KeyError, TypeError, ValueError):
                    continue

    selected_ids = marked_ids | reject_ids
    if not selected_ids:
        return "<p style='color:#f85149'>Select at least one row to mark for review or reject by checking the boxes in the table.</p>", gr.update(visible=False)

    export_rows = []
    review_count = 0
    rejected_count = 0
    conn = get_connection()
    exported_at = datetime.now().isoformat(timespec="seconds")
    try:
        for row_id in sorted(selected_ids):
            if row_id < 1 or row_id > len(records):
                continue
            record = records[row_id - 1]
            emp_id = str(record.get("emp_id") or "")
            is_rejected = row_id in reject_ids
            original_status = record.get("status") or "REVIEW_REQUIRED"
            decision = "Reject Payroll" if is_rejected else "Client Review"
            if is_rejected:
                record["status"] = "REJECTED"
                record["payroll_decision"] = "Rejected"
                record["marked_for_review"] = "Yes"
                rejected_count += 1
            else:
                record["status"] = "SENT_FOR_REVIEW"
                record["payroll_decision"] = "Client Review"
                record["marked_for_review"] = "Yes"
                review_count += 1
            conn.execute(
                """
                UPDATE flagged_reviews
                SET payroll_decision=?, marked_for_review=?, status=?, review_reason=?, exported_at=?
                WHERE client_code=? AND COALESCE(emp_id,'')=? AND exported_at IS NULL
                  AND (? IS NULL OR batch_id=?)
                """,
                (
                    decision,
                    "Yes",
                    record["status"],
                    record.get("review_reason"),
                    exported_at,
                    BATCH.get("client_code"),
                    emp_id,
                    record.get("_flagged_batch_id"),
                    record.get("_flagged_batch_id"),
                ),
            )
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
                    "status": "REJECTED" if is_rejected else original_status,
                    "payroll_decision": decision,
                    "marked_for_review": "Yes",
                    "review_reason": record.get("review_reason"),
                    "anomaly_flags": ", ".join(record.get("anomaly_flags", [])),
                }
            )
        if not export_rows:
            conn.commit()
            log_audit("INSPECTION_QUEUE_UPDATED", notes=f"{review_count} marked for review, {rejected_count} rejected")
            return f"<p style='color:#3fb950'>{review_count} row(s) marked for client review. {rejected_count} row(s) rejected.</p>", gr.update(visible=False)
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
            send_note = " Selected rows sent to client portal."
        finally:
            conn.close()
    log_audit("INSPECTION_QUEUE_UPDATED", notes=f"{review_count} marked for review, {rejected_count} rejected")
    return f"<p style='color:#3fb950'>&check; {review_count} row(s) marked for client review. {rejected_count} row(s) rejected.{send_note}</p>", gr.update(value=path, visible=True)


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
    _title_font = {"color": "#F1F5F9", "size": 16, "family": "Inter"}
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#94A3B8", "family": "Inter"},
        margin=dict(l=36, r=20, t=42, b=36),
        xaxis={"gridcolor": "#1E2D40", "zerolinecolor": "#1E2D40", "tickfont": {"color": "#94A3B8"}},
        yaxis={"gridcolor": "#1E2D40", "zerolinecolor": "#1E2D40", "tickfont": {"color": "#94A3B8"}},
    )
    if not records:
        empty = go.Figure().update_layout(**layout)
        return empty, empty, empty, empty
    statuses = Counter(r.get("status") for r in records)
    status_colors = {"AUTO_APPROVED": "#10B981", "APPROVED": "#10B981", "REVIEW_REQUIRED": "#F59E0B", "REJECTED": "#EF4444"}
    fig1 = go.Figure(go.Pie(labels=list(statuses), values=list(statuses.values()), hole=0.58, marker={"colors": [status_colors.get(k, "#3B82F6") for k in statuses]}, textfont={"color": "#F1F5F9"})).update_layout(**layout, title={"text": "Status Distribution", "font": _title_font}, showlegend=True)
    scores = [r.get("confidence_score", 0) for r in records]
    fig2 = go.Figure(go.Histogram(x=scores, nbinsx=10, marker_color="#3B82F6", marker_line_color="#8B5CF6", marker_line_width=1)).update_layout(**layout, title={"text": "Confidence Scores", "font": _title_font})
    flags = Counter(f for r in records for f in r.get("anomaly_flags", []))
    fig3 = go.Figure(go.Bar(x=list(flags.values()), y=list(flags), orientation="h", marker_color="#8B5CF6")).update_layout(**layout, title={"text": "Anomaly Frequency", "font": _title_font})
    names = [(r.get("full_name") or r.get("emp_id") or "?")[:18] for r in records]
    totals = [r.get("payroll", {}).get("final_total", 0) for r in records]
    fig4 = go.Figure(go.Bar(x=names, y=totals, marker_color="#3B82F6")).update_layout(**layout, title={"text": "Final Total per Employee", "font": _title_font})
    return fig1, fig2, fig3, fig4



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


# ── Change 1: Disputes helpers ─────────────────────────────────────────────────

DISPUTE_COLUMNS = ["dispute_id", "client_name", "emp_name", "emp_id", "invoice_id",
                   "dispute_type", "client_message", "raised_at", "status"]
DISPUTE_RESOLVED_COLUMNS = DISPUTE_COLUMNS + ["admin_response"]


def _dispute_choice_label(row):
    dispute_id = row["dispute_id"] if isinstance(row, dict) else row[0]
    client_name = row["client_name"] if isinstance(row, dict) else row[1]
    emp_name = row["emp_name"] if isinstance(row, dict) else row[2]
    invoice_id = row["invoice_id"] if isinstance(row, dict) else row[4]
    dispute_type = row["dispute_type"] if isinstance(row, dict) else row[5]
    try:
        dispute_id = int(float(dispute_id))
    except (TypeError, ValueError):
        pass
    subject = emp_name or client_name or "Client"
    return f"{dispute_id} | {subject} | {invoice_id or 'No invoice'} | {dispute_type or 'Dispute'}"


def _ensure_disputes_table():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS disputes (
            dispute_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            client_code     TEXT,
            client_name     TEXT,
            emp_id          TEXT,
            emp_name        TEXT,
            invoice_id      TEXT,
            dispute_type    TEXT,
            client_message  TEXT,
            admin_response  TEXT,
            raised_at       TEXT,
            resolved_at     TEXT,
            status          TEXT DEFAULT 'OPEN'
        );
    """)
    conn.commit()
    conn.close()


def render_disputes():
    _ensure_disputes_table()
    conn = get_connection()
    open_rows = conn.execute(
        "SELECT dispute_id,client_name,emp_name,emp_id,invoice_id,dispute_type,client_message,raised_at,status FROM disputes WHERE status='OPEN' ORDER BY raised_at DESC"
    ).fetchall()
    resolved_rows = conn.execute(
        "SELECT dispute_id,client_name,emp_name,emp_id,invoice_id,dispute_type,client_message,raised_at,status,admin_response FROM disputes WHERE status='RESOLVED' ORDER BY resolved_at DESC"
    ).fetchall()
    conn.close()
    open_df = pd.DataFrame(open_rows, columns=DISPUTE_COLUMNS) if open_rows else pd.DataFrame(columns=DISPUTE_COLUMNS)
    resolved_df = pd.DataFrame(resolved_rows, columns=DISPUTE_RESOLVED_COLUMNS) if resolved_rows else pd.DataFrame(columns=DISPUTE_RESOLVED_COLUMNS)
    choices = [_dispute_choice_label(r) for r in open_rows] if open_rows else []
    return open_df, resolved_df, gr.update(choices=choices, value=choices[0] if choices else None), ""


def select_dispute_from_table(open_disputes_df, evt: gr.SelectData):
    if evt is None or evt.index is None:
        return gr.update()
    try:
        row_index = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        df = pd.DataFrame(open_disputes_df, columns=DISPUTE_COLUMNS)
        row = df.iloc[int(row_index)].to_dict()
        return gr.update(value=_dispute_choice_label(row))
    except (IndexError, TypeError, ValueError):
        return gr.update()


def send_dispute_response(selected_label, response_text):
    if not selected_label or not response_text.strip():
        return "<p style='color:#f85149'>Select a dispute and enter a response.</p>", *render_disputes()[:3], ""
    try:
        dispute_id = int(str(selected_label).split("|", 1)[0].strip())
    except (TypeError, ValueError):
        return "<p style='color:#f85149'>Invalid selection.</p>", *render_disputes()[:3], ""
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    # Get the invoice_id for this dispute so we can reset the invoice status
    dispute_row = conn.execute("SELECT invoice_id FROM disputes WHERE dispute_id=?", (dispute_id,)).fetchone()
    conn.execute(
        "UPDATE disputes SET admin_response=?, resolved_at=?, status='RESOLVED' WHERE dispute_id=?",
        (response_text.strip(), now, dispute_id),
    )
    # Reset the client_invoices row back to PENDING_APPROVAL so the client can re-act
    if dispute_row and dispute_row[0]:
        conn.execute(
            "UPDATE client_invoices SET status='PENDING_APPROVAL', dispute_type=NULL, client_response=NULL WHERE invoice_id=?",
            (dispute_row[0],),
        )
    conn.commit()
    conn.close()
    open_df, resolved_df, choices, _ = render_disputes()
    return "<p style='color:#3fb950'>Response sent. Dispute resolved and invoice reset to Pending Approval.</p>", open_df, resolved_df, choices, ""


# ── Change 2: Analytics historical charts ──────────────────────────────────────

def render_historical_charts():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    _tfont = {"color": "#F1F5F9", "size": 14, "family": "Inter"}
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#94A3B8", "family": "Inter"},
        margin=dict(l=36, r=20, t=42, b=36),
        xaxis={"gridcolor": "#1E2D40", "zerolinecolor": "#1E2D40", "tickfont": {"color": "#94A3B8"}},
        yaxis={"gridcolor": "#1E2D40", "zerolinecolor": "#1E2D40", "tickfont": {"color": "#94A3B8"}},
        legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": "#94A3B8"}},
    )

    # Exception Rate Trend — three clients, 6 months
    exc_data = {
        "Aldar Properties":  [22, 18, 25, 15, 12, 10],
        "Dubai Airports":    [30, 28, 20, 24, 19, 16],
        "Emaar Hospitality": [18, 22, 16, 14, 18, 12],
    }
    colors = ["#3B82F6", "#F59E0B", "#10B981"]
    fig_exc = go.Figure()
    for (name, vals), color in zip(exc_data.items(), colors):
        fig_exc.add_trace(go.Scatter(x=months, y=vals, mode="lines+markers", name=name,
                                     line=dict(color=color, width=2),
                                     marker=dict(size=6, color=color)))
    fig_exc.update_layout(**layout, title={"text": "Exception Rate Trend (%)", "font": _tfont})

    # Most Flagged Employees — top 10
    flagged_names = [
        "Ravi Menon", "Omar Hassan", "Priya Nair", "James Okafor",
        "Khalid Al Neyadi", "Fatima Khan", "Yusuf Ibrahim", "Nour Khalil",
        "Ryan Costa", "Amira Saleh",
    ]
    flagged_counts = [14, 11, 10, 9, 8, 8, 7, 6, 5, 5]
    fig_flagged = go.Figure(go.Bar(
        x=flagged_counts, y=flagged_names, orientation="h",
        marker_color="#8B5CF6",
    ))
    fig_flagged.update_layout(**layout, title={"text": "Most Flagged Employees", "font": _tfont},
                               xaxis_title="Flag Count")
    fig_flagged.update_yaxes(autorange="reversed")

    # Touchless Rate Over Time
    touchless = [42, 51, 58, 65, 74, 83]
    fig_touch = go.Figure(go.Scatter(
        x=months, y=touchless, mode="lines+markers+text",
        text=[f"{v}%" for v in touchless], textposition="top center",
        textfont={"color": "#10B981"},
        line=dict(color="#10B981", width=2),
        marker=dict(size=8, color="#10B981"),
        fill="tozeroy", fillcolor="rgba(16,185,129,0.07)",
    ))
    fig_touch.update_layout(**layout, title={"text": "Touchless Rate Over Time (%)", "font": _tfont})
    fig_touch.update_yaxes(range=[0, 105])

    return fig_exc, fig_flagged, fig_touch


def _client_health_html():
    clients = [
        ("ADNOC",            88, "Healthy",        "#10B981", "rgba(16,185,129,0.08)", "rgba(16,185,129,0.2)"),
        ("Emaar Hospitality",84, "Healthy",        "#10B981", "rgba(16,185,129,0.08)", "rgba(16,185,129,0.2)"),
        ("Dubai Airports",   71, "Needs Attention","#F59E0B", "rgba(245,158,11,0.08)", "rgba(245,158,11,0.2)"),
        ("Etihad Airways",   67, "Needs Attention","#F59E0B", "rgba(245,158,11,0.08)", "rgba(245,158,11,0.2)"),
        ("Transguard Group", 48, "At Risk",         "#EF4444", "rgba(239,68,68,0.08)",  "rgba(239,68,68,0.2)"),
        ("Aldar Properties",  82, "Healthy",       "#10B981", "rgba(16,185,129,0.08)", "rgba(16,185,129,0.2)"),
        ("DP World",          74, "Needs Attention","#F59E0B", "rgba(245,158,11,0.08)", "rgba(245,158,11,0.2)"),
    ]
    cards = "".join(
        f"""
        <div style='border:1px solid {border};background:{bg};border-radius:12px;padding:18px 20px;text-align:center;min-width:130px;flex:1'>
          <div style='font-size:12px;color:#94A3B8;font-weight:600;margin-bottom:8px'>{name}</div>
          <div style='font-size:36px;font-weight:800;color:{color};line-height:1'>{score}</div>
          <div style='margin-top:8px;font-size:11px;font-weight:700;color:{color};background:{bg};border:1px solid {border};display:inline-block;padding:2px 10px;border-radius:999px'>{label}</div>
        </div>"""
        for name, score, label, color, bg, border in clients
    )
    return f"<div style='margin-top:8px'><div style='font-size:13px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px'>Client Health Scores</div><div style='display:flex;gap:10px;flex-wrap:wrap'>{cards}</div></div>"


# ── Change 3: Expanded Query Assistant ─────────────────────────────────────────

def _ensure_invoice_history_table():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS invoice_history (
            invoice_id      TEXT PRIMARY KEY,
            client_code     TEXT,
            client_name     TEXT,
            emp_id          TEXT,
            emp_name        TEXT,
            billing_period  TEXT,
            working_days    REAL,
            gross_billable  REAL,
            final_total     REAL,
            status          TEXT,
            raised_at       TEXT
        );
    """)
    count = conn.execute("SELECT COUNT(*) FROM invoice_history").fetchone()[0]
    if count < 20:
        _seed_invoice_history_data(conn)
    conn.commit()
    conn.close()


def _seed_invoice_history_data(conn):
    import random as _r
    clients = [
        ("CL001", "Aldar Properties",  [("EMP10001", "Aisha Al Zaabi"),    ("EMP10011", "Khalid Al Neyadi")]),
        ("CL002", "Dubai Airports",    [("EMP10002", "Ravi Menon"),         ("EMP10012", "Priya Nair")]),
        ("CL004", "ADNOC",             [("EMP10004", "Mohammed Al Ali"),    ("EMP10014", "Hana Al Rashid")]),
        ("CL005", "Emaar Hospitality", [("EMP10003", "Fatima Khan"),        ("EMP10015", "Mia Chen")]),
        ("CL007", "Transguard Group",  [("EMP10006", "Ryan Costa"),         ("EMP10017", "Nadia Volkov")]),
    ]
    periods = ["January 2026", "February 2026", "March 2026", "April 2026", "May 2026", "June 2026"]
    rows = []
    for month_idx, period in enumerate(periods):
        for cl_code, cl_name, emps in clients:
            for emp_id, emp_name in emps:
                days = _r.randint(20, 26)
                gross = round(_r.randint(5000, 12000) * (days / 26), 2)
                final = round(gross * 1.10 + _r.randint(0, 500), 2)
                status = _r.choice(["APPROVED", "APPROVED", "REVIEW_REQUIRED"])
                raised_at = f"2026-{month_idx+1:02d}-{_r.randint(1,25):02d}T10:00:00"
                inv_id = f"HIST-{period[:3].upper()}-{cl_code}-{emp_id[-3:]}"
                rows.append((inv_id, cl_code, cl_name, emp_id, emp_name, period, days, gross, final, status, raised_at))
    rows = rows[:20]
    conn.executemany(
        "INSERT OR IGNORE INTO invoice_history VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows
    )


def answer_query(question):
    q = (question or "").lower()
    if not q:
        return "<p style='color:#8b949e'>Enter a question.</p>"
    try:
        _ensure_invoice_history_table()
    except Exception:
        pass
    try:
        _ensure_disputes_table()
    except Exception:
        pass
    conn = get_connection()
    try:
        # ── Current batch ────────────────────────────────────────────────────────
        if "current" in q or "batch" in q:
            return _summary_cards(BATCH.get("records", []))

        # ── Employee count per client ────────────────────────────────────────────
        if "how many" in q and "employee" in q:
            for client in get_all_clients():
                if client["name"].lower() in q or client["code"].lower() in q:
                    n = conn.execute("SELECT COUNT(*) FROM employees WHERE client_code=?", (client["code"],)).fetchone()[0]
                    return f"<p><b>{html.escape(client['name'])}</b> has <b>{n}</b> employees.</p>"

        # ── Salary / CTC threshold ──────────────────────────────────────────────
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

        # ── Client roster listing ───────────────────────────────────────────────
        for client in get_all_clients():
            if client["name"].lower() in q and not any(kw in q for kw in ["total", "billed", "invoice", "flag", "exception", "confidence", "rate"]):
                rows = conn.execute("SELECT emp_id,full_name,job_title,total_ctc FROM employees WHERE client_code=? LIMIT 20", (client["code"],)).fetchall()
                body = "".join(f"<tr><td>{r[0]}</td><td>{html.escape(r[1])}</td><td>{html.escape(str(r[2]))}</td><td>AED {r[3]:,.0f}</td></tr>" for r in rows)
                return "<table><tr><th>ID</th><th>Name</th><th>Role</th><th>CTC</th></tr>" + body + "</table>"

        # ── NEW: Total AED billed to a client ────────────────────────────────────
        if any(kw in q for kw in ["total", "billed", "billing", "invoice total"]) and "client" in q:
            for client in get_all_clients():
                if client["name"].lower() in q:
                    row = conn.execute(
                        "SELECT SUM(final_total) FROM invoice_history WHERE client_code=?",
                        (client["code"],),
                    ).fetchone()
                    total = row[0] or 0
                    return f"<p>Total billed to <b>{html.escape(client['name'])}</b>: <b>AED {total:,.2f}</b></p>"

        # ── NEW: Top 5 highest billed employees ──────────────────────────────────
        if any(kw in q for kw in ["top", "highest", "billed employee"]):
            rows = conn.execute(
                "SELECT emp_name,client_name,SUM(final_total) as tot FROM invoice_history GROUP BY emp_id ORDER BY tot DESC LIMIT 5"
            ).fetchall()
            body = "".join(f"<tr><td>{html.escape(r[0])}</td><td>{html.escape(r[1])}</td><td>AED {r[2]:,.2f}</td></tr>" for r in rows)
            return "<table><tr><th>Employee</th><th>Client</th><th>Total Billed</th></tr>" + body + "</table>"

        # ── NEW: Average confidence score for a client ───────────────────────────
        if "average confidence" in q or ("confidence" in q and "score" in q):
            for client in get_all_clients():
                if client["name"].lower() in q:
                    row = conn.execute(
                        "SELECT AVG(confidence_score) FROM flagged_reviews WHERE client_code=?",
                        (client["code"],),
                    ).fetchone()
                    avg = row[0] or 0
                    return f"<p>Average confidence for <b>{html.escape(client['name'])}</b>: <b>{avg:.1f}%</b></p>"

        # ── NEW: Highest exception rate client ───────────────────────────────────
        if "exception rate" in q or ("highest exception" in q):
            rows = conn.execute(
                """
                SELECT client_code, COUNT(*) as total,
                       SUM(CASE WHEN status='REVIEW_REQUIRED' THEN 1 ELSE 0 END) as flagged
                FROM invoice_history GROUP BY client_code
                """
            ).fetchall()
            if rows:
                best = max(rows, key=lambda r: (r[2] / r[1]) if r[1] else 0)
                rate = (best[2] / best[1] * 100) if best[1] else 0
                cl_name = next((c["name"] for c in get_all_clients() if c["code"] == best[0]), best[0])
                return f"<p>Highest exception rate: <b>{html.escape(cl_name)}</b> at <b>{rate:.1f}%</b></p>"

        # ── NEW: Flagged more than twice this quarter ────────────────────────────
        if "flagged" in q and any(kw in q for kw in ["twice", "2", "multiple"]):
            for client in get_all_clients():
                if client["name"].lower() in q:
                    rows = conn.execute(
                        """
                        SELECT emp_id, full_name, COUNT(*) as cnt FROM flagged_reviews
                        WHERE client_code=? AND created_at >= '2026-04-01'
                        GROUP BY emp_id HAVING cnt > 2 ORDER BY cnt DESC
                        """,
                        (client["code"],),
                    ).fetchall()
                    if not rows:
                        return f"<p>No employees flagged more than twice this quarter for <b>{html.escape(client['name'])}</b>.</p>"
                    body = "".join(f"<tr><td>{r[0]}</td><td>{html.escape(str(r[1]))}</td><td>{r[2]}</td></tr>" for r in rows)
                    return "<table><tr><th>Emp ID</th><th>Name</th><th>Flag Count</th></tr>" + body + "</table>"

        # ── NEW: Reimbursements > 20% of basic ──────────────────────────────────
        if "reimbursement" in q and any(kw in q for kw in ["20", "exceed", "percent", "%"]):
            rows = conn.execute(
                """
                SELECT ih.emp_name, ih.client_name, ih.billing_period, ih.gross_billable, ih.final_total
                FROM invoice_history ih
                WHERE ih.final_total > ih.gross_billable * 1.20
                ORDER BY ih.final_total DESC LIMIT 20
                """
            ).fetchall()
            body = "".join(f"<tr><td>{html.escape(r[0])}</td><td>{html.escape(r[1])}</td><td>{r[2]}</td><td>AED {r[3]:,.2f}</td><td>AED {r[4]:,.2f}</td></tr>" for r in rows)
            return "<table><tr><th>Employee</th><th>Client</th><th>Period</th><th>Gross Billable</th><th>Final Total</th></tr>" + body + "</table>"

        return "<p style='color:#8b949e'>Try asking about employee count, salary above an amount, total billed to a client, average confidence score, top billed employees, or exception rates.</p>"
    except Exception as exc:
        return f"<p style='color:#f85149'>Query error: {html.escape(str(exc))}</p>"
    finally:
        conn.close()


# ── Change 4: Invoice push helper ──────────────────────────────────────────────

def _ensure_client_invoices_table():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS client_invoices (
            invoice_id      TEXT PRIMARY KEY,
            client_code     TEXT,
            client_name     TEXT,
            billing_period  TEXT,
            pdf_path        TEXT,
            erp_excel_path  TEXT,
            dispatch_notes  TEXT,
            dispatched_at   TEXT,
            status          TEXT DEFAULT 'PENDING_APPROVAL',
            approved_at     TEXT,
            dispute_type    TEXT,
            client_response TEXT,
            total_amount    REAL,
            line_items      TEXT
        );
    """)
    # Migrate existing tables
    existing = [row[1] for row in conn.execute("PRAGMA table_info(client_invoices)").fetchall()]
    if "total_amount" not in existing:
        conn.execute("ALTER TABLE client_invoices ADD COLUMN total_amount REAL")
    if "line_items" not in existing:
        conn.execute("ALTER TABLE client_invoices ADD COLUMN line_items TEXT")
    conn.commit()
    conn.close()


def _rand_inv_id():
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"INV-{datetime.now().strftime('%Y%m%d')}-{suffix}"


def push_invoice_to_portal(period, dispatch_notes):
    records = _approved_invoice_records()
    code = BATCH.get("client_code")
    if not records or not code:
        return "<p style='color:#f85149'>Generate invoice outputs first before dispatching.</p>"
    _ensure_client_invoices_table()
    cfg = get_client_config(code)
    cl_name = cfg.get("client_name", code)
    pdf_path = os.path.join("outputs", f"invoice_{code}_{(period or '').replace(' ', '_')}.pdf")
    erp_path = os.path.join("outputs", f"ERP_{code}_{(period or '').replace(' ', '_')}.xlsx")
    inv_id = _rand_inv_id()
    now = datetime.now().isoformat(timespec="seconds")
    # Compute total_amount and line_items from approved records
    total_amount = 0.0
    line_items_list = []
    for rec in records:
        pay = rec.get("payroll", {})
        ft = pay.get("final_total", 0) or 0
        total_amount += ft
        line_items_list.append({
            "emp_id": rec.get("emp_id") or "",
            "full_name": rec.get("full_name") or (rec.get("resolved_emp") or {}).get("full_name", ""),
            "working_days": rec.get("working_days", 0),
            "ot_hours": rec.get("ot_hours", 0),
            "final_total": round(ft, 2),
        })
    total_amount = round(total_amount, 2)
    line_items_json = json.dumps(line_items_list)
    conn = get_connection()
    conn.execute(
        "INSERT INTO client_invoices(invoice_id,client_code,client_name,billing_period,pdf_path,erp_excel_path,dispatch_notes,dispatched_at,status,total_amount,line_items) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (inv_id, code, cl_name, period or "Current Period", pdf_path, erp_path, dispatch_notes or "", now, "PENDING_APPROVAL", total_amount, line_items_json),
    )
    conn.commit()
    conn.close()
    log_audit("INVOICE_DISPATCHED", invoice_id=inv_id, notes=f"{code} pushed to client portal total={total_amount}")
    return f"<p style='color:#3fb950'>Invoice <b>{inv_id}</b> pushed to Client Portal (AED {total_amount:,.2f}). Status: <b>PENDING_APPROVAL</b></p>"


# ── Change 5: Submission Timeline helper ───────────────────────────────────────

def _submission_timeline_html():
    records = BATCH.get("records", [])
    code = BATCH.get("client_code") or "N/A"
    now_str = datetime.now().strftime("%H:%M %d %b %Y")

    flagged = sum(1 for r in records if r.get("status") == "REVIEW_REQUIRED")
    total = len(records)
    has_exceptions = flagged > 0
    invoice_generated = any(os.path.exists(os.path.join("outputs", f)) for f in (os.listdir("outputs") if os.path.exists("outputs") else []) if f.endswith(".pdf"))

    # Determine which stages are complete
    stages = [
        {"label": "Received",          "color": "#3B82F6", "ts": now_str if total > 0 else None,   "done": total > 0,           "active": total == 0},
        {"label": "Extracting",         "color": "#3B82F6", "ts": now_str if total > 0 else None,   "done": total > 0,           "active": False},
        {"label": f"Validating{'</br><small style=color:#F59E0B>Exceptions Found (' + str(flagged) + ')</small>' if has_exceptions else ''}",
         "color": "#F59E0B" if has_exceptions else ("#3B82F6" if total > 0 else "#475569"),
         "ts":  now_str if total > 0 else None,
         "done": total > 0,  "active": has_exceptions},
        {"label": "Invoice Generated",  "color": "#10B981", "ts": now_str if invoice_generated else None, "done": invoice_generated, "active": total > 0 and not invoice_generated},
        {"label": "Dispatched",          "color": "#10B981", "ts": None,                              "done": False,              "active": False},
    ]

    def _circle(stage):
        if stage["done"]:
            return f"<div style='width:32px;height:32px;border-radius:50%;background:{stage['color']};display:grid;place-items:center;flex-shrink:0;font-size:16px'>✓</div>"
        if stage["active"]:
            return f"<div style='width:32px;height:32px;border-radius:50%;border:2px solid {stage['color']};display:grid;place-items:center;flex-shrink:0;animation:pulse-online 2s infinite'><div style='width:12px;height:12px;border-radius:50%;background:{stage["color"]}'></div></div>"
        return "<div style='width:32px;height:32px;border-radius:50%;border:2px solid #1E2D40;display:grid;place-items:center;flex-shrink:0'></div>"

    items = []
    for i, s in enumerate(stages):
        ts_html = f"<div style='font-size:10px;color:#475569;margin-top:4px;text-align:center'>{s['ts']}</div>" if s["ts"] else "<div style='height:18px'></div>"
        items.append(
            f"<div style='display:flex;flex-direction:column;align-items:center;flex:1'>"
            f"{_circle(s)}"
            f"<div style='font-size:11px;font-weight:600;color:{'#F1F5F9' if s['done'] or s['active'] else '#475569'};margin-top:6px;text-align:center'>{s['label']}</div>"
            f"{ts_html}</div>"
        )
        if i < len(stages) - 1:
            line_color = s["color"] if s["done"] else "#1E2D40"
            items.append(f"<div style='flex:0.5;height:2px;background:{line_color};margin-top:16px;border-radius:2px'></div>")

    client_label = f"Client: <b>{html.escape(code)}</b> &nbsp;|&nbsp; Records: <b>{total}</b>"
    return (
        f"<div style='margin-top:24px;padding:20px;border:1px solid #1E2D40;border-radius:12px;background:#0D1117'>"
        f"<div style='font-size:13px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px'>Submission Timeline &nbsp;·&nbsp; {client_label}</div>"
        f"<div style='display:flex;align-items:flex-start;gap:0'>{''.join(items)}</div>"
        f"</div>"
    )


<<<<<<< HEAD
=======
HEAD_HTML = """
<style>
.gradio-mic-btn {
    position: absolute;
    right: 10px;
    bottom: 10px;
    background: rgba(30, 45, 64, 0.8);
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #94A3B8;
    z-index: 10;
}
.gradio-mic-btn:hover {
    color: #38BDF8;
    border-color: #38BDF8;
}
.gradio-mic-btn.listening {
    color: #EF4444;
    border-color: #EF4444;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    70% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
    100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
</style>
<script>
(function() {
    function attachMic(elemId) {
        const container = document.getElementById(elemId);
        if (!container) return false;
        
        // Check if already attached
        if (container.dataset.micAttached === 'true') return true;
        
        // find the textarea
        const textarea = container.querySelector('textarea');
        if (!textarea) return false;
        
        container.dataset.micAttached = 'true';
        
        // create button
        const btn = document.createElement('button');
        btn.className = 'gradio-mic-btn';
        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" x2="12" y1="19" y2="22"></line></svg>';
        
        textarea.parentElement.style.position = 'relative';
        textarea.parentElement.appendChild(btn);
        
        let ws = null;
        let audioContext = null;
        let processor = null;
        let mediaStream = null;
        let isListening = false;
        
        const stopListening = () => {
            isListening = false;
            btn.classList.remove('listening');
            if (processor) { processor.disconnect(); processor = null; }
            if (mediaStream) { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
            if (audioContext) { audioContext.close(); audioContext = null; }
            if (ws) { ws.close(); ws = null; }
        };

        btn.onclick = async (e) => {
            e.preventDefault();
            if (isListening) {
                stopListening();
                return;
            }
            
            try {
                ws = new WebSocket('ws://127.0.0.1:8500/ws/stt');
                ws.onopen = async () => {
                    isListening = true;
                    btn.classList.add('listening');
                    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 }});
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    audioContext = new AudioContext({ sampleRate: 16000 });
                    const source = audioContext.createMediaStreamSource(mediaStream);
                    processor = audioContext.createScriptProcessor(4096, 1, 1);
                    
                    processor.onaudioprocess = (e) => {
                        if (ws.readyState === WebSocket.OPEN) {
                            const inputData = e.inputBuffer.getChannelData(0);
                            const pcmData = new Int16Array(inputData.length);
                            for (let i = 0; i < inputData.length; i++) {
                                let s = Math.max(-1, Math.min(1, inputData[i]));
                                pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                            }
                            ws.send(pcmData.buffer);
                        }
                    };
                    source.connect(processor);
                    processor.connect(audioContext.destination);
                };
                
                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.is_final && data.transcript) {
                            const currentText = textarea.value;
                            const newText = currentText + (currentText.endsWith(' ') || currentText.length === 0 ? '' : ' ') + data.transcript + ' ';
                            
                            // Set value and trigger Gradio's internal state update
                            textarea.value = newText;
                            textarea.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    } catch (e) {}
                };
                
                ws.onerror = () => stopListening();
                ws.onclose = () => stopListening();
            } catch (err) {
                console.error("STT Error", err);
                stopListening();
            }
        };
        
        return true;
    }
    
    // Poll for elements since Gradio renders tabs dynamically
    setInterval(() => {
        attachMic('dispute_response_input');
        attachMic('dispatch_notes_input');
        attachMic('query_assistant_input');
    }, 1000);
})();
</script>
"""

>>>>>>> 83377e60 (smallest.ai integration)
def build_app():
    ensure_database()
    _ensure_disputes_table()
    _ensure_client_invoices_table()
    _ensure_invoice_history_table()
    with gr.Blocks(title="TIA - Touchless Invoice Agent") as app:
        gr.HTML(
            "<div class='tia-topbar'>"
            "<div class='tia-logo'>TIA</div>"
            "<div class='tia-product'>Touchless Invoice Agent - TASC invoice validation and billing</div>"
            "<div class='tia-status'><span>OFFLINE</span><span class='tia-avatar'>TO</span></div>"
            "</div>"
        )

        # ── Tab 1: Submit Timesheets ────────────────────────────────────────────
        with gr.Tab("Submit Timesheets"):
            client = gr.Dropdown(choices=_client_choices(), label="Client")
            files = gr.File(label="Upload files", file_count="multiple", file_types=[".xlsx", ".xls", ".csv", ".tsv", ".eml", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".webp"])
            gr.HTML("<p class='muted-note'>All files must be the same format. Mixed types will be rejected automatically.</p>")
            run = gr.Button("Process Batch", variant="primary")
            summary = gr.HTML()
            table = gr.HTML()
            auto_csv = gr.File(label="Auto-approved CSV", visible=False)
            run.click(process_upload, inputs=[client, files], outputs=[summary, table, auto_csv])

        # ── Tab 2: Client Messages (Change 5: + Submission Timeline) ───────────
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
            # Change 5 — Submission Timeline
            gr.HTML("<hr style='border-color:#1E2D40;margin:24px 0 8px'>")
            gr.HTML("<p style='font-size:12px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:.08em'>Submission Timeline</p>")
            timeline_html = gr.HTML()
            refresh_timeline_btn = gr.Button("Refresh Timeline", size="sm")
            refresh_client_msgs.click(render_client_messages, outputs=[client_messages, selected_client_message])
            process_client_files.click(
                process_client_message_uploads,
                inputs=[client_messages, selected_client_message, client_msg_client],
                outputs=[client_summary, client_table, client_auto_csv],
            ).then(_submission_timeline_html, outputs=timeline_html)
            refresh_timeline_btn.click(_submission_timeline_html, outputs=timeline_html)

        # ── Tab 3: Exception Queue ──────────────────────────────────────────────
        with gr.Tab("Exception Queue"):
            refresh = gr.Button("Refresh Queue")
            queue = gr.Dataframe(
                headers=EXCEPTION_DISPLAY_COLUMNS,
                datatype=["bool", "bool", "number", "str", "str", "number", "number", "number", "number", "str", "str", "str", "str"],
                interactive=True,
                wrap=True,
                label="Admin Exception Queue",
            )
            send_flagged = gr.Button("Send Flag Reviews", variant="primary")
            flagged_msg = gr.HTML()
            flagged_csv = gr.File(label="Flagged Reviews CSV", visible=False)
            
            refresh.click(render_exception_queue, outputs=[queue, flagged_msg, flagged_csv])
            
            def _refresh_exception_queue_keep_message():
                queue_df, _, _ = render_exception_queue()
                return queue_df

            send_flagged.click(
                export_marked_flagged_reviews,
                inputs=[queue],
                outputs=[flagged_msg, flagged_csv],
            ).then(
                _refresh_exception_queue_keep_message,
                outputs=queue,
            )

        # ── Tab 4: Disputes (Change 1) ─────────────────────────────────────────
        with gr.Tab("Disputes"):
            disputes_refresh_btn = gr.Button("Refresh", size="sm")
            with gr.Row():
                # Left: Open Disputes
                with gr.Column():
                    gr.HTML("<h3 style='font-size:15px;font-weight:700;color:#F1F5F9;margin-bottom:10px'>Open Disputes</h3>")
                    open_disputes_df = gr.Dataframe(
                        headers=DISPUTE_COLUMNS,
                        datatype=["number", "str", "str", "str", "str", "str", "str", "str", "str"],
                        interactive=False,
                        wrap=True,
                        label="",
                    )
                    dispute_selector = gr.Radio(choices=[], label="Select Dispute to Respond")
<<<<<<< HEAD
                    dispute_response_input = gr.Textbox(label="Response", lines=3, placeholder="Type your response here...")
=======
                    dispute_response_input = gr.Textbox(label="Response", lines=3, placeholder="Type your response here...", elem_id="dispute_response_input")
>>>>>>> 83377e60 (smallest.ai integration)
                    send_response_btn = gr.Button("Send Response", variant="primary")
                    dispute_response_msg = gr.HTML()

                # Right: Resolved Disputes
                with gr.Column():
                    gr.HTML("<h3 style='font-size:15px;font-weight:700;color:#F1F5F9;margin-bottom:10px'>Resolved Disputes</h3>")
                    resolved_disputes_df = gr.Dataframe(
                        headers=DISPUTE_RESOLVED_COLUMNS,
                        datatype=["number", "str", "str", "str", "str", "str", "str", "str", "str", "str"],
                        interactive=False,
                        wrap=True,
                        label="",
                    )

            # Wire up refresh
            def _refresh_disputes():
                open_df, resolved_df, choices_update, _ = render_disputes()
                return open_df, resolved_df, choices_update

            disputes_refresh_btn.click(
                _refresh_disputes,
                outputs=[open_disputes_df, resolved_disputes_df, dispute_selector],
            )
            open_disputes_df.select(
                select_dispute_from_table,
                inputs=[open_disputes_df],
                outputs=dispute_selector,
            )
            send_response_btn.click(
                send_dispute_response,
                inputs=[dispute_selector, dispute_response_input],
                outputs=[dispute_response_msg, open_disputes_df, resolved_disputes_df, dispute_selector, dispute_response_input],
            )
            # Load on tab open
            app.load(_refresh_disputes, outputs=[open_disputes_df, resolved_disputes_df, dispute_selector])

        # ── Tab 5: Invoice Output (Change 4: + Push to Client Portal) ──────────
        with gr.Tab("Invoice Output"):
            period = gr.Textbox(label="Billing Period", value="June 2026")
            generate = gr.Button("Generate PDF and ERP Excel", variant="primary")
            output_summary = gr.HTML()
            pdf_file = gr.File(label="Invoice PDF", visible=False)
            xlsx_file = gr.File(label="ERP Excel", visible=False)
            generate.click(generate_outputs, inputs=period, outputs=[output_summary, pdf_file, xlsx_file])

            # Change 4 — Dispatch to Client Portal
            gr.HTML("<hr style='border-color:#1E2D40;margin:28px 0 8px'>")
            gr.HTML("<h3 style='font-size:15px;font-weight:700;color:#F1F5F9;margin-bottom:12px'>Dispatch to Client Portal</h3>")
            with gr.Row():
                dispatch_client_dropdown = gr.Dropdown(choices=_client_choices(), label="Client (auto-filled from batch)", scale=2)
<<<<<<< HEAD
                dispatch_notes_input = gr.Textbox(label="Dispatch Notes", placeholder="Optional notes for the client...", scale=3)
=======
                dispatch_notes_input = gr.Textbox(label="Dispatch Notes", placeholder="Optional notes for the client...", scale=3, elem_id="dispatch_notes_input")
>>>>>>> 83377e60 (smallest.ai integration)
            push_btn = gr.Button("Push Invoice to Client Portal", variant="primary")
            push_msg = gr.HTML()

            def _push_with_period(period_val, notes):
                return push_invoice_to_portal(period_val, notes)

            push_btn.click(_push_with_period, inputs=[period, dispatch_notes_input], outputs=push_msg)

        # ── Tab 6: Analytics (Change 2: + Historical Charts) ───────────────────
        with gr.Tab("Analytics"):
            refresh_charts = gr.Button("Refresh Charts")
            # Existing charts (row 1)
            with gr.Row():
                pie = gr.Plot()
                hist = gr.Plot()
            with gr.Row():
                flags = gr.Plot()
                totals = gr.Plot()
            refresh_charts.click(render_charts, outputs=[pie, hist, flags, totals])

            # Change 2 — Historical multi-batch row (row 2)
            gr.HTML("<hr style='border-color:#1E2D40;margin:24px 0 8px'>")
            gr.HTML("<p style='font-size:12px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px'>Historical Multi-Batch Analytics</p>")
            refresh_historical_btn = gr.Button("Refresh Historical Charts", size="sm")
            with gr.Row():
                exc_trend_plot = gr.Plot()
                flagged_emp_plot = gr.Plot()
                touchless_plot = gr.Plot()
            health_html = gr.HTML()
            refresh_historical_btn.click(
                lambda: (*render_historical_charts(), _client_health_html()),
                outputs=[exc_trend_plot, flagged_emp_plot, touchless_plot, health_html],
            )

        # ── Tab 7: Query Assistant (Change 3: upgraded) ─────────────────────────
        with gr.Tab("Query Assistant"):
            gr.HTML(
                "<p style='color:#94A3B8;font-size:13px;margin-bottom:12px'>Ask questions about employees, invoices, billing history, exception rates, and more.</p>"
            )
<<<<<<< HEAD
            question = gr.Textbox(label="Question", lines=2, placeholder="What is the total AED billed to ADNOC across all batches?")
=======
            question = gr.Textbox(label="Question", lines=2, placeholder="What is the total AED billed to ADNOC across all batches?", elem_id="query_assistant_input")
>>>>>>> 83377e60 (smallest.ai integration)
            ask = gr.Button("Ask", variant="primary")
            answer = gr.HTML()
            ask.click(answer_query, inputs=question, outputs=answer)

        # ── Tab 8: Column Config ────────────────────────────────────────────────
        with gr.Tab("Column Config"):
            cfg_client = gr.Dropdown(choices=_client_choices(), label="Client")
            cfg_columns = gr.CheckboxGroup(choices=ALL_COLUMNS, label="Invoice Output Columns")
            cfg_markup = gr.Number(label="TASC Markup %", minimum=0, maximum=50, step=0.5, value=10.0)
    return app


def launch():
    ensure_database()
<<<<<<< HEAD
    build_app().queue().launch(server_name="127.0.0.1", server_port=7860, share=False, debug=True, css=CSS, theme=gr.themes.Base())
=======
    build_app().queue().launch(server_name="127.0.0.1", server_port=7860, share=False, debug=True, css=CSS, theme=gr.themes.Base(), head=HEAD_HTML)
>>>>>>> 83377e60 (smallest.ai integration)


if __name__ == "__main__":
    launch()
