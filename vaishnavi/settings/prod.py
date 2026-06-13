"""
Production settings — Postgres, whitenoise, SMTP, hardened SSL/cookies.

Required environment variables (will raise KeyError if missing):
    SECRET_KEY, DB_NAME, DB_USER, DB_PASSWORD

Optional with safe defaults:
    DB_HOST (127.0.0.1), DB_PORT (5432),
    ALLOWED_HOSTS (csv), EMAIL_HOST + creds, ADMIN_EMAIL,
    MEDIA_ROOT (for attached volume), SERVER_EMAIL.
"""
import os

from .base import *  # noqa: F401, F403
from .base import BASE_DIR, MIDDLEWARE  # noqa: F401  — for explicit re-use below

DEBUG = False

# Required in production. Fail loudly if missing.
SECRET_KEY = os.environ['SECRET_KEY']

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]


# --------------------------------------------------------------------------
# Database — Postgres (Group B)
# --------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}


# --------------------------------------------------------------------------
# Cache — database-backed so multi-worker gunicorn + cron commands share state
# --------------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache_table',
    }
}


# --------------------------------------------------------------------------
# Static / media — whitenoise serves static, nginx serves /media/ directly (Group C)
# --------------------------------------------------------------------------
# Override MEDIA_ROOT here so it can point at an attached volume in prod.
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'media'))

# Insert WhiteNoiseMiddleware immediately after SecurityMiddleware.
MIDDLEWARE = list(MIDDLEWARE)
_sec_idx = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
MIDDLEWARE.insert(_sec_idx + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}


# --------------------------------------------------------------------------
# Email — SMTP (Group D)
# --------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'

ADMINS = [('Admin', os.environ.get('ADMIN_EMAIL', ''))] if os.environ.get('ADMIN_EMAIL') else []
MANAGERS = ADMINS
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', 'errors@vaishnavigss.com')


# --------------------------------------------------------------------------
# Security hardening (Group C)
# --------------------------------------------------------------------------
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Start HSTS low (60s) for the first week so we can roll back if needed.
# Bump to 31536000 (1 year) once the site is verified stable under HTTPS.
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '60'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False  # only after submitting to hstspreload.org

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # AJAX in Phase 6 reads the token
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in ALLOWED_HOSTS if host]
