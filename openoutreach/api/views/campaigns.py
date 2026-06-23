# Campaign API Views

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import Http404

from openoutreach.core.models import Campaign
from openoutreach.crm.models import Deal
from openoutreach.api.serializers.campaigns import CampaignSerializer, CampaignCreateSerializer, CampaignUpdateSerializer


class CampaignListView(APIView):
    """
    API view for listing and creating campaigns.
    
    GET /api/campaigns - List all campaigns (with filters)
    POST /api/campaigns - Create a new campaign
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all campaigns with optional filters."""
        campaigns = Campaign.objects.all()
        
        # Apply filters
        status_param = request.query_params.get('status')
        if status_param:
            # Filter by deal status
            campaigns = campaigns.filter(deals__state=status_param).distinct()
        
        page = request.query_params.get('page')
        limit = request.query_params.get('limit')
        
        # Pagination
        if page and limit:
            try:
                page_num = int(page)
                limit_num = int(limit)
                start = (page_num - 1) * limit_num
                end = start + limit_num
                campaigns = campaigns[start:end]
            except (ValueError, TypeError):
                pass
        
        serializer = CampaignSerializer(campaigns, many=True)
        return Response({
            'data': serializer.data,
            'pagination': {
                'page': int(page) if page else 1,
                'limit': int(limit) if limit else len(serializer.data),
                'total': Campaign.objects.count(),
            }
        })
    
    def post(self, request):
        """Create a new campaign."""
        serializer = CampaignCreateSerializer(data=request.data)
        if serializer.is_valid():
            campaign = Campaign.objects.create(
                name=serializer.validated_data['name'],
                description=serializer.validated_data.get('description', ''),
                product_docs=serializer.validated_data.get('product_docs', ''),
                campaign_objective=serializer.validated_data.get('campaign_objective', ''),
                booking_link=serializer.validated_data.get('booking_link', ''),
                is_freemium=serializer.validated_data.get('is_freemium', False),
                ghost_mode_enabled=serializer.validated_data.get('ghost_mode_enabled', False),
                action_fraction=serializer.validated_data.get('action_fraction', 0.2),
                velocity=serializer.validated_data.get('velocity', 20),
                cooldown_minutes=serializer.validated_data.get('cooldown_minutes', 0),
                is_paused=serializer.validated_data.get('is_paused', False),
                status=serializer.validated_data.get('status', 'active'),
            )
            campaign.users.add(request.user)
            
            return Response({
                'id': campaign.id,
                'name': campaign.name,
                'description': campaign.description,
                'product_docs': campaign.product_docs,
                'campaign_objective': campaign.campaign_objective,
                'booking_link': campaign.booking_link,
                'is_freemium': campaign.is_freemium,
                'ghost_mode_enabled': campaign.ghost_mode_enabled,
                'action_fraction': campaign.action_fraction,
                'velocity': campaign.velocity,
                'cooldown_minutes': campaign.cooldown_minutes,
                'is_paused': campaign.is_paused,
                'status': campaign.status,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignDetailView(APIView):
    """
    API view for retrieving, updating, and deleting a campaign.
    
    GET /api/campaigns/{id} - Get campaign details
    PATCH /api/campaigns/{id} - Update campaign
    DELETE /api/campaigns/{id} - Delete campaign
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """Get campaign details."""
        campaign = self.get_object(pk)
        serializer = CampaignSerializer(campaign)
        
        # Get additional campaign data
        return Response({
            'id': campaign.id,
            'name': campaign.name,
            'description': campaign.description,
            'product_docs': campaign.product_docs,
            'campaign_objective': campaign.campaign_objective,
            'booking_link': campaign.booking_link,
            'is_freemium': campaign.is_freemium,
            'ghost_mode_enabled': campaign.ghost_mode_enabled,
            'action_fraction': campaign.action_fraction,
            'velocity': campaign.velocity,
            'cooldown_minutes': campaign.cooldown_minutes,
            'is_paused': campaign.is_paused,
            'status': campaign.status,
            'users': list(campaign.users.values_list('id', flat=True)),
            'user_count': campaign.users.count(),
            'deal_count': campaign.deals.count(),
            'active_deals': campaign.deals.filter(state__in=['QUALIFIED', 'READY_TO_CONNECT', 'PENDING', 'CONNECTED']).count(),
            'completed_deals': campaign.deals.filter(state='COMPLETED').count(),
            'failed_deals': campaign.deals.filter(state='FAILED').count(),
        })
    
    def patch(self, request, pk):
        """Update campaign."""
        campaign = self.get_object(pk)
        
        serializer = CampaignUpdateSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            # Update fields if provided
            for field, value in serializer.validated_data.items():
                if field == 'users':
                    continue  # Handle users separately if needed
                setattr(campaign, field, value)
            
            campaign.save()
            
            return Response({
                'id': campaign.id,
                'name': campaign.name,
                'description': campaign.description,
                'product_docs': campaign.product_docs,
                'campaign_objective': campaign.campaign_objective,
                'booking_link': campaign.booking_link,
                'is_freemium': campaign.is_freemium,
                'ghost_mode_enabled': campaign.ghost_mode_enabled,
                'action_fraction': campaign.action_fraction,
                'velocity': campaign.velocity,
                'cooldown_minutes': campaign.cooldown_minutes,
                'is_paused': campaign.is_paused,
                'status': campaign.status,
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete campaign."""
        campaign = self.get_object(pk)
        campaign.delete()
        return Response({'success': True}, status=status.HTTP_204_NO_CONTENT)


class CampaignLeadsView(APIView):
    """
    API view for retrieving leads associated with a campaign.
    
    GET /api/campaigns/{id}/leads - List campaign leads
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """List campaign leads with optional filters."""
        campaign = self.get_object(pk)
        
        leads = campaign.deals.select_related('lead').all()
        
        # Apply filters
        status_param = request.query_params.get('status')
        search_param = request.query_params.get('search')
        
        if status_param:
            leads = leads.filter(state=status_param)
        
        if search_param:
            leads = leads.filter(
                lead__public_identifier__icontains=search_param
            ) | leads.filter(lead__linkedin_url__icontains=search_param)
        
        page = request.query_params.get('page')
        limit = request.query_params.get('limit')
        
        # Pagination
        total = leads.count()
        if page and limit:
            try:
                page_num = int(page)
                limit_num = int(limit)
                start = (page_num - 1) * limit_num
                end = start + limit_num
                leads = leads[start:end]
            except (ValueError, TypeError):
                pass
        
        # Serialize leads
        leads_data = []
        for deal in leads:
            leads_data.append({
                'id': deal.id,
                'lead_id': deal.lead.id,
                'public_identifier': deal.lead.public_identifier,
                'linkedin_url': deal.lead.linkedin_url,
                'state': deal.state,
                'outcome': deal.outcome,
                'creation_date': deal.creation_date.isoformat() if deal.creation_date else None,
                'update_date': deal.update_date.isoformat() if deal.update_date else None,
            })
        
        return Response({
            'data': leads_data,
            'pagination': {
                'page': int(page) if page else 1,
                'limit': int(limit) if limit else len(leads_data),
                'total': total,
            },
            'filters': {
                'status': status_param,
                'search': search_param,
                'total_count': total,
            }
        })


class CampaignMessagesView(APIView):
    """
    API view for retrieving messages associated with a campaign.
    
    GET /api/campaigns/{id}/messages - List campaign messages
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """List campaign messages."""
        campaign = self.get_object(pk)
        
        from openoutreach.linkedin.models import ActionLog
        
        messages = ActionLog.objects.filter(campaign=campaign).select_related(
            'linkedin_profile'
        ).order_by('-created_at')
        
        page = request.query_params.get('page')
        limit = request.query_params.get('limit')
        
        # Pagination
        total = messages.count()
        if page and limit:
            try:
                page_num = int(page)
                limit_num = int(limit)
                start = (page_num - 1) * limit_num
                end = start + limit_num
                messages = messages[start:end]
            except (ValueError, TypeError):
                pass
        
        # Serialize messages
        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'campaign_id': campaign.id,
                'linkedin_profile': msg.linkedin_profile.public_identifier if msg.linkedin_profile else None,
                'action_type': msg.action_type,
                'status': msg.status,
                'error_message': msg.error_message,
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
            })
        
        return Response({
            'data': messages_data,
            'pagination': {
                'page': int(page) if page else 1,
                'limit': int(limit) if limit else len(messages_data),
                'total': total,
            }
        })


class CampaignAnalyticsView(APIView):
    """
    API view for retrieving analytics for a campaign.
    
    GET /api/campaigns/{id}/analytics - Get campaign analytics
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """Get campaign analytics."""
        campaign = self.get_object(pk)
        
        period = request.query_params.get('period', '30d')
        
        from openoutreach.linkedin.models import ActionLog
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate date range
        if period == '7d':
            since = timezone.now() - timedelta(days=7)
        elif period == '30d':
            since = timezone.now() - timedelta(days=30)
        elif period == '90d':
            since = timezone.now() - timedelta(days=90)
        else:
            since = timezone.now() - timedelta(days=30)
        
        # Connection metrics
        connections_sent = ActionLog.objects.filter(
            campaign=campaign,
            action_type=ActionLog.ActionType.CONNECT,
            created_at__gte=since,
        ).count()
        
        connections_accepted = Deal.objects.filter(
            campaign=campaign,
            state='CONNECTED',
            creation_date__gte=since,
        ).count()
        
        connection_accept_rate = (
            connections_accepted / connections_sent * 100
            if connections_sent > 0 else 0
        )
        
        # Follow-up metrics
        messages_sent = ActionLog.objects.filter(
            campaign=campaign,
            action_type=ActionLog.ActionType.FOLLOW_UP,
            created_at__gte=since,
        ).count()
        
        messages_replied = Deal.objects.filter(
            campaign=campaign,
            messages__is_outgoing=False,
            creation_date__gte=since,
        ).distinct().count()
        
        response_rate = (
            messages_replied / connections_sent * 100
            if connections_sent > 0 else 0
        )
        
        # Conversion metrics
        conversions = Deal.objects.filter(
            campaign=campaign,
            state='COMPLETED',
            creation_date__gte=since,
        ).count()
        
        conversion_rate = (
            conversions / connections_sent * 100
            if connections_sent > 0 else 0
        )
        
        # Error metrics
        errors = ActionLog.objects.filter(
            campaign=campaign,
            error_message__isnull=False,
            error_message__gt='',
            created_at__gte=since,
        ).count()
        
        rate_limit_warnings = ActionLog.objects.filter(
            campaign=campaign,
            warning_message__isnull=False,
            warning_message__gt='',
            created_at__gte=since,
        ).count()
        
        # Pipeline statistics
        pipeline = {
            'qualified': Deal.objects.filter(
                campaign=campaign,
                state='QUALIFIED',
            ).count(),
            'ready_to_connect': Deal.objects.filter(
                campaign=campaign,
                state='READY_TO_CONNECT',
            ).count(),
            'pending': Deal.objects.filter(
                campaign=campaign,
                state='PENDING',
            ).count(),
            'connected': Deal.objects.filter(
                campaign=campaign,
                state='CONNECTED',
            ).count(),
            'completed': Deal.objects.filter(
                campaign=campaign,
                state='COMPLETED',
            ).count(),
            'failed': Deal.objects.filter(
                campaign=campaign,
                state='FAILED',
            ).count(),
            'no_email': Deal.objects.filter(
                campaign=campaign,
                state='NO_EMAIL',
            ).count(),
        }
        
        # Daily breakdown (last 7 days)
        daily_breakdown = []
        for i in range(7):
            day_start = since + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_connections_sent = ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.CONNECT,
                created_at__gte=day_start,
                created_at__lt=day_end,
            ).count()
            
            day_connections_accepted = Deal.objects.filter(
                campaign=campaign,
                state='CONNECTED',
                creation_date__gte=day_start,
                creation_date__lt=day_end,
            ).count()
            
            day_messages_sent = ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.FOLLOW_UP,
                created_at__gte=day_start,
                created_at__lt=day_end,
            ).count()
            
            day_messages_replied = Deal.objects.filter(
                campaign=campaign,
                messages__is_outgoing=False,
                creation_date__gte=day_start,
                creation_date__lt=day_end,
            ).distinct().count()
            
            daily_breakdown.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'connections_sent': day_connections_sent,
                'connections_accepted': day_connections_accepted,
                'messages_sent': day_messages_sent,
                'messages_replied': day_messages_replied,
            })
        
        return Response({
            'period': period,
            'campaign_id': pk,
            'stats': {
                'connections_sent': connections_sent,
                'connections_accepted': connections_accepted,
                'connection_accept_rate': round(connection_accept_rate, 2),
                'messages_sent': messages_sent,
                'messages_replied': messages_replied,
                'response_rate': round(response_rate, 2),
                'conversions': conversions,
                'conversion_rate': round(conversion_rate, 2),
                'errors': errors,
                'rate_limit_warnings': rate_limit_warnings,
            },
            'daily_breakdown': daily_breakdown,
            'pipeline': pipeline,
        })


class CampaignStateMachineView(APIView):
    """
    API view for managing state machine for a campaign.
    
    GET /api/campaigns/{id}/state-machine - Get state machine
    POST /api/campaigns/{id}/state-machine - Update state machine
    POST /api/campaigns/{id}/state-machine/validate - Validate state machine
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Campaign.objects.get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """Get campaign state machine."""
        campaign = self.get_object(pk)
        
        from openoutreach.linkedin.models import CampaignStateGraph
        
        try:
            state_graph = campaign.state_graph
            return Response({
                'id': state_graph.id,
                'campaign_id': campaign.id,
                'name': state_graph.name,
                'description': state_graph.description,
                'is_active': state_graph.is_active,
                'is_valid': state_graph.is_valid,
                'validation_errors': state_graph.validation_errors,
                'nodes': list(state_graph.nodes.values()),
                'transitions': list(state_graph.transitions.values()),
            })
        except CampaignStateGraph.DoesNotExist:
            return Response({
                'id': None,
                'campaign_id': campaign.id,
                'name': '',
                'description': '',
                'is_active': True,
                'is_valid': False,
                'validation_errors': [],
                'nodes': [],
                'transitions': [],
            })
    
    def post(self, request, pk):
        """Update or create state machine for campaign."""
        campaign = self.get_object(pk)
        
        from openoutreach.linkedin.models import CampaignStateGraph, StateNode, StateTransition
        
        # Get state machine data
        name = request.data.get('name', campaign.name + ' State Machine')
        description = request.data.get('description', '')
        graph_data = request.data.get('graph_data', {})
        
        # Create or update state graph
        state_graph, created = CampaignStateGraph.objects.get_or_create(
            campaign=campaign,
            defaults={
                'name': name,
                'description': description,
                'graph_data': graph_data,
            }
        )
        
        if not created:
            state_graph.name = name
            state_graph.description = description
            state_graph.graph_data = graph_data
            state_graph.is_valid = False  # Reset validation on update
            state_graph.save()
        
        # Parse nodes and transitions from graph_data
        nodes_data = graph_data.get('nodes', [])
        transitions_data = graph_data.get('transitions', [])
        
        # Clear existing nodes and transitions
        state_graph.nodes.all().delete()
        state_graph.transitions.all().delete()
        
        # Create nodes
        node_map = {}
        for node_data in nodes_data:
            node = StateNode.objects.create(
                state_graph=state_graph,
                name=node_data.get('name', ''),
                node_type=node_data.get('type', 'message'),
                config=node_data.get('config', {}),
                x=node_data.get('x', 0),
                y=node_data.get('y', 0),
                description=node_data.get('description', ''),
                is_active=node_data.get('is_active', True),
            )
            node_map[node_data['id']] = node
        
        # Create transitions
        for transition_data in transitions_data:
            source_node = node_map.get(transition_data['source_node'])
            target_node = node_map.get(transition_data['target_node'])
            
            if source_node and target_node:
                StateTransition.objects.create(
                    state_graph=state_graph,
                    source_node=source_node,
                    target_node=target_node,
                    label=transition_data.get('label', ''),
                    condition_type=transition_data.get('condition_type', 'always'),
                    order=transition_data.get('order', 0),
                )
        
        state_graph.is_valid = True
        state_graph.save()
        
        return Response({
            'id': state_graph.id,
            'campaign_id': campaign.id,
            'name': state_graph.name,
            'description': state_graph.description,
            'is_active': state_graph.is_active,
            'is_valid': state_graph.is_valid,
            'validation_errors': [],
            'nodes': list(state_graph.nodes.values()),
            'transitions': list(state_graph.transitions.values()),
        })
    
    def post_validate(self, request, pk):
        """Validate state machine for campaign."""
        campaign = self.get_object(pk)
        
        from openoutreach.linkedin.models import CampaignStateGraph, StateNode, StateTransition
        
        try:
            state_graph = campaign.state_graph
            nodes = state_graph.nodes.all()
            transitions = state_graph.transitions.all()
            
            errors = []
            warnings = []
            
            # Check for start node
            start_nodes = nodes.filter(node_type=StateNode.TYPE_START)
            if not start_nodes.exists():
                errors.append("No start node defined")
            
            if not errors:
                # Validate transitions
                all_node_ids = set(nodes.values_list('id', flat=True))
                source_node_ids = set(transitions.values_list('source_node_id', flat=True))
                target_node_ids = set(transitions.values_list('target_node_id', flat=True))
                
                # Check for unreachable nodes
                all_referenced = source_node_ids | target_node_ids
                for node_id in all_node_ids:
                    if node_id not in all_referenced:
                        warnings.append(f"Node {node_id} is not connected")
            
            state_graph.validation_errors = errors
            state_graph.is_valid = len(errors) == 0
            state_graph.save()
            
            return Response({
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
            })
        
        except CampaignStateGraph.DoesNotExist:
            return Response({
                'is_valid': False,
                'errors': ['No state machine defined for this campaign'],
                'warnings': [],
            }, status=status.HTTP_404_NOT_FOUND)