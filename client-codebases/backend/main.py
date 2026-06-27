from fastapi import FastAPI, Depends, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import shutil
from pathlib import Path

import models
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Client Portal API")

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev only, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mock Data Initialization ---
def ensure_schema(db: Session):
    bind = db.get_bind()
    with bind.begin() as conn:
        existing_user_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()]
        if "company_name" not in existing_user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN company_name VARCHAR")
        existing_upload_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(uploaded_files)").fetchall()]
        if "sent_to_tasc" not in existing_upload_cols:
            conn.exec_driver_sql("ALTER TABLE uploaded_files ADD COLUMN sent_to_tasc BOOLEAN DEFAULT 1")
        if "processed_by_tasc" not in existing_upload_cols:
            conn.exec_driver_sql("ALTER TABLE uploaded_files ADD COLUMN processed_by_tasc BOOLEAN DEFAULT 0")


def init_mock_data(db: Session):
    ensure_schema(db)
    if not db.query(models.User).first():
        demo_user = models.User(email="demo@client.com", name="Demo Client", company_name="Demo Client LLC")
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        
        # Add mock notifications
        n1 = models.Notification(user_id=demo_user.id, title="Invoice Approved", message="Your invoice INV-1002 has been approved by the main company.")
        n2 = models.Notification(user_id=demo_user.id, title="New Policy Update", message="Please review the new employee reimbursement policy.")
        db.add_all([n1, n2])
        
        # Add mock chat messages
        c1 = models.ChatMessage(user_id=demo_user.id, sender="company", message="Hello! Welcome to the new client portal. Let us know if you need help.")
        db.add(c1)
        
        db.commit()
    else:
        user = db.query(models.User).filter(models.User.email == "demo@client.com").first()
        if user and not user.company_name:
            user.company_name = "Demo Client LLC"
            db.commit()

@app.on_event("startup")
def on_startup():
    db = next(get_db())
    init_mock_data(db)

# --- Routes ---

@app.post("/api/auth/login")
def login(email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"status": "error", "message": "User not found"}
    return {"status": "success", "user_id": user.id, "name": user.name, "company_name": user.company_name}

@app.get("/api/notifications/{user_id}")
def get_notifications(user_id: int, db: Session = Depends(get_db)):
    notifications = db.query(models.Notification).filter(models.Notification.user_id == user_id).order_by(models.Notification.timestamp.desc()).all()
    return notifications

@app.get("/api/chat/{user_id}")
def get_chat_messages(user_id: int, db: Session = Depends(get_db)):
    messages = db.query(models.ChatMessage).filter(models.ChatMessage.user_id == user_id).order_by(models.ChatMessage.timestamp.asc()).all()
    return messages

@app.post("/api/chat/{user_id}")
def send_chat_message(user_id: int, message: str = Form(...), db: Session = Depends(get_db)):
    new_message = models.ChatMessage(user_id=user_id, sender="client", message=message)
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return {"status": "success", "message": new_message}

@app.post("/api/upload/{user_id}")
async def upload_files(user_id: int, file_type: str = Form(...), files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    upload_dir = Path("uploads") / str(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for file in files:
        safe_name = os.path.basename(file.filename)
        file_location = upload_dir / safe_name
        counter = 1
        while file_location.exists():
            file_location = upload_dir / f"{file_location.stem}_{counter}{file_location.suffix}"
            counter += 1
        with open(file_location, "wb") as file_object:
            shutil.copyfileobj(file.file, file_object)
        uploaded_file = models.UploadedFile(
            user_id=user_id,
            filename=file_location.name,
            file_type=file_type,
            filepath=str(file_location),
            sent_to_tasc=True,
        )
        db.add(uploaded_file)
        saved.append(uploaded_file)

    db.commit()
    return {"status": "success", "count": len(saved), "files": [{"filename": f.filename, "file_type": f.file_type} for f in saved]}

@app.get("/api/uploads/{user_id}")
def get_uploads(user_id: int, db: Session = Depends(get_db)):
    return db.query(models.UploadedFile).filter(models.UploadedFile.user_id == user_id).order_by(models.UploadedFile.uploaded_at.desc()).all()

@app.get("/api/returned/{user_id}")
def get_returned_files(user_id: int, db: Session = Depends(get_db)):
    return db.query(models.ReturnedFile).filter(models.ReturnedFile.user_id == user_id).order_by(models.ReturnedFile.created_at.desc()).all()

@app.get("/api/returned/download/{file_id}")
def download_returned_file(file_id: int, db: Session = Depends(get_db)):
    returned = db.query(models.ReturnedFile).filter(models.ReturnedFile.id == file_id).first()
    if not returned or not os.path.exists(returned.filepath):
        return {"status": "error", "message": "File not found"}
    return FileResponse(returned.filepath, filename=returned.filename)
