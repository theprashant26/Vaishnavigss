"""
Development settings — local laptop with SQLite, console email, no SSL.
"""
import os

from .base import *  # noqa: F401, F403
from .base import BASE_DIR, LOGGING

DEBUG = True

ALLOWED_HOSTS = ['*']

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-qvwn10^t=y#l5#psbg_)sqs+%$6la@c&sj860-)ath@xk%2*7(',
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Cache: locmem is fine for single-process dev. Prod uses DatabaseCache.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Email: print to console.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Dev: no SSL, relaxed cookies.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Logging override: drop mail_admins handler (no SMTP configured in dev).
LOGGING['handlers'].pop('mail_admins', None)
for _logger in LOGGING['loggers'].values():
    _logger['handlers'] = [h for h in _logger.get('handlers', []) if h != 'mail_admins']

# Static: skip manifest hashing in dev so template references don't break
# between collectstatic runs.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
