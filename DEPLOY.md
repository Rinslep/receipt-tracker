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

## Progress

| Step | Status | Notes |
|---|---|---|
| 1a. Document Intelligence | ✅ Done | Endpoint: `https://uksouth.api.cognitive.microsoft.com/` |
| 1b. PostgreSQL Flexible Server | ⏳ Pending | Run CLI command below |
| 1c. App Registration (Entra ID) | ✅ Done | Redirect URIs set to Web platform |
| 1d. App Service + Plan | ⏳ Pending quota | Sev C ticket raised for UK South quota |
| 2. Backend (FastAPI) | ✅ Done | Running locally on SQLite |
| 3. Deploy to App Service | ⏳ Blocked | Waiting on App Service quota approval |
| 4. Enable Easy Auth | ⏳ Pending | Can be done once App Service exists |

---

## Step 1: Azure Resources to Create

### 1a. Azure AI Document Intelligence ✅ Complete

Resource created in UK South. Endpoint and key saved to `.env`.

---

### 1b. Azure Database for PostgreSQL (Flexible Server) ⏳ Todo

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

Once created, update `.env`:
```
DATABASE_URL=postgresql+asyncpg://receiptsadmin:<PASSWORD>@receipts-db.postgres.database.azure.com/receipts
```

Then run the Alembic migration to create tables:
```bash
.venv/Scripts/python.exe -m alembic upgrade head
```

> **Note — "table already exists" error:** The FastAPI app creates tables automatically on startup via `Base.metadata.create_all`. If you see `sqlite3.OperationalError: table receipts already exists`, the table was already created by the app before Alembic ran. Fix it by stamping the migration as done without re-running it:
> ```bash
> .venv/Scripts/python.exe -m alembic stamp head
> ```
> Future migrations will apply normally from this point.

---

### 1c. App Registration (Entra ID) ✅ Complete

- Name: `Receipt Tracker`
- Supported account types: Single tenant
- Platform: **Web** (not Public client/native)
- Redirect URIs:
  - `https://your-app.azurewebsites.net/.auth/login/aad/callback`
  - `http://localhost:8080/auth/callback`
- Tenant ID, Client ID, and Client Secret saved to `.env`

> **Note:** If the client secret is rotated, update `CLIENT_SECRET` in `.env` and in the App Service environment variables (Step 3).

---

### 1d. Azure App Service ⏳ Pending quota

A Sev C quota increase ticket has been raised for App Service VMs in UK South (current limit: 0).

Once approved, run:
```bash
# Create the App Service Plan
az appservice plan create \
  --name receipt-plan \
  --resource-group receipts-rg \
  --sku B1 \
  --is-linux

# Create the Web App
az webapp create \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --runtime "PYTHON:3.14" \
  --plan receipt-plan

# Configure Easy Auth
az webapp auth microsoft update \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --client-id <APP_CLIENT_ID> \
  --client-secret <CLIENT_SECRET> \
  --issuer https://login.microsoftonline.com/<TENANT_ID>/v2.0 \
  --allowed-audiences api://<APP_CLIENT_ID>
```

---

## Step 2: Backend (FastAPI) ✅ Complete

All backend code is written and tested. Running locally at `http://localhost:8080`.

### Running locally
```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

### Running tests
```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

### Project structure
```
receipt-tracker/
├── app/
│   ├── main.py            # FastAPI app + static file serving + CORS
│   ├── auth.py            # Easy Auth headers + JWT fallback + X-Dev-User for local dev
│   ├── config.py          # Pydantic settings loaded from .env
│   ├── models.py          # SQLAlchemy Receipt model
│   ├── database.py        # Async engine + get_db dependency
│   ├── routes/
│   │   ├── receipts.py    # POST /scan, POST/GET /api/receipts, DELETE /api/receipts/{id}
│   │   └── analytics.py   # GET /api/analytics
│   └── services/
│       └── ocr.py         # Azure Document Intelligence client + category matcher
├── static/
│   ├── index.html         # PWA frontend (scan, dashboard, history, delete)
│   ├── manifest.json      # PWA manifest
│   └── sw.js              # Service worker (shell caching)
├── alembic/               # Database migrations
├── tests/                 # pytest suite (5 tests, all passing)
├── requirements.txt
├── startup.sh             # gunicorn command for App Service
└── .env                   # Local secrets (gitignored)
```

---

## Step 3: Deploy ⏳ Pending App Service quota

Once the App Service exists:

```bash
# Set startup file
az webapp config set \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --startup-file "startup.sh"

# Set environment variables
az webapp config appsettings set \
  --name receipt-tracker-app \
  --resource-group receipts-rg \
  --settings \
    DATABASE_URL="postgresql+asyncpg://receiptsadmin:<PASSWORD>@receipts-db.postgres.database.azure.com/receipts" \
    DOC_INTEL_ENDPOINT="https://uksouth.api.cognitive.microsoft.com/" \
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

## Step 4: Enable Easy Auth ⏳ Pending App Service

1. Azure Portal → App Service → **Authentication**
2. Add identity provider → **Microsoft**
3. Select the `Receipt Tracker` App Registration
4. Set "Restrict access" to **Require authentication**
5. Set "Unauthenticated requests" to **HTTP 302 (redirect to login)**

Once Easy Auth is enabled, the `X-Dev-User` local dev header is no longer used — the App Service injects `X-MS-CLIENT-PRINCIPAL-ID` automatically after login.

---

## What This Gives You

| Feature | Implementation |
|---|---|
| Phone camera scanning | PWA `capture="environment"` + file upload |
| Receipt OCR | Azure Document Intelligence `prebuilt-receipt` model |
| Expense dashboard | API aggregation + frontend charts |
| Multi-user | Each receipt tagged with Entra ID `oid` |
| Auth | Easy Auth — zero custom login code |
| Delete receipts | Instant DOM removal + API delete, history tab only |
| Export | Client-side CSV generation |
| Offline-ready | PWA manifest + service worker shell caching |

---

## Remaining / Future Work

- **PostgreSQL** — create the flexible server (Step 1b) and run `alembic upgrade head`
- **App Service** — waiting on quota increase ticket, then follow Steps 1d → 3 → 4
- **Azure Blob Storage** — persist receipt images alongside extracted data
- **Line item extraction** — Document Intelligence returns individual items, not just totals
- **Budget alerts** — notify when monthly spend exceeds a threshold
- **Multi-currency** — currently assumes GBP (£)
- **Date extraction for transport tickets** — prebuilt-receipt model doesn't reliably extract dates from bus/train tickets; may need a custom model or manual fallback prompt
