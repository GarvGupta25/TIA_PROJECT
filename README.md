# TIA - Touchless Invoice Agent

This folder implements the phase-wise plan from `phase new.md`.

## Project Layout

- `database.py` loads `TASC_Sample_Database_vF.xlsx` into SQLite and creates app tables.
- `validator.py`, `payroll.py`, `confidence.py`, and `anomaly_detector.py` handle business rules.
- `extractor_excel.py`, `extractor_email.py`, and `extractor_image.py` parse incoming timesheets.
- `invoice_generator.py` creates PDF invoices and ERP Excel exports in `outputs/`.
- `app.py` runs the Gradio frontend on port **7860**.
- `api.py` runs the FastAPI bridge on port **8001**, exposing REST endpoints to the React client portal.
- `client-codebases/backend/` — existing SQLAlchemy client portal backend (port **8000**).
- `client-codebases/frontend/` — React (Vite) client portal (port **3000**).

## Setup

```powershell
python -m venv tia_env
.\tia_env\Scripts\activate
pip install -r requirements.txt
python database.py
python app.py
```

Open `http://localhost:7860`.

## Required Assets

Place the real employee workbook here:

```text
TASC_Sample_Database_vF.xlsx
```

Image extraction is routed to the remote FastAPI model endpoint:

```text
https://uncorrupt-lunar-imbecile.ngrok-free.dev/extract
```

Override it with `IMAGE_EXTRACT_URL` if the public URL changes. Uploaded PDFs are rendered to page images with `pypdfium2` before being sent to the same endpoint.

If the Excel file is missing, `database.py` loads a small built-in demo dataset so the app can still open for UI testing.

---

## Running the Full System

All three processes must be running simultaneously for the full system to work.

Open **three separate terminal windows** and run the following:

### Terminal 1 — FastAPI Bridge (port 8001)
```powershell
.\tia_env\Scripts\activate
python api.py
```
You should see: `✅  API running on port 8001`

### Terminal 2 — Gradio TIA Portal (port 7860)
```powershell
.\tia_env\Scripts\activate
python app.py
```
Open `http://localhost:7860` in your browser.

### Terminal 3 — React Client Portal (port 3000)
```powershell
cd client-codebases\frontend
npm install   # first time only
npm run dev
```
Open `http://localhost:3000` in your browser.

> **Note:** `api.py` must be running before the React portal loads, as it calls `http://localhost:8001` for invoice and dispute data.

### New SQLite Tables (created automatically on first run)

| Table               | Purpose                                              |
|---------------------|------------------------------------------------------|
| `client_invoices`   | Invoices pushed from TASC to client portal           |
| `disputes`          | Client-raised invoice disputes and admin responses   |
| `invoice_history`   | Historical multi-period invoice records for analytics|
| `roster_confirmations` | Roster sign-off tracking                          |
| `resubmissions`     | Re-upload tracking after corrections                 |

### New Tabs in the TIA Gradio Portal

| Tab              | What's new                                                              |
|------------------|-------------------------------------------------------------------------|
| **Disputes**     | Open & Resolved dispute queues; admin can respond and close disputes    |
| **Analytics**    | Second row: Exception Rate Trend, Most Flagged Employees, Touchless Rate, Client Health Scores |
| **Query Assistant** | Expanded to query `invoice_history`, billing totals, exception rates |
| **Invoice Output** | "Dispatch to Client Portal" section pushes invoice to React app       |
| **Client Messages** | Submission Timeline stepper shows extraction → dispatch pipeline    |
