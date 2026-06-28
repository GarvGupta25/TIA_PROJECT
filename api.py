"""
api.py — TIA FastAPI Bridge
Runs on port 8001 alongside the Gradio app on port 7860.
Connects to the same tasc.db SQLite file and exposes REST endpoints
so the React client portal can read/write invoice and dispute data.

Run with:  python api.py
"""

import json
import os
import random
import sqlite3
import string
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "tasc.db"

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="TIA API Bridge", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Database helpers ───────────────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _rand_id(prefix: str = "INV") -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{suffix}"


# ── Schema creation (NO dummy data) ───────────────────────────────────────────
CREATE_TABLES_SQL = """
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

CREATE TABLE IF NOT EXISTS roster_confirmations (
    confirmation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_code     TEXT,
    period          TEXT,
    confirmed_by    TEXT,
    confirmed_at    TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS resubmissions (
    resubmission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_batch  TEXT,
    client_code     TEXT,
    resubmitted_at  TEXT,
    reason          TEXT,
    status          TEXT DEFAULT 'PENDING'
);
"""


def _migrate_columns(conn: sqlite3.Connection):
    """Add new columns to existing tables if they are missing."""
    existing = [row[1] for row in conn.execute("PRAGMA table_info(client_invoices)").fetchall()]
    if "total_amount" not in existing:
        conn.execute("ALTER TABLE client_invoices ADD COLUMN total_amount REAL")
    if "line_items" not in existing:
        conn.execute("ALTER TABLE client_invoices ADD COLUMN line_items TEXT")
    conn.commit()


@app.on_event("startup")
def on_startup():
    conn = get_conn()
    conn.executescript(CREATE_TABLES_SQL)
    conn.commit()
    _migrate_columns(conn)
    conn.close()
    print("API running on port 8001")


# ── Request/Response Models ────────────────────────────────────────────────────
class ApproveInvoiceRequest(BaseModel):
    invoice_id: str


class DisputeInvoiceRequest(BaseModel):
    invoice_id: str
    client_code: str
    reason: str


class CorrectionRequest(BaseModel):
    invoice_id: str
    client_code: str
    details: str


class PushInvoiceRequest(BaseModel):
    client_code: str
    client_name: str
    billing_period: str
    pdf_path: str = ""
    erp_excel_path: str = ""
    dispatch_notes: str = ""
    total_amount: float = 0.0
    line_items: str = "[]"


class DisputeResponseRequest(BaseModel):
    dispute_id: int
    admin_response: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/client-invoices")
def get_client_invoices(client_code: str):
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM client_invoices WHERE client_code=?
           ORDER BY
             CASE status
               WHEN 'CORRECTION_REQUESTED' THEN 0
               WHEN 'DISPUTED' THEN 1
               WHEN 'PENDING_APPROVAL' THEN 2
               WHEN 'APPROVED' THEN 3
               ELSE 4
             END,
             dispatched_at DESC""",
        (client_code,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/approve-invoice")
def approve_invoice(req: ApproveInvoiceRequest):
    conn = get_conn()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE client_invoices SET status='APPROVED', approved_at=? WHERE invoice_id=?",
        (now, req.invoice_id),
    )
    conn.commit()
    conn.close()
    return {"status": "success", "invoice_id": req.invoice_id, "approved_at": now}


@app.post("/dispute-invoice")
def dispute_invoice(req: DisputeInvoiceRequest):
    conn = get_conn()
    now = datetime.now().isoformat(timespec="seconds")
    # Update client_invoices
    conn.execute(
        "UPDATE client_invoices SET status='DISPUTED', dispute_type='DISPUTED', client_response=? WHERE invoice_id=?",
        (req.reason, req.invoice_id),
    )
    # Get client name from invoice
    row = conn.execute("SELECT client_name FROM client_invoices WHERE invoice_id=?", (req.invoice_id,)).fetchone()
    client_name = row["client_name"] if row else ""
    # Insert into disputes table
    conn.execute(
        """INSERT INTO disputes(client_code,client_name,invoice_id,dispute_type,client_message,raised_at,status)
           VALUES(?,?,?,?,?,?,?)""",
        (req.client_code, client_name, req.invoice_id, "DISPUTED", req.reason, now, "OPEN"),
    )
    conn.commit()
    conn.close()
    return {"status": "success", "invoice_id": req.invoice_id}


@app.post("/request-correction")
def request_correction(req: CorrectionRequest):
    conn = get_conn()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE client_invoices SET status='CORRECTION_REQUESTED', dispute_type='CORRECTION_REQUESTED', client_response=? WHERE invoice_id=?",
        (req.details, req.invoice_id),
    )
    row = conn.execute("SELECT client_name FROM client_invoices WHERE invoice_id=?", (req.invoice_id,)).fetchone()
    client_name = row["client_name"] if row else ""
    conn.execute(
        """INSERT INTO disputes(client_code,client_name,invoice_id,dispute_type,client_message,raised_at,status)
           VALUES(?,?,?,?,?,?,?)""",
        (req.client_code, client_name, req.invoice_id, "CORRECTION_REQUESTED", req.details, now, "OPEN"),
    )
    conn.commit()
    conn.close()
    return {"status": "success", "invoice_id": req.invoice_id}


@app.post("/push-invoice")
def push_invoice(req: PushInvoiceRequest):
    conn = get_conn()
    inv_id = _rand_id("INV")
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """INSERT INTO client_invoices(invoice_id,client_code,client_name,billing_period,
           pdf_path,erp_excel_path,dispatch_notes,dispatched_at,status,total_amount,line_items)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (inv_id, req.client_code, req.client_name, req.billing_period,
         req.pdf_path, req.erp_excel_path, req.dispatch_notes, now,
         "PENDING_APPROVAL", req.total_amount, req.line_items),
    )
    conn.commit()
    conn.close()
    return {"status": "success", "invoice_id": inv_id, "dispatched_at": now}


@app.get("/disputes")
def get_disputes(status: str = None):
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM disputes WHERE status=? ORDER BY raised_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM disputes ORDER BY raised_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/resolve-dispute")
def resolve_dispute(req: DisputeResponseRequest):
    conn = get_conn()
    now = datetime.now().isoformat(timespec="seconds")
    # Get the dispute to find the invoice_id
    dispute = conn.execute("SELECT * FROM disputes WHERE dispute_id=?", (req.dispute_id,)).fetchone()
    conn.execute(
        "UPDATE disputes SET admin_response=?, resolved_at=?, status='RESOLVED' WHERE dispute_id=?",
        (req.admin_response, now, req.dispute_id),
    )
    # Reset the matching client_invoices row back to PENDING_APPROVAL so client can re-act
    if dispute and dispute["invoice_id"]:
        conn.execute(
            "UPDATE client_invoices SET status='PENDING_APPROVAL', dispute_type=NULL, client_response=NULL WHERE invoice_id=?",
            (dispute["invoice_id"],),
        )
    conn.commit()
    conn.close()
    return {"status": "success", "dispute_id": req.dispute_id, "resolved_at": now}


@app.get("/invoice-history")
def get_invoice_history(client_code: str = None):
    conn = get_conn()
    if client_code:
        rows = conn.execute(
            "SELECT * FROM invoice_history WHERE client_code=? ORDER BY raised_at DESC",
            (client_code,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM invoice_history ORDER BY raised_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/invoice-pdf/{invoice_id}")
def get_invoice_pdf(invoice_id: str):
    """Serve the generated PDF file for a given invoice."""
    conn = get_conn()
    row = conn.execute("SELECT pdf_path FROM client_invoices WHERE invoice_id=?", (invoice_id,)).fetchone()
    conn.close()
    if not row or not row["pdf_path"]:
        raise HTTPException(status_code=404, detail="Invoice PDF not found")
    pdf_path = row["pdf_path"]
    # Handle relative paths
    if not os.path.isabs(pdf_path):
        pdf_path = os.path.join(str(BASE_DIR), pdf_path)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail=f"PDF file not found on disk: {pdf_path}")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{invoice_id}.pdf")


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=False)
