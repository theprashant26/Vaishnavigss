"""Phase 6: cart counters in every template, for the navbar badge."""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def cart_meta(request):
    # Local import — avoid app-loading cycles.
    from orders.services.cart import CartService
    try:
        svc = CartService(request)
        return {
            'cart_item_count': svc.get_item_count(),
            'cart_subtotal': svc.get_subtotal(),
        }
    except Exception:
        logger.exception('cart_meta context processor failed')
        return {'cart_item_count': 0, 'cart_subtotal': Decimal('0')}
