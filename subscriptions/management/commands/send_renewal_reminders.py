"""
Phase 7 D.2 — Send renewal reminders D-5 / D-3 / D-1 before period_end.

Idempotent via a cache key per (subscription, days_before). Safe to re-run
within the same day; safe to run multiple times across the 5/3/1 window
without duplicate sends.
"""
from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from subscriptions.models import Subscription, SubscriptionStatus
from subscriptions.services.emails import send_renewal_reminder_email


REMINDER_OFFSETS = [5, 3, 1]
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days — well past the last reminder window


class Command(BaseCommand):
    help = (
        "Send renewal reminders to active, not-cancelled subscriptions "
        "whose period ends in 5, 3, or 1 days. Idempotent via cache key."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be sent without emailing or marking sent.',
        )

    def handle(self, *args, **opts):
        today = timezone.now().date()
        total_sent = 0
        for days_before in REMINDER_OFFSETS:
            target_date = today + timedelta(days=days_before)
            subs = Subscription.objects.filter(
                status=SubscriptionStatus.ACTIVE,
                cancel_at_period_end=False,
                current_period_end=target_date,
            ).select_related('user', 'plan')

            for sub in subs:
                key = f'renewal_reminder:{sub.subscription_number}:{days_before}'
                if cache.get(key):
                    self.stdout.write(
                        f'  skip {sub.subscription_number} D-{days_before} (already sent)'
                    )
                    continue
                if opts['dry_run']:
                    self.stdout.write(
                        f'  [dry-run] would send D-{days_before} to {sub.user.email} '
                        f'for {sub.subscription_number}'
                    )
                    continue
                send_renewal_reminder_email(sub, days_before)
                cache.set(key, '1', timeout=CACHE_TTL_SECONDS)
                total_sent += 1
                self.stdout.write(
                    f'  sent D-{days_before} reminder to {sub.user.email} '
                    f'for {sub.subscription_number}'
                )
        self.stdout.write(self.style.SUCCESS(f'done; sent={total_sent}'))
