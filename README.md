# TIA - Touchless Invoice Agent

TIA is a dual-portal invoice validation and payroll billing prototype for TASC operations and client users. It ingests client-submitted timesheets from multiple formats, validates each payroll row against the employee master database, calculates billable invoice amounts, separates clean rows from exceptions, generates finance outputs, and shares invoice packages with a React client portal for approval, disputes, and corrections.

The project is intentionally local-first: the Gradio operations portal, FastAPI bridge, SQLite database, generated PDFs/Excel files, and React client portal all run from this workspace.

## What The System Does

- Accepts timesheet inputs from Excel, CSV, TSV, email/text, PDF, and image files.
- Routes each file type to a dedicated extractor.
- Matches submitted employees by employee ID or name against the TASC employee database.
- Validates client ownership, active employee status, working days, overtime, IBAN, reimbursement data, and invoice amount variance.
- Calculates payroll billing using daily CTC, overtime, reimbursements, client markup, and 5% VAT.
- Assigns confidence scores and statuses: `AUTO_APPROVED`, `REVIEW_REQUIRED`, or `REJECTED`.
- Stores flagged records in SQLite for audit and exception handling.
- Lets TASC operations reject records or mark them for client review from the Exception Queue.
- Generates invoice PDFs and ERP Excel exports for approved records.
- Pushes invoice packages to the client portal through the FastAPI bridge.
- Lets clients approve invoices, dispute invoices, request corrections, view notifications, and upload files.
- Provides analytics and a query assistant over employees, invoices, exceptions, and billing history.

## Architecture

```text
Client Uploads / Timesheets
        |
        v
router.py
        |
        +-- extractor_excel.py       Excel, CSV, TSV
        +-- extractor_email.py       EML, TXT, text-style PDFs
        +-- extractor_image.py       Images and rendered PDF pages via remote extractor
        |
        v
validator.py  ---> database.py / tasc.db
        |
        v
payroll.py + confidence.py
        |
        v
app.py Gradio Operations Portal
        |
        +-- outputs/ PDFs, ERP Excel, review CSVs
        +-- flagged_reviews / invoice tables in SQLite
        |
        v
api.py FastAPI Bridge on :8001
        |
        v
client-codebases/frontend React Client Portal on :3000
```

## Main Applications

| Surface | File / Folder | Default Port | Purpose |
|---|---|---:|---|
| TASC Operations Portal | `app.py` | `7860` | Main Gradio UI for processing, exceptions, invoices, disputes, analytics, and config. |
| FastAPI Bridge | `api.py` | `8001` | REST API used by the React client portal to access invoices, disputes, PDFs, and history. |
| React Client Portal | `client-codebases/frontend` | `3000` | Client-facing portal for uploads, notifications, invoice approval, disputes, and chat. |
| SQLite Database | `tasc.db` | local file | Shared local database for employee master data, invoices, exceptions, disputes, and history. |

## Repository Layout

```text
.
|-- app.py                         # Gradio TASC operations portal
|-- api.py                         # FastAPI bridge for client portal
|-- database.py                    # SQLite setup, employee/client loading, audit helpers
|-- router.py                      # File-type routing
|-- extractor_excel.py             # Excel/CSV/TSV extraction
|-- extractor_email.py             # Email/text/PDF-text extraction
|-- extractor_image.py             # Image/PDF-page extraction via remote model endpoint
|-- validator.py                   # Employee lookup and anomaly validation
|-- confidence.py                  # Confidence scoring and review reason generation
|-- payroll.py                     # Payroll and invoice calculation rules
|-- invoice_generator.py           # Invoice PDF, ERP Excel, and invoice persistence
|-- anomaly_detector.py            # Batch status and anomaly summaries
|-- stt_proxy.py                   # Speech-to-text websocket helper for voice inputs
|-- TASC_Sample_Database_vF.xlsx   # Employee/client master workbook
|-- tasc.db                        # Local SQLite database
|-- outputs/                       # Generated CSV, PDF, and Excel artifacts
`-- client-codebases/
    |-- frontend/                  # React + Vite client portal
    `-- backend/                   # Client portal backend/database assets
```

## Processing Flow

1. TASC operator chooses a client and uploads one or more files in the Gradio portal.
2. `router.py` detects the file type from the extension.
3. The selected extractor returns normalized payroll records with common fields such as employee ID, name, working days, overtime, submitted total, IBAN, reimbursements, and raw snapshot.
4. `validator.py` resolves the employee against `employees` in SQLite.
5. `payroll.py` calculates billable amounts when an employee is resolved.
6. `confidence.py` scores the row and produces a user-readable review reason.
7. `app.py` stores flagged rows in `flagged_reviews`, shows summary metrics, and exports clean rows as auto-approved CSVs.
8. Exception rows stay in the Exception Queue until TASC marks them for client review or rejects them.
9. Approved records can be used to generate PDF invoices and ERP Excel outputs.
10. Invoice packages can be pushed to the client portal through `api.py`.

## Supported Input Formats

| Format | Extensions | Extractor | Notes |
|---|---|---|---|
| Spreadsheet | `.xlsx`, `.xls`, `.csv`, `.tsv` | `extractor_excel.py` | Uses flexible column aliases for employee, attendance, amount, IBAN, and reimbursement fields. |
| Email / Text | `.eml`, `.msg`, `.txt` | `extractor_email.py` | Parses text blocks with labels such as Employee ID, Name, Working Days, OT Hours, and Total. |
| PDF | `.pdf` | `extractor_image.py` | Renders pages to images and sends them to the remote extraction model. |
| Image | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp` | `extractor_image.py` | Sends file to the remote extraction model and normalizes JSON-like responses. |

## Expected Payroll Fields

The extractors normalize many aliases into these internal fields:

| Field | Meaning |
|---|---|
| `emp_id` | Employee identifier, preferably matching the master workbook. |
| `full_name` | Employee name, used for fallback matching when ID is missing. |
| `working_days` | Billable working days for the invoice period. |
| `ot_hours` | Overtime hours. |
| `submitted_total` | Client-submitted total used for variance checks. |
| `iban` | Bank IBAN, compared with the employee master record when present. |
| `reimbursements` | Optional list of reimbursement amounts and reasons. |
| `client_code` | Optional row-level client code; mismatched rows are skipped or flagged. |

## Validation And Status Rules

### Employee Matching

- Direct employee ID lookup is attempted first.
- Name lookup is used when ID is missing.
- Multiple name matches create an `AMBIGUOUS_EMPLOYEE` exception.
- Employees outside the selected client trigger `CLIENT_MISMATCH`.
- Missing employee matches trigger `EMPLOYEE_NOT_FOUND`.

### Anomaly Flags

High-risk flags include:

- `EMPLOYEE_NOT_FOUND`
- `CLIENT_MISMATCH`
- `AMBIGUOUS_EMPLOYEE`
- `ID_NAME_MISMATCH`
- `INVOICE_AMOUNT_DEVIATION`

Medium-risk flags include:

- `EXCESS_DAYS`
- `DAILY_HOURS_EXCEEDED`
- `IBAN_MISMATCH`
- `REIMBURSEMENT_HIGH`
- `MISSING_REQUIRED_FIELD`

Other validation flags include missing reimbursement reasons and inactive employees.

### Confidence Scoring

Rows start at 100 confidence points.

- High-risk flags reduce confidence by 18 points each.
- Medium-risk flags reduce confidence by 10 points each.
- Other flags reduce confidence by 5 points each.
- Name-only unique resolution reduces confidence by 8 points.
- Image-sourced records reduce confidence by 5 points.

### Status Assignment

| Status | When It Happens |
|---|---|
| `AUTO_APPROVED` | Score is at least 85 and no anomaly flags exist. |
| `REVIEW_REQUIRED` | Record is usable but needs manual/client review. |
| `REJECTED` | Employee cannot be found or belongs to another selected client. |
| `SENT_FOR_REVIEW` | TASC sends an exception row to the client review flow. |

## Payroll Calculation

Payroll billing is calculated in `payroll.py`.

| Component | Rule |
|---|---|
| Monthly CTC | Uses `total_ctc`; falls back to basic + housing + transport + food + phone. |
| Daily rate | Monthly CTC / 26. |
| Working days amount | Daily rate x working days. |
| Overtime hourly rate | Basic / 26 / 8. |
| Overtime amount | Hourly rate x 1.25 x OT hours. |
| Reimbursements | Sum of reimbursement amounts. |
| Markup | Client-configured markup percentage, default 10%. |
| VAT | 5% of invoice amount. |
| Final total | Invoice amount + VAT. |

## Gradio Operations Portal

Run with:

```powershell
.\tia_env\Scripts\activate
python app.py
```

Open:

```text
http://localhost:7860
```

### Tabs

| Tab | Purpose |
|---|---|
| Submit Timesheets | Upload files, process batches, see validation summary, and download auto-approved CSVs. |
| Client Messages | Pull uploads from the client portal database and process them into TASC records. |
| Exception Queue | Review flagged rows, reject payroll rows, or mark rows for client review. |
| Disputes | View open/resolved client disputes and send admin responses. |
| Invoice Output | Generate PDF invoices and ERP Excel outputs; push invoices to the client portal. |
| Analytics | View status distribution, confidence trends, anomaly counts, billing totals, historical exception rates, flagged employees, and touchless rate. |
| Query Assistant | Ask natural-language questions over employees, invoice history, billing, confidence, and exceptions. |
| Column Config | Configure output columns and client markup percentage. |

## Exception Queue Behavior

The Exception Queue shows rows that are not invoice-approved and are not already rejected or sent for review.

TASC operators can:

- Select `Reject` to reject a payroll row.
- Select `Mark for Review` to send a row to the client review path.
- Export selected flagged rows to `outputs/FLAGGED_REVIEWS_<client>_<timestamp>.csv`.
- Send selected rows back to the client portal when the batch came from a client upload.

The selection columns are mutually exclusive per row: selecting Reject clears Mark for Review, and selecting Mark for Review clears Reject.

## Invoice Outputs

Generated artifacts are written to `outputs/`.

| Artifact | Example | Purpose |
|---|---|---|
| Auto-approved CSV | `AUTO_APPROVED_CL004_YYYYMMDD_HHMMSS.csv` | Clean records ready for downstream processing. |
| Flagged review CSV | `FLAGGED_REVIEWS_CL004_YYYYMMDD_HHMMSS.csv` | Exception rows rejected or sent for client review. |
| Invoice PDF | `INV-YYYYMMDD-XXXXXX.pdf` | Client-facing invoice. |
| ERP Excel | `ERP_CL004_YYYYMMDD_HHMMSS.xlsx` | Finance/ERP upload workbook. |

## FastAPI Bridge

Run with:

```powershell
.\tia_env\Scripts\activate
python api.py
```

Open health check:

```text
http://localhost:8001/health
```

### Key Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API health check. |
| GET | `/client-invoices?client_code=CL004` | List invoices for a client. |
| POST | `/push-invoice` | Insert an invoice package for the client portal. |
| POST | `/approve-invoice` | Mark a client invoice approved. |
| POST | `/dispute-invoice` | Mark an invoice disputed and create a dispute record. |
| POST | `/request-correction` | Request correction and create a dispute/correction record. |
| GET | `/disputes` | List all disputes. |
| GET | `/disputes?status=OPEN` | List open disputes. |
| POST | `/resolve-dispute` | Resolve a dispute and return the invoice to pending approval. |
| GET | `/invoice-history` | List historical invoice records. |
| GET | `/invoice-pdf/{invoice_id}` | Serve an invoice PDF file. |

## React Client Portal

The client portal is in `client-codebases/frontend` and uses React, Vite, React Router, Axios, and Lucide icons.

Run with:

```powershell
cd client-codebases\frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

### Client Routes

| Route | Page | Purpose |
|---|---|---|
| `/login` | Login | Client sign-in entry. |
| `/dashboard/upload` | Upload Center | Submit payroll/timesheet files to TASC. |
| `/dashboard/notifications` | Notification Center | View client portal alerts. |
| `/dashboard/invoices` | Invoices | Review, approve, dispute, or request correction for invoices. |
| `/dashboard/chat` | Chat | Client communication surface. |

## Database

`database.py` initializes core TASC tables. `api.py` also creates client-portal-facing tables at startup.

### Core Tables

| Table | Purpose |
|---|---|
| `employees` | Employee master data loaded from `TASC_Sample_Database_vF.xlsx` or built-in sample data. |
| `clients` | Distinct clients, default location, markup percentage, and output column configuration. |
| `invoices` | Generated invoice headers. |
| `invoice_lines` | Employee-level invoice line details and validation metadata. |
| `audit_log` | Operational audit entries. |
| `exception_queue` | Legacy/pending exception queue support. |
| `flagged_reviews` | Persisted exception/review rows from processed batches. |

### Client Portal Tables

| Table | Purpose |
|---|---|
| `client_invoices` | Invoice packages pushed from TASC to the client portal. |
| `disputes` | Client disputes/correction requests and TASC responses. |
| `invoice_history` | Historical invoice data for analytics and query assistant. |
| `roster_confirmations` | Roster sign-off tracking. |
| `resubmissions` | Correction/resubmission tracking. |

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `IMAGE_EXTRACT_URL` | `https://uncorrupt-lunar-imbecile.ngrok-free.dev/extract` | Remote model endpoint for image/PDF-page extraction. |
| `IMAGE_EXTRACT_TIMEOUT_SECONDS` | `120` | Timeout for remote image extraction requests. |

## Setup From A Fresh Clone

1. Create and activate the virtual environment.

```powershell
python -m venv tia_env
.\tia_env\Scripts\activate
```

2. Install Python dependencies.

```powershell
pip install -r requirements.txt
```

3. Initialize the database.

```powershell
python database.py
```

4. Start the TASC operations portal.

```powershell
python app.py
```

5. In a second terminal, start the API bridge.

```powershell
.\tia_env\Scripts\activate
python api.py
```

6. In a third terminal, start the React client portal.

```powershell
cd client-codebases\frontend
npm install
npm run dev
```

## Full System Startup Checklist

| Process | Command | Expected URL |
|---|---|---|
| TASC Gradio portal | `python app.py` | `http://localhost:7860` |
| FastAPI bridge | `python api.py` | `http://localhost:8001/health` |
| React client portal | `npm run dev` from `client-codebases/frontend` | `http://localhost:3000` |

The React client portal expects the FastAPI bridge to be available on port `8001`.

## Typical Demo Script

1. Start the Gradio portal.
2. Select a client in Submit Timesheets.
3. Upload a payroll spreadsheet or supported sample file.
4. Process the batch.
5. Review the summary cards and records table.
6. Open Exception Queue.
7. Reject high-risk rows or mark rows for client review.
8. Generate invoice PDF and ERP Excel for approved records.
9. Push invoice to the client portal.
10. Open the client portal and approve, dispute, or request correction.
11. Return to the TASC Disputes tab to respond to client disputes.
12. Refresh Analytics and Query Assistant to review operational impact.

## Troubleshooting

### Gradio does not start

- Confirm dependencies are installed with `pip install -r requirements.txt`.
- Confirm `gradio` and `pandas` exist in the active environment.
- Confirm port `7860` is not already in use.
- Run `python database.py` once before `python app.py` if `tasc.db` is missing or empty.

### React portal cannot load invoices

- Start `api.py` before loading the React portal.
- Check `http://localhost:8001/health`.
- Confirm invoice records exist in `client_invoices`.

### Image or PDF extraction fails

- Confirm `IMAGE_EXTRACT_URL` is reachable.
- Confirm the remote service returns JSON, or a text response containing JSON.
- For PDFs, confirm `pypdfium2` is installed.
- Increase `IMAGE_EXTRACT_TIMEOUT_SECONDS` for large files.

### No records appear in Exception Queue

- Exception Queue only shows current in-memory batch records.
- Process a batch first in Submit Timesheets or Client Messages.
- Auto-approved rows do not appear in the queue.
- Rows already `REJECTED` or `SENT_FOR_REVIEW` are filtered out after submission.

### Generated files are missing

- Check the `outputs/` folder.
- Confirm the active process has write access to the workspace.
- Confirm there are approved records before generating invoice outputs.

## Current Limitations

- The current batch is held in process memory through `BATCH`; restarting `app.py` clears the active UI batch.
- SQLite is used as a local prototype database and is not configured for high-concurrency production workloads.
- Image/PDF extraction depends on an external remote endpoint.
- Authentication and authorization are prototype-level and should be hardened before production use.
- Several analytics depend on populated historical invoice data.
- Generated artifacts are stored on local disk under `outputs/`.

## Development Notes

- Keep extractor outputs normalized to the internal payroll record shape.
- Add new anomaly flags in `validator.py` and update scoring/reasons in `confidence.py`.
- Keep invoice math changes centralized in `payroll.py`.
- Use `database.py` for core schema setup and `api.py` for client-portal-facing schema setup.
- Avoid changing generated files under `outputs/` unless the task is explicitly about artifacts.

## Quick Commands

```powershell
# Initialize / refresh database
.\tia_env\Scripts\activate
python database.py

# Start TASC operations portal
python app.py

# Start API bridge
python api.py

# Start client portal
cd client-codebases\frontend
npm install
npm run dev
```
