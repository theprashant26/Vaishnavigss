import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import SubmissionBase


class SubscriptionPlan(models.Model):
    DAILY_ESSENTIALS = 'DAILY_ESSENTIALS'
    MONTHLY_PANTRY = 'MONTHLY_PANTRY'
    CURATED_BOXES = 'CURATED_BOXES'
    TIER_CHOICES = [
        (DAILY_ESSENTIALS, 'Daily Essentials'),
        (MONTHLY_PANTRY, 'Monthly Pantry'),
        (CURATED_BOXES, 'Curated Boxes'),
    ]

    DAILY = 'DAILY'
    MONTHLY = 'MONTHLY'
    QUARTERLY = 'QUARTERLY'
    ONE_TIME = 'ONE_TIME'
    CYCLE_CHOICES = [
        (DAILY, 'Daily'),
        (MONTHLY, 'Monthly'),
        (QUARTERLY, 'Quarterly'),
        (ONE_TIME, 'One-time'),
    ]

    NCR_ONLY = 'NCR_ONLY'
    PAN_INDIA = 'PAN_INDIA'
    SCOPE_CHOICES = [
        (NCR_ONLY, 'NCR only'),
        (PAN_INDIA, 'Pan-India'),
    ]

    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    whats_included = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # Phase 7: renamed from billing_cycle. Same column data; describes delivery cadence.
    delivery_frequency = models.CharField(max_length=20, choices=CYCLE_CHOICES)
    delivery_scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    image = models.ImageField(upload_to='subscriptions/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    # Phase 7 — subscription mechanics
    billing_period_days = models.PositiveIntegerField(
        default=30,
        help_text='Customer pays once every N days. 30 for monthly plans, 90 for quarterly, 0 for one-time.',
    )
    delivery_lead_days = models.PositiveIntegerField(
        default=1,
        help_text='For pan-India shipping: days between order and delivery. Daily NCR plans use 0.',
    )
    is_self_serve = models.BooleanField(
        default=True,
        help_text="If False, 'Get Started' routes to inquiry form from Phase 5 instead of real signup.",
    )

    class Meta:
        ordering = ['tier', 'display_order', 'price']

    def __str__(self):
        return f'{self.name} ({self.get_tier_display()})'

    def get_absolute_url(self):
        # TODO: wire in Phase 3
        return '#'


class SubscriptionPlanItem(models.Model):
    """What ships in each delivery for a given plan."""
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT)
    quantity_per_delivery = models.DecimalField(
        max_digits=8, decimal_places=2, default=1,
        help_text='How much of this variant per delivery',
    )
    notes = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['plan', 'display_order']
        unique_together = ('plan', 'variant')

    def __str__(self):
        return (
            f'{self.plan.name} → {self.quantity_per_delivery} × '
            f'{self.variant.product.name} ({self.variant.label})'
        )


# --------------------------------------------------------------------------
# Phase 7 — Subscription lifecycle
# --------------------------------------------------------------------------
class SubscriptionStatus(models.TextChoices):
    PENDING_PAYMENT = 'PENDING_PAYMENT', 'Pending first payment'
    ACTIVE = 'ACTIVE', 'Active'
    PAUSED = 'PAUSED', 'Paused'
    CANCELLED = 'CANCELLED', 'Cancelled'      # cancelled but period not yet ended
    EXPIRED = 'EXPIRED', 'Expired'            # period ended, not renewed
    ENDED = 'ENDED', 'Ended'                  # cancelled and period ended


class DeliveryStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Scheduled'
    OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', 'Out for delivery'
    DELIVERED = 'DELIVERED', 'Delivered'
    SKIPPED = 'SKIPPED', 'Skipped by customer'
    PAUSED = 'PAUSED', 'In pause window'
    MISSED = 'MISSED', 'Missed (not delivered)'
    REFUNDED = 'REFUNDED', 'Refunded'


class Subscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )

    subscription_number = models.CharField(max_length=30, unique=True, editable=False)
    status = models.CharField(
        max_length=30,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING_PAYMENT,
    )

    # Period tracking (current paid period)
    current_period_start = models.DateField(null=True, blank=True)
    current_period_end = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(null=True, blank=True)  # = current_period_end + 1

    # Pause tracking
    paused_until = models.DateField(null=True, blank=True)
    pause_started_at = models.DateField(null=True, blank=True)

    # Cancellation tracking
    cancel_at_period_end = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=200, blank=True)

    # Shipping address snapshot (at signup; updated via dedicated endpoint)
    shipping_recipient_name = models.CharField(max_length=100)
    shipping_phone = models.CharField(max_length=20)
    shipping_line_1 = models.CharField(max_length=200)
    shipping_line_2 = models.CharField(max_length=200, blank=True)
    shipping_landmark = models.CharField(max_length=200, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_pincode = models.CharField(max_length=10)

    # Delivery preferences
    MORNING = 'MORNING'
    EVENING = 'EVENING'
    TIME_SLOT_CHOICES = [
        (MORNING, 'Morning (6 AM – 10 AM)'),
        (EVENING, 'Evening (5 PM – 8 PM)'),
    ]
    delivery_time_slot = models.CharField(
        max_length=20, default=MORNING, choices=TIME_SLOT_CHOICES,
    )

    # Metadata
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subscription_number} — {self.plan.name}'

    def save(self, *args, **kwargs):
        if not self.subscription_number:
            today = timezone.now().date()
            prefix = f"VS-{today.strftime('%Y%m%d')}"
            count_today = Subscription.objects.filter(
                subscription_number__startswith=prefix,
            ).count() + 1
            self.subscription_number = f'{prefix}-{count_today:04d}'
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == SubscriptionStatus.ACTIVE

    @property
    def days_until_renewal(self):
        if not self.current_period_end:
            return None
        return (self.current_period_end - timezone.now().date()).days

    @property
    def next_delivery(self):
        return self.deliveries.filter(
            status=DeliveryStatus.SCHEDULED,
            scheduled_date__gte=timezone.now().date(),
        ).order_by('scheduled_date').first()


class SubscriptionDelivery(models.Model):
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name='deliveries',
    )
    scheduled_date = models.DateField()
    delivery_window = models.CharField(max_length=20, default='MORNING')
    status = models.CharField(
        max_length=30,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.SCHEDULED,
    )

    # Address snapshot at generation time
    shipping_recipient_name = models.CharField(max_length=100)
    shipping_phone = models.CharField(max_length=20)
    shipping_line_1 = models.CharField(max_length=200)
    shipping_line_2 = models.CharField(max_length=200, blank=True)
    shipping_landmark = models.CharField(max_length=200, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_pincode = models.CharField(max_length=10)

    # Outcome tracking
    delivered_at = models.DateTimeField(null=True, blank=True)
    skipped_at = models.DateTimeField(null=True, blank=True)
    skipped_by_customer = models.BooleanField(default=False)
    delivery_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'shipping_pincode']
        indexes = [
            models.Index(fields=['scheduled_date', 'status']),
            models.Index(fields=['scheduled_date', 'shipping_pincode']),
        ]

    def __str__(self):
        return f'{self.subscription.subscription_number} on {self.scheduled_date}'


class SubscriptionDeliveryItem(models.Model):
    """Snapshot of what's in this specific delivery."""
    delivery = models.ForeignKey(
        SubscriptionDelivery, on_delete=models.CASCADE, related_name='items',
    )
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)
    variant_label = models.CharField(max_length=50)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f'{self.quantity} × {self.product_name} ({self.variant_label})'


class SubscriptionPayment(models.Model):
    class PaymentType(models.TextChoices):
        INITIAL = 'INITIAL', 'Initial signup'
        RENEWAL = 'RENEWAL', 'Renewal'

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'

    subscription = models.ForeignKey(
        Subscription, on_delete=models.PROTECT, related_name='payments',
    )
    payment_number = models.CharField(max_length=30, unique=True, editable=False)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING,
    )

    # Period this payment covers
    period_start = models.DateField()
    period_end = models.DateField()

    # Money
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Razorpay
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature = models.CharField(max_length=200, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.payment_number} ({self.get_status_display()})'

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = f'VSP-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)


# --------------------------------------------------------------------------
# Phase 5 Group D — SubscriptionInquiry
# --------------------------------------------------------------------------
class SubscriptionInquiry(SubmissionBase):
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='inquiries')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_pincode = models.CharField(max_length=10, blank=True)
    start_date_preference = models.DateField(null=True, blank=True)
    message = models.TextField(blank=True)

    class Meta(SubmissionBase.Meta):
        verbose_name = 'Subscription inquiry'
        verbose_name_plural = 'Subscription inquiries'

    def __str__(self):
        return f'{self.name} — {self.plan.name}'
