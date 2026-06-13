from datetime import date, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Address
from core.forms import AntiSpamFormMixin, _normalize_phone_optional

from .models import Subscription, SubscriptionInquiry


class SubscriptionInquiryForm(AntiSpamFormMixin, forms.ModelForm):
    class Meta:
        model = SubscriptionInquiry
        fields = [
            'plan',
            'name', 'email', 'phone',
            'delivery_city', 'delivery_pincode',
            'start_date_preference', 'message',
        ]
        widgets = {
            'plan': forms.HiddenInput,
            'message': forms.Textarea(attrs={'rows': 3}),
            'start_date_preference': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_phone(self):
        phone = _normalize_phone_optional(self.cleaned_data['phone'])
        if len(phone) != 10:
            raise ValidationError('Phone must be 10 digits (with optional +91 prefix).')
        return phone

    def clean_delivery_pincode(self):
        pin = (self.cleaned_data.get('delivery_pincode') or '').strip()
        if pin and (not pin.isdigit() or len(pin) != 6):
            raise ValidationError('PIN code must be exactly 6 digits.')
        return pin

    def clean_start_date_preference(self):
        d = self.cleaned_data.get('start_date_preference')
        if d and d < date.today():
            raise ValidationError('Start date must be today or later.')
        return d


# --------------------------------------------------------------------------
# Phase 7 — Subscription signup
# --------------------------------------------------------------------------
class SubscriptionSignupForm(forms.Form):
    address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control-vai'}),
        help_text='Your first delivery date.',
    )
    delivery_time_slot = forms.ChoiceField(
        choices=Subscription.TIME_SLOT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control-vai'}),
    )
    customer_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3, 'class': 'form-control-vai',
            'placeholder': 'Anything our delivery team should know (gate code, dog at home, etc.)',
        }),
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].queryset = Address.objects.filter(user=user)

    def clean_start_date(self):
        d = self.cleaned_data['start_date']
        today = timezone.now().date()
        if d < today:
            raise ValidationError("Start date can't be in the past.")
        if d > today + timedelta(days=30):
            raise ValidationError('Start date can be at most 30 days out.')
        return d


# --------------------------------------------------------------------------
# Phase 7 Group C — Pause / Cancel
# --------------------------------------------------------------------------
class PauseForm(forms.Form):
    pause_start = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control-vai'}),
        help_text='Min 1 day from today.',
    )
    pause_end = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control-vai'}),
        help_text='Max 30 days after the start.',
    )

    def __init__(self, *args, subscription=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscription = subscription

    def clean(self):
        cd = super().clean()
        start = cd.get('pause_start')
        end = cd.get('pause_end')
        if not start or not end:
            return cd
        today = timezone.now().date()
        if start < today + timedelta(days=1):
            raise ValidationError('Pause must start at least 1 day in advance.')
        if end < start:
            raise ValidationError('End date must be after start date.')
        if self.subscription and self.subscription.current_period_end:
            if end > self.subscription.current_period_end:
                raise ValidationError(
                    "Pause can't extend past current period end. "
                    'Cancel and resubscribe instead.'
                )
        if (end - start).days > 30:
            raise ValidationError('Maximum pause length is 30 days.')
        return cd


class CancellationForm(forms.Form):
    REASON_CHOICES = [
        ('TOO_EXPENSIVE', 'Too expensive'),
        ('NOT_USING', 'Not using enough'),
        ('QUALITY_ISSUE', 'Quality issue'),
        ('SERVICE_ISSUE', 'Service / delivery issue'),
        ('TEMPORARY_BREAK', 'Just a temporary break'),
        ('OTHER', 'Other'),
    ]
    reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control-vai'}),
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3, 'class': 'form-control-vai',
            'placeholder': 'Anything that would help us improve?',
        }),
        required=False,
    )
