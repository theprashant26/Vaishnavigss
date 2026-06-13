import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# --------------------------------------------------------------------------
# Submission base (Phase 5) — shared by every inquiry/submission model.
# --------------------------------------------------------------------------
class SubmissionStatus(models.TextChoices):
    NEW = 'NEW', 'New'
    CONTACTED = 'CONTACTED', 'Contacted'
    RESOLVED = 'RESOLVED', 'Resolved'
    SPAM = 'SPAM', 'Spam'


class SubmissionBase(models.Model):
    """Abstract base for every inquiry/submission. Subclasses add their own fields."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    status = models.CharField(
        max_length=20,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.NEW,
    )
    internal_notes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class Testimonial(models.Model):
    customer_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, blank=True)
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    content = models.TextField()
    photo = models.ImageField(upload_to='testimonials/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return f'{self.customer_name} ({self.rating}★)'


class FAQ(models.Model):
    GENERAL = 'GENERAL'
    PRODUCTS = 'PRODUCTS'
    DELIVERY = 'DELIVERY'
    SUBSCRIPTION = 'SUBSCRIPTION'
    ADOPTION = 'ADOPTION'
    CATEGORY_CHOICES = [
        (GENERAL, 'General'),
        (PRODUCTS, 'Products'),
        (DELIVERY, 'Delivery'),
        (SUBSCRIPTION, 'Subscription'),
        (ADOPTION, 'Adoption'),
    ]

    question = models.CharField(max_length=300)
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=GENERAL)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'display_order']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return self.question


class SiteSettings(models.Model):
    business_name = models.CharField(max_length=200, default='Vaishnavi Gau Seva Gausansthan')
    tagline = models.CharField(max_length=300, blank=True)

    address_line_1 = models.CharField(max_length=200, blank=True)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    phone_primary = models.CharField(max_length=20, blank=True)
    phone_whatsapp = models.CharField(max_length=20, blank=True)
    email_primary = models.EmailField(blank=True)
    business_hours = models.CharField(max_length=200, blank=True)

    gstin = models.CharField(max_length=20, blank=True)
    fssai_license = models.CharField(max_length=20, blank=True)

    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    map_embed_url = models.URLField(blank=True)

    cow_count = models.PositiveIntegerField(default=35)

    # Phase 6 — Shipping
    shipping_ncr_charge = models.DecimalField(max_digits=8, decimal_places=2, default=50)
    shipping_other_charge = models.DecimalField(max_digits=8, decimal_places=2, default=120)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=2000)
    ncr_pincode_prefixes = models.CharField(
        max_length=200, default='11,12,20,30',
        help_text=(
            'Comma-separated pincode prefixes considered NCR for shipping. '
            '11=Delhi, 12=Haryana, 20=UP NCR, 30=Faridabad/Gurgaon'
        ),
    )

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Singleton — refuse to delete.
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# --------------------------------------------------------------------------
# ContactSubmission (Phase 5 Group B)
# --------------------------------------------------------------------------
class ContactSubject(models.TextChoices):
    GENERAL = 'GENERAL', 'General inquiry'
    PRODUCT = 'PRODUCT', 'Product question'
    ORDER = 'ORDER', 'Order issue'
    FEEDBACK = 'FEEDBACK', 'Feedback'
    OTHER = 'OTHER', 'Other'


class ContactSubmission(SubmissionBase):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=20, choices=ContactSubject.choices, default=ContactSubject.GENERAL)
    message = models.TextField()

    def __str__(self):
        return f'{self.name} — {self.get_subject_display()}'


# --------------------------------------------------------------------------
# NewsletterSubscriber (Phase 5 Group B)
# --------------------------------------------------------------------------
class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    is_active = models.BooleanField(default=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=50, blank=True, help_text='e.g. homepage_footer, checkout')
    unsubscribe_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-subscribed_at']

    def __str__(self):
        return self.email
