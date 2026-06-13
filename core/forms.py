"""
Form classes for Phase 5 inquiry forms (contact + newsletter).
Shared mixin lives at the top.

AntiSpamFormMixin adds:
  - `website` honeypot (hidden via CSS .vai-honeypot; bots fill it, humans don't)
  - `submitted_at_min` hidden timestamp; reject if submission arrives < 3 seconds
    after the form was rendered

Both checks raise a generic "Submission rejected" error so the view can catch
it and silently render the success page (don't tell a bot it failed).
"""
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime


MIN_FILL_SECONDS = 3


class AntiSpamFormMixin:
    """Mix into any forms.Form / forms.ModelForm. Adds two hidden fields + brand styling + validation."""

    # Set of widget input types that should get the brand .form-control-vai class.
    _BRAND_INPUT_TYPES = {'text', 'email', 'tel', 'url', 'number', 'date', 'datetime-local', 'password'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hidden honeypot — humans never see it (CSS-positioned off-screen).
        self.fields['website'] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                'tabindex': '-1',
                'autocomplete': 'off',
                'aria-hidden': 'true',
            }),
        )
        # Hidden timestamp — view sets this on initial render.
        self.fields['submitted_at_min'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput,
        )

        # Apply brand CSS class to every non-hidden, non-checkbox field.
        for name, field in self.fields.items():
            if name in ('website', 'submitted_at_min'):
                continue
            widget = field.widget
            existing = widget.attrs.get('class', '')
            if isinstance(widget, (forms.HiddenInput, forms.CheckboxInput)):
                continue
            if isinstance(widget, (forms.Textarea, forms.Select, forms.SelectMultiple)):
                widget.attrs['class'] = (existing + ' form-control-vai').strip()
                continue
            input_type = getattr(widget, 'input_type', None)
            if input_type in self._BRAND_INPUT_TYPES:
                widget.attrs['class'] = (existing + ' form-control-vai').strip()

    def clean(self):
        cleaned = super().clean()

        # 1) Honeypot — any value at all is a bot.
        if cleaned.get('website'):
            raise ValidationError('Submission rejected.', code='spam_honeypot')

        # 2) Timing — if the form was filled in less than MIN_FILL_SECONDS, it's a bot.
        raw_ts = cleaned.get('submitted_at_min')
        if raw_ts:
            parsed = parse_datetime(raw_ts)
            if parsed is not None:
                # Tolerate missing TZ — treat as aware in current TZ.
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
                if timezone.now() - parsed < timedelta(seconds=MIN_FILL_SECONDS):
                    raise ValidationError('Submission rejected.', code='spam_timing')

        return cleaned


# --------------------------------------------------------------------------
# ContactForm + NewsletterForm (Group B)
# --------------------------------------------------------------------------
import re

from .models import ContactSubmission


def _normalize_phone_optional(raw: str) -> str:
    """Lightweight phone normalize used by inquiry forms (not auth)."""
    if not raw:
        return ''
    s = re.sub(r'[\s\-()]+', '', str(raw))
    if s.startswith('+91'):
        s = s[3:]
    elif s.startswith('91') and len(s) == 12:
        s = s[2:]
    if s.startswith('0'):
        s = s[1:]
    return s


class ContactForm(AntiSpamFormMixin, forms.ModelForm):
    class Meta:
        model = ContactSubmission
        fields = ['name', 'email', 'phone', 'subject', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
        }

    def clean_name(self):
        name = (self.cleaned_data['name'] or '').strip()
        if len(name) < 2:
            raise ValidationError('Please enter your full name.')
        return name

    def clean_message(self):
        msg = (self.cleaned_data['message'] or '').strip()
        if len(msg) < 10:
            raise ValidationError('Please share a few words so we can help.')
        return msg

    def clean_phone(self):
        raw = self.cleaned_data.get('phone', '')
        if not raw:
            return ''
        phone = _normalize_phone_optional(raw)
        if len(phone) != 10:
            raise ValidationError('Phone must be 10 digits (with optional +91 prefix).')
        return phone


class NewsletterForm(AntiSpamFormMixin, forms.Form):
    email = forms.EmailField()
    name = forms.CharField(max_length=100, required=False)
    source = forms.CharField(max_length=50, required=False, widget=forms.HiddenInput)
