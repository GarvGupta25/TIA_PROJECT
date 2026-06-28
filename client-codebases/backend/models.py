from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    company_name = Column(String)
    client_code = Column(String, default="CL004")
    is_active = Column(Boolean, default=True)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    is_read = Column(Boolean, default=False)
    
    user = relationship("User")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    sender = Column(String) # 'client' or 'company'
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User")

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    file_type = Column(String) # 'invoice', 'excel', 'photo', 'pdf'
    filepath = Column(String)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    sent_to_tasc = Column(Boolean, default=True)
    processed_by_tasc = Column(Boolean, default=False)
    
    user = relationship("User")

class ReturnedFile(Base):
    __tablename__ = "returned_files"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    filepath = Column(String)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")
