"""Phase 8 — set the default django.contrib.sites Site row to SITE_DOMAIN.

Idempotent: only updates the existing Site #1 (auto-created by sites' 0001_initial).
"""
import os
from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations


def _populate_site(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    domain_url = os.environ.get('SITE_DOMAIN') or settings.SITE_DOMAIN
    parsed = urlparse(domain_url)
    # parsed.netloc is "vaishnavigss.com" or "127.0.0.1:8000". Falls back to the
    # raw string if SITE_DOMAIN was bare-hostname.
    domain = parsed.netloc or parsed.path or 'example.com'
    name = settings.SITE_NAME

    Site.objects.update_or_create(
        pk=1,
        defaults={'domain': domain, 'name': name},
    )


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_sitesettings_free_shipping_threshold_and_more'),
        ('sites', '0002_alter_domain_unique'),
    ]
    operations = [
        migrations.RunPython(_populate_site, _noop_reverse),
    ]
