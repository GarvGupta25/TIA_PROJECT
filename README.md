# TIA - Touchless Invoice Agent

This folder implements the phase-wise plan from `phase new.md`.

## Project Layout

- `database.py` loads `TASC_Sample_Database_vF.xlsx` into SQLite and creates app tables.
- `validator.py`, `payroll.py`, `confidence.py`, and `anomaly_detector.py` handle business rules.
- `extractor_excel.py`, `extractor_email.py`, and `extractor_image.py` parse incoming timesheets.
- `invoice_generator.py` creates PDF invoices and ERP Excel exports in `outputs/`.
- `app.py` runs the Gradio frontend.

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

Copy Qwen local weights here for image extraction:

```text
models/qwen2_5_vl_7b/
```

That folder must include `config.json`, tokenizer files, processor config, and all safetensors shards. Image extraction uses `local_files_only=True`.

If the Excel file is missing, `database.py` loads a small built-in demo dataset so the app can still open for UI testing.
