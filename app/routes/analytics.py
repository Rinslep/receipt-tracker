from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Receipt
from app.database import get_db
from app.auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics")
async def get_analytics(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated expense data for the dashboard, scoped to the current user."""
    result = await db.execute(
        select(Receipt).where(Receipt.user_id == user["oid"])
    )
    receipts = list(result.scalars())

    by_category: dict = {}
    by_month: dict = {}
    for r in receipts:
        by_category[r.category] = round(by_category.get(r.category, 0) + r.total, 2)
        month_key = r.date[:7]  # "YYYY-MM"
        by_month[month_key] = round(by_month.get(month_key, 0) + r.total, 2)

    now = datetime.utcnow()
    this_month_key = now.strftime("%Y-%m")
    this_month_receipts = [r for r in receipts if r.date.startswith(this_month_key)]

    return {
        "total": round(sum(r.total for r in receipts), 2),
        "count": len(receipts),
        "by_category": by_category,
        "by_month": by_month,
        "this_month_total": round(sum(r.total for r in this_month_receipts), 2),
        "this_month_count": len(this_month_receipts),
    }
