"""
SMS OTP dispatch.

Production: MSG91 (India DLT-compliant) over stdlib urllib.
Dev:        prints to console — same pattern as Phase 1-7.

The branch is controlled by settings.MSG91_AUTH_KEY: empty → mock, set → real.
This means dev workflows keep working with no config; staging/prod with valid
creds in .env automatically switches to live SMS.
"""
import json
import logging
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.conf import settings

logger = logging.getLogger(__name__)

MSG91_URL = 'https://control.msg91.com/api/v5/flow/'


def _normalize_phone(phone: str) -> str | None:
    """Strip +, spaces, dashes, leading 91. Returns 10-digit string or None."""
    digits = phone.lstrip('+').replace(' ', '').replace('-', '')
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10 or not digits.isdigit():
        return None
    return digits


def _mask_phone(ten_digit: str) -> str:
    """+91 98XX XX XX 12 — keep first 4 and last 2 visible only."""
    return f'+91{ten_digit[:4]}****{ten_digit[-2:]}'


def send_sms_otp(phone: str, code: str, purpose: str = 'verification') -> bool:
    """Returns True on success, False on failure.

    Callers in accounts/views.py currently ignore the return value (compat with
    the prior void implementation), but the bool is here for future call sites
    that want to know whether the SMS dispatched cleanly.
    """
    normalized = _normalize_phone(phone)
    if normalized is None:
        logger.error('Invalid phone format for SMS: %r', phone)
        return False

    if settings.MSG91_AUTH_KEY:
        return _send_via_msg91(normalized, code, purpose)

    # Dev / unconfigured: visible mock so register/login flows work offline.
    print(
        f'\n========== MOCK SMS ==========\n'
        f'To: +91{normalized}\n'
        f'Body: Your Vaishnavi {purpose} OTP is {code}. Valid for 10 minutes.\n'
        f'==============================\n'
    )
    return True


def _send_via_msg91(phone: str, code: str, purpose: str) -> bool:
    """POST to MSG91 flow API. Returns True on success."""
    if not settings.MSG91_OTP_TEMPLATE_ID:
        logger.error('MSG91_OTP_TEMPLATE_ID is empty; cannot dispatch SMS.')
        return False

    payload = {
        'template_id': settings.MSG91_OTP_TEMPLATE_ID,
        'short_url': '0',
        'recipients': [
            {'mobiles': f'91{phone}', 'otp': code},
        ],
    }
    body = json.dumps(payload).encode('utf-8')
    req = urllib_request.Request(
        MSG91_URL,
        data=body,
        headers={
            'authkey': settings.MSG91_AUTH_KEY,
            'accept': 'application/json',
            'content-type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib_request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        logger.error('MSG91 HTTP %s for %s (%s): %s',
                     e.code, _mask_phone(phone), purpose, err_body)
        return False
    except URLError as e:
        logger.error('MSG91 network error for %s (%s): %s',
                     _mask_phone(phone), purpose, e)
        return False
    except Exception:
        logger.exception('MSG91 send failed for %s (%s)',
                         _mask_phone(phone), purpose)
        return False

    if data.get('type') == 'success':
        logger.info('SMS dispatched to %s for %s (request_id=%s)',
                    _mask_phone(phone), purpose, data.get('request_id', ''))
        return True

    logger.error('MSG91 non-success response for %s (%s): %s',
                 _mask_phone(phone), purpose, data)
    return False
