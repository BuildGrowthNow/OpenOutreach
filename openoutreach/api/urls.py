# API URL Configuration

from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views.health import HealthView
from .views.auth import (
    CustomTokenObtainPairView,
    AuthView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    UpdatePasswordView,
    LinkSupabaseUserView,
    SupabaseUserInfoView,
    SupabaseVerifyTokenView,
)
from .views.campaigns import (
    CampaignListView,
    CampaignDetailView,
    CampaignLeadsView,
    CampaignMessagesView,
    CampaignAnalyticsView,
    CampaignStateMachineView,
)
from .views.leads import (
    LeadListView,
    LeadDetailView,
    LeadProfileView,
    LeadMessagesView,
    LeadNotesView,
)
from .views.settings import SettingsView, RateLimitsView
from .views.analytics import AnalyticsView
from .views.links import LinksView, LinkDetailView
from .views.state_machine import StateMachineSimulationView
from .views.messages import MessagesView, MessagesDetailView
from .views.linkedin_credentials import (
    LinkedInCredentialsView,
    LinkedInCredentialsVerifyView,
    LinkedInCredentialsRotationView,
    LinkedInCredentialsHealthView,
    LinkedInCredentialsLogsView,
)

# API URL Patterns (no version prefix for frontend compatibility)
urlpatterns = [
    # Authentication endpoints
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/status/', AuthView.as_view(), name='auth_status'),
    path('auth/logout/', AuthView.as_view(), name='auth_logout'),
    
    # Password reset endpoints
    path('auth/password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('auth/update-password/', UpdatePasswordView.as_view(), name='update-password'),
    
    # Supabase endpoints
    path('auth/link-supabase-user/', LinkSupabaseUserView.as_view(), name='link-supabase-user'),
    path('auth/supabase-user/<str:supabase_user_id>/', SupabaseUserInfoView.as_view(), name='supabase-user-info'),
    path('auth/verify-supabase-token/', SupabaseVerifyTokenView.as_view(), name='verify-supabase-token'),
    
    # Health endpoint
    path('health/', HealthView.as_view(), name='health'),
    
    # Settings endpoints
    path('settings/', SettingsView.as_view(), name='settings'),
    path('settings/rate-limits/', RateLimitsView.as_view(), name='rate-limits'),
    
    # Campaigns endpoints
    path('campaigns/', CampaignListView.as_view(), name='campaign-list'),
    path('campaigns/<int:pk>/', CampaignDetailView.as_view(), name='campaign-detail'),
    path('campaigns/<int:pk>/leads/', CampaignLeadsView.as_view(), name='campaign-leads'),
    path('campaigns/<int:pk>/messages/', CampaignMessagesView.as_view(), name='campaign-messages'),
    path('campaigns/<int:pk>/analytics/', CampaignAnalyticsView.as_view(), name='campaign-analytics'),
    path('campaigns/<int:pk>/state-machine/', CampaignStateMachineView.as_view(), name='campaign-state-machine'),
    path('campaigns/<int:pk>/state-machine/validate/', CampaignStateMachineView.as_view(), name='campaign-state-machine-validate'),
    path('campaigns/<int:pk>/state-machine/simulate/', StateMachineSimulationView.as_view(), name='campaign-state-machine-simulate'),
    
    # Leads endpoints
    path('leads/', LeadListView.as_view(), name='lead-list'),
    path('leads/<int:pk>/', LeadDetailView.as_view(), name='lead-detail'),
    path('leads/<int:pk>/profile/', LeadProfileView.as_view(), name='lead-profile'),
    path('leads/<int:pk>/messages/', LeadMessagesView.as_view(), name='lead-messages'),
    path('leads/<int:pk>/notes/', LeadNotesView.as_view(), name='lead-notes-list'),
    path('leads/<int:pk>/notes/<int:note_id>/', LeadNotesView.as_view(), name='lead-notes-detail'),
    
    # Messages endpoints
    path('messages/', MessagesView.as_view(), name='messages-list'),
    path('messages/<int:pk>/', MessagesDetailView.as_view(), name='messages-detail'),
    
    # Analytics endpoints
    path('analytics/overview/', AnalyticsView.as_view(), name='analytics-overview'),
    
    # Links endpoints
    path('links/', LinksView.as_view(), name='links-list'),
    path('links/<int:pk>/', LinkDetailView.as_view(), name='link-detail'),
    
     # State machine endpoints (global simulation)
     path('state-machine/simulate/', StateMachineSimulationView.as_view(), name='state-machine-simulate'),
     
     # LinkedIn credentials endpoints
     path('linkedin-credentials/', LinkedInCredentialsView.as_view(), name='linkedin-credentials-list'),
     path('linkedin-credentials/<int:pk>/', LinkedInCredentialsView.as_view(), name='linkedin-credentials-detail'),
     path('linkedin-credentials/<int:pk>/verify/', LinkedInCredentialsVerifyView.as_view(), name='linkedin-credentials-verify'),
     path('linkedin-credentials/<int:pk>/rotate/', LinkedInCredentialsRotationView.as_view(), name='linkedin-credentials-rotate'),
     path('linkedin-credentials/<int:pk>/health/', LinkedInCredentialsHealthView.as_view(), name='linkedin-credentials-health'),
     path('linkedin-credentials/<int:pk>/logs/', LinkedInCredentialsLogsView.as_view(), name='linkedin-credentials-logs'),
 ]
