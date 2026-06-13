from collections import OrderedDict
from datetime import date as _date

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import path
from django.utils import timezone

from core.admin import SubmissionAdminMixin

from .models import (
    DeliveryStatus,
    Subscription,
    SubscriptionDelivery,
    SubscriptionDeliveryItem,
    SubscriptionInquiry,
    SubscriptionPayment,
    SubscriptionPlan,
    SubscriptionPlanItem,
    SubscriptionStatus,
)


# --------------------------------------------------------------------------
# SubscriptionPlan + inline items
# --------------------------------------------------------------------------
class SubscriptionPlanItemInline(admin.TabularInline):
    model = SubscriptionPlanItem
    extra = 0
    autocomplete_fields = ('variant',)
    fields = ('variant', 'quantity_per_delivery', 'notes', 'display_order')


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'tier',
        'price',
        'delivery_frequency',
        'billing_period_days',
        'delivery_scope',
        'item_count',
        'is_self_serve',
        'is_featured',
        'is_active',
        'display_order',
    )
    list_filter = (
        'tier', 'delivery_frequency', 'delivery_scope',
        'is_self_serve', 'is_featured', 'is_active',
    )
    search_fields = ('name', 'slug', 'description', 'whats_included')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_featured', 'is_active', 'is_self_serve', 'display_order')
    ordering = ('tier', 'display_order', 'price')
    inlines = [SubscriptionPlanItemInline]
    fieldsets = (
        (None, {
            'fields': ('tier', 'name', 'slug', 'image'),
        }),
        ('Content', {
            'fields': ('description', 'whats_included'),
        }),
        ('Pricing & delivery', {
            'fields': (
                'price', 'delivery_frequency', 'delivery_scope',
                'billing_period_days', 'delivery_lead_days',
            ),
        }),
        ('Display & routing', {
            'fields': ('is_self_serve', 'is_featured', 'is_active', 'display_order'),
        }),
    )

    @admin.display(description='Items')
    def item_count(self, obj):
        return obj.items.count()


# --------------------------------------------------------------------------
# Subscription
# --------------------------------------------------------------------------
class SubscriptionDeliveryInline(admin.TabularInline):
    model = SubscriptionDelivery
    fields = ('scheduled_date', 'status', 'shipping_city', 'shipping_pincode')
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True
    max_num = 0  # display-only

    def get_queryset(self, request):
        # Show last 30 deliveries for the subscription
        qs = super().get_queryset(request).order_by('-scheduled_date')[:30]
        return qs

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'subscription_number', 'user', 'plan', 'status',
        'current_period_end', 'next_delivery_date_display',
    )
    list_filter = ('status', 'plan')
    search_fields = ('subscription_number', 'user__email', 'user__username', 'shipping_phone')
    autocomplete_fields = ('user', 'plan')
    readonly_fields = (
        'subscription_number', 'created_at', 'activated_at', 'updated_at',
        'cancelled_at',
    )
    inlines = [SubscriptionDeliveryInline]
    actions = ['cancel_immediately', 'force_expire']
    fieldsets = (
        (None, {
            'fields': ('subscription_number', 'user', 'plan', 'status'),
        }),
        ('Period', {
            'fields': ('current_period_start', 'current_period_end', 'next_billing_date'),
        }),
        ('Pause', {
            'fields': ('pause_started_at', 'paused_until'),
            'classes': ('collapse',),
        }),
        ('Cancellation', {
            'fields': ('cancel_at_period_end', 'cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',),
        }),
        ('Shipping address (snapshot)', {
            'fields': (
                'shipping_recipient_name', 'shipping_phone',
                'shipping_line_1', 'shipping_line_2', 'shipping_landmark',
                'shipping_city', 'shipping_state', 'shipping_pincode',
                'delivery_time_slot',
            ),
        }),
        ('Notes', {
            'fields': ('customer_notes', 'internal_notes'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'activated_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Next delivery')
    def next_delivery_date_display(self, obj):
        nd = obj.next_delivery
        return nd.scheduled_date if nd else '—'

    @admin.action(description='Cancel immediately (end period now)')
    def cancel_immediately(self, request, queryset):
        n = 0
        for sub in queryset:
            sub.status = SubscriptionStatus.ENDED
            sub.cancel_at_period_end = True
            sub.cancelled_at = timezone.now()
            sub.current_period_end = timezone.now().date()
            sub.save()
            n += 1
        self.message_user(request, f'Cancelled {n} subscription(s) immediately.', messages.SUCCESS)

    @admin.action(description='Force expire (mark EXPIRED)')
    def force_expire(self, request, queryset):
        updated = queryset.update(status=SubscriptionStatus.EXPIRED)
        self.message_user(request, f'Marked {updated} subscription(s) as EXPIRED.', messages.SUCCESS)


# --------------------------------------------------------------------------
# SubscriptionDelivery
# --------------------------------------------------------------------------
class SubscriptionDeliveryItemInline(admin.TabularInline):
    model = SubscriptionDeliveryItem
    extra = 0
    readonly_fields = ('variant', 'product_name', 'variant_label', 'quantity')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SubscriptionDelivery)
class SubscriptionDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'scheduled_date', 'subscription', 'status',
        'shipping_city', 'shipping_pincode', 'delivery_window',
    )
    list_filter = ('status', 'scheduled_date', 'shipping_pincode', 'delivery_window')
    search_fields = (
        'subscription__subscription_number', 'shipping_phone', 'shipping_pincode',
        'shipping_recipient_name',
    )
    autocomplete_fields = ('subscription',)
    date_hierarchy = 'scheduled_date'
    readonly_fields = ('subscription', 'created_at', 'updated_at')
    inlines = [SubscriptionDeliveryItemInline]
    actions = ['mark_out_for_delivery', 'mark_delivered', 'mark_missed']
    change_list_template = 'admin/subscriptions/subscriptiondelivery/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'roster/',
                self.admin_site.admin_view(delivery_roster_view),
                name='subscriptions_subscriptiondelivery_roster',
            ),
        ]
        return custom + urls

    @admin.action(description='Mark as out for delivery')
    def mark_out_for_delivery(self, request, queryset):
        updated = queryset.update(status=DeliveryStatus.OUT_FOR_DELIVERY)
        self.message_user(request, f'{updated} delivery/deliveries out for delivery.', messages.SUCCESS)

    @admin.action(description='Mark as delivered')
    def mark_delivered(self, request, queryset):
        n = 0
        for d in queryset:
            d.status = DeliveryStatus.DELIVERED
            d.delivered_at = timezone.now()
            d.save()
            n += 1
        self.message_user(request, f'{n} delivery/deliveries marked delivered.', messages.SUCCESS)

    @admin.action(description='Mark as missed')
    def mark_missed(self, request, queryset):
        updated = queryset.update(status=DeliveryStatus.MISSED)
        self.message_user(request, f'{updated} delivery/deliveries marked missed.', messages.SUCCESS)


# --------------------------------------------------------------------------
# SubscriptionPayment
# --------------------------------------------------------------------------
@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_number', 'subscription', 'payment_type',
        'status', 'total', 'paid_at',
    )
    list_filter = ('payment_type', 'status', 'paid_at')
    search_fields = (
        'payment_number', 'subscription__subscription_number',
        'razorpay_order_id', 'razorpay_payment_id',
    )
    autocomplete_fields = ('subscription',)
    readonly_fields = (
        'payment_number', 'razorpay_order_id', 'razorpay_payment_id',
        'razorpay_signature', 'paid_at', 'created_at', 'updated_at',
    )


# --------------------------------------------------------------------------
# SubscriptionInquiry (Phase 5, unchanged)
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Daily delivery roster — the killer feature for the milk team
# --------------------------------------------------------------------------
@staff_member_required
def delivery_roster_view(request):
    """Group E.2 — print-friendly delivery roster for a single date.

    Groups by pincode then by route window so the dispatcher can hand a
    pincode-block to one rider. Renders as HTML; staff prints to PDF
    via the browser if they want a paper copy.
    """
    date_str = (request.GET.get('date') or timezone.now().date().isoformat()).strip()
    try:
        roster_date = _date.fromisoformat(date_str)
    except ValueError:
        roster_date = timezone.now().date()

    qs = (
        SubscriptionDelivery.objects
        .filter(scheduled_date=roster_date)
        .exclude(status__in=[DeliveryStatus.SKIPPED, DeliveryStatus.PAUSED])
        .select_related('subscription', 'subscription__plan')
        .prefetch_related('items')
        .order_by('shipping_pincode', 'delivery_window', 'shipping_recipient_name')
    )

    # Group by (pincode, window). OrderedDict preserves insertion (which the
    # queryset already orders by pincode then window).
    grouped = OrderedDict()
    for d in qs:
        key = (d.shipping_pincode or '—', d.delivery_window or 'MORNING')
        grouped.setdefault(key, []).append(d)

    totals = {
        'deliveries': qs.count(),
        'scheduled': qs.filter(status=DeliveryStatus.SCHEDULED).count(),
        'out_for_delivery': qs.filter(status=DeliveryStatus.OUT_FOR_DELIVERY).count(),
        'delivered': qs.filter(status=DeliveryStatus.DELIVERED).count(),
        'missed': qs.filter(status=DeliveryStatus.MISSED).count(),
        'pincodes': len({k[0] for k in grouped.keys()}),
    }

    return render(request, 'admin/subscriptions/roster.html', {
        'title': f'Delivery roster — {roster_date:%a, %d %b %Y}',
        'roster_date': roster_date,
        'prev_date': roster_date.replace(day=max(1, roster_date.day - 1)) if roster_date.day > 1 else None,
        'grouped': grouped,
        'totals': totals,
        # Bare-minimum admin context to satisfy admin/base.html
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
        'has_permission': True,
        'is_popup': False,
        'is_nav_sidebar_enabled': True,
        'available_apps': admin.site.get_app_list(request),
        'opts': SubscriptionDelivery._meta,
    })


@admin.register(SubscriptionInquiry)
class SubscriptionInquiryAdmin(SubmissionAdminMixin, admin.ModelAdmin):
    list_display = ('created_at', 'status', 'name', 'plan', 'email_display', 'phone_display')
    list_filter = SubmissionAdminMixin.list_filter + ('plan',)
    search_fields = ('name', 'email', 'phone', 'delivery_city', 'delivery_pincode', 'message')
    autocomplete_fields = ('plan',)
    fieldsets = (
        ('Plan', {'fields': ('plan',)}),
        ('Contact', {'fields': ('name', 'email', 'phone')}),
        ('Delivery', {'fields': ('delivery_city', 'delivery_pincode', 'start_date_preference')}),
        ('Message', {'fields': ('message',)}),
        ('Internal', {'fields': ('status', 'internal_notes', 'user')}),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
