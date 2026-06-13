from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    Cart, CartItem, Order, OrderItem,
    OrderStatus, PaymentStatus, PromoCode,
)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ('variant',)
    readonly_fields = ('added_at',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_count', 'subtotal', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CartItemInline]


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'min_order_amount',
                    'uses_count', 'max_uses', 'is_active', 'valid_from', 'valid_until')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code',)
    readonly_fields = ('uses_count', 'created_at')


# --------------------------------------------------------------------------
# Orders (Phase 6 Group C)
# --------------------------------------------------------------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ('product_name', 'variant_label', 'hsn_code', 'unit_price',
              'gst_rate', 'quantity', 'line_subtotal', 'line_tax', 'line_total')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'status', 'payment_status',
                    'payment_method', 'total', 'placed_at')
    list_filter = ('status', 'payment_status', 'payment_method', 'placed_at')
    search_fields = ('order_number', 'user__email', 'user__username',
                     'shipping_recipient_name', 'shipping_phone')
    date_hierarchy = 'placed_at'
    readonly_fields = (
        'order_number', 'subtotal', 'discount', 'promo_code',
        'shipping_charge', 'tax_amount', 'total',
        'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature',
        'placed_at', 'paid_at', 'created_at', 'updated_at',
    )
    inlines = [OrderItemInline]
    actions = ['mark_processing', 'mark_shipped', 'mark_delivered']
    fieldsets = (
        ('Order', {
            'fields': ('order_number', 'user', 'status', 'payment_status', 'payment_method'),
        }),
        ('Shipping', {
            'fields': ('shipping_recipient_name', 'shipping_phone',
                       'shipping_line_1', 'shipping_line_2', 'shipping_landmark',
                       'shipping_city', 'shipping_state', 'shipping_pincode'),
        }),
        ('Money', {
            'fields': ('subtotal', 'discount', 'promo_code',
                       'shipping_charge', 'tax_amount', 'total'),
        }),
        ('Razorpay', {
            'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature'),
            'classes': ('collapse',),
        }),
        ('Notes', {
            'fields': ('customer_notes', 'internal_notes'),
        }),
        ('Timeline', {
            'fields': ('placed_at', 'paid_at', 'shipped_at', 'delivered_at',
                       'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.action(description='Mark as processing')
    def mark_processing(self, request, queryset):
        n = queryset.filter(status__in=[OrderStatus.PAID, OrderStatus.PENDING]).update(
            status=OrderStatus.PROCESSING,
        )
        self.message_user(request, f'{n} order(s) marked as processing.', messages.SUCCESS)

    @admin.action(description='Mark as shipped + email customer')
    def mark_shipped(self, request, queryset):
        # Local import — avoids circular at module load.
        from .services.emails import send_order_shipped_email
        sent = 0
        for order in queryset:
            if order.status in (OrderStatus.PAID, OrderStatus.PROCESSING):
                order.status = OrderStatus.SHIPPED
                order.shipped_at = timezone.now()
                order.save(update_fields=['status', 'shipped_at', 'updated_at'])
                try:
                    send_order_shipped_email(order)
                    sent += 1
                except Exception:
                    pass
        self.message_user(request, f'Marked {sent} order(s) as shipped + emailed customers.', messages.SUCCESS)

    @admin.action(description='Mark as delivered + email customer')
    def mark_delivered(self, request, queryset):
        from .services.emails import send_order_delivered_email
        sent = 0
        for order in queryset:
            if order.status == OrderStatus.SHIPPED:
                order.status = OrderStatus.DELIVERED
                order.delivered_at = timezone.now()
                order.save(update_fields=['status', 'delivered_at', 'updated_at'])
                try:
                    send_order_delivered_email(order)
                    sent += 1
                except Exception:
                    pass
        self.message_user(request, f'Marked {sent} order(s) as delivered + emailed customers.', messages.SUCCESS)
