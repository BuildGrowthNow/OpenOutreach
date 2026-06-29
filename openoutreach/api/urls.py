# API URL Configuration

from django.urls import path, re_path
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
    CampaignLeadsUploadView,
    CampaignMessagesView,
    CampaignAnalyticsView,
    CampaignStateMachineView,
    CampaignStatusView,
    CampaignGhostModeSimulationView,
    CampaignGhostModeSimulationListView,
    CampaignGhostModeActionView,
)
from .views.campaign_templates import (
    CampaignTemplateListView,
    CampaignTemplateDetailView,
    CampaignTemplateCloneView,
    CampaignCreateFromTemplateView,
)
from .views.leads import (
    LeadListView,
    LeadDetailView,
    LeadProfileView,
    LeadMessagesView,
    LeadNotesView,
    LeadAddToCampaignView,
)
from .views.settings import SettingsView, RateLimitsView, DailyUsageView
from .views.analytics import AnalyticsView
from .views.links import LinksListView, LinksDetailView
from .views.state_machine import StateMachineSimulationView
from .views.messages import MessagesView, MessagesDetailView
from .views.linkedin_credentials import (
    LinkedInCredentialsView,
    LinkedInCredentialsVerifyView,
    LinkedInCredentialsRotationView,
    LinkedInCredentialsHealthView,
    LinkedInCredentialsLogsView,
)
from .views.linkedin_setup import (
    LinkedInCookieInstructionsView,
    LinkedInSetupGuideView,
    LinkedInSetupStatusView,
)
from .views.linkedin_profiles import LinkedInProfilesListView
from .views.linkedin_profile_health import LinkedInProfileHealthView

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
    path('settings/daily-usage/', DailyUsageView.as_view(), name='daily-usage'),
    
    # Campaigns endpoints
    path('campaigns/', CampaignListView.as_view(), name='campaign-list'),
    path('campaigns/<int:pk>/', CampaignDetailView.as_view(), name='campaign-detail'),
    path('campaigns/<int:pk>/leads/', CampaignLeadsView.as_view(), name='campaign-leads'),
    path('campaigns/<int:pk>/leads/upload/', CampaignLeadsUploadView.as_view(), name='campaign-leads-upload'),
    path('campaigns/<int:pk>/messages/', CampaignMessagesView.as_view(), name='campaign-messages'),
    path('campaigns/<int:pk>/analytics/', CampaignAnalyticsView.as_view(), name='campaign-analytics'),
    path('campaigns/<int:pk>/state-machine/', CampaignStateMachineView.as_view(), name='campaign-state-machine'),
    path('campaigns/<int:pk>/state-machine/validate/', CampaignStateMachineView.as_view(), name='campaign-state-machine-validate'),
    path('campaigns/<int:pk>/state-machine/simulate/', StateMachineSimulationView.as_view(), name='campaign-state-machine-simulate'),
    path('campaigns/<int:pk>/status/', CampaignStatusView.as_view(), name='campaign-status'),
    
    # Ghost mode endpoints - separate endpoints for different actions
    path('campaigns/<int:pk>/ghost-mode/simulations/', CampaignGhostModeSimulationListView.as_view(), name='campaign-ghost-mode-simulations'),
     path('campaigns/<int:pk>/ghost-mode/action/', CampaignGhostModeActionView.as_view(), name='campaign-ghost-mode-action'),
     
     # Campaign templates endpoints
     path('campaign-templates/', CampaignTemplateListView.as_view(), name='campaign-template-list'),
     path('campaign-templates/<int:pk>/', CampaignTemplateDetailView.as_view(), name='campaign-template-detail'),
     path('campaign-templates/<int:pk>/clone/', CampaignTemplateCloneView.as_view(), name='campaign-template-clone'),
     path('campaign-templates/<int:pk>/create-campaign/', CampaignCreateFromTemplateView.as_view(), name='campaign-template-create-campaign'),
     
     # Leads endpoints
    path('leads/', LeadListView.as_view(), name='lead-list'),
    path('leads/<int:pk>/', LeadDetailView.as_view(), name='lead-detail'),
    path('leads/<int:pk>/profile/', LeadProfileView.as_view(), name='lead-profile'),
    path('leads/<int:pk>/messages/', LeadMessagesView.as_view(), name='lead-messages'),
    path('leads/<int:pk>/notes/', LeadNotesView.as_view(), name='lead-notes-list'),
    path('leads/<int:pk>/notes/<int:note_id>/', LeadNotesView.as_view(), name='lead-notes-detail'),
    path('leads/<int:pk>/add-to-campaign/', LeadAddToCampaignView.as_view(), name='lead-add-to-campaign'),
    
    # Messages endpoints
    path('messages/', MessagesView.as_view(), name='messages-list'),
    path('messages/<int:pk>/', MessagesDetailView.as_view(), name='messages-detail'),
    
    # Analytics endpoints
    path('analytics/overview/', AnalyticsView.as_view(), name='analytics-overview'),
    
    # Links endpoints
    path('links/', LinksListView.as_view(), name='links-list'),
    path('links/<int:pk>/', LinksDetailView.as_view(), name='link-detail'),
    # Link redirect is handled by CRM (must be before api to avoid prefix)
    
    # State machine endpoints (global simulation)
    path('state-machine/simulate/', StateMachineSimulationView.as_view(), name='state-machine-simulate'),
    
    # LinkedIn credentials endpoints
    path('linkedin-credentials/', LinkedInCredentialsView.as_view(), name='linkedin-credentials-list'),
    path('linkedin-credentials/<int:pk>/', LinkedInCredentialsView.as_view(), name='linkedin-credentials-detail'),
    path('linkedin-credentials/<int:pk>/verify/', LinkedInCredentialsVerifyView.as_view(), name='linkedin-credentials-verify'),
    path('linkedin-credentials/<int:pk>/rotate/', LinkedInCredentialsRotationView.as_view(), name='linkedin-credentials-rotate'),
    path('linkedin-credentials/<int:pk>/health/', LinkedInCredentialsHealthView.as_view(), name='linkedin-credentials-health'),
    path('linkedin-credentials/<int:pk>/logs/', LinkedInCredentialsLogsView.as_view(), name='linkedin-credentials-logs'),
    
    # LinkedIn profiles endpoints
    path('linkedin-profiles/', LinkedInProfilesListView.as_view(), name='linkedin-profiles-list'),
    path('linkedin-profile-health/', LinkedInProfileHealthView.as_view(), name='linkedin-profile-health'),
    
    # LinkedIn setup endpoints (OAuth/cookie guide)
    path('linkedin-setup/cookie-instructions/', LinkedInCookieInstructionsView.as_view(), name='linkedin-setup-cookie-instructions'),
    path('linkedin-setup/guide/', LinkedInSetupGuideView.as_view(), name='linkedin-setup-guide'),
    path('linkedin-setup/status/', LinkedInSetupStatusView.as_view(), name='linkedin-setup-status'),
]

# Fallback URL patterns for both trailing-slash and no-trailing-slash versions
# This prevents 301 redirects that lose CORS credentials during cross-origin requests
# Add no-trailing-slash versions of all endpoints
urlpatterns += [
    # Health endpoint (no trailing slash)
    re_path(r'^health$', HealthView.as_view(), name='health-no-slash'),
    
    # Settings endpoints (no trailing slash)
    re_path(r'^settings$', SettingsView.as_view(), name='settings-no-slash'),
    re_path(r'^settings/rate-limits$', RateLimitsView.as_view(), name='rate-limits-no-slash'),
    re_path(r'^settings/daily-usage$', DailyUsageView.as_view(), name='daily-usage-no-slash'),
    
    # Campaigns endpoints (no trailing slash)
    re_path(r'^campaigns$', CampaignListView.as_view(), name='campaign-list-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)$', CampaignDetailView.as_view(), name='campaign-detail-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/leads$', CampaignLeadsView.as_view(), name='campaign-leads-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/leads/upload$', CampaignLeadsUploadView.as_view(), name='campaign-leads-upload-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/messages$', CampaignMessagesView.as_view(), name='campaign-messages-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/analytics$', CampaignAnalyticsView.as_view(), name='campaign-analytics-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/state-machine$', CampaignStateMachineView.as_view(), name='campaign-state-machine-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/state-machine/validate$', CampaignStateMachineView.as_view(), name='campaign-state-machine-validate-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/state-machine/simulate$', StateMachineSimulationView.as_view(), name='campaign-state-machine-simulate-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/status$', CampaignStatusView.as_view(), name='campaign-status-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/ghost-mode/simulations$', CampaignGhostModeSimulationListView.as_view(), name='campaign-ghost-mode-simulations-no-slash'),
    re_path(r'^campaigns/(?P<pk>[0-9]+)/ghost-mode/action$', CampaignGhostModeActionView.as_view(), name='campaign-ghost-mode-action-no-slash'),
    
    # Campaign templates endpoints (no trailing slash)
    re_path(r'^campaign-templates$', CampaignTemplateListView.as_view(), name='campaign-template-list-no-slash'),
    re_path(r'^campaign-templates/(?P<pk>[0-9]+)$', CampaignTemplateDetailView.as_view(), name='campaign-template-detail-no-slash'),
    re_path(r'^campaign-templates/(?P<pk>[0-9]+)/clone$', CampaignTemplateCloneView.as_view(), name='campaign-template-clone-no-slash'),
    re_path(r'^campaign-templates/(?P<pk>[0-9]+)/create-campaign$', CampaignCreateFromTemplateView.as_view(), name='campaign-template-create-campaign-no-slash'),
    
    # Leads endpoints (no trailing slash)
    re_path(r'^leads$', LeadListView.as_view(), name='lead-list-no-slash'),
    re_path(r'^leads/(?P<pk>[0-9]+)$', LeadDetailView.as_view(), name='lead-detail-no-slash'),
    re_path(r'^leads/(?P<pk>[0-9]+)/profile$', LeadProfileView.as_view(), name='lead-profile-no-slash'),
    re_path(r'^leads/(?P<pk>[0-9]+)/messages$', LeadMessagesView.as_view(), name='lead-messages-no-slash'),
    re_path(r'^leads/(?P<pk>[0-9]+)/notes$', LeadNotesView.as_view(), name='lead-notes-list-no-slash'),
    re_path(r'^leads/(?P<pk>[0-9]+)/notes/(?P<note_id>[0-9]+)$', LeadNotesView.as_view(), name='lead-notes-detail-no-slash'),
    re_path(r'^leads/(?P<pk>[0-9]+)/add-to-campaign$', LeadAddToCampaignView.as_view(), name='lead-add-to-campaign-no-slash'),
    
    # Messages endpoints (no trailing slash)
    re_path(r'^messages$', MessagesView.as_view(), name='messages-list-no-slash'),
    re_path(r'^messages/(?P<pk>[0-9]+)$', MessagesDetailView.as_view(), name='messages-detail-no-slash'),
    
    # Analytics endpoints (no trailing slash)
    re_path(r'^analytics/overview$', AnalyticsView.as_view(), name='analytics-overview-no-slash'),
    
    # Links endpoints (no trailing slash)
    re_path(r'^links$', LinksListView.as_view(), name='links-list-no-slash'),
    re_path(r'^links/(?P<pk>[0-9]+)$', LinksDetailView.as_view(), name='link-detail-no-slash'),
    # Link redirect is handled by CRM (must be before api to avoid prefix)
    
    # State machine endpoints (no trailing slash)
    re_path(r'^state-machine/simulate$', StateMachineSimulationView.as_view(), name='state-machine-simulate-no-slash'),
    
    # LinkedIn credentials endpoints (no trailing slash)
    re_path(r'^linkedin-credentials$', LinkedInCredentialsView.as_view(), name='linkedin-credentials-list-no-slash'),
    re_path(r'^linkedin-credentials/(?P<pk>[0-9]+)$', LinkedInCredentialsView.as_view(), name='linkedin-credentials-detail-no-slash'),
    re_path(r'^linkedin-credentials/(?P<pk>[0-9]+)/verify$', LinkedInCredentialsVerifyView.as_view(), name='linkedin-credentials-verify-no-slash'),
    re_path(r'^linkedin-credentials/(?P<pk>[0-9]+)/rotate$', LinkedInCredentialsRotationView.as_view(), name='linkedin-credentials-rotate-no-slash'),
    re_path(r'^linkedin-credentials/(?P<pk>[0-9]+)/health$', LinkedInCredentialsHealthView.as_view(), name='linkedin-credentials-health-no-slash'),
    re_path(r'^linkedin-credentials/(?P<pk>[0-9]+)/logs$', LinkedInCredentialsLogsView.as_view(), name='linkedin-credentials-logs-no-slash'),
    
    # LinkedIn profiles endpoints (no trailing slash)
    re_path(r'^linkedin-profiles$', LinkedInProfilesListView.as_view(), name='linkedin-profiles-list-no-slash'),
    re_path(r'^linkedin-profile-health$', LinkedInProfileHealthView.as_view(), name='linkedin-profile-health-no-slash'),
    
    # LinkedIn setup endpoints (no trailing slash)
    re_path(r'^linkedin-setup/cookie-instructions$', LinkedInCookieInstructionsView.as_view(), name='linkedin-setup-cookie-instructions-no-slash'),
    re_path(r'^linkedin-setup/guide$', LinkedInSetupGuideView.as_view(), name='linkedin-setup-guide-no-slash'),
    re_path(r'^linkedin-setup/status$', LinkedInSetupStatusView.as_view(), name='linkedin-setup-status-no-slash'),
]