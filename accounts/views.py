import time

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .auth_backends import normalize_phone
from .forms import LoginForm, OTPRequestForm, OTPVerifyForm, RegisterForm
from .models import OneTimePasscode, Profile
from .utils.email import send_email_otp, send_verification_email, send_welcome_email
from .utils.sms import send_sms_otp


RESEND_COOLDOWN_SECONDS = 60
BACKEND_PATH = 'accounts.auth_backends.EmailOrPhoneBackend'


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _cooldown_remaining(request, identifier: str) -> int:
    key = f'last_otp_sent_at::{identifier}'
    last = request.session.get(key)
    if not last:
        return 0
    elapsed = int(time.time()) - int(last)
    return max(RESEND_COOLDOWN_SECONDS - elapsed, 0)


def _mark_otp_sent(request, identifier: str):
    request.session[f'last_otp_sent_at::{identifier}'] = int(time.time())


def _mask_email(email: str) -> str:
    if not email or '@' not in email:
        return email or ''
    name, domain = email.split('@', 1)
    if len(name) <= 2:
        return name[0] + '*@' + domain
    return name[0] + '*' * (len(name) - 2) + name[-1] + '@' + domain


def _mask_phone(phone: str) -> str:
    if not phone:
        return ''
    return '*' * (len(phone) - 4) + phone[-4:]


def _resolve_identifier(identifier: str):
    """
    Look up a user by email or phone. Returns (user, identifier_type, normalized_value)
    or (None, identifier_type, normalized_value) if no account matches.
    """
    User = get_user_model()
    value = (identifier or '').strip()
    if '@' in value:
        user = User.objects.filter(email__iexact=value).first()
        return user, OneTimePasscode.EMAIL, value.lower()
    else:
        phone = normalize_phone(value)
        if len(phone) != 10:
            return None, OneTimePasscode.PHONE, phone
        profile = Profile.objects.filter(phone=phone).select_related('user').first()
        return (profile.user if profile else None), OneTimePasscode.PHONE, phone


# --------------------------------------------------------------------------
# Registration (Group B)
# --------------------------------------------------------------------------
def register(request):
    """Register an account, then route to the login page.

    Email/phone verification is intentionally NOT required at signup — the
    Profile.email_verified flag is set True on creation so the unverified-email
    banner doesn't appear. Users who want to verify (or who change their email
    later) can still go through `register_verify` via the email-change flow in
    profile_settings. Removed OTP send/verify gate here so customers can sign
    up mid-checkout without a mailbox round-trip.
    """
    if request.user.is_authenticated:
        return redirect('accounts:profile')

    # Thread ?next= through so post-login lands the user back where they were
    # (typically /cart/checkout/).
    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Skip verification: mark email as verified at signup time. The
            # post_save Profile signal has already created the row.
            profile = getattr(user, 'profile', None)
            if profile is not None:
                profile.email_verified = True
                profile.email_verified_at = timezone.now()
                profile.save(update_fields=['email_verified', 'email_verified_at'])
            send_welcome_email(user)
            messages.success(
                request,
                f'Account created. Sign in with your email and password to continue.',
            )
            login_url = reverse('accounts:login')
            if next_url:
                login_url = f'{login_url}?next={next_url}'
            return redirect(login_url)
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form, 'next': next_url})


def register_verify(request):
    """Email verification is disabled until post-production.

    The URL is kept (`/account/register/verify/`) so old emails, bookmarks,
    and the banner partial don't 404. Anyone hitting it is bounced to a
    sensible page — profile if logged in, register otherwise.

    To re-enable: restore the OTP/resend/verify logic from git history
    (commit prior to the "stop mail verification" change). The Profile
    fields (`email_verified`, `email_verified_at`), the `email_verify.html`
    template, and `send_verification_email()` are all still in place.
    """
    request.session.pop('pending_verification_email', None)
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    return redirect('accounts:register')


# --------------------------------------------------------------------------
# Login (Group C) — password
# --------------------------------------------------------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['identifier'],
                password=form.cleaned_data['password'],
            )
            if user is not None:
                login(request, user)
                if not form.cleaned_data.get('remember_me'):
                    request.session.set_expiry(0)  # browser-close
                messages.success(request, f'Welcome back, {user.first_name or user.username}.')
                next_url = request.GET.get('next') or request.POST.get('next')
                return redirect(next_url or 'accounts:profile')
            form.add_error(None, 'Invalid email/phone or password.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


# --------------------------------------------------------------------------
# Login (Group C) — OTP
# --------------------------------------------------------------------------
GENERIC_OTP_MSG = "If an account exists for that email or phone, we've sent a code."


def login_otp_request(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')

    if request.method == 'POST':
        form = OTPRequestForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['identifier']
            user, id_type, normalized = _resolve_identifier(identifier)

            cooldown = _cooldown_remaining(request, normalized) if normalized else 0
            if cooldown > 0:
                messages.error(request, f'Please wait {cooldown}s before requesting another code.')
                return redirect('accounts:login_otp')

            # Only generate + send if user exists. Either way, redirect to verify
            # with the same generic message — no account-existence leak.
            if user is not None and normalized:
                otp = OneTimePasscode.generate(
                    identifier=normalized,
                    identifier_type=id_type,
                    purpose=OneTimePasscode.LOGIN,
                    user=user,
                )
                if id_type == OneTimePasscode.EMAIL:
                    send_email_otp(normalized, otp.code, 'login')
                else:
                    send_sms_otp(normalized, otp.code, 'login')
                _mark_otp_sent(request, normalized)

            request.session['pending_login_identifier'] = normalized
            request.session['pending_login_id_type'] = id_type
            messages.success(request, GENERIC_OTP_MSG)
            return redirect('accounts:login_otp_verify')
    else:
        form = OTPRequestForm()

    return render(request, 'accounts/login_otp.html', {'form': form})


def login_otp_verify(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')

    identifier = request.session.get('pending_login_identifier')
    id_type = request.session.get('pending_login_id_type')
    if not identifier:
        messages.error(request, 'No pending OTP login found. Please request a code.')
        return redirect('accounts:login_otp')

    cooldown = _cooldown_remaining(request, identifier)

    if request.method == 'POST':
        if request.POST.get('resend'):
            if cooldown > 0:
                messages.error(request, f'Please wait {cooldown}s before requesting another code.')
            else:
                User = get_user_model()
                if id_type == OneTimePasscode.EMAIL:
                    user = User.objects.filter(email__iexact=identifier).first()
                else:
                    profile = Profile.objects.filter(phone=identifier).select_related('user').first()
                    user = profile.user if profile else None
                if user is not None:
                    otp = OneTimePasscode.generate(
                        identifier=identifier,
                        identifier_type=id_type,
                        purpose=OneTimePasscode.LOGIN,
                        user=user,
                    )
                    if id_type == OneTimePasscode.EMAIL:
                        send_email_otp(identifier, otp.code, 'login')
                    else:
                        send_sms_otp(identifier, otp.code, 'login')
                    _mark_otp_sent(request, identifier)
                messages.success(request, GENERIC_OTP_MSG)
            return redirect('accounts:login_otp_verify')

        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            otp = (
                OneTimePasscode.objects.filter(
                    identifier=identifier,
                    purpose=OneTimePasscode.LOGIN,
                    is_used=False,
                )
                .order_by('-created_at')
                .first()
            )
            # Whether OTP doesn't exist OR is wrong, return identical error to avoid leaking existence.
            if otp is None or not otp.is_valid():
                messages.error(request, 'Invalid or expired code. Please try again.')
            elif otp.code != code:
                otp.attempts += 1
                otp.save(update_fields=['attempts'])
                remaining = OneTimePasscode.MAX_ATTEMPTS - otp.attempts
                if remaining <= 0:
                    otp.mark_used()
                    messages.error(request, 'Too many wrong attempts. Please request a new code.')
                    request.session.pop('pending_login_identifier', None)
                    request.session.pop('pending_login_id_type', None)
                    return redirect('accounts:login_otp')
                messages.error(request, f'Wrong code. {remaining} attempt{"s" if remaining != 1 else ""} left.')
            else:
                otp.mark_used()
                login(request, otp.user, backend=BACKEND_PATH)
                request.session.pop('pending_login_identifier', None)
                request.session.pop('pending_login_id_type', None)
                messages.success(request, f'Welcome back, {otp.user.first_name or otp.user.username}.')
                return redirect('accounts:profile')
    else:
        form = OTPVerifyForm()

    masked = _mask_email(identifier) if id_type == OneTimePasscode.EMAIL else _mask_phone(identifier)
    return render(request, 'accounts/otp_verify.html', {
        'form': form,
        'masked_identifier': masked,
        'id_type': id_type,
        'cooldown': cooldown,
    })


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Profile sub-views (Group E) + logout
# --------------------------------------------------------------------------
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .forms import AddressForm, ProfileEditForm
from .models import Address


def logout_view(request):
    # Replaced by django.contrib.auth.views.LogoutView in urls.py — kept for back-compat.
    return redirect('core:home')


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {
        'active_section': 'dashboard',
    })


@login_required
def profile_orders(request):
    # Local import — orders app is otherwise unused inside accounts.
    from orders.models import Order
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related('items')
        .order_by('-placed_at')
    )
    return render(request, 'accounts/profile_orders.html', {
        'active_section': 'orders',
        'orders': orders,
    })


@login_required
def profile_order_detail(request, order_number):
    from orders.models import Order
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number,
        user=request.user,
    )
    return render(request, 'accounts/profile_order_detail.html', {
        'active_section': 'orders',
        'order': order,
    })


@login_required
def profile_subscriptions(request):
    from subscriptions.models import Subscription
    subs = (
        Subscription.objects
        .filter(user=request.user)
        .select_related('plan')
        .prefetch_related('deliveries')
    )
    return render(request, 'accounts/profile_subscriptions.html', {
        'subscriptions': subs,
        'active_section': 'subscriptions',
    })


@login_required
def profile_subscription_detail(request, subscription_number):
    from subscriptions.models import DeliveryStatus, Subscription
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )
    upcoming = sub.deliveries.filter(
        status=DeliveryStatus.SCHEDULED,
        scheduled_date__gte=timezone.now().date(),
    ).order_by('scheduled_date')[:30]
    past = sub.deliveries.filter(
        status__in=[
            DeliveryStatus.DELIVERED,
            DeliveryStatus.SKIPPED,
            DeliveryStatus.MISSED,
        ],
    ).order_by('-scheduled_date')[:20]
    payments = sub.payments.order_by('-created_at')
    return render(request, 'accounts/profile_subscription_detail.html', {
        'subscription': sub,
        'upcoming_deliveries': upcoming,
        'past_deliveries': past,
        'payments': payments,
        'today': timezone.now().date(),
        'active_section': 'subscriptions',
    })


@login_required
def profile_wishlist(request):
    return render(request, 'accounts/profile_wishlist.html', {
        'active_section': 'wishlist',
    })


@login_required
def profile_settings(request):
    # Self-heal: users created before the post_save Profile signal landed
    # (e.g. the initial dev superuser) won't have a Profile row.
    from .models import Profile
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            user = request.user

            email_changed = data['email'] != user.email
            phone_changed = data['phone'] != profile.phone

            user.first_name = data['first_name']
            user.last_name = data['last_name']
            if email_changed:
                user.email = data['email']
                user.username = data['email']  # we use email as username
            user.save()

            profile.first_name = data['first_name']
            profile.last_name = data['last_name']
            profile.phone = data['phone']
            profile.marketing_opt_in = data.get('marketing_opt_in', False)
            # Email verification is OFF until post-production (see register()).
            # When email changes, immediately mark the new address as verified
            # so the unverified-email banner doesn't appear. Re-enable the OTP
            # flow (removed below) when you want to gate this again.
            if email_changed:
                profile.email_verified = True
                profile.email_verified_at = timezone.now()
            if phone_changed:
                profile.is_phone_verified = False
                profile.phone_verified_at = None
            profile.save()

            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile_settings')
    else:
        form = ProfileEditForm(
            user=request.user,
            initial={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': profile.phone,
                'marketing_opt_in': profile.marketing_opt_in,
            },
        )
    return render(request, 'accounts/profile_settings.html', {
        'active_section': 'settings',
        'form': form,
        'profile': profile,
    })


# --------------------------------------------------------------------------
# Password change (Group D) — Django's PasswordChangeForm, brand template.
# --------------------------------------------------------------------------
@login_required
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)  # keep user signed in
            messages.success(request, 'Your password has been updated.')
            return redirect('accounts:profile')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'accounts/password_change.html', {'form': form})


# --------------------------------------------------------------------------
# Address CRUD (Group E.3)
# --------------------------------------------------------------------------
@login_required
def address_list(request):
    addresses = request.user.addresses.all().order_by('-is_default', '-updated_at')
    return render(request, 'accounts/address_list.html', {
        'active_section': 'addresses',
        'addresses': addresses,
    })


@login_required
def address_add(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            # First address auto-default for convenience.
            if not request.user.addresses.exists():
                address.is_default = True
            address.save()
            messages.success(request, f'Address "{address.label}" saved.')
            return redirect('accounts:address_list')
    else:
        form = AddressForm()
    return render(request, 'accounts/address_form.html', {
        'active_section': 'addresses',
        'form': form,
        'mode': 'add',
    })


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, f'Address "{address.label}" updated.')
            return redirect('accounts:address_list')
    else:
        form = AddressForm(instance=address)
    return render(request, 'accounts/address_form.html', {
        'active_section': 'addresses',
        'form': form,
        'mode': 'edit',
        'address': address,
    })


@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        label = address.label
        address.delete()
        messages.success(request, f'Address "{label}" deleted.')
        return redirect('accounts:address_list')
    return render(request, 'accounts/address_confirm_delete.html', {
        'active_section': 'addresses',
        'address': address,
    })


@login_required
@require_POST
def address_set_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save()  # save() already demotes any other default
    messages.success(request, f'"{address.label}" is now your default address.')
    return redirect('accounts:address_list')
