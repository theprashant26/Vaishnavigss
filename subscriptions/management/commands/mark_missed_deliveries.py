"""
Phase 7 D.5 — Flag past-dated SCHEDULED deliveries as MISSED.

Anything left in SCHEDULED after its scheduled_date passes means the
delivery team forgot to mark it. The roster surfaces these so they
can be reconciled the next morning.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from subscriptions.models import DeliveryStatus, SubscriptionDelivery


class Command(BaseCommand):
    help = "Mark SCHEDULED deliveries whose date has passed as MISSED."

    def handle(self, *args, **opts):
        yesterday = timezone.now().date() - timedelta(days=1)
        qs = SubscriptionDelivery.objects.filter(
            status=DeliveryStatus.SCHEDULED,
            scheduled_date__lte=yesterday,
        )
        count = qs.count()
        if count:
            qs.update(status=DeliveryStatus.MISSED)
            self.stdout.write(self.style.WARNING(
                f'Marked {count} delivery/deliveries as MISSED (scheduled on or before {yesterday}).'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('No missed deliveries.'))
