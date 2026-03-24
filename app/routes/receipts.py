from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Receipt
from app.database import get_db
from app.services.ocr import analyse_receipt, _guess_category
from app.auth import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


class ReceiptCreate(BaseModel):
    vendor: str
    date: str
    total: float
    category: str = "other"
    notes: str = ""


def _to_response(r: Receipt) -> dict:
    return {
        "id": r.id,
        "vendor": r.vendor,
        "date": r.date,
        "total": r.total,
        "category": r.category,
        "notes": r.notes or "",
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


@router.post("/scan")
async def scan_receipt(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a receipt image and extract data via Azure Document Intelligence."""
    contents = await file.read()
    if len(contents) > 10_000_000:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    result = await analyse_receipt(contents)
    return {
        "vendor": result["vendor"],
        "date": result["date"],
        "total": result["total"],
        "suggested_category": result.get("suggested_category", _guess_category(result["vendor"])),
    }


@router.post("")
async def create_receipt(
    data: ReceiptCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a confirmed receipt to the database."""
    receipt = Receipt(
        user_id=user["oid"],
        vendor=data.vendor,
        date=data.date,
        total=data.total,
        category=data.category,
        notes=data.notes,
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    return _to_response(receipt)


@router.get("")
async def list_receipts(
    category: Optional[str] = None,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's receipts, optionally filtered by category."""
    q = select(Receipt).where(Receipt.user_id == user["oid"])
    if category and category != "all":
        q = q.where(Receipt.category == category)
    q = q.order_by(Receipt.date.desc())
    result = await db.execute(q)
    return [_to_response(r) for r in result.scalars()]


@router.delete("/{receipt_id}")
async def delete_receipt(
    receipt_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a receipt — only allowed if owned by the current user."""
    result = await db.execute(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.user_id == user["oid"])
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    await db.delete(receipt)
    await db.commit()
    return {"deleted": receipt_id}
