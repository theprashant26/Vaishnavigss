from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def _send(subject: str, to_email: str, text_template: str, html_template: str, context: dict):
    text_body = render_to_string(text_template, context)
    html_body = render_to_string(html_template, context)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)


def send_email_otp(email: str, code: str, purpose: str = 'verification'):
    """Generic OTP delivery via email (used by login_otp + register flows)."""
    context = {
        'code': code,
        'purpose': purpose,
        'site_name': settings.SITE_NAME,
        'lifetime_minutes': 10,
    }
    _send(
        subject=f'Your {settings.SITE_NAME} OTP: {code}',
        to_email=email,
        text_template='accounts/emails/otp_email.txt',
        html_template='accounts/emails/otp_email.html',
        context=context,
    )


def send_verification_email(user, code: str):
    """Email verification — same as send_email_otp but with a friendlier subject."""
    context = {
        'code': code,
        'first_name': user.first_name or user.username,
        'site_name': settings.SITE_NAME,
        'lifetime_minutes': 10,
    }
    _send(
        subject=f'Verify your {settings.SITE_NAME} email',
        to_email=user.email,
        text_template='accounts/emails/verify_email.txt',
        html_template='accounts/emails/verify_email.html',
        context=context,
    )


def send_welcome_email(user):
    context = {
        'first_name': user.first_name or user.username,
        'site_name': settings.SITE_NAME,
        'site_domain': settings.SITE_DOMAIN,
    }
    _send(
        subject=f'Welcome to {settings.SITE_NAME}',
        to_email=user.email,
        text_template='accounts/emails/welcome.txt',
        html_template='accounts/emails/welcome.html',
        context=context,
    )
