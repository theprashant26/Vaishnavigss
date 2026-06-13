"""
CartService — unified interface over session-cart (anonymous) and DB-cart (logged in).

Session shape: request.session['cart'] = {str(variant_id): int(quantity)}
DB shape:      orders.Cart / orders.CartItem

Always instantiate fresh per request: svc = CartService(request)
"""
import logging
from decimal import Decimal

from orders.models import Cart, CartItem

logger = logging.getLogger(__name__)

SESSION_KEY = 'cart'


def _session_dict(session) -> dict:
    """Return the session cart dict, lazily initializing it."""
    if SESSION_KEY not in session or not isinstance(session.get(SESSION_KEY), dict):
        session[SESSION_KEY] = {}
    return session[SESSION_KEY]


class CartService:
    def __init__(self, request):
        self.request = request
        self.user = request.user if request.user.is_authenticated else None

    # ---------- Internal: DB cart helpers --------------------------------
    def _get_or_create_db_cart(self) -> Cart:
        cart, _ = Cart.objects.get_or_create(user=self.user)
        return cart

    # ---------- Mutations ------------------------------------------------
    def add(self, variant_id: int, quantity: int = 1) -> None:
        if quantity < 1:
            return
        variant_id = int(variant_id)

        if self.user:
            cart = self._get_or_create_db_cart()
            item, created = CartItem.objects.get_or_create(
                cart=cart, variant_id=variant_id,
                defaults={'quantity': quantity},
            )
            if not created:
                item.quantity += quantity
                item.save(update_fields=['quantity'])
        else:
            d = _session_dict(self.request.session)
            d[str(variant_id)] = d.get(str(variant_id), 0) + quantity
            self.request.session.modified = True

    def update(self, variant_id: int, quantity: int) -> None:
        variant_id = int(variant_id)
        if quantity <= 0:
            self.remove(variant_id)
            return

        if self.user:
            cart = self._get_or_create_db_cart()
            CartItem.objects.filter(cart=cart, variant_id=variant_id).update(quantity=quantity)
        else:
            d = _session_dict(self.request.session)
            d[str(variant_id)] = quantity
            self.request.session.modified = True

    def remove(self, variant_id: int) -> None:
        variant_id = int(variant_id)
        if self.user:
            cart = self._get_or_create_db_cart()
            CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()
        else:
            d = _session_dict(self.request.session)
            d.pop(str(variant_id), None)
            self.request.session.modified = True

    def clear(self) -> None:
        if self.user:
            cart = self._get_or_create_db_cart()
            cart.items.all().delete()
        else:
            self.request.session[SESSION_KEY] = {}
            self.request.session.modified = True

    # ---------- Reads ----------------------------------------------------
    def get_items(self) -> list:
        """
        Returns: [{'variant': ProductVariant, 'quantity': int, 'line_total': Decimal}, ...]
        Silently drops items whose variant no longer exists or is inactive.
        """
        from catalog.models import ProductVariant  # local import to avoid app-loading cycles

        if self.user:
            cart = self._get_or_create_db_cart()
            qs = cart.items.select_related('variant', 'variant__product').all()
            results = []
            for item in qs:
                if not item.variant.is_active:
                    logger.info('Dropping inactive variant %s from DB cart', item.variant_id)
                    item.delete()
                    continue
                results.append({
                    'variant': item.variant,
                    'quantity': item.quantity,
                    'line_total': item.variant.price * item.quantity,
                })
            return results

        # Session backend
        d = _session_dict(self.request.session)
        if not d:
            return []
        variant_ids = [int(k) for k in d.keys()]
        variants = {
            v.pk: v for v in ProductVariant.objects.select_related('product').filter(
                pk__in=variant_ids, is_active=True,
            )
        }
        results = []
        stale_keys = []
        for k, qty in d.items():
            v = variants.get(int(k))
            if v is None:
                stale_keys.append(k)
                continue
            results.append({
                'variant': v,
                'quantity': qty,
                'line_total': v.price * qty,
            })
        if stale_keys:
            for k in stale_keys:
                d.pop(k, None)
            self.request.session.modified = True
            logger.info('Dropped %d stale session-cart entries', len(stale_keys))
        return results

    def get_subtotal(self) -> Decimal:
        return sum((row['line_total'] for row in self.get_items()), Decimal('0'))

    def get_item_count(self) -> int:
        return sum(row['quantity'] for row in self.get_items())

    # ---------- Merge ----------------------------------------------------
    def merge_session_to_db(self) -> None:
        """
        Called from the user_logged_in signal. Moves session cart into the user's DB cart.
        Adds quantities — never overwrites — and clears the session entry on success.
        """
        if not self.user:
            return
        session = self.request.session
        d = session.get(SESSION_KEY) or {}
        if not d:
            return

        # We need a temporary anon-style helper: walk the dict, add each item via DB path.
        cart = self._get_or_create_db_cart()
        for vid_str, qty in d.items():
            try:
                vid = int(vid_str)
                qty = int(qty)
            except (TypeError, ValueError):
                continue
            if qty < 1:
                continue
            item, created = CartItem.objects.get_or_create(
                cart=cart, variant_id=vid,
                defaults={'quantity': qty},
            )
            if not created:
                item.quantity += qty
                item.save(update_fields=['quantity'])

        session[SESSION_KEY] = {}
        session.modified = True
        logger.info('Merged session cart into user=%s cart', self.user.pk)
