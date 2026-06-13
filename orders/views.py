"""Phase 6 — cart + checkout + payment views."""
import json
import logging
from decimal import Decimal

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import PromoCode
from .services.cart import CartService
from .services.pricing import calculate_shipping, calculate_tax

logger = logging.getLogger(__name__)

PROMO_SESSION_KEY = 'promo_code'


def _get_session_promo(request, subtotal: Decimal):
    """Returns {'code': str, 'discount': Decimal, 'promo': PromoCode} or None."""
    code = request.session.get(PROMO_SESSION_KEY)
    if not code:
        return None
    try:
        promo = PromoCode.objects.get(code=code, is_active=True)
    except PromoCode.DoesNotExist:
        request.session.pop(PROMO_SESSION_KEY, None)
        return None
    ok, _ = promo.is_valid(subtotal)
    if not ok:
        request.session.pop(PROMO_SESSION_KEY, None)
        return None
    return {
        'code': promo.code,
        'discount': promo.calculate_discount(subtotal),
        'promo': promo,
    }


# --------------------------------------------------------------------------
# Cart page (Group B.1)
# --------------------------------------------------------------------------
def cart(request):
    svc = CartService(request)
    items = svc.get_items()
    subtotal = svc.get_subtotal()

    pincode = request.session.get('shipping_pincode', '')
    shipping = calculate_shipping(subtotal, pincode)
    promo = _get_session_promo(request, subtotal)
    discount = promo['discount'] if promo else Decimal('0')
    tax = calculate_tax(items)
    total = subtotal - discount + shipping + tax

    # "Add ₹X more for free shipping" hint
    from core.models import SiteSettings
    threshold = SiteSettings.load().free_shipping_threshold
    free_ship_remaining = max(Decimal('0'), threshold - subtotal) if subtotal < threshold else Decimal('0')

    return render(request, 'orders/cart.html', {
        'items': items,
        'subtotal': subtotal,
        'shipping': shipping,
        'discount': discount,
        'promo': promo,
        'tax': tax,
        'total': total,
        'free_ship_remaining': free_ship_remaining,
        'free_ship_threshold': threshold,
    })


# --------------------------------------------------------------------------
# AJAX endpoints (Group B.2)
# --------------------------------------------------------------------------
def _cart_summary(svc):
    """Tiny payload used by every AJAX response."""
    return {
        'cart_item_count': svc.get_item_count(),
        'cart_subtotal': str(svc.get_subtotal()),
    }


@require_POST
def cart_api_add(request):
    from catalog.models import ProductVariant
    try:
        variant_id = int(request.POST.get('variant_id') or 0)
        quantity = int(request.POST.get('quantity') or 1)
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid input'}, status=400)

    if variant_id <= 0 or quantity <= 0:
        return JsonResponse({'ok': False, 'error': 'Invalid input'}, status=400)

    variant = get_object_or_404(ProductVariant, pk=variant_id, is_active=True)
    if variant.stock_quantity < quantity:
        return JsonResponse({'ok': False, 'error': 'Not enough stock'}, status=400)

    svc = CartService(request)
    svc.add(variant_id, quantity)
    logger.info('Cart add variant=%s qty=%s anon=%s', variant_id, quantity, request.user.is_anonymous)
    return JsonResponse({'ok': True, **_cart_summary(svc), 'variant_name': f'{variant.product.name} ({variant.label})'})


@require_POST
def cart_api_update(request):
    try:
        variant_id = int(request.POST.get('variant_id') or 0)
        quantity = int(request.POST.get('quantity') or 0)
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid input'}, status=400)

    if variant_id <= 0:
        return JsonResponse({'ok': False, 'error': 'Invalid input'}, status=400)

    svc = CartService(request)
    svc.update(variant_id, quantity)
    return JsonResponse({'ok': True, **_cart_summary(svc)})


@require_POST
def cart_api_remove(request):
    try:
        variant_id = int(request.POST.get('variant_id') or 0)
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid input'}, status=400)

    if variant_id <= 0:
        return JsonResponse({'ok': False, 'error': 'Invalid input'}, status=400)

    svc = CartService(request)
    svc.remove(variant_id)
    return JsonResponse({'ok': True, **_cart_summary(svc)})


@require_POST
def cart_api_bulk_add(request):
    """
    Migration endpoint. Body: {"items": {"<variant_id>": <qty>, ...}}.
    Silently drops items that don't map to a live, active variant.
    """
    from catalog.models import ProductVariant
    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'invalid json'}, status=400)

    items = body.get('items') or {}
    if not isinstance(items, dict):
        return JsonResponse({'ok': False, 'error': 'items must be an object'}, status=400)

    svc = CartService(request)
    added = 0
    for vid_str, qty in items.items():
        try:
            vid = int(vid_str)
            qty = int(qty)
        except (TypeError, ValueError):
            continue
        if qty < 1:
            continue
        if not ProductVariant.objects.filter(pk=vid, is_active=True).exists():
            continue
        svc.add(vid, qty)
        added += 1

    logger.info('Bulk-add migrated %d items (anon=%s)', added, request.user.is_anonymous)
    return JsonResponse({'ok': True, **_cart_summary(svc), 'added': added})


# --------------------------------------------------------------------------
# Promo apply / remove (Group B.3)
# --------------------------------------------------------------------------
@require_POST
def cart_apply_promo(request):
    code = (request.POST.get('code') or '').strip().upper()
    subtotal = CartService(request).get_subtotal()
    try:
        promo = PromoCode.objects.get(code=code, is_active=True)
    except PromoCode.DoesNotExist:
        messages.error(request, 'Invalid promo code.')
        return redirect('orders:cart')

    ok, err = promo.is_valid(subtotal)
    if not ok:
        messages.error(request, err or 'This promo cannot be applied right now.')
        return redirect('orders:cart')

    request.session[PROMO_SESSION_KEY] = code
    messages.success(request, f'Promo applied: {code}')
    return redirect('orders:cart')


@require_POST
def cart_remove_promo(request):
    request.session.pop(PROMO_SESSION_KEY, None)
    messages.success(request, 'Promo removed.')
    return redirect('orders:cart')


# --------------------------------------------------------------------------
# Checkout — 3-step flow (Group C)
# --------------------------------------------------------------------------
from django.contrib.auth.decorators import login_required
from django.db import transaction

from accounts.forms import AddressForm
from accounts.models import Address

from .models import (
    Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus,
)

CHECKOUT_ADDRESS_KEY = 'checkout_address_id'
CHECKOUT_PAYMENT_KEY = 'checkout_payment_method'


def _empty_cart_redirect():
    """Redirect anyone in checkout with an empty cart back to the cart page."""
    return redirect('orders:cart')


@login_required
def checkout(request):
    """Legacy entry point — kicks user into step 1."""
    return redirect('orders:checkout_address')


@login_required
def checkout_address(request):
    svc = CartService(request)
    if svc.get_item_count() == 0:
        messages.info(request, 'Your cart is empty.')
        return _empty_cart_redirect()

    addresses = list(request.user.addresses.all().order_by('-is_default', '-updated_at'))

    if request.method == 'POST':
        # Two POST paths: pick an existing address, or add a new one.
        if 'new_address' in request.POST:
            form = AddressForm(request.POST)
            if form.is_valid():
                address = form.save(commit=False)
                address.user = request.user
                if not addresses:
                    address.is_default = True
                address.save()
                request.session[CHECKOUT_ADDRESS_KEY] = address.pk
                return redirect('orders:checkout_payment')
        else:
            try:
                address_id = int(request.POST.get('address_id') or 0)
            except (TypeError, ValueError):
                address_id = 0
            if not Address.objects.filter(pk=address_id, user=request.user).exists():
                messages.error(request, 'Please choose a shipping address.')
                return redirect('orders:checkout_address')
            request.session[CHECKOUT_ADDRESS_KEY] = address_id
            return redirect('orders:checkout_payment')
        # POST-with-form-errors path falls through to render below
    else:
        form = AddressForm()

    return render(request, 'orders/checkout_address.html', {
        'step': 1,
        'addresses': addresses,
        'form': form,
        'selected_address_id': request.session.get(CHECKOUT_ADDRESS_KEY),
    })


@login_required
def checkout_payment(request):
    svc = CartService(request)
    if svc.get_item_count() == 0:
        return _empty_cart_redirect()
    if not request.session.get(CHECKOUT_ADDRESS_KEY):
        return redirect('orders:checkout_address')

    if request.method == 'POST':
        method = request.POST.get('payment_method')
        if method not in {PaymentMethod.RAZORPAY, PaymentMethod.COD}:
            messages.error(request, 'Please pick a payment method.')
            return redirect('orders:checkout_payment')
        request.session[CHECKOUT_PAYMENT_KEY] = method
        return redirect('orders:checkout_review')

    return render(request, 'orders/checkout_payment.html', {
        'step': 2,
        'methods': PaymentMethod.choices,
        'selected_method': request.session.get(CHECKOUT_PAYMENT_KEY),
    })


def _build_review_context(request):
    """Compute everything review needs. Reused by GET and POST branches."""
    from core.models import SiteSettings
    svc = CartService(request)
    items = svc.get_items()
    subtotal = svc.get_subtotal()
    address = Address.objects.filter(
        pk=request.session.get(CHECKOUT_ADDRESS_KEY),
        user=request.user,
    ).first()
    pincode = address.pincode if address else ''
    shipping = calculate_shipping(subtotal, pincode)
    promo = _get_session_promo(request, subtotal)
    discount = promo['discount'] if promo else Decimal('0')
    tax = calculate_tax(items)
    total = subtotal - discount + shipping + tax
    payment_method = request.session.get(CHECKOUT_PAYMENT_KEY)
    return {
        'items': items,
        'subtotal': subtotal,
        'shipping': shipping,
        'discount': discount,
        'promo': promo,
        'tax': tax,
        'total': total,
        'address': address,
        'payment_method': payment_method,
    }


@login_required
def checkout_review(request):
    svc = CartService(request)
    if svc.get_item_count() == 0:
        return _empty_cart_redirect()
    if not request.session.get(CHECKOUT_ADDRESS_KEY):
        return redirect('orders:checkout_address')
    if not request.session.get(CHECKOUT_PAYMENT_KEY):
        return redirect('orders:checkout_payment')

    ctx = _build_review_context(request)
    if ctx['address'] is None:
        return redirect('orders:checkout_address')

    # Re-check stock for each cart line. Block placement if anything ran out.
    stock_errors = []
    for row in ctx['items']:
        v = row['variant']
        if v.stock_quantity < row['quantity']:
            stock_errors.append(f'{v.product.name} ({v.label}) — only {v.stock_quantity} left')

    if request.method == 'POST' and not stock_errors:
        order = _place_order(request, ctx, request.POST.get('customer_notes', ''))
        # Route based on payment method
        if order.payment_method == PaymentMethod.RAZORPAY:
            return redirect('orders:checkout_pay', order_number=order.order_number)
        # COD branch
        try:
            from .services.emails import send_order_placed_email
            send_order_placed_email(order)
        except Exception:
            logger.exception('Order-placed email failed for %s', order.order_number)
        return redirect('orders:checkout_success', order_number=order.order_number)

    return render(request, 'orders/checkout_review.html', {
        'step': 3,
        'stock_errors': stock_errors,
        **ctx,
    })


def _place_order(request, ctx, customer_notes: str) -> Order:
    """Create Order + OrderItems atomically. Clears cart + session keys on success."""
    addr = ctx['address']
    items = ctx['items']
    with transaction.atomic():
        order = Order.objects.create(
            user=request.user,
            payment_method=ctx['payment_method'],
            status=OrderStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            shipping_recipient_name=addr.recipient_name,
            shipping_phone=addr.recipient_phone,
            shipping_line_1=addr.line_1,
            shipping_line_2=addr.line_2,
            shipping_landmark=addr.landmark,
            shipping_city=addr.city,
            shipping_state=addr.state,
            shipping_pincode=addr.pincode,
            subtotal=ctx['subtotal'],
            discount=ctx['discount'],
            promo_code=(ctx['promo']['code'] if ctx['promo'] else ''),
            shipping_charge=ctx['shipping'],
            tax_amount=ctx['tax'],
            total=ctx['total'],
            customer_notes=customer_notes,
        )
        for row in items:
            v = row['variant']
            p = v.product
            unit_price = v.price
            qty = row['quantity']
            rate = p.gst_rate or Decimal('0')
            line_subtotal = (unit_price * qty).quantize(Decimal('0.01'))
            line_tax = (line_subtotal * rate / Decimal('100')).quantize(Decimal('0.01'))
            OrderItem.objects.create(
                order=order,
                product=p,
                variant=v,
                product_name=p.name,
                variant_label=v.label,
                hsn_code=p.hsn_code or '',
                unit_price=unit_price,
                gst_rate=rate,
                quantity=qty,
                line_subtotal=line_subtotal,
                line_tax=line_tax,
                line_total=line_subtotal + line_tax,
            )

        # Clear cart + session checkout state
        CartService(request).clear()
        request.session.pop(CHECKOUT_ADDRESS_KEY, None)
        request.session.pop(CHECKOUT_PAYMENT_KEY, None)
        request.session.pop(PROMO_SESSION_KEY, None)
    logger.info('Order placed: %s (method=%s, total=Rs.%s)', order.order_number, order.payment_method, order.total)
    return order


@login_required
def checkout_success(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    return render(request, 'orders/checkout_success.html', {'order': order})


# --------------------------------------------------------------------------
# Razorpay payment flow (Group D)
# --------------------------------------------------------------------------
from django.conf import settings
from django.db.models import F
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone as dj_timezone
from django.views.decorators.csrf import csrf_exempt

from .services import razorpay_client


@login_required
def checkout_pay(request, order_number):
    """
    Renders the Razorpay-modal launcher page. We create the Razorpay order
    lazily on first GET (one Razorpay order per local Order). After the user
    pays via the modal, their browser POSTs the signature back to `checkout_callback`.
    """
    order = get_object_or_404(Order, order_number=order_number, user=request.user)

    if order.payment_status == PaymentStatus.COMPLETED:
        return redirect('orders:checkout_success', order_number=order.order_number)
    if order.payment_method != PaymentMethod.RAZORPAY:
        return redirect('orders:checkout_success', order_number=order.order_number)

    if not order.razorpay_order_id:
        try:
            rzp_order = razorpay_client.create_order(
                amount_paise=int(order.total * 100),
                receipt=order.order_number,
                notes={'order_number': order.order_number, 'user_id': str(request.user.pk)},
            )
        except razorpay_client.RazorpayError as e:
            logger.error('create_order failed for %s: %s', order.order_number, e)
            messages.error(request, 'We could not start the payment. Please try again or contact support.')
            return redirect('orders:checkout_failed')
        order.razorpay_order_id = rzp_order['id']
        order.save(update_fields=['razorpay_order_id', 'updated_at'])

    return render(request, 'orders/checkout_pay.html', {
        'order': order,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'callback_url': request.build_absolute_uri(reverse('orders:checkout_callback')),
    })


@require_POST
@csrf_exempt  # Razorpay's checkout.js POSTs from their domain into ours
def checkout_callback(request):
    rzp_order_id = (request.POST.get('razorpay_order_id') or '').strip()
    rzp_payment_id = (request.POST.get('razorpay_payment_id') or '').strip()
    rzp_signature = (request.POST.get('razorpay_signature') or '').strip()

    try:
        order = Order.objects.get(razorpay_order_id=rzp_order_id)
    except Order.DoesNotExist:
        logger.warning('Callback for unknown Razorpay order id=%s',
                       razorpay_client._mask(rzp_order_id))
        return redirect('orders:checkout_failed')

    if not razorpay_client.verify_payment_signature(rzp_order_id, rzp_payment_id, rzp_signature):
        logger.error('Payment signature mismatch for order %s', order.order_number)
        order.payment_status = PaymentStatus.FAILED
        order.save(update_fields=['payment_status', 'updated_at'])
        return redirect('orders:checkout_failed')

    _mark_order_paid(order, rzp_payment_id, rzp_signature)
    return redirect('orders:checkout_success', order_number=order.order_number)


@require_POST
@csrf_exempt
def webhook_razorpay(request):
    """Server-to-server webhook. Critical fallback for when the browser tab is closed."""
    signature = request.headers.get('X-Razorpay-Signature', '')
    if not razorpay_client.verify_webhook_signature(request.body, signature):
        return HttpResponseForbidden('Bad signature')

    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return HttpResponseForbidden('Bad JSON')

    event = payload.get('event', '')
    logger.info('Razorpay webhook received: event=%s', event)

    if event == 'payment.captured':
        try:
            payment = payload['payload']['payment']['entity']
            rzp_order_id = payment['order_id']
            rzp_payment_id = payment.get('id', '')
        except (KeyError, TypeError):
            logger.error('Webhook payload missing payment.entity.order_id')
            return HttpResponse('OK')

        # Dispatch: Order first, then SubscriptionPayment. Both look up by
        # razorpay_order_id, both have idempotent _mark_*_paid helpers.
        try:
            order = Order.objects.get(razorpay_order_id=rzp_order_id)
        except Order.DoesNotExist:
            order = None

        if order is not None:
            if order.payment_status != PaymentStatus.COMPLETED:
                _mark_order_paid(order, rzp_payment_id, '')
        else:
            from subscriptions.models import SubscriptionPayment
            try:
                sub_payment = SubscriptionPayment.objects.get(
                    razorpay_order_id=rzp_order_id,
                )
            except SubscriptionPayment.DoesNotExist:
                logger.warning(
                    'Webhook for unknown razorpay_order_id=%s (neither Order nor SubscriptionPayment)',
                    razorpay_client._mask(rzp_order_id),
                )
                return HttpResponse('OK')
            from subscriptions.views import _mark_subscription_payment_paid
            if sub_payment.status != SubscriptionPayment.PaymentStatus.COMPLETED:
                _mark_subscription_payment_paid(sub_payment, rzp_payment_id, '')

    elif event == 'payment.failed':
        try:
            payment = payload['payload']['payment']['entity']
            logger.info('Webhook payment.failed: order=%s reason=%s',
                        razorpay_client._mask(payment.get('order_id', '')),
                        payment.get('error_description', ''))
        except (KeyError, TypeError):
            pass

    return HttpResponse('OK')


def _mark_order_paid(order: Order, payment_id: str, signature: str) -> None:
    """
    Idempotent paid-state transition.
    Wrapped in a transaction + select_for_update to handle the
    browser-callback-vs-webhook race.
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status == PaymentStatus.COMPLETED:
            return  # already done — webhook or callback already ran

        order.razorpay_payment_id = payment_id
        order.razorpay_signature = signature
        order.payment_status = PaymentStatus.COMPLETED
        order.status = OrderStatus.PAID
        order.paid_at = dj_timezone.now()
        order.save(update_fields=[
            'razorpay_payment_id', 'razorpay_signature',
            'payment_status', 'status', 'paid_at', 'updated_at',
        ])

        # Stock decrement
        from catalog.models import ProductVariant
        for item in order.items.select_related('variant'):
            ProductVariant.objects.filter(pk=item.variant_id).update(
                stock_quantity=F('stock_quantity') - item.quantity,
            )

        # Promo usage bump
        if order.promo_code:
            PromoCode.objects.filter(code=order.promo_code).update(
                uses_count=F('uses_count') + 1,
            )

    logger.info('Order %s marked PAID. payment_id=%s', order.order_number,
                razorpay_client._mask(payment_id))

    # Email is best-effort (outside the txn so no locks held).
    try:
        from .services.emails import send_order_paid_email
        send_order_paid_email(order)
    except Exception:
        logger.exception('Order-paid email failed for %s', order.order_number)


def checkout_failed(request):
    return render(request, 'orders/checkout_failed.html')


# --------------------------------------------------------------------------
# GST Invoice (Group E.5)
# --------------------------------------------------------------------------
from collections import OrderedDict

from django.http import Http404


@login_required
def invoice(request, order_number):
    order = get_object_or_404(Order.objects.prefetch_related('items'), order_number=order_number)
    if order.user_id != request.user.pk and not request.user.is_staff:
        raise Http404()

    # Invoice valid after payment for online orders. COD invoices always available.
    if order.payment_method != PaymentMethod.COD and order.payment_status != PaymentStatus.COMPLETED:
        return HttpResponseForbidden('Invoice available only after payment is confirmed.')

    # Tax break-up by rate, for the GST summary box.
    breakdown = OrderedDict()
    for item in order.items.all():
        key = item.gst_rate
        b = breakdown.setdefault(key, {'taxable': Decimal('0'), 'tax': Decimal('0')})
        b['taxable'] += item.line_subtotal
        b['tax'] += item.line_tax

    from core.models import SiteSettings
    return render(request, 'orders/invoice.html', {
        'order': order,
        'site': SiteSettings.load(),
        'tax_breakdown': breakdown,
    })
