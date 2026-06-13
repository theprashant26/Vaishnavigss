from django.db import models

from core.models import SubmissionBase


class Service(models.Model):
    ADOPTION = 'ADOPTION'
    VISIT = 'VISIT'
    WHOLESALE = 'WHOLESALE'
    HAMPER = 'HAMPER'
    OTHER = 'OTHER'
    TYPE_CHOICES = [
        (ADOPTION, 'Cow Adoption'),
        (VISIT, 'Gaushala Visit'),
        (WHOLESALE, 'Bulk / Wholesale'),
        (HAMPER, 'Custom Hamper'),
        (OTHER, 'Other'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    service_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    short_description = models.CharField(max_length=300)
    description = models.TextField()
    price_display = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return '#'


# --------------------------------------------------------------------------
# Phase 5 Group C — 4 inquiry types
# --------------------------------------------------------------------------
class AdoptionInquiry(SubmissionBase):
    class PlanInterest(models.TextChoices):
        MONTHLY = 'MONTHLY', 'Monthly (₹3,000/month)'
        YEARLY = 'YEARLY', 'Yearly (₹35,000/year)'
        ONE_TIME = 'ONE_TIME', 'One-time contribution'
        UNSURE = 'UNSURE', 'Not sure yet'

    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    preferred_cow = models.ForeignKey(
        'catalog.Cow', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    preferred_breed = models.ForeignKey(
        'catalog.Breed', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    plan_interest = models.CharField(
        max_length=20, choices=PlanInterest.choices, default=PlanInterest.UNSURE,
    )
    message = models.TextField(blank=True)

    class Meta(SubmissionBase.Meta):
        verbose_name = 'Adoption inquiry'
        verbose_name_plural = 'Adoption inquiries'

    def __str__(self):
        return f'{self.name} — {self.get_plan_interest_display()}'


class WholesaleInquiry(SubmissionBase):
    class Volume(models.TextChoices):
        SMALL = 'SMALL', 'Up to ₹50,000 / month'
        MEDIUM = 'MEDIUM', '₹50,000 – ₹2,00,000 / month'
        LARGE = 'LARGE', 'Above ₹2,00,000 / month'

    business_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    gstin = models.CharField(max_length=20, blank=True)
    expected_volume = models.CharField(max_length=20, choices=Volume.choices)
    products_interested = models.CharField(
        max_length=500,
        help_text='Free text — products of interest',
    )
    delivery_city = models.CharField(max_length=100, blank=True)
    message = models.TextField(blank=True)

    class Meta(SubmissionBase.Meta):
        verbose_name = 'Wholesale inquiry'
        verbose_name_plural = 'Wholesale inquiries'

    def __str__(self):
        return f'{self.business_name} — {self.contact_name}'


class HamperInquiry(SubmissionBase):
    class Occasion(models.TextChoices):
        WEDDING = 'WEDDING', 'Wedding'
        POOJA = 'POOJA', 'Pooja / religious occasion'
        FESTIVAL = 'FESTIVAL', 'Festival gifting'
        CORPORATE = 'CORPORATE', 'Corporate gifting'
        PERSONAL = 'PERSONAL', 'Personal gift'
        OTHER = 'OTHER', 'Other'

    class BudgetRange(models.TextChoices):
        UNDER_2K = 'UNDER_2K', 'Under ₹2,000 per hamper'
        TWO_FIVE = 'TWO_FIVE', '₹2,000 – ₹5,000'
        FIVE_TEN = 'FIVE_TEN', '₹5,000 – ₹10,000'
        ABOVE_TEN = 'ABOVE_TEN', 'Above ₹10,000'

    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    occasion = models.CharField(max_length=20, choices=Occasion.choices)
    budget_range = models.CharField(max_length=20, choices=BudgetRange.choices)
    quantity = models.PositiveIntegerField(default=1, help_text='Number of hampers needed')
    delivery_date = models.DateField(null=True, blank=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    message = models.TextField(blank=True)

    class Meta(SubmissionBase.Meta):
        verbose_name = 'Hamper inquiry'
        verbose_name_plural = 'Hamper inquiries'

    def __str__(self):
        return f'{self.name} — {self.get_occasion_display()} ({self.quantity})'


class VisitBooking(SubmissionBase):
    class VisitStatus(models.TextChoices):
        NEW = 'NEW', 'New'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        NO_SHOW = 'NO_SHOW', 'No-show'

    # Override status from SubmissionBase with visit-specific choices.
    status = models.CharField(
        max_length=20, choices=VisitStatus.choices, default=VisitStatus.NEW,
    )

    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    preferred_date = models.DateField()
    alternate_date = models.DateField(null=True, blank=True)
    party_size = models.PositiveIntegerField(default=1)
    has_children = models.BooleanField(default=False)
    special_requests = models.TextField(blank=True)

    class Meta(SubmissionBase.Meta):
        verbose_name = 'Visit booking'
        verbose_name_plural = 'Visit bookings'

    def __str__(self):
        return f'{self.name} on {self.preferred_date}'
