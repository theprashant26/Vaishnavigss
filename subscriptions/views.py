import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Address
from core.utils.email import send_inquiry_emails
from core.utils.form_handler import _user_initial
from core.utils.ratelimit import check_rate_limit
from core.utils.request_meta import get_client_ip, get_user_agent
from orders.services import razorpay_client

from .forms import (
    CancellationForm,
    PauseForm,
    SubscriptionInquiryForm,
    SubscriptionSignupForm,
)
from .models import (
    DeliveryStatus,
    Subscription,
    SubscriptionDelivery,
    SubscriptionPayment,
    SubscriptionPlan,
    SubscriptionStatus,
)
from .services.delivery_generation import generate_deliveries

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Phase 5 — Inquiry (unchanged)
# --------------------------------------------------------------------------
def inquiry(request, plan_slug):
    """Subscription inquiry form. The plan is locked to the URL slug."""
    plan = get_object_or_404(SubscriptionPlan, slug=plan_slug, is_active=True)

    if request.method == 'POST':
        form = SubscriptionInquiryForm(request.POST)
        if form.is_valid():
            if not check_rate_limit(request, f'sub_inquiry:{plan_slug}'):
                messages.success(request, "Thank you. We'll be in touch.")
                return redirect('subscriptions:inquiry_success', plan_slug=plan_slug)

            submission = form.save(commit=False)
            submission.plan = plan
            submission.user = request.user if request.user.is_authenticated else None
            submission.ip_address = get_client_ip(request)
            submission.user_agent = get_user_agent(request)
            submission.save()
            logger.info('Subscription inquiry #%s for plan=%s', submission.pk, plan.slug)

            send_inquiry_emails(
                submission=submission,
                business_subject=f'[Subscription] {plan.name} ({plan.get_tier_display()}) — {submission.name}',
                business_template='emails/subscription_inquiry_business.txt',
                customer_subject=f'Thank you — your {plan.name} inquiry',
                customer_template='emails/subscription_inquiry_customer.txt',
                customer_email=submission.email,
            )
            messages.success(request, "Thank you. We'll be in touch within a business day.")
            return redirect('subscriptions:inquiry_success', plan_slug=plan_slug)

        spam_codes = {'spam_honeypot', 'spam_timing'}
        codes = {e.code for e in form.non_field_errors().as_data()}
        if codes and codes.issubset(spam_codes):
            messages.success(request, "Thank you. We'll be in touch.")
            return redirect('subscriptions:inquiry_success', plan_slug=plan_slug)
        return render(request, 'subscriptions/inquiry.html', {'plan': plan, 'form': form})

    initial = _user_initial(request, SubscriptionInquiryForm)
    initial['plan'] = plan.pk
    initial['submitted_at_min'] = timezone.now().isoformat()
    form = SubscriptionInquiryForm(initial=initial)
    return render(request, 'subscriptions/inquiry.html', {'plan': plan, 'form': form})


def inquiry_success(request, plan_slug):
    plan = get_object_or_404(SubscriptionPlan, slug=plan_slug, is_active=True)
    return render(request, 'subscriptions/inquiry_success.html', {'plan': plan})


# --------------------------------------------------------------------------
# Phase 7 — Signup + payment
# --------------------------------------------------------------------------
SIGNUP_SESSION_KEY = 'subscription_signup'


@login_required
def signup(request, plan_slug):
    """Step 1: Address + start date + time slot."""
    plan = get_object_or_404(
        SubscriptionPlan, slug=plan_slug, is_active=True, is_self_serve=True,
    )
    addresses = Address.objects.filter(user=request.user)

    if request.method == 'POST':
        form = SubscriptionSignupForm(request.POST, user=request.user)
        if form.is_valid():
            request.session[SIGNUP_SESSION_KEY] = {
                'plan_slug': plan.slug,
                'address_id': form.cleaned_data['address'].pk,
                'start_date': form.cleaned_data['start_date'].isoformat(),
                'delivery_time_slot': form.cleaned_data['delivery_time_slot'],
                'customer_notes': form.cleaned_data.get('customer_notes', ''),
            }
            return redirect('subscriptions:signup_review', plan_slug=plan.slug)
    else:
        form = SubscriptionSignupForm(user=request.user, initial={
            'start_date': timezone.now().date() + timedelta(days=1),
            'delivery_time_slot': Subscription.MORNING,
        })

    return render(request, 'subscriptions/signup.html', {
        'plan': plan, 'form': form, 'addresses': addresses,
    })


@login_required
def signup_review(request, plan_slug):
    """Step 2: Review summary, create pending subscription, redirect to pay."""
    plan = get_object_or_404(
        SubscriptionPlan, slug=plan_slug, is_active=True, is_self_serve=True,
    )
    data = request.session.get(SIGNUP_SESSION_KEY) or {}
    if data.get('plan_slug') != plan.slug:
        return redirect('subscriptions:signup', plan_slug=plan.slug)

    address = get_object_or_404(Address, pk=data['address_id'], user=request.user)
    start_date = date.fromisoformat(data['start_date'])
    # period_end is inclusive: start + (N-1) days. For one-time plans (N=0) collapse to start.
    if plan.billing_period_days > 0:
        period_end = start_date + timedelta(days=plan.billing_period_days - 1)
    else:
        period_end = start_date

    if request.method == 'POST':
        sub = _create_pending_subscription(
            request.user, plan, address, data, start_date, period_end,
        )
        request.session.pop(SIGNUP_SESSION_KEY, None)
        return redirect('subscriptions:pay', subscription_number=sub.subscription_number)

    return render(request, 'subscriptions/signup_review.html', {
        'plan': plan, 'address': address,
        'start_date': start_date, 'period_end': period_end,
        'data': data, 'plan_items': plan.items.select_related('variant__product'),
    })


def _create_pending_subscription(user, plan, address, data, start_date, period_end):
    """Create the Subscription + initial PENDING SubscriptionPayment row."""
    with transaction.atomic():
        sub = Subscription.objects.create(
            user=user, plan=plan,
            status=SubscriptionStatus.PENDING_PAYMENT,
            current_period_start=start_date,
            current_period_end=period_end,
            next_billing_date=period_end + timedelta(days=1),
            shipping_recipient_name=address.recipient_name,
            shipping_phone=address.recipient_phone,
            shipping_line_1=address.line_1,
            shipping_line_2=address.line_2,
            shipping_landmark=address.landmark,
            shipping_city=address.city,
            shipping_state=address.state,
            shipping_pincode=address.pincode,
            delivery_time_slot=data['delivery_time_slot'],
            customer_notes=data.get('customer_notes', ''),
        )
        SubscriptionPayment.objects.create(
            subscription=sub,
            payment_type=SubscriptionPayment.PaymentType.INITIAL,
            status=SubscriptionPayment.PaymentStatus.PENDING,
            period_start=start_date,
            period_end=period_end,
            amount=plan.price,
            tax_amount=Decimal('0'),  # GST handled differently for subs; 0 for MVP
            total=plan.price,
        )
    logger.info('Pending subscription created: %s (plan=%s, user=%s)',
                sub.subscription_number, plan.slug, user.pk)
    return sub


@login_required
def pay(request, subscription_number):
    """Renders the Razorpay-modal launcher for the pending payment."""
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )

    # Allow pay through whenever there is a pending payment — this covers both
    # initial signup (sub=PENDING_PAYMENT) and renewals (sub=ACTIVE/EXPIRED).
    payment = sub.payments.filter(
        status=SubscriptionPayment.PaymentStatus.PENDING,
    ).order_by('-created_at').first()
    if not payment:
        # No pending payment — bounce to detail (active sub) or 404 otherwise.
        if sub.status == SubscriptionStatus.ACTIVE:
            return redirect(
                'accounts:profile_subscription_detail',
                subscription_number=sub.subscription_number,
            )
        raise Http404('No pending payment for this subscription.')

    if not payment.razorpay_order_id:
        try:
            rzp_order = razorpay_client.create_order(
                amount_paise=int(payment.total * 100),
                receipt=payment.payment_number,
                notes={
                    'subscription_number': sub.subscription_number,
                    'user_id': str(request.user.pk),
                    'payment_type': payment.payment_type,
                },
            )
        except razorpay_client.RazorpayError as e:
            logger.error('Subscription create_order failed for %s: %s',
                         sub.subscription_number, e)
            messages.error(request, 'We could not start the payment. Please try again.')
            return redirect('subscriptions:pay_failed')
        payment.razorpay_order_id = rzp_order['id']
        payment.save(update_fields=['razorpay_order_id', 'updated_at'])

    return render(request, 'subscriptions/pay.html', {
        'subscription': sub, 'payment': payment,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'callback_url': request.build_absolute_uri(reverse('subscriptions:pay_callback')),
    })


@require_POST
@csrf_exempt  # Razorpay checkout.js POSTs from their domain
def pay_callback(request):
    rzp_order_id = (request.POST.get('razorpay_order_id') or '').strip()
    rzp_payment_id = (request.POST.get('razorpay_payment_id') or '').strip()
    rzp_signature = (request.POST.get('razorpay_signature') or '').strip()

    try:
        payment = SubscriptionPayment.objects.get(razorpay_order_id=rzp_order_id)
    except SubscriptionPayment.DoesNotExist:
        logger.warning('Subscription callback for unknown razorpay_order_id=%s',
                       razorpay_client._mask(rzp_order_id))
        return redirect('subscriptions:pay_failed')

    if not razorpay_client.verify_payment_signature(rzp_order_id, rzp_payment_id, rzp_signature):
        logger.error('Subscription payment signature mismatch for %s',
                     payment.payment_number)
        payment.status = SubscriptionPayment.PaymentStatus.FAILED
        payment.save(update_fields=['status', 'updated_at'])
        return redirect('subscriptions:pay_failed')

    _mark_subscription_payment_paid(payment, rzp_payment_id, rzp_signature)
    return redirect(
        'subscriptions:signup_success',
        subscription_number=payment.subscription.subscription_number,
    )


def _mark_subscription_payment_paid(payment, payment_id: str, signature: str) -> None:
    """Idempotent paid-state transition for SubscriptionPayment.

    Wrapped in a transaction + select_for_update to handle the
    browser-callback-vs-webhook race. Activates the subscription (initial),
    extends period (renewal), generates the matching deliveries, and fires
    the customer/business emails.
    """
    with transaction.atomic():
        payment = SubscriptionPayment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == SubscriptionPayment.PaymentStatus.COMPLETED:
            return  # already done

        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.status = SubscriptionPayment.PaymentStatus.COMPLETED
        payment.paid_at = timezone.now()
        payment.save(update_fields=[
            'razorpay_payment_id', 'razorpay_signature',
            'status', 'paid_at', 'updated_at',
        ])

        sub = Subscription.objects.select_for_update().get(pk=payment.subscription_id)
        if payment.payment_type == SubscriptionPayment.PaymentType.INITIAL:
            sub.status = SubscriptionStatus.ACTIVE
            sub.activated_at = timezone.now()
        elif payment.payment_type == SubscriptionPayment.PaymentType.RENEWAL:
            sub.current_period_start = payment.period_start
            sub.current_period_end = payment.period_end
            sub.next_billing_date = payment.period_end + timedelta(days=1)
            sub.status = SubscriptionStatus.ACTIVE  # in case it had expired briefly
        sub.save()

        generate_deliveries(sub, payment.period_start, payment.period_end)

    logger.info(
        'Subscription payment %s marked PAID (type=%s sub=%s)',
        payment.payment_number, payment.payment_type, sub.subscription_number,
    )

    # Emails are best-effort; Group D wires the dedicated templates.
    try:
        from .services.emails import send_subscription_payment_email
        send_subscription_payment_email(payment)
    except Exception:
        logger.exception(
            'Subscription paid email failed for %s', payment.payment_number,
        )


@login_required
def signup_success(request, subscription_number):
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )
    first_delivery = sub.next_delivery
    return render(request, 'subscriptions/signup_success.html', {
        'subscription': sub, 'first_delivery': first_delivery,
    })


def pay_failed(request):
    return render(request, 'subscriptions/pay_failed.html')


@login_required
def renew(request, subscription_number):
    """Customer clicks the renewal link in email or profile.

    Creates (or reuses) a PENDING RENEWAL payment and routes to the pay flow.
    Same Razorpay machinery as initial signup.
    """
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )

    if sub.status == SubscriptionStatus.ENDED:
        messages.error(request, 'This subscription has ended. Subscribe again to restart.')
        return redirect('subscriptions:signup', plan_slug=sub.plan.slug)

    # Compute new period bounds (start = day after current period end).
    new_start = sub.next_billing_date or (sub.current_period_end + timedelta(days=1))
    if sub.plan.billing_period_days > 0:
        new_end = new_start + timedelta(days=sub.plan.billing_period_days - 1)
    else:
        new_end = new_start

    with transaction.atomic():
        SubscriptionPayment.objects.get_or_create(
            subscription=sub,
            payment_type=SubscriptionPayment.PaymentType.RENEWAL,
            status=SubscriptionPayment.PaymentStatus.PENDING,
            period_start=new_start,
            defaults={
                'period_end': new_end,
                'amount': sub.plan.price,
                'tax_amount': Decimal('0'),
                'total': sub.plan.price,
            },
        )

    return redirect('subscriptions:pay', subscription_number=sub.subscription_number)


# --------------------------------------------------------------------------
# Phase 7 Group C — User actions (skip / pause / resume / cancel / address)
# --------------------------------------------------------------------------
@login_required
def skip_delivery(request, subscription_number, delivery_id):
    """Skip one SCHEDULED future delivery; period gets a 1-day make-up."""
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )
    delivery = get_object_or_404(SubscriptionDelivery, pk=delivery_id, subscription=sub)

    if delivery.status != DeliveryStatus.SCHEDULED:
        messages.error(request, "This delivery can't be skipped.")
        return redirect(
            'accounts:profile_subscription_detail',
            subscription_number=sub.subscription_number,
        )
    if delivery.scheduled_date <= timezone.now().date():
        messages.error(request, 'Skip requests must be made at least 1 day in advance.')
        return redirect(
            'accounts:profile_subscription_detail',
            subscription_number=sub.subscription_number,
        )

    if request.method == 'POST':
        with transaction.atomic():
            delivery.status = DeliveryStatus.SKIPPED
            delivery.skipped_at = timezone.now()
            delivery.skipped_by_customer = True
            delivery.save(update_fields=[
                'status', 'skipped_at', 'skipped_by_customer', 'updated_at',
            ])

            # Extend period by 1 day, generate one make-up delivery on the new last day.
            sub.current_period_end += timedelta(days=1)
            sub.next_billing_date = sub.current_period_end + timedelta(days=1)
            sub.save(update_fields=['current_period_end', 'next_billing_date', 'updated_at'])

            generate_deliveries(sub, sub.current_period_end, sub.current_period_end)

        try:
            from .services.emails import send_delivery_skipped_email
            send_delivery_skipped_email(delivery)
        except Exception:
            logger.exception('skipped email failed for %s', delivery.pk)

        messages.success(
            request, 'Delivery skipped. Your period has been extended by 1 day.',
        )
        return redirect(
            'accounts:profile_subscription_detail',
            subscription_number=sub.subscription_number,
        )

    return render(request, 'subscriptions/skip_delivery.html', {
        'subscription': sub, 'delivery': delivery,
    })


@login_required
def pause(request, subscription_number):
    """Pause an ACTIVE subscription for a chosen window; period extends by N days."""
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )

    if sub.status != SubscriptionStatus.ACTIVE:
        messages.error(request, 'Only active subscriptions can be paused.')
        return redirect(
            'accounts:profile_subscription_detail',
            subscription_number=sub.subscription_number,
        )

    if request.method == 'POST':
        form = PauseForm(request.POST, subscription=sub)
        if form.is_valid():
            start = form.cleaned_data['pause_start']
            end = form.cleaned_data['pause_end']
            pause_days = (end - start).days + 1

            with transaction.atomic():
                # Mark all SCHEDULED deliveries inside [start, end] as PAUSED.
                sub.deliveries.filter(
                    status=DeliveryStatus.SCHEDULED,
                    scheduled_date__gte=start,
                    scheduled_date__lte=end,
                ).update(status=DeliveryStatus.PAUSED)

                old_end = sub.current_period_end
                sub.current_period_end += timedelta(days=pause_days)
                sub.next_billing_date = sub.current_period_end + timedelta(days=1)
                sub.status = SubscriptionStatus.PAUSED
                sub.pause_started_at = start
                sub.paused_until = end
                sub.save(update_fields=[
                    'current_period_end', 'next_billing_date',
                    'status', 'pause_started_at', 'paused_until', 'updated_at',
                ])

                # Generate make-up deliveries for the appended window.
                generate_deliveries(
                    sub, old_end + timedelta(days=1), sub.current_period_end,
                )

            try:
                from .services.emails import send_subscription_paused_email
                send_subscription_paused_email(sub)
            except Exception:
                logger.exception('paused email failed for %s', sub.subscription_number)

            messages.success(
                request, f'Subscription paused. Period extended by {pause_days} day(s).',
            )
            return redirect(
                'accounts:profile_subscription_detail',
                subscription_number=sub.subscription_number,
            )
    else:
        form = PauseForm(subscription=sub, initial={
            'pause_start': timezone.now().date() + timedelta(days=1),
            'pause_end': timezone.now().date() + timedelta(days=7),
        })

    return render(request, 'subscriptions/pause.html', {
        'subscription': sub, 'form': form,
    })


@login_required
def resume(request, subscription_number):
    """Manually resume a PAUSED subscription, possibly before paused_until."""
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )
    if sub.status != SubscriptionStatus.PAUSED:
        messages.error(request, "Subscription isn't paused.")
        return redirect(
            'accounts:profile_subscription_detail',
            subscription_number=sub.subscription_number,
        )

    if request.method == 'POST':
        with transaction.atomic():
            today = timezone.now().date()

            # Restore PAUSED deliveries from today onward (past PAUSED rows
            # represent days that have actually elapsed in pause — leave them).
            sub.deliveries.filter(
                status=DeliveryStatus.PAUSED,
                scheduled_date__gte=today,
            ).update(status=DeliveryStatus.SCHEDULED)

            # If resuming early, shrink the period by the unused pause days
            # and remove the surplus make-up deliveries past the new period end.
            if sub.paused_until and today < sub.paused_until:
                unused = (sub.paused_until - today).days
                sub.current_period_end -= timedelta(days=unused)
                sub.next_billing_date = sub.current_period_end + timedelta(days=1)
                sub.deliveries.filter(
                    scheduled_date__gt=sub.current_period_end,
                ).delete()

            sub.status = SubscriptionStatus.ACTIVE
            sub.pause_started_at = None
            sub.paused_until = None
            sub.save(update_fields=[
                'status', 'pause_started_at', 'paused_until',
                'current_period_end', 'next_billing_date', 'updated_at',
            ])

        try:
            from .services.emails import send_subscription_resumed_email
            send_subscription_resumed_email(sub)
        except Exception:
            logger.exception('resumed email failed for %s', sub.subscription_number)

        messages.success(request, 'Subscription resumed.')
        return redirect(
            'accounts:profile_subscription_detail',
            subscription_number=sub.subscription_number,
        )

    return render(request, 'subscriptions/resume_confirm.html', {'subscription': sub})


@login_required
def cancel(request, subscription_number):
    """Cancel at period end. Deliveries within the paid period continue."""
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )

    if sub.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAUSED):
        messages.error(request, "Subscription can't be cancelled in its current state.")
        return redirect(
            'accounts:profile_subscription_detail',
            subscription_number=sub.subscription_number,
        )

    if request.method == 'POST':
        form = CancellationForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            notes = (form.cleaned_data.get('notes') or '').strip()
            reason_field = f'{reason}: {notes}' if notes else reason

            with transaction.atomic():
                sub.cancel_at_period_end = True
                sub.cancelled_at = timezone.now()
                sub.cancellation_reason = reason_field[:200]
                sub.status = SubscriptionStatus.CANCELLED
                sub.save(update_fields=[
                    'cancel_at_period_end', 'cancelled_at',
                    'cancellation_reason', 'status', 'updated_at',
                ])

            try:
                from .services.emails import send_subscription_cancelled_email
                send_subscription_cancelled_email(sub)
            except Exception:
                logger.exception('cancelled email failed for %s', sub.subscription_number)

            messages.success(
                request,
                "Subscription cancelled. You'll continue receiving deliveries "
                'until the current period ends.',
            )
            return redirect(
                'accounts:profile_subscription_detail',
                subscription_number=sub.subscription_number,
            )
    else:
        form = CancellationForm()

    return render(request, 'subscriptions/cancel.html', {
        'subscription': sub, 'form': form,
    })


@login_required
def update_address(request, subscription_number):
    """Switch the subscription to a different saved address; propagates to future deliveries."""
    sub = get_object_or_404(
        Subscription, subscription_number=subscription_number, user=request.user,
    )
    addresses = Address.objects.filter(user=request.user)

    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        address = get_object_or_404(Address, pk=address_id, user=request.user)

        # Address.attr -> Subscription/SubscriptionDelivery.attr. Note that
        # Address.recipient_phone maps to shipping_phone (not shipping_recipient_phone).
        addr_field_map = [
            ('recipient_name', 'shipping_recipient_name'),
            ('recipient_phone', 'shipping_phone'),
            ('line_1', 'shipping_line_1'),
            ('line_2', 'shipping_line_2'),
            ('landmark', 'shipping_landmark'),
            ('city', 'shipping_city'),
            ('state', 'shipping_state'),
            ('pincode', 'shipping_pincode'),
        ]
        shipping_attrs = [s for _, s in addr_field_map]

        with transaction.atomic():
            for src, dst in addr_field_map:
                setattr(sub, dst, getattr(address, src))
            sub.save(update_fields=shipping_attrs + ['updated_at'])

            # Update future scheduled deliveries only — leave past/in-flight alone.
            future = list(sub.deliveries.filter(
                status=DeliveryStatus.SCHEDULED,
                scheduled_date__gt=timezone.now().date(),
            ))
            for d in future:
                for src, dst in addr_field_map:
                    setattr(d, dst, getattr(address, src))
            if future:
                SubscriptionDelivery.objects.bulk_update(future, shipping_attrs)

        messages.success(
            request, 'Address updated. Future deliveries will use the new address.',
        )
        return redirect(
            'accounts:profile_subscription_detail',
            subscription_number=sub.subscription_number,
        )

    return render(request, 'subscriptions/update_address.html', {
        'subscription': sub, 'addresses': addresses,
    })
