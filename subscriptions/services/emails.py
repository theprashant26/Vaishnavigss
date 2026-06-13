"""
Phase 7 Group D — Subscription lifecycle emails.

Same pattern as Phase 6 (orders.services.emails): every public function
wraps EmailMultiAlternatives in a try/except so a missing template or
broken SMTP never bubbles into payment-flow control logic.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------
def _send_pair(*, subject: str, to_email: str, text_template: str,
               html_template: str, context: dict) -> None:
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


def _business_email(default=None) -> str:
    from core.models import SiteSettings
    return SiteSettings.load().email_primary or default or settings.DEFAULT_FROM_EMAIL


def _context_for(subscription, **extra) -> dict:
    """Standard context dict for every subscription email."""
    from core.models import SiteSettings
    ctx = {
        'subscription': subscription,
        'site': SiteSettings.load(),
        'site_name': settings.SITE_NAME,
        'site_domain': settings.SITE_DOMAIN,
    }
    ctx.update(extra)
    return ctx


# --------------------------------------------------------------------------
# Initial signup / renewal (dispatched from _mark_subscription_payment_paid)
# --------------------------------------------------------------------------
def send_subscription_payment_email(payment) -> None:
    """Sends INITIAL (business + customer) or RENEWAL (customer only) emails."""
    sub = payment.subscription
    ctx = _context_for(sub, payment=payment, first_delivery=sub.next_delivery)

    if payment.payment_type == payment.PaymentType.INITIAL:
        try:
            _send_pair(
                subject=f'[Subscription] New activation {sub.subscription_number} — Rs.{payment.total:.0f}',
                to_email=_business_email(),
                text_template='emails/subscription_initial_paid_business.txt',
                html_template='emails/subscription_initial_paid_business.html',
                context=ctx,
            )
        except Exception:
            logger.exception('initial_paid_business email failed for %s', sub.subscription_number)
        try:
            _send_pair(
                subject=f'Welcome aboard — {sub.plan.name}',
                to_email=sub.user.email,
                text_template='emails/subscription_initial_paid_customer.txt',
                html_template='emails/subscription_initial_paid_customer.html',
                context=ctx,
            )
        except Exception:
            logger.exception('initial_paid_customer email failed for %s', sub.subscription_number)
    else:  # RENEWAL
        try:
            _send_pair(
                subject=f'Subscription renewed — {sub.subscription_number}',
                to_email=sub.user.email,
                text_template='emails/subscription_renewed_customer.txt',
                html_template='emails/subscription_renewed_customer.html',
                context=ctx,
            )
        except Exception:
            logger.exception('renewed_customer email failed for %s', sub.subscription_number)


# --------------------------------------------------------------------------
# Lifecycle events
# --------------------------------------------------------------------------
def send_delivery_skipped_email(delivery) -> None:
    sub = delivery.subscription
    ctx = _context_for(sub, delivery=delivery)
    try:
        _send_pair(
            subject=f'Delivery skipped — {sub.subscription_number}',
            to_email=sub.user.email,
            text_template='emails/subscription_delivery_skipped_customer.txt',
            html_template='emails/subscription_delivery_skipped_customer.html',
            context=ctx,
        )
    except Exception:
        logger.exception('delivery_skipped email failed for %s', sub.subscription_number)


def send_subscription_paused_email(subscription) -> None:
    try:
        _send_pair(
            subject=f'Subscription paused — {subscription.subscription_number}',
            to_email=subscription.user.email,
            text_template='emails/subscription_paused_customer.txt',
            html_template='emails/subscription_paused_customer.html',
            context=_context_for(subscription),
        )
    except Exception:
        logger.exception('paused email failed for %s', subscription.subscription_number)


def send_subscription_resumed_email(subscription) -> None:
    try:
        _send_pair(
            subject=f'Subscription resumed — {subscription.subscription_number}',
            to_email=subscription.user.email,
            text_template='emails/subscription_resumed_customer.txt',
            html_template='emails/subscription_resumed_customer.html',
            context=_context_for(subscription),
        )
    except Exception:
        logger.exception('resumed email failed for %s', subscription.subscription_number)


def send_subscription_cancelled_email(subscription) -> None:
    try:
        _send_pair(
            subject=f'Subscription cancelled — {subscription.subscription_number}',
            to_email=subscription.user.email,
            text_template='emails/subscription_cancelled_customer.txt',
            html_template='emails/subscription_cancelled_customer.html',
            context=_context_for(subscription),
        )
    except Exception:
        logger.exception('cancelled email failed for %s', subscription.subscription_number)


def send_subscription_expired_email(subscription) -> None:
    try:
        _send_pair(
            subject=f'Subscription expired — {subscription.subscription_number}',
            to_email=subscription.user.email,
            text_template='emails/subscription_expired_customer.txt',
            html_template='emails/subscription_expired_customer.html',
            context=_context_for(subscription),
        )
    except Exception:
        logger.exception('expired email failed for %s', subscription.subscription_number)


def send_renewal_reminder_email(subscription, days_before: int) -> None:
    ctx = _context_for(subscription, days_before=days_before)
    try:
        _send_pair(
            subject=(
                f'Renew in {days_before} day{"s" if days_before != 1 else ""} — '
                f'{subscription.plan.name}'
            ),
            to_email=subscription.user.email,
            text_template='emails/subscription_renewal_reminder_customer.txt',
            html_template='emails/subscription_renewal_reminder_customer.html',
            context=ctx,
        )
    except Exception:
        logger.exception(
            'renewal_reminder (D-%d) email failed for %s',
            days_before, subscription.subscription_number,
        )
