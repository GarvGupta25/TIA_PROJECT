from collections import Counter
import html

import gradio as gr
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
from invoice_generator import ALL_COLUMNS, export_erp_excel, generate_invoice_pdf
from router import process_file


BATCH = {"records": [], "client_code": None}

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
    colors = {"AUTO_APPROVED": "#238636", "REVIEW_REQUIRED": "#9e6a03", "REJECTED": "#da3633"}
    color = colors.get(status, "#6e7681")
    return f"<span style='background:{color};color:white;border-radius:4px;padding:2px 6px;font-size:11px'>{html.escape(str(status))}</span>"


def _records_table(records):
    if not records:
        return "<p style='color:#8b949e'>No records processed yet.</p>"
    rows = []
    for r in records:
        pay = r.get("payroll", {})
        flags = ", ".join(r.get("anomaly_flags", [])) or "None"
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
            f"<td>{html.escape(flags)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Emp ID</th><th>Name</th><th>Days</th><th>OT</th>"
        "<th>Total</th><th>Score</th><th>Status</th><th>Flags</th></tr></thead><tbody>"
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


def process_upload(client_choice, files):
    if not client_choice:
        return "<p style='color:#f85149'>Select a client first.</p>", ""
    if not files:
        return "<p style='color:#f85149'>Upload at least one Excel, email, PDF, or image file.</p>", ""
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
    log_audit("BATCH_PROCESSED", notes=f"{len(all_records)} records for {code}")
    err_html = ""
    if errors:
        err_html = "<p style='color:#f85149'>" + "<br>".join(html.escape(e) for e in errors) + "</p>"
    return _summary_cards(all_records) + err_html, _records_table(all_records)


def render_exception_queue():
    records = [r for r in BATCH.get("records", []) if r.get("status") != "AUTO_APPROVED"]
    return _records_table(records)


def generate_outputs(period):
    records = BATCH.get("records", [])
    code = BATCH.get("client_code")
    if not records or not code:
        return "<p style='color:#f85149'>No processed batch available.</p>", gr.update(visible=False), gr.update(visible=False)
    cfg = get_client_config(code)
    columns = cfg.get("output_columns") or ALL_COLUMNS[:10]
    pdf_path = generate_invoice_pdf(records, code, period or "Current Period", columns)
    xlsx_path = export_erp_excel(records, code, columns)
    log_audit("INVOICE_GENERATED", notes=f"{code} {period}")
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
            run.click(process_upload, inputs=[client, files], outputs=[summary, table])

        with gr.Tab("Exception Queue"):
            refresh = gr.Button("Refresh Queue")
            queue = gr.HTML()
            refresh.click(render_exception_queue, outputs=queue)

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
