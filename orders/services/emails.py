"""
Phase 6 Group E — order lifecycle emails.

Spec says: don't use signals. Call these explicitly from views / admin actions
so duplicates are obvious in the call graph.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _send_pair(*, subject: str, to_email: str, text_template: str, html_template: str, context: dict):
    text_body = render_to_string(text_template, context)
    html_body = render_to_string(html_template, context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)


def _context_for(order):
    """Standard context dict for every order email."""
    from core.models import SiteSettings
    site = SiteSettings.load()
    return {
        'order': order,
        'site': site,
        'site_name': settings.SITE_NAME,
        'site_domain': settings.SITE_DOMAIN,
    }


def _business_email(default=None) -> str:
    from core.models import SiteSettings
    return SiteSettings.load().email_primary or default or settings.DEFAULT_FROM_EMAIL


def send_order_placed_email(order) -> None:
    """Sent on COD placement (Razorpay-paid orders get send_order_paid_email instead)."""
    ctx = _context_for(order)
    # Business notification
    try:
        _send_pair(
            subject=f'[Order] New COD order {order.order_number} — Rs.{order.total:.0f}',
            to_email=_business_email(),
            text_template='emails/order_placed_business.txt',
            html_template='emails/order_placed_business.html',
            context=ctx,
        )
    except Exception:
        logger.exception('order_placed_business email failed for %s', order.order_number)

    # Customer confirmation
    try:
        _send_pair(
            subject=f'Order received — {order.order_number}',
            to_email=order.user.email,
            text_template='emails/order_placed_customer.txt',
            html_template='emails/order_placed_customer.html',
            context=ctx,
        )
    except Exception:
        logger.exception('order_placed_customer email failed for %s', order.order_number)


def send_order_paid_email(order) -> None:
    """Sent on successful Razorpay capture (via callback or webhook)."""
    ctx = _context_for(order)
    try:
        _send_pair(
            subject=f'[Order] Payment received {order.order_number} — Rs.{order.total:.0f}',
            to_email=_business_email(),
            text_template='emails/order_paid_business.txt',
            html_template='emails/order_paid_business.html',
            context=ctx,
        )
    except Exception:
        logger.exception('order_paid_business email failed for %s', order.order_number)

    try:
        _send_pair(
            subject=f'Payment confirmed — {order.order_number}',
            to_email=order.user.email,
            text_template='emails/order_paid_customer.txt',
            html_template='emails/order_paid_customer.html',
            context=ctx,
        )
    except Exception:
        logger.exception('order_paid_customer email failed for %s', order.order_number)


def send_order_shipped_email(order) -> None:
    """Sent when admin marks an order shipped."""
    ctx = _context_for(order)
    try:
        _send_pair(
            subject=f'On its way — {order.order_number}',
            to_email=order.user.email,
            text_template='emails/order_shipped_customer.txt',
            html_template='emails/order_shipped_customer.html',
            context=ctx,
        )
    except Exception:
        logger.exception('order_shipped_customer email failed for %s', order.order_number)


def send_order_delivered_email(order) -> None:
    """Sent when admin marks an order delivered."""
    ctx = _context_for(order)
    try:
        _send_pair(
            subject=f'Delivered — {order.order_number}',
            to_email=order.user.email,
            text_template='emails/order_delivered_customer.txt',
            html_template='emails/order_delivered_customer.html',
            context=ctx,
        )
    except Exception:
        logger.exception('order_delivered_customer email failed for %s', order.order_number)
