from django.urls import path

from . import views

app_name = 'subscriptions'

urlpatterns = [
    # Phase 5 — Inquiry (non-self-serve plans)
    path('plans/<slug:plan_slug>/inquire/', views.inquiry, name='inquiry'),
    path('plans/<slug:plan_slug>/inquire/success/', views.inquiry_success, name='inquiry_success'),

    # Phase 7 — Self-serve signup + payment
    path('plans/<slug:plan_slug>/signup/', views.signup, name='signup'),
    path('plans/<slug:plan_slug>/signup/review/', views.signup_review, name='signup_review'),
    path('<str:subscription_number>/pay/', views.pay, name='pay'),
    path('pay/callback/', views.pay_callback, name='pay_callback'),
    path('pay/failed/', views.pay_failed, name='pay_failed'),
    path('<str:subscription_number>/success/', views.signup_success, name='signup_success'),

    # Phase 7 Group C — User actions
    path('<str:subscription_number>/skip/<int:delivery_id>/', views.skip_delivery, name='skip_delivery'),
    path('<str:subscription_number>/pause/', views.pause, name='pause'),
    path('<str:subscription_number>/resume/', views.resume, name='resume'),
    path('<str:subscription_number>/cancel/', views.cancel, name='cancel'),
    path('<str:subscription_number>/address/', views.update_address, name='update_address'),

    # Phase 7 Group D — Renewal
    path('<str:subscription_number>/renew/', views.renew, name='renew'),
]
