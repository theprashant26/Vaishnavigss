from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


# --------------------------------------------------------------------------
# Cart (Phase 6 Group A) — one per logged-in user. Anonymous carts live in session.
# --------------------------------------------------------------------------
class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Cart of {self.user.username}'

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal('0'))


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'variant')
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.quantity}× {self.variant}'

    @property
    def line_total(self):
        return self.variant.price * self.quantity


# --------------------------------------------------------------------------
# PromoCode (Phase 6 Group A)
# --------------------------------------------------------------------------
class PromoCode(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = 'PERCENT', 'Percent off'
        AMOUNT = 'AMOUNT', 'Flat amount off'

    code = models.CharField(max_length=30, unique=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    uses_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or '').upper().strip()
        super().save(*args, **kwargs)

    def is_valid(self, order_total) -> tuple[bool, str]:
        """Returns (is_valid, error_message). Empty error means valid."""
        if not self.is_active:
            return False, 'This promo code is no longer active.'
        now = timezone.now()
        if now < self.valid_from:
            return False, 'This promo code is not yet active.'
        if now > self.valid_until:
            return False, 'This promo code has expired.'
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False, 'This promo code has reached its usage limit.'
        if order_total < self.min_order_amount:
            return False, f'Promo requires a minimum order of ₹{self.min_order_amount:.0f}.'
        return True, ''

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """How much to deduct from `subtotal`. Never exceeds subtotal."""
        if self.discount_type == self.DiscountType.PERCENT:
            disc = (subtotal * self.discount_value / Decimal('100')).quantize(Decimal('0.01'))
        else:
            disc = self.discount_value
        return min(disc, subtotal)


# --------------------------------------------------------------------------
# Orders (Phase 6 Group C)
# --------------------------------------------------------------------------
class OrderStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending payment'
    PAID = 'PAID', 'Paid'
    PROCESSING = 'PROCESSING', 'Processing'
    SHIPPED = 'SHIPPED', 'Shipped'
    DELIVERED = 'DELIVERED', 'Delivered'
    CANCELLED = 'CANCELLED', 'Cancelled'
    REFUNDED = 'REFUNDED', 'Refunded'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    REFUNDED = 'REFUNDED', 'Refunded'


class PaymentMethod(models.TextChoices):
    RAZORPAY = 'RAZORPAY', 'Online (Razorpay)'
    COD = 'COD', 'Cash on Delivery'


class Order(models.Model):
    order_number = models.CharField(max_length=30, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')

    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)

    # Address snapshot — frozen at order time even if user later edits their saved Address.
    shipping_recipient_name = models.CharField(max_length=100)
    shipping_phone = models.CharField(max_length=20)
    shipping_line_1 = models.CharField(max_length=200)
    shipping_line_2 = models.CharField(max_length=200, blank=True)
    shipping_landmark = models.CharField(max_length=200, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_pincode = models.CharField(max_length=10)

    # Money (all snapshots at order placement)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    promo_code = models.CharField(max_length=30, blank=True)
    shipping_charge = models.DecimalField(max_digits=8, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # Razorpay refs (blank for COD orders)
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature = models.CharField(max_length=200, blank=True)

    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    placed_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    def _generate_order_number(self) -> str:
        """Format: VG-YYYYMMDD-NNNN with a daily sequence."""
        today = timezone.now().date()
        prefix = f'VG-{today.strftime("%Y%m%d")}'
        count_today = Order.objects.filter(order_number__startswith=prefix).count() + 1
        return f'{prefix}-{count_today:04d}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT)
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT)

    # Snapshots at order time — frozen even if product/variant later edited.
    product_name = models.CharField(max_length=200)
    variant_label = models.CharField(max_length=50)
    hsn_code = models.CharField(max_length=10, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    line_tax = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.quantity}× {self.product_name} ({self.variant_label})'
