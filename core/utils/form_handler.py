"""
Generic form-submission handler used by every inquiry view in Phase 5.

NOTE: Spec called for `core/views/_form_handler.py`, which would require
converting `core/views.py` into a package and risk regressing Phase 1-4
imports. Placed in `core/utils/` instead — same purpose, safer location.

Pattern per view:

    def contact(request):
        return handle_form_submission(
            request,
            form_class=ContactForm,
            template_name='core/contact.html',
            rate_limit_key='contact',
            save_callback=_save_contact,
            success_url_name='core:contact_success',
            extra_context={'site': site, 'faqs': faqs},
        )
"""
import logging

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from .ratelimit import check_rate_limit

logger = logging.getLogger(__name__)


def _user_initial(request, form_class) -> dict:
    """Pre-fill name/email/phone for logged-in users when the form has those fields."""
    initial = {}
    if not request.user.is_authenticated:
        return initial

    declared = getattr(form_class, 'base_fields', {})
    user = request.user
    profile = getattr(user, 'profile', None)
    full_name = (user.get_full_name() or '').strip()

    if 'name' in declared and full_name:
        initial['name'] = full_name
    if 'contact_name' in declared and full_name:
        initial['contact_name'] = full_name
    if 'email' in declared and user.email:
        initial['email'] = user.email
    if 'phone' in declared and profile and profile.phone:
        initial['phone'] = profile.phone

    return initial


def handle_form_submission(
    request,
    *,
    form_class,
    template_name,
    rate_limit_key,
    save_callback,
    success_url_name,
    success_message='Thank you. We will be in touch.',
    rate_limit_max=5,
    rate_limit_window=3600,
    extra_context=None,
):
    """
    GET: render the form (pre-filled, with submitted_at_min set to now).
    POST: validate → rate-limit → save_callback → redirect to success URL.
    Spam-rejected submissions silently render the success page (no DB write,
    no leak to the bot that we caught them).
    """
    extra_context = extra_context or {}

    if request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            # Rate limit check happens AFTER form validation so genuine validation
            # errors aren't counted against the limit.
            if not check_rate_limit(
                request, rate_limit_key,
                max_attempts=rate_limit_max,
                window_seconds=rate_limit_window,
            ):
                logger.warning(
                    'Rate limit hit for key=%s ip=%s', rate_limit_key,
                    request.META.get('REMOTE_ADDR'),
                )
                # Silently show success — don't tell attacker they're throttled.
                messages.success(request, success_message)
                return redirect(success_url_name)

            try:
                save_callback(form, request)
            except Exception:
                logger.error('save_callback raised in form_handler', exc_info=True)
                messages.error(request, "Something went wrong on our end. Please try again.")
                return render(request, template_name, {'form': form, **extra_context})

            messages.success(request, success_message)
            return redirect(success_url_name)

        # If the form failed ONLY because of spam codes, silently "succeed".
        spam_codes = {'spam_honeypot', 'spam_timing'}
        codes = {e.code for e in form.non_field_errors().as_data()}
        if codes and codes.issubset(spam_codes):
            logger.info('Honeypot/timing rejected key=%s ip=%s', rate_limit_key, request.META.get('REMOTE_ADDR'))
            messages.success(request, success_message)
            return redirect(success_url_name)

        # Genuine validation failure — re-render with errors.
        return render(request, template_name, {'form': form, **extra_context})

    # GET — render with pre-filled values and a fresh timestamp.
    initial = _user_initial(request, form_class)
    initial['submitted_at_min'] = timezone.now().isoformat()
    form = form_class(initial=initial)
    return render(request, template_name, {'form': form, **extra_context})
