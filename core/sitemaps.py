"""
Phase 8 Group E — sitemap definitions.

Mounted at /sitemap.xml via vaishnavi/urls.py.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product
from subscriptions.models import SubscriptionPlan


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return [
            'core:home',
            'core:about',
            'core:contact',
            'catalog:product_list',
            'services:service_list',
        ]

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    priority = 0.9
    changefreq = 'weekly'

    def items(self):
        return Product.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('catalog:product_detail', kwargs={'slug': obj.slug})


class CategorySitemap(Sitemap):
    priority = 0.7
    changefreq = 'weekly'

    def items(self):
        return Category.objects.filter(is_active=True)

    def location(self, obj):
        # Category URL is the product list with a ?category= filter.
        return reverse('catalog:product_list') + f'?category={obj.slug}'


class SubscriptionPlanSitemap(Sitemap):
    priority = 0.7
    changefreq = 'monthly'

    def items(self):
        return SubscriptionPlan.objects.filter(is_active=True, is_self_serve=True)

    def location(self, obj):
        return reverse('subscriptions:signup', kwargs={'plan_slug': obj.slug})
