from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse

from .models import FAQ, ContactSubmission, NewsletterSubscriber, SiteSettings, SubmissionStatus, Testimonial


# --------------------------------------------------------------------------
# SubmissionAdminMixin (Phase 5)
# Used by every inquiry/submission admin in core / services / subscriptions.
# --------------------------------------------------------------------------
class SubmissionAdminMixin:
    """
    Reasonable defaults for any model that inherits SubmissionBase.
    Subclasses can extend list_display / list_filter / search_fields freely.
    """
    list_display = ('created_at', 'status', '__str__', 'email_display', 'phone_display')
    list_filter = ('status', 'created_at')
    readonly_fields = ('ip_address', 'user_agent', 'user', 'created_at', 'updated_at')
    actions = ['mark_contacted', 'mark_resolved', 'mark_spam']
    date_hierarchy = 'created_at'

    @admin.display(description='Email')
    def email_display(self, obj):
        return getattr(obj, 'email', '—')

    @admin.display(description='Phone')
    def phone_display(self, obj):
        return getattr(obj, 'phone', '—')

    @admin.action(description='Mark as contacted')
    def mark_contacted(self, request, queryset):
        n = queryset.update(status=SubmissionStatus.CONTACTED)
        self.message_user(request, f'{n} submission(s) marked as contacted.', messages.SUCCESS)

    @admin.action(description='Mark as resolved')
    def mark_resolved(self, request, queryset):
        n = queryset.update(status=SubmissionStatus.RESOLVED)
        self.message_user(request, f'{n} submission(s) marked as resolved.', messages.SUCCESS)

    @admin.action(description='Mark as spam')
    def mark_spam(self, request, queryset):
        n = queryset.update(status=SubmissionStatus.SPAM)
        self.message_user(request, f'{n} submission(s) marked as spam.', messages.SUCCESS)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'location', 'rating', 'is_featured', 'display_order', 'created_at')
    list_filter = ('rating', 'is_featured')
    search_fields = ('customer_name', 'location', 'content')
    list_editable = ('is_featured', 'display_order')
    readonly_fields = ('created_at',)
    ordering = ('display_order', '-created_at')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'display_order', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('question', 'answer')
    list_editable = ('display_order', 'is_active')
    ordering = ('category', 'display_order')


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Business Info', {
            'fields': ('business_name', 'tagline', 'cow_count'),
        }),
        ('Contact', {
            'fields': ('phone_primary', 'phone_whatsapp', 'email_primary', 'business_hours'),
        }),
        ('Address', {
            'fields': ('address_line_1', 'address_line_2', 'city', 'state', 'pincode'),
        }),
        ('Compliance', {
            'fields': ('gstin', 'fssai_license'),
        }),
        ('Social', {
            'fields': ('instagram_url', 'facebook_url', 'youtube_url'),
        }),
        ('Display', {
            'fields': ('map_embed_url',),
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return redirect(reverse('admin:core_sitesettings_change', args=[obj.pk]))


# --------------------------------------------------------------------------
# Phase 5 submissions
# --------------------------------------------------------------------------
@admin.register(ContactSubmission)
class ContactSubmissionAdmin(SubmissionAdminMixin, admin.ModelAdmin):
    list_display = SubmissionAdminMixin.list_display + ('subject',)
    list_filter = SubmissionAdminMixin.list_filter + ('subject',)
    search_fields = ('name', 'email', 'phone', 'message')
    fieldsets = (
        ('Submission', {'fields': ('name', 'email', 'phone', 'subject', 'message')}),
        ('Internal', {'fields': ('status', 'internal_notes', 'user')}),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'is_active', 'source', 'subscribed_at')
    list_filter = ('is_active', 'source', 'subscribed_at')
    search_fields = ('email', 'name')
    readonly_fields = ('unsubscribe_token', 'subscribed_at', 'unsubscribed_at', 'ip_address', 'user', 'confirmed_at')
    date_hierarchy = 'subscribed_at'
