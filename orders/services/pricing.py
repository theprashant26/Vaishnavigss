"""Phase 6 — shipping + tax math, reused by cart view, checkout review, order creation."""
from decimal import Decimal

from core.models import SiteSettings

ZERO = Decimal('0')
TWO_PLACES = Decimal('0.01')


def calculate_shipping(subtotal: Decimal, pincode: str = '') -> Decimal:
    """
    Pincode-based shipping. Free above SiteSettings.free_shipping_threshold.
    NCR pincodes (matching one of the comma-separated 2-digit prefixes in
    `ncr_pincode_prefixes`) get the NCR rate; everyone else pays the higher rate.
    """
    site = SiteSettings.load()
    if subtotal >= site.free_shipping_threshold:
        return ZERO

    pincode = (pincode or '').strip()
    if pincode and len(pincode) >= 2:
        prefixes = {p.strip() for p in (site.ncr_pincode_prefixes or '').split(',') if p.strip()}
        if pincode[:2] in prefixes:
            return site.shipping_ncr_charge

    return site.shipping_other_charge


def calculate_tax(items) -> Decimal:
    """
    Sum GST across cart items. `items` is the dict list returned by
    CartService.get_items() — each row has `variant` + `quantity`.
    Tax per row = unit_price * qty * (gst_rate / 100).
    """
    total = ZERO
    for row in items:
        variant = row['variant']
        qty = row['quantity']
        rate = variant.product.gst_rate or ZERO
        line = (variant.price * qty * rate / Decimal('100')).quantize(TWO_PLACES)
        total += line
    return total
