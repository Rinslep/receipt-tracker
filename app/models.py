from sqlalchemy import Column, String, Float, DateTime, Text, Index
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid


class Base(DeclarativeBase):
    pass


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)  # Entra ID OID
    vendor = Column(String, nullable=False)
    date = Column(String, nullable=False)   # ISO date string "YYYY-MM-DD"
    total = Column(Float, nullable=False)
    category = Column(String, nullable=False, default="other")
    notes = Column(Text, default="")
    image_url = Column(String, default="")  # Azure Blob URL if storing images
    raw_ocr = Column(Text, default="")      # Full OCR JSON for audit
    created_at = Column(DateTime, default=datetime.utcnow)
