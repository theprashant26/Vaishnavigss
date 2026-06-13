from django.urls import path

from . import views

app_name = 'services'

urlpatterns = [
    path('', views.service_list, name='service_list'),

    # Phase 5 inquiry forms
    path('adoption/', views.adoption, name='adoption'),
    path('adoption/success/', views.adoption_success, name='adoption_success'),
    path('wholesale/', views.wholesale, name='wholesale'),
    path('wholesale/success/', views.wholesale_success, name='wholesale_success'),
    path('hampers/', views.hampers, name='hampers'),
    path('hampers/success/', views.hampers_success, name='hampers_success'),
    path('visit/', views.visit, name='visit'),
    path('visit/success/', views.visit_success, name='visit_success'),
]
