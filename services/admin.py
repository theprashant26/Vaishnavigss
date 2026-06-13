from django.contrib import admin

from core.admin import SubmissionAdminMixin

from .models import AdoptionInquiry, HamperInquiry, Service, VisitBooking, WholesaleInquiry


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'service_type', 'price_display', 'is_active', 'display_order')
    list_filter = ('service_type', 'is_active')
    search_fields = ('name', 'slug', 'description', 'short_description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active', 'display_order')
    ordering = ('display_order', 'name')


# --------------------------------------------------------------------------
# Phase 5 inquiry admins
# --------------------------------------------------------------------------
@admin.register(AdoptionInquiry)
class AdoptionInquiryAdmin(SubmissionAdminMixin, admin.ModelAdmin):
    list_display = SubmissionAdminMixin.list_display + ('plan_interest',)
    list_filter = SubmissionAdminMixin.list_filter + ('plan_interest',)
    search_fields = ('name', 'email', 'phone', 'message')
    autocomplete_fields = ('preferred_cow', 'preferred_breed')
    fieldsets = (
        ('Submission', {
            'fields': ('name', 'email', 'phone', 'plan_interest',
                       'preferred_cow', 'preferred_breed', 'message'),
        }),
        ('Internal', {'fields': ('status', 'internal_notes', 'user')}),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(WholesaleInquiry)
class WholesaleInquiryAdmin(SubmissionAdminMixin, admin.ModelAdmin):
    list_display = ('created_at', 'status', 'business_name', 'contact_name', 'expected_volume', 'email_display', 'phone_display')
    list_filter = SubmissionAdminMixin.list_filter + ('expected_volume',)
    search_fields = ('business_name', 'contact_name', 'email', 'phone', 'gstin', 'products_interested')
    fieldsets = (
        ('Business', {'fields': ('business_name', 'contact_name', 'gstin', 'delivery_city')}),
        ('Contact', {'fields': ('email', 'phone')}),
        ('Inquiry', {'fields': ('expected_volume', 'products_interested', 'message')}),
        ('Internal', {'fields': ('status', 'internal_notes', 'user')}),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(HamperInquiry)
class HamperInquiryAdmin(SubmissionAdminMixin, admin.ModelAdmin):
    list_display = ('created_at', 'status', 'name', 'occasion', 'quantity', 'budget_range', 'delivery_date')
    list_filter = SubmissionAdminMixin.list_filter + ('occasion', 'budget_range')
    search_fields = ('name', 'email', 'phone', 'delivery_city', 'message')
    fieldsets = (
        ('Submission', {
            'fields': ('name', 'email', 'phone',
                       'occasion', 'budget_range', 'quantity',
                       'delivery_date', 'delivery_city', 'message'),
        }),
        ('Internal', {'fields': ('status', 'internal_notes', 'user')}),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(VisitBooking)
class VisitBookingAdmin(SubmissionAdminMixin, admin.ModelAdmin):
    # VisitBooking uses its own VisitStatus choices — list_display + filters mostly the same
    list_display = ('created_at', 'status', 'name', 'preferred_date', 'party_size', 'has_children', 'email_display')
    list_filter = ('status', 'preferred_date', 'has_children')
    search_fields = ('name', 'email', 'phone', 'special_requests')
    fieldsets = (
        ('Visitor', {'fields': ('name', 'email', 'phone', 'party_size', 'has_children')}),
        ('Date', {'fields': ('preferred_date', 'alternate_date')}),
        ('Notes', {'fields': ('special_requests',)}),
        ('Internal', {'fields': ('status', 'internal_notes', 'user')}),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
