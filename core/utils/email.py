"""
Inquiry email sender (Phase 5).

`send_inquiry_emails` fires two emails per inquiry:
  - business notification (to site.email_primary or override)
  - customer confirmation (to the submitter)

Both render .txt + .html siblings of the same template path stem.
Failures are logged but never raised — form submission still succeeds.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _send_one(*, subject: str, to_email: str, text_template: str, html_template: str, context: dict):
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


def send_inquiry_emails(
    *,
    submission,
    business_subject: str,
    business_template: str,   # e.g. 'emails/contact_business.txt' (.html sibling assumed)
    customer_subject: str,
    customer_template: str,
    customer_email: str,
    business_email: str | None = None,
):
    """Fire both emails. Log errors; never raise."""
    # Resolve business email lazily — avoid module-level import cycle.
    if business_email is None:
        from core.models import SiteSettings
        business_email = SiteSettings.load().email_primary or settings.DEFAULT_FROM_EMAIL

    context = {
        'submission': submission,
        'site_name': settings.SITE_NAME,
        'site_domain': settings.SITE_DOMAIN,
    }

    # Business email
    try:
        _send_one(
            subject=business_subject,
            to_email=business_email,
            text_template=business_template,
            html_template=business_template.replace('.txt', '.html'),
            context=context,
        )
    except Exception:
        logger.error('Inquiry business email failed for submission pk=%s', submission.pk, exc_info=True)

    # Customer email
    if customer_email:
        try:
            _send_one(
                subject=customer_subject,
                to_email=customer_email,
                text_template=customer_template,
                html_template=customer_template.replace('.txt', '.html'),
                context=context,
            )
        except Exception:
            logger.error('Inquiry customer email failed for submission pk=%s', submission.pk, exc_info=True)
