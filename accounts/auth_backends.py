import re

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .models import Profile


def normalize_phone(raw: str) -> str:
    """Strip spaces, +91/91 country code, leading 0 — return bare 10-digit phone."""
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


class EmailOrPhoneBackend(ModelBackend):
    """Authenticate via email OR 10-digit phone + password."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()

        if '@' in username:
            users = list(User.objects.filter(email__iexact=username.strip()))
        else:
            phone = normalize_phone(username)
            if len(phone) != 10:
                return None
            user_ids = list(
                Profile.objects.filter(phone=phone).values_list('user_id', flat=True)
            )
            users = list(User.objects.filter(pk__in=user_ids))

        # Defense in depth: multiple matches → refuse rather than guess.
        if len(users) != 1:
            return None

        user = users[0]
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
