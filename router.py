import os


EXCEL_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
EMAIL_EXTENSIONS = {".eml", ".msg", ".txt"}


def detect_input_type(file_path: str) -> str:
    ext = os.path.splitext(file_path or "")[1].lower()
    if ext in EXCEL_EXTENSIONS:
        return "excel"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in EMAIL_EXTENSIONS:
        return "email"
    if ext == ".pdf":
        return "pdf"
    return "unknown"


def process_file(file_path: str, client_code: str):
    input_type = detect_input_type(file_path)
    if input_type == "excel":
        from extractor_excel import extract_from_excel

        return extract_from_excel(file_path, client_code)
    if input_type == "email":
        from extractor_email import extract_from_email

        return extract_from_email(file_path, client_code)
    if input_type == "image":
        from extractor_image import extract_from_image

        return extract_from_image(file_path, client_code)
    if input_type == "pdf":
        from extractor_email import extract_from_pdf

        return extract_from_pdf(file_path, client_code)
    raise ValueError(f"Unsupported input type for {file_path}")
