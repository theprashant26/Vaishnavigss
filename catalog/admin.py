from django.contrib import admin

from .models import Breed, Category, Cow, Product, ProductImage, ProductVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')


@admin.register(Breed)
class BreedAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'region', 'display_order')
    search_fields = ('name', 'slug', 'region', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('display_order',)
    ordering = ('display_order', 'name')


@admin.register(Cow)
class CowAdmin(admin.ModelAdmin):
    list_display = ('name', 'breed', 'age_years', 'is_featured', 'display_order')
    list_filter = ('breed', 'is_featured')
    search_fields = ('name', 'bio')
    list_editable = ('is_featured', 'display_order')
    autocomplete_fields = ('breed',)
    ordering = ('display_order', 'name')


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('label', 'price', 'stock_quantity', 'sku', 'is_active', 'display_order')


class ProductImageInline(admin.StackedInline):
    model = ProductImage
    extra = 0
    fields = ('image', 'alt_text', 'display_order')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'starting_price_display',
        'variant_count',
        'is_featured',
        'is_active',
        'display_order',
    )
    list_filter = ('category', 'is_featured', 'is_active')
    search_fields = ('name', 'slug', 'description', 'short_description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_featured', 'is_active', 'display_order')
    autocomplete_fields = ('category',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('display_order', 'name')
    inlines = [ProductVariantInline, ProductImageInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'category', 'image'),
        }),
        ('Descriptions', {
            'fields': ('short_description', 'description', 'how_its_made', 'nutrition_info'),
        }),
        ('Display', {
            'fields': ('is_featured', 'is_active', 'display_order'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Starting price', ordering='display_order')
    def starting_price_display(self, obj):
        price = obj.starting_price
        return f'₹{price}' if price is not None else '—'

    @admin.display(description='Variants')
    def variant_count(self, obj):
        return obj.variants.count()


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'label', 'price', 'stock_quantity', 'sku', 'is_active', 'display_order')
    list_filter = ('is_active', 'product__category')
    search_fields = ('product__name', 'label', 'sku')
    autocomplete_fields = ('product',)
    list_editable = ('display_order', 'is_active')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'alt_text', 'display_order')
    search_fields = ('product__name', 'alt_text')
    autocomplete_fields = ('product',)
    list_editable = ('display_order',)
