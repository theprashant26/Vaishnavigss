from django.db import models
from django.db.models import Q


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        # TODO: wire in Phase 3
        return '#'


class Breed(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    region = models.CharField(max_length=100)
    description = models.TextField()
    key_traits = models.TextField(blank=True)
    image = models.ImageField(upload_to='breeds/', blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        # TODO: wire in Phase 3
        return '#'


class Cow(models.Model):
    name = models.CharField(max_length=100)
    breed = models.ForeignKey(Breed, on_delete=models.PROTECT, related_name='cows')
    age_years = models.PositiveIntegerField(null=True, blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='cows/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Cows'

    def __str__(self):
        return f'{self.name} ({self.breed.name})'

    def get_absolute_url(self):
        # TODO: wire in Phase 3
        return '#'


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField()
    how_its_made = models.TextField(blank=True)
    nutrition_info = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    # Phase 6 — GST / invoice fields
    hsn_code = models.CharField(max_length=10, blank=True, help_text='HSN code for GST invoice')
    gst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='GST percentage, e.g. 12.00',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        # TODO: wire in Phase 3
        return '#'

    @property
    def starting_price(self):
        agg = self.variants.filter(is_active=True).aggregate(models.Min('price'))
        return agg['price__min']

    @property
    def is_in_stock(self):
        return self.variants.filter(is_active=True, stock_quantity__gt=0).exists()


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f'{self.product.name} — image #{self.display_order}'


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    label = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'price']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'label'],
                name='unique_variant_label_per_product',
            ),
            models.UniqueConstraint(
                fields=['sku'],
                condition=~Q(sku=''),
                name='unique_sku_when_not_blank',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} — {self.label}'
