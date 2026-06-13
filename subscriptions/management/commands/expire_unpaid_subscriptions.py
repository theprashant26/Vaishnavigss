"""
Phase 7 D.3 — Daily lifecycle transitions.

Two passes:
  ACTIVE + period ended + no cancel flag  → EXPIRED  (email customer)
  CANCELLED + period ended                → ENDED    (silent — already notified)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from subscriptions.models import Subscription, SubscriptionStatus
from subscriptions.services.emails import send_subscription_expired_email


class Command(BaseCommand):
    help = (
        "Mark ACTIVE subscriptions whose period ended as EXPIRED; "
        "transition CANCELLED → ENDED at period end."
    )

    def handle(self, *args, **opts):
        today = timezone.now().date()
        expired_n = 0
        ended_n = 0

        expired_qs = Subscription.objects.filter(
            status=SubscriptionStatus.ACTIVE,
            current_period_end__lt=today,
            cancel_at_period_end=False,
        ).select_related('user', 'plan')
        for sub in expired_qs:
            with transaction.atomic():
                sub.status = SubscriptionStatus.EXPIRED
                sub.save(update_fields=['status', 'updated_at'])
            self.stdout.write(f'  EXPIRED {sub.subscription_number} (user={sub.user.email})')
            send_subscription_expired_email(sub)
            expired_n += 1

        ended_qs = Subscription.objects.filter(
            status=SubscriptionStatus.CANCELLED,
            current_period_end__lt=today,
        )
        for sub in ended_qs:
            with transaction.atomic():
                sub.status = SubscriptionStatus.ENDED
                sub.save(update_fields=['status', 'updated_at'])
            self.stdout.write(f'  ENDED   {sub.subscription_number}')
            ended_n += 1

        self.stdout.write(self.style.SUCCESS(
            f'done; expired={expired_n} ended={ended_n}'
        ))
