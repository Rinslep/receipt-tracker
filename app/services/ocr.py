import json
from datetime import date, datetime
from decimal import Decimal
from app.config import settings


def _json_default(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

_client = None


def _get_client():
    global _client
    if _client is None:
        if not settings.doc_intel_endpoint or not settings.doc_intel_key:
            raise ValueError(
                "Azure Document Intelligence credentials not configured. "
                "Set DOC_INTEL_ENDPOINT and DOC_INTEL_KEY in .env."
            )
        from azure.ai.formrecognizer import DocumentAnalysisClient
        from azure.core.credentials import AzureKeyCredential

        _client = DocumentAnalysisClient(
            endpoint=settings.doc_intel_endpoint,
            credential=AzureKeyCredential(settings.doc_intel_key),
        )
    return _client


async def analyse_receipt(image_bytes: bytes) -> dict:
    """Send receipt image to Azure Document Intelligence prebuilt-receipt model."""
    import asyncio

    client = _get_client()

    # SDK is synchronous; run in thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: client.begin_analyze_document(
            "prebuilt-receipt", document=image_bytes
        ).result(),
    )

    if not result.documents:
        return {
            "vendor": "", "date": "", "total": 0.0,
            "subtotal": 0.0, "tax": 0.0, "raw": "{}",
            "suggested_category": "other",
        }

    doc = result.documents[0]
    fields = doc.fields

    def get_val(name, default=""):
        f = fields.get(name)
        if f is None:
            return default
        if hasattr(f, "value") and f.value is not None:
            return f.value
        if hasattr(f, "content") and f.content is not None:
            return f.content
        return default

    vendor = str(get_val("MerchantName", ""))
    return {
        "vendor": vendor,
        "date": str(get_val("TransactionDate", "")),
        "total": float(get_val("Total", 0) or 0),
        "subtotal": float(get_val("Subtotal", 0) or 0),
        "tax": float(get_val("TotalTax", 0) or 0),
        "raw": json.dumps(result.to_dict(), default=_json_default),
        "suggested_category": _guess_category(vendor),
    }


def _guess_category(vendor: str) -> str:
    v = vendor.lower()
    food = [
        "tesco", "sainsbury", "lidl", "aldi", "mcdonald", "costa", "pret",
        "greggs", "nandos", "starbucks", "waitrose", "marks", "m&s", "morrisons",
        "subway", "kfc", "pizza",
    ]
    transport = [
        "shell", "bp", "esso", "uber", "bolt", "trainline", "tfl",
        "national rail", "eurostar", "avis", "hertz",
        "compass travel", "stagecoach", "arriva", "first bus",
        "go-ahead", "transdev", "megabus", "national express",
    ]
    office = ["staples", "ryman", "viking", "currys", "argos"]
    software = [
        "amazon web", "github", "microsoft", "google cloud",
        "digital ocean", "aws", "atlassian", "adobe", "slack",
    ]
    utilities = [
        "british gas", "octopus", "eon", "bulb", "thames water",
        "bt ", "sky ", "virgin media", "ee ", "vodafone", "o2 ",
    ]
    travel = [
        "hilton", "premier inn", "ibis", "airbnb", "booking.com",
        "expedia", "easyjet", "ryanair", "british airways", "tui",
    ]

    if any(k in v for k in food):      return "food"
    if any(k in v for k in transport): return "transport"
    if any(k in v for k in office):    return "office"
    if any(k in v for k in software):  return "software"
    if any(k in v for k in utilities): return "utilities"
    if any(k in v for k in travel):    return "travel"
    return "other"
