import json
import os
import sqlite3
from datetime import datetime

import pandas as pd


BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "tasc.db")
EXCEL_PATH = os.path.join(BASE_DIR, "TASC_Sample_Database_vF.xlsx")

COL_MAP = {
    "Employee ID": "emp_id",
    "Full Name": "full_name",
    "Email": "email",
    "Client Code": "client_code",
    "Client Name": "client_name",
    "Job Title": "job_title",
    "Department": "department",
    "Nationality": "nationality",
    "Date of Joining": "date_of_joining",
    "Status": "status",
    "IBAN": "iban",
    "Basic Salary": "basic",
    "Housing Allowance": "housing",
    "Transport Allowance": "transport",
    "Food Allowance": "food",
    "Phone Allowance": "phone",
    "Total CTC": "total_ctc",
}


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def _sample_employees():
    rows = [
        ["EMP10001", "Aisha Al Zaabi", "aisha@example.com", "CL001", "Aldar Properties", "Admin Executive", "Operations", "UAE", "2022-01-10", "Active", "AE070331234567890123456", 9000, 2500, 800, 400, 200, 12900],
        ["EMP10002", "Ravi Menon", "ravi@example.com", "CL002", "Dubai Airports", "Site Supervisor", "Facilities", "India", "2021-05-15", "Active", "AE070331234567890123457", 7000, 2000, 700, 300, 200, 10200],
        ["EMP10003", "Fatima Khan", "fatima1@example.com", "CL005", "Emaar Hospitality", "Guest Relations", "Hospitality", "Pakistan", "2023-03-20", "Active", "AE070331234567890123458", 6500, 1800, 600, 300, 150, 9350],
        ["EMP10004", "Fatima Khan", "fatima2@example.com", "CL005", "Emaar Hospitality", "Coordinator", "Hospitality", "India", "2022-11-02", "Active", "AE070331234567890123459", 6200, 1600, 550, 300, 150, 8800],
        ["EMP10058", "Omar Hassan", "omar@example.com", "CL003", "DP World", "Forklift Operator", "Logistics", "Egypt", "2020-07-01", "Active", "AE070331234567890123460", 5200, 1300, 500, 250, 100, 7350],
    ]
    return pd.DataFrame(rows, columns=list(COL_MAP.values()))


def _create_base_tables(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id TEXT PRIMARY KEY, client_code TEXT, period TEXT,
            created_at TEXT, status TEXT, total_aed REAL,
            record_count INTEGER, approved_by TEXT, approved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS invoice_lines (
            line_id TEXT PRIMARY KEY, invoice_id TEXT, emp_id TEXT,
            full_name TEXT, working_days REAL, ot_hours REAL DEFAULT 0,
            ot_amount REAL DEFAULT 0, reimbursements_json TEXT DEFAULT '[]',
            gross_billable REAL, markup_pct REAL, invoice_amount REAL,
            vat_amount REAL, final_total REAL, confidence_score INTEGER,
            anomaly_flags TEXT DEFAULT '[]', status TEXT, raw_input_snapshot TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
            action TEXT, invoice_id TEXT, line_id TEXT,
            operator TEXT DEFAULT 'TASC_OPS', notes TEXT
        );
        CREATE TABLE IF NOT EXISTS exception_queue (
            queue_id TEXT PRIMARY KEY, line_id TEXT, invoice_id TEXT,
            status TEXT DEFAULT 'PENDING', confidence_score INTEGER,
            anomaly_flags TEXT, created_at TEXT, resolved_at TEXT, resolution TEXT
        );
        """
    )


def initialize_database(use_sample_if_missing=True):
    conn = get_connection()
    if os.path.exists(EXCEL_PATH):
        df = pd.read_excel(EXCEL_PATH)
        df.rename(columns=COL_MAP, inplace=True)
        df = df[[c for c in COL_MAP.values() if c in df.columns]]
    elif use_sample_if_missing:
        df = _sample_employees()
        print("TASC_Sample_Database_vF.xlsx not found; loaded built-in demo data.")
    else:
        raise FileNotFoundError(f"Missing {EXCEL_PATH}")

    for col in ["basic", "housing", "transport", "food", "phone", "total_ctc"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df.to_sql("employees", conn, if_exists="replace", index=False)

    clients_df = df[["client_code", "client_name"]].drop_duplicates().copy()
    location_map = {
        "CL001": "Abu Dhabi", "CL002": "Dubai", "CL003": "Dubai", "CL004": "Abu Dhabi",
        "CL005": "Dubai", "CL006": "Abu Dhabi", "CL007": "Dubai", "CL008": "Abu Dhabi",
        "CL009": "Abu Dhabi", "CL010": "Dubai",
    }
    clients_df["location"] = clients_df["client_code"].map(location_map).fillna("Dubai")
    clients_df["markup_pct"] = 10.0
    clients_df["output_columns"] = "[]"
    clients_df.to_sql("clients", conn, if_exists="replace", index=False)
    _create_base_tables(conn)
    conn.commit()
    conn.close()
    print("Database initialized. Tables: employees, clients, invoices, invoice_lines, audit_log, exception_queue")


def ensure_database():
    if not os.path.exists(DB_PATH):
        initialize_database()


def get_all_clients():
    ensure_database()
    conn = get_connection()
    rows = conn.execute("SELECT client_code, client_name FROM clients ORDER BY client_name").fetchall()
    conn.close()
    return [{"code": r[0], "name": r[1]} for r in rows]


def get_client_config(client_code: str) -> dict:
    ensure_database()
    conn = get_connection()
    cur = conn.execute("SELECT * FROM clients WHERE client_code=?", (client_code,))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.close()
    if not row:
        return {}
    cfg = dict(zip(cols, row))
    cfg["output_columns"] = json.loads(cfg.get("output_columns") or "[]")
    return cfg


def save_client_columns(client_code: str, columns: list):
    ensure_database()
    conn = get_connection()
    conn.execute("UPDATE clients SET output_columns=? WHERE client_code=?", (json.dumps(columns), client_code))
    conn.commit()
    conn.close()


def save_client_markup(client_code: str, markup: float):
    ensure_database()
    conn = get_connection()
    conn.execute("UPDATE clients SET markup_pct=? WHERE client_code=?", (markup, client_code))
    conn.commit()
    conn.close()


def log_audit(action: str, invoice_id: str = None, line_id: str = None, notes: str = None):
    ensure_database()
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log(timestamp,action,invoice_id,line_id,notes) VALUES(?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), action, invoice_id, line_id, notes),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_database()
