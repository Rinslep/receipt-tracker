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
| 1b. PostgreSQL Flexible Server | ✅ Done | Server created, migrations run |
| 1c. App Registration (Entra ID) | ✅ Done | Redirect URIs set to Web platform |
| 1d. App Service + Plan | ✅ Done | F1 plan in East US 2, env vars set via portal |
| 2. Backend (FastAPI) | ✅ Done | Running locally on SQLite |
| 3. Deploy to App Service | ✅ Done | Deployed via GitHub Actions |
| 4. Enable Easy Auth | ✅ Done | Entra ID authentication enabled |

---

## Step 1: Azure Resources to Create

### 1a. Azure AI Document Intelligence ✅ Complete

Resource created in UK South. Endpoint and key saved to `.env`.

---

### 1b. Azure Database for PostgreSQL (Flexible Server) ✅ Complete

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

### 1d. Azure App Service ✅ Complete

F1 plan created in East US 2. Environment variables set via the portal. Note: UK South quota was 0 — F1 in East US 2 was used instead.

Commands used:
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
  --runtime "PYTHON:3.12" \
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

## Step 3: Deploy ✅ Complete

Deployed via GitHub Actions CI/CD pipeline. Reference commands used:

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

## Step 4: Enable Easy Auth ✅ Complete

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

---

### Planned features

#### Line item extraction
Document Intelligence already returns individual items (e.g. bread £1.20, milk £0.89) inside `result.documents[0].fields["Items"]`. The work needed:
- Add a `LineItem` table to the database (linked to `Receipt` by foreign key) storing `description`, `quantity`, `unit_price`, `total_price`
- Extract and save line items in `ocr.py` alongside the receipt header fields
- Add a new Alembic migration for the `line_items` table
- Show line items in a collapsible section on the history/scan view
- Include line items in the CSV export
- Enable analytics by item name (e.g. "how much have I spent on coffee across all shops")

#### Date fallback to current day
When the OCR returns no `TransactionDate` (common with transport tickets, digital receipts), the backend currently returns an empty string. The fix:
- In `ocr.py`, if `TransactionDate` is not found, default to `datetime.date.today().isoformat()` before returning
- This means the date field always arrives pre-filled; the user can correct it if wrong

#### Merchant deduplication
"Tesco Express", "Tesco Metro", and "TESCO STORES LTD" are all Tesco. Without dedup, analytics fragment across variants. Approach:
- Add a normalisation step in `ocr.py` (or a new `services/merchants.py`) that maps known variants to a canonical name using a lookup dict
- Optionally, use fuzzy matching (e.g. `rapidfuzz`) for unknown merchants
- Store both the raw vendor name (for audit) and the normalised name (for analytics)
- Surface a "merge duplicates" UI so the user can manually consolidate merchants they recognise

#### Receipt photo storage (Azure Blob Storage)
Currently only extracted data is saved — the original image is discarded after OCR. To store it:
- Create an Azure Storage Account and a Blob container (`receipts-images`) in `receipts-rg`
- Add `azure-storage-blob` to `requirements.txt`
- In the scan endpoint, upload the image bytes to Blob Storage and save the returned URL to `Receipt.image_url`
- Add a `AZURE_STORAGE_CONNECTION_STRING` (or account name + key) to `.env` and App Service settings
- In the history view, show a thumbnail or "View original" link per receipt

```bash
# Create storage account
az storage account create \
  --name receiptstorageacc \
  --resource-group receipts-rg \
  --location uksouth \
  --sku Standard_LRS

# Create blob container
az storage container create \
  --name receipt-images \
  --account-name receiptstorageacc \
  --public-access off
```

#### Enhanced CSV / Excel export
The current export button generates a flat CSV of receipt headers. Improvements:
- Include line items as additional rows (indented or in a separate sheet)
- Add a date range picker so you can export "March 2026" rather than everything
- Generate a proper `.xlsx` file using `openpyxl` with a summary sheet and a data sheet
- Add a monthly subtotal row per category

#### Email-to-receipt import
Allow forwarding a receipt email (or attaching a photo) to a dedicated address and have it auto-import. Architecture:
- **Azure Communication Services** (or **SendGrid Inbound Parse**) receives the email and POSTs it as a webhook to a new endpoint `POST /api/receipts/ingest-email`
- The endpoint extracts attachments (PDF, JPEG, PNG) or the HTML body
- Image/PDF attachments are passed through the existing `analyse_receipt()` OCR pipeline
- HTML email bodies (e.g. Amazon order confirmations, Trainline e-tickets) are parsed with BeautifulSoup or a regex pattern per known sender to extract total, date, vendor without needing OCR
- The resulting receipt is saved against the user's account (matched by the `From:` email address to their Entra ID email)
- Requires a publicly reachable endpoint — only works once deployed to App Service

```bash
# Create an Azure Communication Services resource for email ingestion
az communication create \
  --name receipts-comms \
  --resource-group receipts-rg \
  --location global \
  --data-location uksouth
```

---

### Lower priority
- **Budget alerts** — notify when monthly spend in a category exceeds a set threshold
- **Multi-currency** — currently assumes GBP (£)
- **Date extraction for transport tickets** — fallback to today's date (see above) handles the immediate problem; a custom Document Intelligence model would handle it properly long-term
