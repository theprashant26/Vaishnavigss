from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core import views as core_views
from core.sitemaps import (
    CategorySitemap,
    ProductSitemap,
    StaticViewSitemap,
    SubscriptionPlanSitemap,
)

admin.site.site_header = 'Vaishnavi Gaushala — Admin'
admin.site.site_title = 'Vaishnavi Gaushala admin'
admin.site.index_title = 'Manage your gaushala'

handler404 = 'core.views.custom_404'
handler500 = 'core.views.custom_500'
handler403 = 'core.views.custom_403'

sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'subscriptions': SubscriptionPlanSitemap,
}

urlpatterns = [
    # Health check first — bypasses anything heavier (load balancers hit this constantly).
    path('healthz/', core_views.healthz, name='healthz'),

    # SEO endpoints
    path('robots.txt', core_views.robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),

    path('admin/', admin.site.urls),
    path('products/', include('catalog.urls')),
    path('services/', include('services.urls')),
    path('subscriptions/', include('subscriptions.urls')),
    path('cart/', include('orders.urls')),
    path('account/', include('accounts.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
