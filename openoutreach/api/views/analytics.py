# Analytics API View

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal
from openoutreach.linkedin.models import ActionLog
from django.utils import timezone
from datetime import timedelta


class AnalyticsView(APIView):
    """
    API view for retrieving analytics overview.
    
    GET /api/analytics/overview - Get system-wide analytics
    GET /api/analytics/campaigns - Get cross-campaign analytics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get analytics overview."""
        period = request.query_params.get('period', '30d')
        
        # Calculate date range
        if period == '7d':
            since = timezone.now() - timedelta(days=7)
        elif period == '30d':
            since = timezone.now() - timedelta(days=30)
        elif period == '90d':
            since = timezone.now() - timedelta(days=90)
        else:
            since = timezone.now() - timedelta(days=30)
        
        # Overall statistics (only count campaigns user has access to)
        total_campaigns = Campaign.objects.filter(users=request.user).count()
        total_leads = Deal.objects.filter(campaign__users=request.user).count()
        
        # Active deals (in funnel)
        active_deals = Deal.objects.filter(
            state__in=['QUALIFIED', 'READY_TO_CONNECT', 'PENDING', 'CONNECTED']
        ).count()
        
        # Completed deals
        completed_deals = Deal.objects.filter(state='COMPLETED').count()
        
        # Failed deals
        failed_deals = Deal.objects.filter(state='FAILED').count()
        
        # Connection metrics
        connections_sent = ActionLog.objects.filter(
            action_type=ActionLog.ActionType.CONNECT,
            created_at__gte=since,
        ).count()
        
        connections_accepted = Deal.objects.filter(
            state='CONNECTED',
            creation_date__gte=since,
        ).count()
        
        connection_accept_rate = (
            connections_accepted / connections_sent * 100
            if connections_sent > 0 else 0
        )
        
        # Response metrics
        response_deals = Deal.objects.filter(
            messages__is_outgoing=False,
            creation_date__gte=since,
        ).distinct().count()
        
        response_rate = (
            response_deals / connections_sent * 100
            if connections_sent > 0 else 0
        )
        
        # Conversion metrics
        conversions = Deal.objects.filter(
            state='COMPLETED',
            creation_date__gte=since,
        ).count()
        
        conversion_rate = (
            conversions / connections_sent * 100
            if connections_sent > 0 else 0
        )
        
        # Pipeline by stage
        pipeline = {
            'qualified': Deal.objects.filter(state='QUALIFIED').count(),
            'ready_to_connect': Deal.objects.filter(state='READY_TO_CONNECT').count(),
            'pending': Deal.objects.filter(state='PENDING').count(),
            'connected': Deal.objects.filter(state='CONNECTED').count(),
            'completed': Deal.objects.filter(state='COMPLETED').count(),
            'failed': Deal.objects.filter(state='FAILED').count(),
            'no_email': Deal.objects.filter(state='NO_EMAIL').count(),
        }
        
        # Cross-campaign comparison
        campaigns_data = []
        for campaign in Campaign.objects.filter(users=request.user)[:10]:
            campaign_connections = ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.CONNECT,
                created_at__gte=since,
            ).count()
            
            campaign_accepted = Deal.objects.filter(
                campaign=campaign,
                state='CONNECTED',
                creation_date__gte=since,
            ).count()
            
            campaigns_data.append({
                'id': campaign.id,
                'name': campaign.name,
                'connections_sent': campaign_connections,
                'connections_accepted': campaign_accepted,
                'connection_accept_rate': round(
                    campaign_accepted / campaign_connections * 100,
                    2
                ) if campaign_connections > 0 else 0,
                'deals': campaign.deals.count(),
                'active_deals': campaign.deals.filter(
                    state__in=['QUALIFIED', 'READY_TO_CONNECT', 'PENDING', 'CONNECTED']
                ).count(),
            })
        
        return Response({
            'data': {
                'period': period,
                'overall': {
                    'total_campaigns': total_campaigns,
                    'total_leads': total_leads,
                    'active_deals': active_deals,
                    'completed_deals': completed_deals,
                    'failed_deals': failed_deals,
                },
                'stats': {
                    'connections_sent': connections_sent,
                    'connections_accepted': connections_accepted,
                    'connection_accept_rate': round(connection_accept_rate, 2),
                    'response_rate': round(response_rate, 2),
                    'conversion_rate': round(conversion_rate, 2),
                },
                'metrics': {
                    'connections_sent': connections_sent,
                    'connections_accepted': connections_accepted,
                    'connection_accept_rate': round(connection_accept_rate, 2),
                    'response_rate': round(response_rate, 2),
                    'conversion_rate': round(conversion_rate, 2),
                },
                'pipeline': pipeline,
                'campaigns': campaigns_data,
            },
            'period': period,
            'overall': {
                'total_campaigns': total_campaigns,
                'total_leads': total_leads,
                'active_deals': active_deals,
                'completed_deals': completed_deals,
                'failed_deals': failed_deals,
            },
            'stats': {
                'connections_sent': connections_sent,
                'connections_accepted': connections_accepted,
                'connection_accept_rate': round(connection_accept_rate, 2),
                'response_rate': round(response_rate, 2),
                'conversion_rate': round(conversion_rate, 2),
            },
            'metrics': {
                'connections_sent': connections_sent,
                'connections_accepted': connections_accepted,
                'connection_accept_rate': round(connection_accept_rate, 2),
                'response_rate': round(response_rate, 2),
                'conversion_rate': round(conversion_rate, 2),
            },
            'pipeline': pipeline,
            'campaigns': campaigns_data,
        })
