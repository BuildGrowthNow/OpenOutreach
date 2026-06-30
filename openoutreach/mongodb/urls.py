from django.urls import path
from . import views

app_name = "mongodb"

urlpatterns = [
    path("mongodb/health/", views.health_check, name="health_check"),
]
