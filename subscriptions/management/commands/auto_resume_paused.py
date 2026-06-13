"""
Phase 7 D.4 — Auto-resume PAUSED subscriptions whose paused_until has passed.

Restores PAUSED deliveries dated today or later to SCHEDULED (deliveries
that fell entirely inside the pause window were already counted toward
the period extension done at pause-time, so no further math is needed).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from subscriptions.models import DeliveryStatus, Subscription, SubscriptionStatus
from subscriptions.services.emails import send_subscription_resumed_email


class Command(BaseCommand):
    help = "Auto-resume PAUSED subscriptions whose paused_until date has passed."

    def handle(self, *args, **opts):
        today = timezone.now().date()
        resumed_n = 0

        paused_qs = Subscription.objects.filter(
            status=SubscriptionStatus.PAUSED,
            paused_until__lt=today,
        ).select_related('user', 'plan')

        for sub in paused_qs:
            with transaction.atomic():
                # Restore any still-PAUSED future deliveries to SCHEDULED.
                sub.deliveries.filter(
                    status=DeliveryStatus.PAUSED,
                    scheduled_date__gte=today,
                ).update(status=DeliveryStatus.SCHEDULED)

                sub.status = SubscriptionStatus.ACTIVE
                sub.pause_started_at = None
                sub.paused_until = None
                sub.save(update_fields=[
                    'status', 'pause_started_at', 'paused_until', 'updated_at',
                ])
            self.stdout.write(f'  RESUMED {sub.subscription_number}')
            send_subscription_resumed_email(sub)
            resumed_n += 1

        self.stdout.write(self.style.SUCCESS(f'done; resumed={resumed_n}'))
