from datetime import date, timedelta

from django import forms
from django.core.exceptions import ValidationError

from core.forms import AntiSpamFormMixin, _normalize_phone_optional

from .models import AdoptionInquiry, HamperInquiry, VisitBooking, WholesaleInquiry


def _validate_phone(raw: str) -> str:
    phone = _normalize_phone_optional(raw)
    if len(phone) != 10:
        raise ValidationError('Phone must be 10 digits (with optional +91 prefix).')
    return phone


class AdoptionInquiryForm(AntiSpamFormMixin, forms.ModelForm):
    class Meta:
        model = AdoptionInquiry
        fields = [
            'name', 'email', 'phone',
            'preferred_cow', 'preferred_breed', 'plan_interest',
            'message',
        ]
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}

    def clean_phone(self):
        return _validate_phone(self.cleaned_data['phone'])


class WholesaleInquiryForm(AntiSpamFormMixin, forms.ModelForm):
    class Meta:
        model = WholesaleInquiry
        fields = [
            'business_name', 'contact_name', 'email', 'phone',
            'gstin', 'expected_volume', 'products_interested',
            'delivery_city', 'message',
        ]
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}

    def clean_phone(self):
        return _validate_phone(self.cleaned_data['phone'])

    def clean_gstin(self):
        gstin = (self.cleaned_data.get('gstin') or '').strip().upper()
        if gstin and len(gstin) != 15:
            raise ValidationError('GSTIN must be exactly 15 characters.')
        return gstin


class HamperInquiryForm(AntiSpamFormMixin, forms.ModelForm):
    class Meta:
        model = HamperInquiry
        fields = [
            'name', 'email', 'phone',
            'occasion', 'budget_range', 'quantity',
            'delivery_date', 'delivery_city', 'message',
        ]
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
            'delivery_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_phone(self):
        return _validate_phone(self.cleaned_data['phone'])

    def clean_delivery_date(self):
        d = self.cleaned_data.get('delivery_date')
        if d and d < date.today():
            raise ValidationError('Delivery date must be in the future.')
        return d

    def clean_quantity(self):
        q = self.cleaned_data.get('quantity') or 1
        if q < 1:
            raise ValidationError('Order at least 1 hamper.')
        return q


class VisitBookingForm(AntiSpamFormMixin, forms.ModelForm):
    class Meta:
        model = VisitBooking
        fields = [
            'name', 'email', 'phone',
            'preferred_date', 'alternate_date',
            'party_size', 'has_children', 'special_requests',
        ]
        widgets = {
            'special_requests': forms.Textarea(attrs={'rows': 3}),
            'preferred_date': forms.DateInput(attrs={'type': 'date'}),
            'alternate_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_phone(self):
        return _validate_phone(self.cleaned_data['phone'])

    def _validate_visit_date(self, d, field_name='preferred_date'):
        """Weekend-only, at least 2 days out, max 60 days."""
        if d is None:
            return d
        today = date.today()
        min_d = today + timedelta(days=2)
        max_d = today + timedelta(days=60)
        if d < min_d:
            raise ValidationError('Please pick a date at least 2 days from today.')
        if d > max_d:
            raise ValidationError('Please pick a date within the next 60 days.')
        # Saturday=5, Sunday=6
        if d.weekday() not in (5, 6):
            raise ValidationError('Visits are on Saturday and Sunday only.')
        return d

    def clean_preferred_date(self):
        return self._validate_visit_date(self.cleaned_data.get('preferred_date'))

    def clean_alternate_date(self):
        return self._validate_visit_date(self.cleaned_data.get('alternate_date'))

    def clean_party_size(self):
        n = self.cleaned_data.get('party_size') or 1
        if n < 1 or n > 20:
            raise ValidationError('Party size must be between 1 and 20.')
        return n
