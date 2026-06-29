# CRM URL Configuration
from django.urls import path
from . import views

urlpatterns = [
    path('link/<str:short_code>/', views.link_redirect, name='link_redirect'),
]