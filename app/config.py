from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database — defaults to SQLite for local dev; use postgresql+asyncpg:// in prod
    database_url: str = "sqlite+aiosqlite:///./receipts.db"

    # Upload size limit in MB for /api/receipts/scan
    max_upload_mb: int = 20

    # Azure Document Intelligence
    doc_intel_endpoint: str = ""
    doc_intel_key: str = ""

    # Azure Blob Storage
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "receipt-images"

    # Entra ID
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""


settings = Settings()
