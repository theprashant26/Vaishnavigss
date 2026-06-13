from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.cart, name='cart'),
    path('checkout/', views.checkout, name='checkout'),  # replaced in Group C

    # AJAX
    path('api/add/', views.cart_api_add, name='cart_api_add'),
    path('api/update/', views.cart_api_update, name='cart_api_update'),
    path('api/remove/', views.cart_api_remove, name='cart_api_remove'),
    path('api/bulk-add/', views.cart_api_bulk_add, name='cart_api_bulk_add'),

    # Promo codes
    path('promo/apply/', views.cart_apply_promo, name='cart_apply_promo'),
    path('promo/remove/', views.cart_remove_promo, name='cart_remove_promo'),

    # Checkout — 3-step flow (Group C)
    path('checkout/address/', views.checkout_address, name='checkout_address'),
    path('checkout/payment/', views.checkout_payment, name='checkout_payment'),
    path('checkout/review/', views.checkout_review, name='checkout_review'),
    path('checkout/success/<str:order_number>/', views.checkout_success, name='checkout_success'),

    # Razorpay (Group D)
    path('checkout/pay/<str:order_number>/', views.checkout_pay, name='checkout_pay'),
    path('checkout/callback/', views.checkout_callback, name='checkout_callback'),
    path('checkout/webhook/razorpay/', views.webhook_razorpay, name='webhook_razorpay'),
    path('checkout/failed/', views.checkout_failed, name='checkout_failed'),

    # GST invoice (Group E.5)
    path('invoice/<str:order_number>/', views.invoice, name='invoice'),
]
