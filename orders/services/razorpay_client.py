"""
Razorpay client — stdlib only.

Three functions:
  create_order(amount_paise, currency, receipt, notes) -> dict
  verify_payment_signature(order_id, payment_id, signature) -> bool
  verify_webhook_signature(body_bytes, signature) -> bool

Keep this module boring. No clever metaprogramming. Every code path is
auditable by a human paying-attention review.
"""
import base64
import hashlib
import hmac
import json
import logging
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.conf import settings

logger = logging.getLogger(__name__)

RAZORPAY_API_BASE = 'https://api.razorpay.com/v1'


class RazorpayError(Exception):
    """Raised on any non-2xx response from the Razorpay API."""


def _mask(s: str) -> str:
    """For logging: show first 4 / last 4, mask the middle."""
    if not s:
        return '<empty>'
    if len(s) <= 8:
        return s[0] + '***' + s[-1]
    return f'{s[:4]}…{s[-4:]}'


def _auth_header() -> str:
    creds = f'{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}'
    return 'Basic ' + base64.b64encode(creds.encode()).decode()


def create_order(amount_paise: int, currency: str = 'INR',
                 receipt: str = '', notes: dict | None = None) -> dict:
    """
    Create a Razorpay order. Returns the order dict from the API
    (caller usually keeps just the `id` field).
    `amount_paise` must be an integer; ₹100 = 10000 paise.
    Raises RazorpayError on non-2xx.
    """
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise RazorpayError('Razorpay credentials not configured. Check .env.')

    payload = {
        'amount': int(amount_paise),
        'currency': currency,
        'receipt': receipt,
        'notes': notes or {},
    }
    body = json.dumps(payload).encode('utf-8')

    req = urllib_request.Request(
        f'{RAZORPAY_API_BASE}/orders',
        data=body,
        headers={
            'Authorization': _auth_header(),
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib_request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8')
            data = json.loads(raw)
            logger.info('Razorpay order created: id=%s receipt=%s amount=%s',
                        _mask(data.get('id', '')), receipt, amount_paise)
            return data
    except HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        logger.error('Razorpay create_order HTTP %s: %s', e.code, err_body)
        raise RazorpayError(f'HTTP {e.code}: {err_body}') from e
    except URLError as e:
        logger.error('Razorpay create_order network error: %s', e)
        raise RazorpayError(f'Network error: {e}') from e


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    HMAC-SHA256 verification of the payment signature returned by Razorpay
    to the browser-side callback. Per Razorpay docs:
        expected = HMAC_SHA256(key_secret, order_id + "|" + payment_id)
    """
    if not (order_id and payment_id and signature):
        return False
    secret = settings.RAZORPAY_KEY_SECRET.encode('utf-8')
    message = f'{order_id}|{payment_id}'.encode('utf-8')
    expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(expected, signature)
    if not ok:
        logger.warning('Razorpay payment signature MISMATCH for order=%s payment=%s',
                       _mask(order_id), _mask(payment_id))
    return ok


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """
    HMAC-SHA256 verification of webhook payloads. Per Razorpay docs:
        expected = HMAC_SHA256(webhook_secret, raw_request_body)
    """
    if not (body and signature):
        return False
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        logger.error('Webhook signature check called but RAZORPAY_WEBHOOK_SECRET is empty.')
        return False
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
        body,
        hashlib.sha256,
    ).hexdigest()
    ok = hmac.compare_digest(expected, signature)
    if not ok:
        logger.warning('Razorpay webhook signature MISMATCH (body bytes=%d)', len(body))
    return ok
