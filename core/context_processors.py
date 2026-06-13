from catalog.models import Category

from .models import SiteSettings


def site_settings(request):
    return {'site': SiteSettings.load()}


def category_nav(request):
    """Active categories for the navbar dropdown / mobile sublist."""
    return {'nav_categories': Category.objects.filter(is_active=True)}
