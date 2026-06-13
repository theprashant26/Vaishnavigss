from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .auth_backends import normalize_phone
from .models import Address, Profile

User = get_user_model()


class RegisterForm(forms.Form):
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    password_confirm = forms.CharField(widget=forms.PasswordInput)
    terms = forms.BooleanField(error_messages={'required': 'You must accept the terms to continue.'})
    marketing_opt_in = forms.BooleanField(required=False)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_phone(self):
        raw = self.cleaned_data['phone']
        phone = normalize_phone(raw)
        if len(phone) != 10:
            raise ValidationError('Phone must be a 10-digit number (with optional +91 prefix).')
        if Profile.objects.filter(phone=phone).exists():
            raise ValidationError('An account with this phone number already exists.')
        return phone

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('password')
        pw2 = cleaned.get('password_confirm')
        if pw and pw2 and pw != pw2:
            self.add_error('password_confirm', 'Passwords do not match.')
        if pw:
            try:
                validate_password(pw)
            except ValidationError as e:
                self.add_error('password', e)
        return cleaned

    def save(self):
        """Create the User + sync Profile fields. Returns the user."""
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
        )
        # Profile auto-created by signal — refresh and populate Phase 4 fields.
        profile = user.profile
        profile.first_name = data['first_name']
        profile.last_name = data['last_name']
        profile.phone = data['phone']
        profile.marketing_opt_in = data.get('marketing_opt_in', False)
        profile.save()
        return user


class OTPVerifyForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=6)

    def clean_code(self):
        code = (self.cleaned_data['code'] or '').strip()
        if not code.isdigit() or len(code) != 6:
            raise ValidationError('Enter the 6-digit code.')
        return code


class LoginForm(forms.Form):
    """Password login by email OR phone — backend resolves which."""
    identifier = forms.CharField(max_length=100, label='Email or phone')
    password = forms.CharField(widget=forms.PasswordInput)
    remember_me = forms.BooleanField(required=False)


class OTPRequestForm(forms.Form):
    """Login-via-OTP: ask for identifier; backend sends a 6-digit code."""
    identifier = forms.CharField(max_length=100, label='Email or phone')


class ProfileEditForm(forms.Form):
    """
    Edit user's name, email, phone, marketing opt-in.
    Email/phone changes trigger re-verification (handled in the view).
    """
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    marketing_opt_in = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = (self.cleaned_data['email'] or '').strip().lower()
        # Allow keeping current email; reject if taken by another user.
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError('Another account is using this email.')
        return email

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data['phone'])
        if len(phone) != 10:
            raise ValidationError('Phone must be a 10-digit number (with optional +91 prefix).')
        if Profile.objects.filter(phone=phone).exclude(user_id=self.user.pk).exists():
            raise ValidationError('Another account is using this phone number.')
        return phone


class AddressForm(forms.ModelForm):
    """ModelForm for Address — used by both add and edit views."""
    class Meta:
        model = Address
        fields = (
            'label', 'recipient_name', 'recipient_phone',
            'line_1', 'line_2', 'landmark',
            'city', 'state', 'pincode',
            'is_default',
        )

    def clean_recipient_phone(self):
        phone = normalize_phone(self.cleaned_data['recipient_phone'])
        if len(phone) != 10:
            raise ValidationError('Phone must be a 10-digit number (with optional +91 prefix).')
        return phone

    def clean_pincode(self):
        pin = (self.cleaned_data['pincode'] or '').strip()
        if not pin.isdigit() or len(pin) != 6:
            raise ValidationError('PIN code must be exactly 6 digits.')
        return pin
