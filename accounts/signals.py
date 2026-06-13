import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    """Auto-create a Profile whenever a new User is created."""
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    """Phase 6: move anonymous session cart into the user's DB cart on login."""
    # Local import — avoids loading orders models during AppConfig setup.
    from orders.services.cart import CartService
    try:
        CartService(request).merge_session_to_db()
    except Exception:
        logger.exception('merge_cart_on_login failed for user=%s', user.pk)
