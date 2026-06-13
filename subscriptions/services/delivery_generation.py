"""
Phase 7 — Subscription delivery generation.

Pure functions. Idempotent: rerunning never duplicates rows because each
SubscriptionDelivery insert is gated on (subscription, scheduled_date).
"""
import logging
from datetime import timedelta

from ..models import (
    DeliveryStatus,
    SubscriptionDelivery,
    SubscriptionDeliveryItem,
    SubscriptionPlan,
)

logger = logging.getLogger(__name__)


def generate_deliveries(subscription, period_start, period_end):
    """Create SubscriptionDelivery rows for [period_start, period_end] inclusive.

    Idempotent — skips dates that already have a delivery for this subscription,
    so it's safe to call from both the browser callback and webhook paths.
    """
    plan = subscription.plan
    items = list(plan.items.select_related('variant__product'))
    if not items:
        logger.warning(
            'Subscription %s plan %s has no items defined; '
            'skipping delivery generation.',
            subscription.subscription_number, plan.slug,
        )
        return 0

    dates = _compute_delivery_dates(plan, period_start, period_end)
    created = 0
    for d in dates:
        if SubscriptionDelivery.objects.filter(
            subscription=subscription, scheduled_date=d,
        ).exists():
            continue
        delivery = SubscriptionDelivery.objects.create(
            subscription=subscription,
            scheduled_date=d,
            delivery_window=subscription.delivery_time_slot,
            status=DeliveryStatus.SCHEDULED,
            shipping_recipient_name=subscription.shipping_recipient_name,
            shipping_phone=subscription.shipping_phone,
            shipping_line_1=subscription.shipping_line_1,
            shipping_line_2=subscription.shipping_line_2,
            shipping_landmark=subscription.shipping_landmark,
            shipping_city=subscription.shipping_city,
            shipping_state=subscription.shipping_state,
            shipping_pincode=subscription.shipping_pincode,
        )
        for item in items:
            SubscriptionDeliveryItem.objects.create(
                delivery=delivery,
                variant=item.variant,
                product_name=item.variant.product.name,
                variant_label=item.variant.label,
                quantity=item.quantity_per_delivery,
            )
        created += 1
    logger.info(
        'Generated %d delivery row(s) for %s in [%s, %s]',
        created, subscription.subscription_number, period_start, period_end,
    )
    return created


def _compute_delivery_dates(plan, period_start, period_end):
    """Return the list of dates a delivery should be scheduled on.

    Inclusive of both bounds. Cadence comes from the plan's `delivery_frequency`.
    """
    freq = plan.delivery_frequency
    if freq == SubscriptionPlan.DAILY:
        span = (period_end - period_start).days
        return [period_start + timedelta(days=i) for i in range(span + 1)]
    if freq == 'WEEKLY':  # not in choices today, future-proofing
        out, i = [], 0
        while period_start + timedelta(weeks=i) <= period_end:
            out.append(period_start + timedelta(weeks=i))
            i += 1
        return out
    if freq == SubscriptionPlan.MONTHLY:
        # One delivery on day-5 of the period (gives time to dispatch).
        d = period_start + timedelta(days=5)
        return [d] if d <= period_end else [period_start]
    if freq == SubscriptionPlan.QUARTERLY:
        # 3 deliveries: one per month within the 90-day window.
        candidates = [
            period_start + timedelta(days=5),
            period_start + timedelta(days=35),
            period_start + timedelta(days=65),
        ]
        return [d for d in candidates if d <= period_end]
    if freq == SubscriptionPlan.ONE_TIME:
        return [period_start + timedelta(days=plan.delivery_lead_days)]
    return []
