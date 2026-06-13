import logging
from collections import OrderedDict

from django.shortcuts import render

from core.models import FAQ
from core.utils.email import send_inquiry_emails
from core.utils.form_handler import handle_form_submission
from core.utils.request_meta import get_client_ip, get_user_agent
from subscriptions.models import SubscriptionPlan

from .forms import AdoptionInquiryForm, HamperInquiryForm, VisitBookingForm, WholesaleInquiryForm
from .models import Service

logger = logging.getLogger(__name__)


# Tier metadata for the page.
TIER_BLURBS = OrderedDict([
    (SubscriptionPlan.DAILY_ESSENTIALS, {
        'name': 'Daily Essentials',
        'tagline': 'Delhi NCR · before sunrise',
        'footnote': 'All Tier A: free glass-bottle delivery, 6 AM slot, pause / skip / swap anytime from your dashboard.',
    }),
    (SubscriptionPlan.MONTHLY_PANTRY, {
        'name': 'Monthly Pantry',
        'tagline': 'Pan-India · cold-chain',
        'footnote': 'All Tier B: ships pan-India via insured cold-chain courier within 48 hours of churning.',
    }),
    (SubscriptionPlan.CURATED_BOXES, {
        'name': 'Curated Boxes',
        'tagline': 'Hampers and full-plate combos',
        'footnote': 'Tier C boxes are assembled fresh on your scheduled date. Snack tins arrive vacuum-sealed; ghee in glass.',
    }),
])


def service_list(request):
    plans = (
        SubscriptionPlan.objects.filter(is_active=True)
        .order_by('tier', 'display_order', 'price')
    )

    tiers = []
    for tier_key, meta in TIER_BLURBS.items():
        tier_plans = [p for p in plans if p.tier == tier_key]
        tiers.append({
            'id': tier_key,
            'slug': tier_key.lower().replace('_', '-'),
            'name': meta['name'],
            'tagline': meta['tagline'],
            'footnote': meta['footnote'],
            'plans': tier_plans,
        })

    services = Service.objects.filter(is_active=True).order_by('display_order', 'name')
    faqs = FAQ.objects.filter(
        is_active=True,
        category__in=[FAQ.SUBSCRIPTION, FAQ.DELIVERY, FAQ.GENERAL],
    ).order_by('category', 'display_order')

    return render(request, 'services/service_list.html', {
        'tiers': tiers,
        'services': services,
        'faqs': faqs,
    })


# --------------------------------------------------------------------------
# Phase 5 Group C — inquiry views
# --------------------------------------------------------------------------
def _save_inquiry(form, request, *, kind: str):
    """Shared save helper for all 4 service inquiry types."""
    submission = form.save(commit=False)
    submission.user = request.user if request.user.is_authenticated else None
    submission.ip_address = get_client_ip(request)
    submission.user_agent = get_user_agent(request)
    submission.save()
    logger.info('%s inquiry #%s submitted', kind, submission.pk)
    return submission


# --- Adoption -----------------------------------------------------------
def _save_adoption(form, request):
    sub = _save_inquiry(form, request, kind='Adoption')
    send_inquiry_emails(
        submission=sub,
        business_subject=f'[Adoption] {sub.get_plan_interest_display()} — {sub.name}',
        business_template='emails/adoption_business.txt',
        customer_subject='Thank you for your adoption interest — Vaishnavi Gaushala',
        customer_template='emails/adoption_customer.txt',
        customer_email=sub.email,
    )
    return sub


def adoption(request):
    return handle_form_submission(
        request,
        form_class=AdoptionInquiryForm,
        template_name='services/adoption.html',
        rate_limit_key='adoption',
        save_callback=_save_adoption,
        success_url_name='services:adoption_success',
        success_message="Thank you. We'll reach out within a business day.",
    )


def adoption_success(request):
    return render(request, 'services/adoption_success.html')


# --- Wholesale ----------------------------------------------------------
def _save_wholesale(form, request):
    sub = _save_inquiry(form, request, kind='Wholesale')
    send_inquiry_emails(
        submission=sub,
        business_subject=f'[Wholesale] {sub.business_name} ({sub.get_expected_volume_display()})',
        business_template='emails/wholesale_business.txt',
        customer_subject='We received your wholesale inquiry — Vaishnavi Gaushala',
        customer_template='emails/wholesale_customer.txt',
        customer_email=sub.email,
    )
    return sub


def wholesale(request):
    return handle_form_submission(
        request,
        form_class=WholesaleInquiryForm,
        template_name='services/wholesale.html',
        rate_limit_key='wholesale',
        save_callback=_save_wholesale,
        success_url_name='services:wholesale_success',
        success_message="Thank you. Our team will reach out within a business day.",
    )


def wholesale_success(request):
    return render(request, 'services/wholesale_success.html')


# --- Hampers ------------------------------------------------------------
def _save_hampers(form, request):
    sub = _save_inquiry(form, request, kind='Hamper')
    send_inquiry_emails(
        submission=sub,
        business_subject=f'[Hamper] {sub.get_occasion_display()} × {sub.quantity} — {sub.name}',
        business_template='emails/hamper_business.txt',
        customer_subject='We received your hamper inquiry — Vaishnavi Gaushala',
        customer_template='emails/hamper_customer.txt',
        customer_email=sub.email,
    )
    return sub


def hampers(request):
    return handle_form_submission(
        request,
        form_class=HamperInquiryForm,
        template_name='services/hampers.html',
        rate_limit_key='hampers',
        save_callback=_save_hampers,
        success_url_name='services:hampers_success',
        success_message="Thank you. We'll send a curated proposal within a business day.",
    )


def hampers_success(request):
    return render(request, 'services/hampers_success.html')


# --- Visit booking ------------------------------------------------------
def _save_visit(form, request):
    sub = _save_inquiry(form, request, kind='Visit')
    send_inquiry_emails(
        submission=sub,
        business_subject=f'[Visit] {sub.preferred_date} — {sub.name} (party of {sub.party_size})',
        business_template='emails/visit_business.txt',
        customer_subject='Your gaushala visit request — Vaishnavi Gaushala',
        customer_template='emails/visit_customer.txt',
        customer_email=sub.email,
    )
    return sub


def visit(request):
    return handle_form_submission(
        request,
        form_class=VisitBookingForm,
        template_name='services/visit.html',
        rate_limit_key='visit',
        save_callback=_save_visit,
        success_url_name='services:visit_success',
        success_message="Thank you. We'll confirm your slot by email.",
    )


def visit_success(request):
    return render(request, 'services/visit_success.html')
