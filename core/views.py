import logging

from django.contrib import messages
from django.db.models import Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalog.models import Breed, Category, Cow, Product
from core.forms import ContactForm, NewsletterForm
from core.models import FAQ, ContactSubmission, NewsletterSubscriber, SiteSettings, Testimonial
from core.utils.email import send_inquiry_emails
from core.utils.form_handler import handle_form_submission
from core.utils.ratelimit import check_rate_limit
from core.utils.request_meta import get_client_ip, get_user_agent
from subscriptions.models import SubscriptionPlan

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Home / about / styleguide / 404 (Phase 1-3)
# --------------------------------------------------------------------------
def home(request):
    featured_categories = (
        Category.objects.filter(is_active=True).order_by('display_order', 'name')[:2]
    )
    # Bestsellers row: prefer is_featured=True, but always show up to 6 cards
    # so the carousel never strands with 1-2 items. `-is_featured` orders True
    # before False; then display_order/name as a stable tie-breaker.
    featured_products = (
        Product.objects.filter(is_active=True)
        .select_related('category')
        .prefetch_related('variants')
        .annotate(min_price=Min('variants__price', filter=Q(variants__is_active=True)))
        .order_by('-is_featured', 'display_order', 'name')[:6]
    )
    testimonials = Testimonial.objects.filter(is_featured=True).order_by('display_order', '-created_at')[:3]
    featured_plans = (
        SubscriptionPlan.objects.filter(is_active=True, is_featured=True)
        .order_by('tier', 'display_order')[:3]
    )
    return render(request, 'core/home.html', {
        'featured_categories': featured_categories,
        'featured_products': featured_products,
        'testimonials': testimonials,
        'featured_plans': featured_plans,
    })


def about(request):
    breeds = Breed.objects.all().order_by('display_order', 'name')
    featured_cows = (
        Cow.objects.filter(is_featured=True)
        .select_related('breed')
        .order_by('display_order', 'name')
    )
    return render(request, 'core/about.html', {
        'breeds': breeds,
        'featured_cows': featured_cows,
    })


def styleguide(request):
    return render(request, 'core/styleguide.html')


def custom_404(request, exception):
    return render(request, 'core/404.html', status=404)


def custom_500(request):
    """Standalone 500 page — must not touch the DB or context processors,
    because whatever caused the 500 might have broken them too.
    """
    return render(request, 'core/500.html', status=500)


def custom_403(request, exception):
    """403 — typically CSRF failure or permission denied."""
    return render(request, 'core/403.html', status=403)


def healthz(request):
    """Lightweight health check for load balancer / uptime monitoring.
    Verifies process is up AND DB is reachable. Returns 200/503.
    """
    from django.db import connection
    from django.http import JsonResponse
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
    except Exception:
        return JsonResponse({'status': 'unhealthy'}, status=503)
    return JsonResponse({'status': 'ok'})


def robots_txt(request):
    """Serve /robots.txt with sitemap URL pointed at the configured SITE_DOMAIN."""
    from django.conf import settings as _settings
    return render(
        request, 'robots.txt',
        {'site_domain': _settings.SITE_DOMAIN.rstrip('/')},
        content_type='text/plain',
    )


# --------------------------------------------------------------------------
# Contact form (Phase 5 Group B)
# --------------------------------------------------------------------------
def _save_contact(form, request):
    submission = form.save(commit=False)
    submission.user = request.user if request.user.is_authenticated else None
    submission.ip_address = get_client_ip(request)
    submission.user_agent = get_user_agent(request)
    submission.save()
    logger.info('Contact submission #%s from %s (%s)', submission.pk, submission.email, submission.get_subject_display())

    send_inquiry_emails(
        submission=submission,
        business_subject=f'[Contact] {submission.get_subject_display()} — {submission.name}',
        business_template='emails/contact_business.txt',
        customer_subject='We received your message — Vaishnavi Gaushala',
        customer_template='emails/contact_customer.txt',
        customer_email=submission.email,
    )
    return submission


def contact(request):
    site = SiteSettings.load()
    faqs = FAQ.objects.filter(is_active=True).order_by('category', 'display_order')
    return handle_form_submission(
        request,
        form_class=ContactForm,
        template_name='core/contact.html',
        rate_limit_key='contact',
        save_callback=_save_contact,
        success_url_name='core:contact_success',
        success_message="Thank you. We'll be in touch soon.",
        extra_context={'site': site, 'faqs': faqs},
    )


def contact_success(request):
    return render(request, 'core/contact_success.html')


# --------------------------------------------------------------------------
# Newsletter (Phase 5 Group B)
# --------------------------------------------------------------------------
@require_POST
def newsletter_subscribe(request):
    form = NewsletterForm(request.POST)
    referer = request.META.get('HTTP_REFERER') or 'core:home'

    if not form.is_valid():
        # Spam fails are silent (return same success message); real failures show error.
        codes = {e.code for e in form.non_field_errors().as_data()}
        if codes and codes.issubset({'spam_honeypot', 'spam_timing'}):
            messages.success(request, 'Thanks for subscribing.')
            return redirect(referer)
        messages.error(request, 'Please enter a valid email.')
        return redirect(referer)

    if not check_rate_limit(request, 'newsletter', max_attempts=3, window_seconds=3600):
        # Silent success — don't tell scrapers they hit the limit.
        messages.success(request, 'Thanks for subscribing.')
        return redirect(referer)

    email = form.cleaned_data['email'].strip().lower()
    sub, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={
            'name': form.cleaned_data.get('name', ''),
            'source': form.cleaned_data.get('source', ''),
            'user': request.user if request.user.is_authenticated else None,
            'ip_address': get_client_ip(request),
        },
    )
    if not created and not sub.is_active:
        # Re-activate on resubscribe.
        sub.is_active = True
        sub.unsubscribed_at = None
        sub.save(update_fields=['is_active', 'unsubscribed_at'])

    if created:
        logger.info('Newsletter subscriber #%s: %s (source=%s)', sub.pk, sub.email, sub.source)
        send_inquiry_emails(
            submission=sub,
            business_subject=f'[Newsletter] New subscriber: {sub.email}',
            business_template='emails/newsletter_business.txt',
            customer_subject='Welcome to the Vaishnavi family',
            customer_template='emails/newsletter_customer.txt',
            customer_email=sub.email,
        )

    messages.success(request, 'Thanks for subscribing.')
    return redirect(referer)


def newsletter_unsubscribe(request, token):
    sub = get_object_or_404(NewsletterSubscriber, unsubscribe_token=token)
    if request.method == 'POST':
        sub.is_active = False
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=['is_active', 'unsubscribed_at'])
        return render(request, 'core/newsletter_unsubscribed.html', {'subscriber': sub})
    return render(request, 'core/newsletter_unsubscribe_confirm.html', {'subscriber': sub})
