import uuid
import logging
from azure.storage.blob.aio import BlobServiceClient
from app.config import settings

logger = logging.getLogger(__name__)


async def upload_receipt_image(image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    """Upload receipt image to Azure Blob Storage. Returns the blob URL, or empty string if storage is not configured."""
    if not settings.azure_storage_connection_string:
        return ""

    blob_name = f"{uuid.uuid4()}.jpg"
    blob_service = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)

    async with blob_service:
        container_client = blob_service.get_container_client(settings.azure_storage_container)
        blob_client = container_client.get_blob_client(blob_name)
        await blob_client.upload_blob(image_bytes, content_type=content_type, overwrite=True)
        return blob_client.url
