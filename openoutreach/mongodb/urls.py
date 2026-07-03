from django.urls import path
from . import views

app_name = "mongodb"

urlpatterns = [
    path("mongodb/health/", views.health_check, name="health_check"),
    path("mongodb/profile/", views.user_profile_view, name="user_profile"),
    path("mongodb/profile/update/", views.update_user_profile, name="update_user_profile"),
]
