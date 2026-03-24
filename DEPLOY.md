# Receipt Tracker — Azure Deployment Guide

## Architecture Overview

```
┌──────────────┐     ┌─────────────────────────┐     ┌──────────────────────────┐
│  PWA Client  │────▶│  Azure App Service       │────▶│  Azure Document          │
│  (Browser)   │◀────│  (Python / FastAPI)       │◀────│  Intelligence            │
└──────────────┘     │                           │     │  (prebuilt-receipt)      │
                     │  • Entra ID auth (MSAL)   │     └──────────────────────────┘
                     │  • Receipt CRUD API        │
                     │  • Expense analytics       │     ┌──────────────────────────┐
                     │                           │────▶│  Azure SQL / PostgreSQL   │
                     └─────────────────────────┘     │  (receipt storage)         │
                                                      └──────────────────────────┘
```

**Auth flow:** Browser → MSAL.js redirect → Entra ID login → access token → FastAPI validates JWT on every request.

---

## Step 1: Azure Resources to Create

In the Azure Portal (or via CLI), create these resources in a single resource group:

### 1a. Azure AI Document Intelligence
```bash
az cognitiveservices account create \
  --name receipt-doc-intel \
  --resource-group receipts-rg \
  --kind FormRecognizer \
  --sku S0 \
  --location uksouth \
  --yes
```
Note the **endpoint** and **key** from the portal under Keys and Endpoint.

### 1b. Azure Database for PostgreSQL (Flexible Server)
```bash
az postgres flexible-server create \
  --name receipts-db \
  --resource-group receipts-rg \
  --location uksouth \
  --admin-user receiptsadmin \
  --admin-password <STRONG_PASSWORD> \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32
```

### 1c. App Registration (Entra ID)
1. Go to **Azure Portal → Entra ID → App registrations → New registration**
2. Name: `Receipt Tracker`
3. Redirect URI: `https://your-app.azurewebsites.net/.auth/login/aad/callback` (for Easy Auth)
   - Also add `http://localhost:8000/auth/callback` for local dev
4. Under **API permissions**, add `User.Read` (Microsoft Graph)
5. Under **Certificates & secrets**, create a client secret — note it down
6. Note the **Application (client) ID** and **Directory (tenant) ID**

### 1d. Azure App Service
```bash
az webapp create \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --runtime "PYTHON:3.14" \
  --plan receipt-plan

# Configure Easy Auth (built-in Entra ID login)
az webapp auth microsoft update \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --client-id <APP_CLIENT_ID> \
  --client-secret <CLIENT_SECRET> \
  --issuer https://login.microsoftonline.com/<TENANT_ID>/v2.0 \
  --allowed-audiences api://<APP_CLIENT_ID>
```

---

## Step 2: Backend (FastAPI)

### Project structure
```
receipt-tracker/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app + static file serving
│   ├── auth.py            # JWT validation middleware
│   ├── config.py          # Environment settings
│   ├── models.py          # SQLAlchemy models
│   ├── database.py        # DB session management
│   ├── routes/
│   │   ├── receipts.py    # CRUD + scan endpoints
│   │   └── analytics.py   # Dashboard data endpoints
│   └── services/
│       └── ocr.py         # Document Intelligence client
├── static/                # PWA files (index.html, manifest, icons)
├── requirements.txt
├── startup.sh
└── .env
```

### requirements.txt
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
asyncpg==0.30.0
psycopg2-binary==2.9.9
python-multipart==0.0.12
python-jose[cryptography]==3.3.0
azure-ai-formrecognizer==3.3.3
azure-identity==1.19.0
httpx==0.27.0
pydantic-settings==2.6.0
alembic==1.13.3
```

### app/config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost/receipts"

    # Azure Document Intelligence
    doc_intel_endpoint: str = ""
    doc_intel_key: str = ""

    # Entra ID
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
```

### app/models.py
```python
from sqlalchemy import Column, String, Float, DateTime, Text
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
    date = Column(String, nullable=False)  # ISO date
    total = Column(Float, nullable=False)
    category = Column(String, nullable=False, default="other")
    notes = Column(Text, default="")
    image_url = Column(String, default="")  # Azure Blob URL if storing images
    raw_ocr = Column(Text, default="")  # Full OCR JSON for audit
    created_at = Column(DateTime, default=datetime.utcnow)
```

### app/services/ocr.py
```python
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from app.config import settings

client = DocumentAnalysisClient(
    endpoint=settings.doc_intel_endpoint,
    credential=AzureKeyCredential(settings.doc_intel_key),
)

async def analyse_receipt(image_bytes: bytes) -> dict:
    """Send receipt image to Azure Document Intelligence.

    Uses the prebuilt-receipt model which extracts:
    vendor name, transaction date, total, subtotal, tax,
    line items, payment method, and more.
    """
    poller = client.begin_analyze_document(
        "prebuilt-receipt", document=image_bytes
    )
    result = poller.result()

    if not result.documents:
        return {"vendor": "", "date": "", "total": 0.0, "items": []}

    doc = result.documents[0]
    fields = doc.fields

    def get_val(name, default=""):
        f = fields.get(name)
        if f is None:
            return default
        if hasattr(f, "value"):
            return f.value
        if hasattr(f, "content"):
            return f.content
        return default

    return {
        "vendor": get_val("MerchantName", ""),
        "date": str(get_val("TransactionDate", "")),
        "total": float(get_val("Total", 0)),
        "subtotal": float(get_val("Subtotal", 0)),
        "tax": float(get_val("TotalTax", 0)),
        "raw": result.to_dict(),  # Store for audit
    }
```

### app/routes/receipts.py
```python
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Receipt
from app.database import get_db
from app.services.ocr import analyse_receipt
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

class ReceiptResponse(BaseModel):
    id: str
    vendor: str
    date: str
    total: float
    category: str
    notes: str
    created_at: str

@router.post("/scan")
async def scan_receipt(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a receipt image, extract data via Azure Document Intelligence."""
    contents = await file.read()
    if len(contents) > 10_000_000:
        raise HTTPException(413, "File too large (max 10MB)")

    result = await analyse_receipt(contents)
    return {
        "vendor": result["vendor"],
        "date": result["date"],
        "total": result["total"],
        "suggested_category": _guess_category(result["vendor"]),
    }

@router.post("/", response_model=ReceiptResponse)
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

@router.get("/")
async def list_receipts(
    category: Optional[str] = None,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all receipts for the current user, optionally filtered."""
    q = select(Receipt).where(Receipt.user_id == user["oid"])
    if category and category != "all":
        q = q.where(Receipt.category == category)
    q = q.order_by(Receipt.date.desc())
    result = await db.execute(q)
    return [_to_response(r) for r in result.scalars()]

@router.get("/analytics")
async def get_analytics(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated expense data for the dashboard."""
    q = select(Receipt).where(Receipt.user_id == user["oid"])
    result = await db.execute(q)
    receipts = list(result.scalars())

    by_category = {}
    by_month = {}
    for r in receipts:
        by_category[r.category] = by_category.get(r.category, 0) + r.total
        month_key = r.date[:7]  # "YYYY-MM"
        by_month[month_key] = by_month.get(month_key, 0) + r.total

    return {
        "total": sum(r.total for r in receipts),
        "count": len(receipts),
        "by_category": by_category,
        "by_month": by_month,
    }

def _to_response(r: Receipt) -> dict:
    return {
        "id": r.id, "vendor": r.vendor, "date": r.date,
        "total": r.total, "category": r.category, "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }

def _guess_category(vendor: str) -> str:
    v = vendor.lower()
    food = ["tesco", "sainsbury", "lidl", "aldi", "mcdonald", "costa", "pret", "greggs", "nandos", "starbucks"]
    transport = ["shell", "bp", "esso", "uber", "bolt", "trainline", "tfl"]
    software = ["amazon web", "github", "microsoft", "google cloud", "digital ocean"]
    if any(f in v for f in food): return "food"
    if any(f in v for f in transport): return "transport"
    if any(f in v for f in software): return "software"
    return "other"
```

### app/auth.py
```python
from fastapi import Request, HTTPException
from jose import jwt, JWTError
import httpx

# When using App Service Easy Auth, the validated user info
# is passed in request headers — no manual JWT validation needed.
# This works for both approaches:

async def get_current_user(request: Request) -> dict:
    """Extract authenticated user from Easy Auth headers or JWT."""

    # Option A: App Service Easy Auth (recommended for production)
    # Easy Auth injects these headers after validating the token
    principal_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
    principal_name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")

    if principal_id:
        return {
            "oid": principal_id,
            "name": principal_name or "User",
            "email": principal_name or "",
        }

    # Option B: Manual JWT validation (for local dev without Easy Auth)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")

    token = auth.split(" ", 1)[1]
    try:
        # In production, validate against Entra ID JWKS
        payload = jwt.decode(token, options={"verify_signature": False})
        return {
            "oid": payload.get("oid", ""),
            "name": payload.get("name", "User"),
            "email": payload.get("preferred_username", ""),
        }
    except JWTError:
        raise HTTPException(401, "Invalid token")
```

### app/main.py
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes import receipts
from app.database import engine
from app.models import Base

app = FastAPI(title="Receipt Tracker")

app.include_router(receipts.router)

# Serve the PWA
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

### startup.sh (for Azure App Service)
```bash
#!/bin/bash
gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## Step 3: Deploy

```bash
# From the project root
az webapp config set \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --startup-file "startup.sh"

# Set environment variables
az webapp config appsettings set \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --settings \
    DATABASE_URL="postgresql+asyncpg://user:pass@receipts-db.postgres.database.azure.com/receipts" \
    DOC_INTEL_ENDPOINT="https://receipt-doc-intel.cognitiveservices.azure.com/" \
    DOC_INTEL_KEY="<your-key>" \
    TENANT_ID="<your-tenant-id>" \
    CLIENT_ID="<your-client-id>" \
    CLIENT_SECRET="<your-client-secret>"

# Deploy code
az webapp deploy \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --src-path . \
  --type zip
```

---

## Step 4: Enable Easy Auth

The simplest way to secure the entire app with Entra ID:

1. Azure Portal → App Service → **Authentication**
2. Add identity provider → **Microsoft**
3. Select the App Registration you created
4. Set "Restrict access" to **Require authentication**
5. Set "Unauthenticated requests" to **HTTP 302 (redirect to login)**

This means anyone hitting your app URL gets redirected to Microsoft login first. Only users in your Entra ID tenant (your domain) can log in.

---

## What This Gives You

| Feature | Implementation |
|---|---|
| Phone camera scanning | PWA `capture="environment"` + file upload |
| Receipt OCR | Azure Document Intelligence `prebuilt-receipt` model |
| Expense dashboard | API aggregation + frontend charts |
| Multi-user | Each receipt tagged with Entra ID `oid` |
| Auth | Easy Auth — zero custom login code |
| Export | Client-side CSV generation |
| Offline-ready | PWA with service worker (add manifest.json + sw.js) |

---

## Next Steps

- Add **Azure Blob Storage** to persist receipt images alongside the extracted data
- Add **Alembic migrations** for schema changes
- Add a **service worker** (`sw.js`) for true offline PWA capability
- Add **line item extraction** — Document Intelligence returns individual items, not just totals
- Add **budget alerts** — notify when monthly spend exceeds a threshold
- Add **multi-currency** support if needed