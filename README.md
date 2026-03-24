# receipt-tracker

A Progressive Web App (PWA) for capturing, parsing, and analysing receipts
using Azure Document Intelligence (Form Recognizer) and a FastAPI + PostgreSQL
backend secured with Azure Entra ID (formerly Azure AD).

---

## Project structure

```
receipt-tracker/
├── app/               # FastAPI application package
│   ├── main.py        # App entry point & router registration
│   ├── auth.py        # Azure AD token validation
│   ├── config.py      # Typed settings via pydantic-settings
│   ├── models.py      # SQLAlchemy ORM models
│   ├── database.py    # Async engine & session factory
│   ├── routes/
│   │   ├── receipts.py
│   │   └── analytics.py
│   └── services/
│       └── ocr.py     # Azure Document Intelligence client
├── static/            # PWA front-end shell
├── tests/             # Pytest test suite
├── alembic/           # Database migrations
├── alembic.ini
├── requirements.txt
├── startup.sh
└── .env.example
```

## Getting started

Prerequisite: Python 3.12

```bash
# 1. Copy and populate secrets
cp .env.example .env

# 2. Activate the virtual environment
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\Activate.ps1  # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run database migrations
alembic upgrade head

# 5. Start the dev server
./startup.sh
```

## Environment variables

| Variable            | Description                                   |
|---------------------|-----------------------------------------------|
| `DATABASE_URL`      | Async PostgreSQL connection string (asyncpg)  |
| `DOC_INTEL_ENDPOINT`| Azure Document Intelligence endpoint URL      |
| `DOC_INTEL_KEY`     | Azure Document Intelligence API key           |
| `TENANT_ID`         | Azure Entra ID tenant ID                      |
| `CLIENT_ID`         | App registration client ID                    |
| `CLIENT_SECRET`     | App registration client secret                |

## Running tests

```bash
pytest
```
