from django.contrib import admin

from .models import Address, OneTimePasscode, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'first_name', 'last_name', 'phone',
        'email_verified', 'is_phone_verified', 'marketing_opt_in', 'created_at',
    )
    list_filter = ('email_verified', 'is_phone_verified', 'marketing_opt_in')
    search_fields = ('user__username', 'user__email', 'first_name', 'last_name', 'phone')
    readonly_fields = ('created_at', 'updated_at', 'email_verified_at', 'phone_verified_at')
    autocomplete_fields = ('user',)
    fieldsets = (
        (None, {'fields': ('user', 'first_name', 'last_name')}),
        ('Contact', {'fields': ('phone',)}),
        ('Verification', {
            'fields': ('email_verified', 'email_verified_at', 'is_phone_verified', 'phone_verified_at'),
        }),
        ('Preferences', {'fields': ('marketing_opt_in',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('label', 'user', 'recipient_name', 'city', 'state', 'pincode', 'is_default', 'updated_at')
    list_filter = ('is_default', 'state')
    search_fields = ('user__username', 'user__email', 'recipient_name', 'city', 'pincode', 'label')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OneTimePasscode)
class OneTimePasscodeAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'identifier_type', 'purpose', 'code', 'is_used', 'attempts', 'created_at', 'expires_at')
    list_filter = ('identifier_type', 'purpose', 'is_used')
    search_fields = ('identifier', 'user__username', 'user__email')
    autocomplete_fields = ('user',)
    readonly_fields = ('code', 'created_at', 'expires_at', 'used_at', 'attempts', 'is_used')
