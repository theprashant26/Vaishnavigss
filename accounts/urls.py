from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = 'accounts'

urlpatterns = [
    # Registration
    path('register/', views.register, name='register'),
    path('register/verify/', views.register_verify, name='register_verify'),

    # Password login
    path('login/', views.login_view, name='login'),

    # OTP login
    path('login/otp/', views.login_otp_request, name='login_otp'),
    path('login/otp/verify/', views.login_otp_verify, name='login_otp_verify'),

    # Logout — Django built-in, POST-only in Django 5.x
    path(
        'logout/',
        auth_views.LogoutView.as_view(next_page=reverse_lazy('core:home')),
        name='logout',
    ),

    # Profile — dashboard + sub-views (all @login_required)
    path('profile/', views.profile_view, name='profile'),
    path('profile/orders/', views.profile_orders, name='profile_orders'),
    path('profile/orders/<str:order_number>/', views.profile_order_detail, name='profile_order_detail'),
    path('profile/subscriptions/', views.profile_subscriptions, name='profile_subscriptions'),
    path('profile/subscriptions/<str:subscription_number>/', views.profile_subscription_detail, name='profile_subscription_detail'),
    path('profile/wishlist/', views.profile_wishlist, name='profile_wishlist'),
    path('profile/settings/', views.profile_settings, name='profile_settings'),
    path('profile/password/', views.password_change, name='password_change'),

    # Addresses (CRUD; set-default is POST-only)
    path('profile/addresses/', views.address_list, name='address_list'),
    path('profile/addresses/add/', views.address_add, name='address_add'),
    path('profile/addresses/<int:pk>/edit/', views.address_edit, name='address_edit'),
    path('profile/addresses/<int:pk>/delete/', views.address_delete, name='address_delete'),
    path('profile/addresses/<int:pk>/set-default/', views.address_set_default, name='address_set_default'),

    # Password reset — Django built-in 4-step flow with branded templates + emails.
    path(
        'password/reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/emails/password_reset_email.txt',
            html_email_template_name='accounts/emails/password_reset_email.html',
            subject_template_name='accounts/emails/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password/reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'password/reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
]
