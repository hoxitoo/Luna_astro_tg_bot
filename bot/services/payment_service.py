"""ЮKassa (YooKassa) payment integration.

Self-employed (НПД) mode: YooKassa registers the income in «Мой налог» and
generates the fiscal receipt itself, so we do NOT send a `receipt` object.
If the operator later becomes ИП/ООО with fiscalization, add a `receipt`
block (customer email/phone + items with vat_code) to the create body.

YooKassa has no request signatures. A webhook notification is therefore
verified by re-fetching the payment via the API (`fetch_payment`) and trusting
only the server's own copy of status/amount — never the values in the webhook
body, which an attacker could forge.
"""
import base64
import uuid
import aiohttp
from bot.config import settings

_API_BASE = "https://api.yookassa.ru/v3/payments"
_TIMEOUT = aiohttp.ClientTimeout(total=15)
# Stable namespace so a retried create for the same DB row reuses the same
# Idempotence-Key and YooKassa returns the existing payment instead of a new one.
_IDEMPOTENCE_NS = uuid.UUID("6f1c2d3e-4a5b-6c7d-8e9f-0a1b2c3d4e5f")


class PaymentError(Exception):
    """Raised when YooKassa returns a non-success response or is unreachable."""


def _auth_header() -> str:
    raw = f"{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _return_url() -> str:
    return settings.YOOKASSA_RETURN_URL or f"https://t.me/{settings.BOT_USERNAME}"


async def create_payment_link(amount: int, description: str, payment_db_id: int) -> tuple[str, str]:
    """Create a YooKassa payment and return (confirmation_url, provider_payment_id).

    Raises PaymentError on any non-success response."""
    body = {
        "amount": {"value": f"{amount}.00", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": _return_url()},
        "description": description,
        "metadata": {"payment_db_id": str(payment_db_id)},
    }
    headers = {
        "Authorization": _auth_header(),
        "Idempotence-Key": str(uuid.uuid5(_IDEMPOTENCE_NS, f"luna-payment-{payment_db_id}")),
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.post(_API_BASE, json=body, headers=headers) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    raise PaymentError(f"YooKassa create failed [{resp.status}]: {data}")
    except aiohttp.ClientError as e:
        raise PaymentError(f"YooKassa unreachable: {e}") from e

    try:
        return data["confirmation"]["confirmation_url"], data["id"]
    except (KeyError, TypeError) as e:
        raise PaymentError(f"YooKassa malformed response: {data}") from e


async def fetch_payment(provider_payment_id: str) -> dict:
    """Re-fetch a payment from YooKassa to verify a webhook (no signatures exist).

    Raises PaymentError on failure."""
    headers = {"Authorization": _auth_header()}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.get(f"{_API_BASE}/{provider_payment_id}", headers=headers) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise PaymentError(f"YooKassa fetch failed [{resp.status}]: {data}")
                return data
    except aiohttp.ClientError as e:
        raise PaymentError(f"YooKassa unreachable: {e}") from e
