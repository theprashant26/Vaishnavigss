import random
import re
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


# --------------------------------------------------------------------------
# Profile (extends Phase 2; new fields added here, none removed)
# --------------------------------------------------------------------------
class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    phone = models.CharField(max_length=20, blank=True)
    is_phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Phase 4 additions
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Profile: {self.user.username}'


# --------------------------------------------------------------------------
# Address (Phase 4)
# --------------------------------------------------------------------------
PINCODE_VALIDATOR = RegexValidator(
    regex=r'^\d{6}$',
    message='Pincode must be exactly 6 digits.',
)

PHONE_VALIDATOR = RegexValidator(
    # Accepts: 10 digits, or +91 prefix + 10 digits (spaces OK in input but should be stripped)
    regex=r'^(\+?91)?[6-9]\d{9}$',
    message='Phone must be 10 digits (with optional +91 prefix).',
)


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
    )
    label = models.CharField(max_length=50)
    recipient_name = models.CharField(max_length=100)
    recipient_phone = models.CharField(max_length=20, validators=[PHONE_VALIDATOR])
    line_1 = models.CharField(max_length=200)
    line_2 = models.CharField(max_length=200, blank=True)
    landmark = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10, validators=[PINCODE_VALIDATOR])
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name_plural = 'Addresses'

    def __str__(self):
        return f'{self.label} — {self.city}'

    def save(self, *args, **kwargs):
        # If this address is marked default, demote any other default for the same user.
        if self.is_default and self.user_id:
            Address.objects.filter(
                user_id=self.user_id, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# --------------------------------------------------------------------------
# OneTimePasscode (Phase 4)
# --------------------------------------------------------------------------
class OneTimePasscodeManager(models.Manager):
    def cleanup_expired(self):
        """Delete OTPs older than 24 hours. Wire to a periodic task in a later phase."""
        cutoff = timezone.now() - timedelta(hours=24)
        return self.filter(created_at__lt=cutoff).delete()


class OneTimePasscode(models.Model):
    EMAIL = 'EMAIL'
    PHONE = 'PHONE'
    IDENTIFIER_TYPES = [(EMAIL, 'Email'), (PHONE, 'Phone')]

    REGISTER = 'REGISTER'
    LOGIN = 'LOGIN'
    VERIFY_EMAIL = 'VERIFY_EMAIL'
    VERIFY_PHONE = 'VERIFY_PHONE'
    RESET_PASSWORD = 'RESET_PASSWORD'
    PURPOSE_CHOICES = [
        (REGISTER, 'Register'),
        (LOGIN, 'Login'),
        (VERIFY_EMAIL, 'Verify email'),
        (VERIFY_PHONE, 'Verify phone'),
        (RESET_PASSWORD, 'Reset password'),
    ]

    MAX_ATTEMPTS = 3
    LIFETIME = timedelta(minutes=10)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='otps',
    )
    identifier = models.CharField(max_length=100)
    identifier_type = models.CharField(max_length=10, choices=IDENTIFIER_TYPES)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    objects = OneTimePasscodeManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['identifier', 'purpose', 'is_used']),
        ]

    def __str__(self):
        return f'OTP {self.code} → {self.identifier} ({self.purpose})'

    def is_valid(self):
        return (
            not self.is_used
            and self.attempts < self.MAX_ATTEMPTS
            and timezone.now() < self.expires_at
        )

    def mark_used(self):
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])

    @classmethod
    def generate(cls, identifier, identifier_type, purpose, user=None):
        """Create a fresh OTP. Invalidate any prior unused OTP for same identifier+purpose."""
        cls.objects.filter(
            identifier=identifier, purpose=purpose, is_used=False
        ).update(is_used=True, used_at=timezone.now())
        code = f'{random.randint(0, 999999):06d}'
        return cls.objects.create(
            user=user,
            identifier=identifier,
            identifier_type=identifier_type,
            purpose=purpose,
            code=code,
            expires_at=timezone.now() + cls.LIFETIME,
        )
