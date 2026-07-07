# Campaign API Views

from datetime import timedelta

from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from openoutreach.api.serializers.campaigns import (
    CampaignCreateSerializer,
    CampaignSerializer,
    CampaignUpdateSerializer,
)
from openoutreach.core.models import Campaign, Task
from openoutreach.crm.models import Deal
from openoutreach.crm.models.deal import DealState
from openoutreach.linkedin.models import ActionLog
from openoutreach.linkedin.models.ghost_mode import GhostCampaign, GhostSimulationLog


class CampaignListView(APIView):
    """
    API view for listing and creating campaigns.

    GET /api/campaigns - List all campaigns (with filters)
    POST /api/campaigns - Create a new campaign
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List campaigns accessible by the current user with optional filters."""
        campaigns = Campaign.objects.filter(users=request.user)

        # Apply filters
        status_param = request.query_params.get("status")
        if status_param:
            # Filter by campaign status (not deal state)
            campaigns = campaigns.filter(status=status_param)

        page = request.query_params.get("page")
        limit = request.query_params.get("limit")

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
        return Response(
            {
                "data": serializer.data,
                "pagination": {
                    "page": int(page) if page else 1,
                    "limit": int(limit) if limit else len(serializer.data),
                    "total": campaigns.count(),
                },
            }
        )

    def post(self, request):
        """Create a new campaign."""
        from openoutreach.linkedin.models import SearchKeyword

        serializer = CampaignCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Extract search_keywords before creating campaign
            search_keywords = serializer.validated_data.get("search_keywords", [])

            campaign = Campaign.objects.create(
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                product_pitch=serializer.validated_data.get("product_pitch", ""),
                campaign_objective=serializer.validated_data.get(
                    "campaign_objective", ""
                ),
                booking_link=serializer.validated_data.get("booking_link", ""),
                icp_titles=serializer.validated_data.get("icp_titles", []),
                follow_up_strategy=serializer.validated_data.get(
                    "follow_up_strategy", ""
                ),
                is_freemium=serializer.validated_data.get("is_freemium", False),
                ghost_mode_enabled=serializer.validated_data.get(
                    "ghost_mode_enabled", False
                ),
                action_fraction=serializer.validated_data.get("action_fraction", 0.2),
                velocity=serializer.validated_data.get("velocity", 20),
                cooldown_minutes=serializer.validated_data.get("cooldown_minutes", 0),
                is_paused=serializer.validated_data.get("is_paused", False),
                status=serializer.validated_data.get("status", "active"),
            )
            campaign.users.add(request.user)

            # Create SearchKeyword instances
            for keyword in search_keywords:
                if keyword.strip():  # Skip empty strings
                    SearchKeyword.objects.get_or_create(
                        campaign=campaign,
                        keyword=keyword.strip()
                    )

            # Use serializer to return consistent response format
            response_serializer = CampaignSerializer(campaign)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
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
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """Get campaign details."""
        campaign = self.get_object(pk)

        # Use the serializer to get full campaign data including search_keywords
        serializer = CampaignSerializer(campaign)
        return Response(serializer.data)

    def patch(self, request, pk):
        """Update campaign."""
        from openoutreach.linkedin.models import SearchKeyword

        campaign = self.get_object(pk)

        # Store old values for comparison
        old_is_paused = campaign.is_paused
        old_status = campaign.status

        serializer = CampaignUpdateSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            # Extract search_keywords if provided
            search_keywords = serializer.validated_data.pop("search_keywords", None)

            # Update fields if provided
            for field, value in serializer.validated_data.items():
                if field == "users":
                    continue  # Handle users separately if needed
                setattr(campaign, field, value)

            campaign.save()
            # Update SearchKeyword instances if provided
            if search_keywords is not None:
                # Clear existing keywords
                campaign.search_keywords.all().delete()
                # Create new ones
                for keyword in search_keywords:
                    if keyword.strip():  # Skip empty strings
                        SearchKeyword.objects.create(
                            campaign=campaign,
                            keyword=keyword.strip()
                        )

            # Emit real-time notifications for status changes
            self._emit_status_change_notifications(campaign, old_is_paused, old_status)

            # Use the serializer to return the full campaign data including search_keywords
            response_serializer = CampaignSerializer(campaign)
            return Response(response_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _emit_status_change_notifications(self, campaign, old_is_paused, old_status):
        """
        Emit real-time notifications when campaign status changes.

        Args:
            campaign: The updated Campaign instance
            old_is_paused: Previous is_paused value
            old_status: Previous status value
        """
        try:
            from openoutreach.notifications.signals import (
                create_campaign_status_change_notification,
            )

            # Check for status change
            if old_status != campaign.status:
                create_campaign_status_change_notification(campaign, "status_changed")

            # Check for is_paused change
            elif old_is_paused != campaign.is_paused:
                if campaign.is_paused:
                    create_campaign_status_change_notification(campaign, "paused")
                else:
                    create_campaign_status_change_notification(campaign, "started")
        except Exception:
            # Don't crash if notification fails
            pass

        # Create ActionLog entries for status changes
        try:
            from openoutreach.linkedin.models import ActionLog

            if old_is_paused != campaign.is_paused:
                action_type = (
                    ActionLog.ActionType.CAMPAIGN_PAUSED
                    if campaign.is_paused
                    else ActionLog.ActionType.CAMPAIGN_STARTED
                )
                ActionLog.objects.create(
                    linkedin_profile=None,
                    campaign=campaign,
                    action_type=action_type,
                    status="completed",
                )
        except Exception:
            # Don't crash if ActionLog creation fails
            pass

    def delete(self, request, pk):
        """Delete campaign."""
        campaign = self.get_object(pk)
        campaign.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CampaignStatusView(APIView):
    """
    API view for targeted polling - returns only the campaign status.

    GET /api/campaigns/{id}/status - Get only campaign status (lightweight polling)
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """Get only the campaign status (for efficient polling)."""
        campaign = self.get_object(pk)
        return Response(
            {
                "status": campaign.status,
                "is_paused": campaign.is_paused,
            }
        )


class CampaignLeadsView(APIView):
    """
    API view for retrieving leads associated with a campaign.

    GET /api/campaigns/{id}/leads - List campaign leads
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """List campaign leads with optional filters."""
        campaign = self.get_object(pk)

        leads = campaign.deals.select_related("lead").all()

        # Apply filters
        status_param = request.query_params.get("status")
        search_param = request.query_params.get("search")

        if status_param:
            leads = leads.filter(state=status_param)

        if search_param:
            leads = leads.filter(
                lead__public_identifier__icontains=search_param
            ) | leads.filter(lead__linkedin_url__icontains=search_param)

        page = request.query_params.get("page")
        limit = request.query_params.get("limit")

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
        from openoutreach.api.views.leads import _extract_lead_info, _extract_lead_name

        for deal in leads:
            name = _extract_lead_name(deal.lead)
            company, title, _ = _extract_lead_info(deal.lead)
            leads_data.append(
                {
                    "id": deal.lead.id,  # Use lead.id instead of deal.id for frontend linking
                    "lead_id": deal.lead.id,
                    "deal_id": deal.id,  # Add deal_id for internal use
                    "public_identifier": deal.lead.public_identifier,
                    "linkedin_url": deal.lead.linkedin_url,
                    "name": name,
                    "company": company,
                    "title": title,
                    "state": deal.state,
                    "outcome": deal.outcome,
                    "next_check_pending_at": (
                        deal.next_check_pending_at.isoformat()
                        if deal.next_check_pending_at
                        else None
                    ),
                    "creation_date": (
                        deal.creation_date.isoformat() if deal.creation_date else None
                    ),
                    "update_date": (
                        deal.update_date.isoformat() if deal.update_date else None
                    ),
                }
            )

        return Response(
            {
                "data": leads_data,
                "pagination": {
                    "page": int(page) if page else 1,
                    "limit": int(limit) if limit else len(leads_data),
                    "total": total,
                },
                "filters": {
                    "status": status_param,
                    "search": search_param,
                    "total_count": total,
                },
            }
        )


class CampaignLeadsUploadView(APIView):
    """
    API view for uploading leads via CSV/text file.

    POST /api/campaigns/{id}/leads/upload/ - Upload file
    """

    permission_classes = [IsAuthenticated]
    from rest_framework.parsers import MultiPartParser

    parser_classes = [MultiPartParser]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def post(self, request, pk):
        campaign = self.get_object(pk)

        if "file" not in request.FILES:
            return Response(
                {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
            )

        file_obj = request.FILES["file"]

        import csv
        import io

        from linkedin_cli.url_utils import public_id_to_url, url_to_public_id

        from openoutreach.crm.models import Deal, Lead
        from openoutreach.crm.models.deal import DealState

        try:
            decoded_file = file_obj.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string)
        except Exception as e:
            return Response(
                {"error": f"Failed to parse file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connections = []

        # Parse CSV lines
        first_row = next(reader, None)
        if first_row:
            # Check if first row is header
            if (
                "firstName" in str(first_row)
                or "LastName" in str(first_row)
                or "first" in str(first_row).lower()
            ):
                pass  # skip header
            else:
                connections.append(first_row[0].strip())

        for row in reader:
            if row and len(row) >= 1:
                url = row[0].strip()
                if url and not url.startswith("#"):
                    connections.append(url)

        imported_count = 0
        skipped_count = 0

        for conn in connections:
            try:
                # Convert URL to public identifier
                if "linkedin.com" in conn:
                    public_id = url_to_public_id(conn)
                    url = conn
                else:
                    public_id = conn
                    url = public_id_to_url(public_id)

                if not public_id:
                    skipped_count += 1
                    continue

                # Get or create Lead
                lead, lead_created = Lead.objects.get_or_create(
                    public_identifier=public_id, defaults={"linkedin_url": url}
                )

                # Check if deal already exists for this campaign/lead
                if Deal.objects.filter(lead=lead, campaign=campaign).exists():
                    skipped_count += 1
                    continue

                # Create Deal in QUALIFIED state so it skips connect request and is immediately processed for follow_up
                Deal.objects.create(
                    lead=lead,
                    campaign=campaign,
                    state=DealState.QUALIFIED,
                    reason="1st-degree connection imported via CSV",
                )

                # Mark as seed public ID for freemium if needed
                if not campaign.seed_public_ids:
                    campaign.seed_public_ids = []
                if public_id not in campaign.seed_public_ids:
                    campaign.seed_public_ids.append(public_id)

                imported_count += 1
            except Exception:
                skipped_count += 1

        if imported_count > 0:
            campaign.save(update_fields=["seed_public_ids"])

        return Response(
            {"success": True, "imported": imported_count, "skipped": skipped_count},
            status=status.HTTP_200_OK,
        )


class CampaignMessagesView(APIView):
    """
    API view for retrieving messages associated with a campaign.

    GET /api/campaigns/{id}/messages - List campaign messages
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """List campaign messages (ChatMessage entries for the campaign)."""
        campaign = self.get_object(pk)

        from openoutreach.chat.models import ChatMessage
        from openoutreach.crm.models import Deal

        # Get all deals for this campaign
        deals = Deal.objects.filter(campaign=campaign).select_related("lead")
        deal_ids = list(deals.values_list("id", flat=True))

        # Get messages for these deals
        messages = (
            ChatMessage.objects.filter(deal_id__in=deal_ids)
            .select_related("deal__lead", "owner")
            .order_by("-creation_date")
        )

        page = request.query_params.get("page")
        limit = request.query_params.get("limit")

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
            # Determine sender: 'me' if owner is the current user, 'them' otherwise
            sender = "me" if msg.owner == request.user else "them"

            messages_data.append(
                {
                    "id": str(msg.id),
                    "deal_id": str(msg.deal.id),
                    "deal_urn": (
                        msg.deal.lead.urn if msg.deal.lead.urn else str(msg.deal.id)
                    ),
                    "content": msg.content,
                    "is_outgoing": msg.is_outgoing,
                    "sender": sender,
                    "creation_date": (
                        msg.creation_date.isoformat() if msg.creation_date else None
                    ),
                    "recipient_name": (
                        msg.deal.lead.public_identifier if msg.deal.lead else None
                    ),
                    "recipient_url": (
                        msg.deal.lead.linkedin_url if msg.deal.lead else None
                    ),
                }
            )

        return Response(
            {
                "data": messages_data,
                "pagination": {
                    "page": int(page) if page else 1,
                    "limit": int(limit) if limit else len(messages_data),
                    "total": total,
                },
            }
        )


class CampaignAnalyticsView(APIView):
    """
    API view for retrieving analytics for a campaign.

    GET /api/campaigns/{id}/analytics - Get campaign analytics
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """Get campaign analytics."""
        campaign = self.get_object(pk)

        period = request.query_params.get("period", "30d")

        # Calculate date range
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        else:
            period_days = 30

        since = timezone.now() - timedelta(days=period_days)

        # Connection metrics
        connections_sent = ActionLog.objects.filter(
            campaign=campaign,
            action_type=ActionLog.ActionType.CONNECT,
            created_at__gte=since,
        ).count()

        connections_accepted = Deal.objects.filter(
            campaign=campaign,
            state=DealState.CONNECTED,
            creation_date__gte=since,
        ).count()

        connection_accept_rate = (
            connections_accepted / connections_sent * 100 if connections_sent > 0 else 0
        )

        # Follow-up metrics
        messages_sent = ActionLog.objects.filter(
            campaign=campaign,
            action_type=ActionLog.ActionType.FOLLOW_UP,
            created_at__gte=since,
        ).count()

        messages_replied = (
            Deal.objects.filter(
                campaign=campaign,
                messages__is_outgoing=False,
                messages__creation_date__gte=since,
            )
            .distinct()
            .count()
        )

        response_rate = (
            messages_replied / messages_sent * 100 if messages_sent > 0 else 0
        )

        # Conversion metrics
        conversions = Deal.objects.filter(
            campaign=campaign,
            state=DealState.COMPLETED,
            creation_date__gte=since,
        ).count()

        conversion_rate = (
            conversions / connections_accepted * 100 if connections_accepted > 0 else 0
        )

        # Error metrics
        errors = ActionLog.objects.filter(
            campaign=campaign,
            error_message__isnull=False,
            error_message__gt="",
            created_at__gte=since,
        ).count()

        # ActionLog does not currently persist structured rate-limit warnings.
        rate_limit_warnings = 0

        # Pipeline statistics
        pipeline = {
            "qualified": Deal.objects.filter(
                campaign=campaign,
                state=DealState.QUALIFIED,
            ).count(),
            "ready_to_connect": Deal.objects.filter(
                campaign=campaign,
                state=DealState.READY_TO_CONNECT,
            ).count(),
            "pending": Deal.objects.filter(
                campaign=campaign,
                state=DealState.PENDING,
            ).count(),
            "connected": Deal.objects.filter(
                campaign=campaign,
                state=DealState.CONNECTED,
            ).count(),
            "completed": Deal.objects.filter(
                campaign=campaign,
                state=DealState.COMPLETED,
            ).count(),
            "failed": Deal.objects.filter(
                campaign=campaign,
                state=DealState.FAILED,
            ).count(),
            "no_email": Deal.objects.filter(
                campaign=campaign,
                state=DealState.NO_EMAIL,
            ).count(),
        }

        # Daily breakdown (last 7 days)
        daily_breakdown = []
        breakdown_start = timezone.now() - timedelta(days=6)
        for i in range(7):
            day_start = breakdown_start + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            day_connections_sent = ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.CONNECT,
                created_at__gte=day_start,
                created_at__lt=day_end,
            ).count()

            day_connections_accepted = Deal.objects.filter(
                campaign=campaign,
                state=DealState.CONNECTED,
                creation_date__gte=day_start,
                creation_date__lt=day_end,
            ).count()

            day_messages_sent = ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.FOLLOW_UP,
                created_at__gte=day_start,
                created_at__lt=day_end,
            ).count()

            day_messages_replied = (
                Deal.objects.filter(
                    campaign=campaign,
                    messages__is_outgoing=False,
                    messages__creation_date__gte=day_start,
                    messages__creation_date__lt=day_end,
                )
                .distinct()
                .count()
            )

            daily_breakdown.append(
                {
                    "date": day_start.strftime("%Y-%m-%d"),
                    "connections_sent": day_connections_sent,
                    "connections_accepted": day_connections_accepted,
                    "messages_sent": day_messages_sent,
                    "messages_replied": day_messages_replied,
                    "responses": day_messages_replied,  # Alias for frontend compatibility
                }
            )

        last_7_days = {
            "connections_sent": ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.CONNECT,
                created_at__gte=timezone.now() - timedelta(days=7),
            ).count(),
            "connections_accepted": Deal.objects.filter(
                campaign=campaign,
                state=DealState.CONNECTED,
                creation_date__gte=timezone.now() - timedelta(days=7),
            ).count(),
            "conversions": Deal.objects.filter(
                campaign=campaign,
                state=DealState.COMPLETED,
                creation_date__gte=timezone.now() - timedelta(days=7),
            ).count(),
        }
        last_30_days = {
            "connections_sent": ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.CONNECT,
                created_at__gte=timezone.now() - timedelta(days=30),
            ).count(),
            "connections_accepted": Deal.objects.filter(
                campaign=campaign,
                state=DealState.CONNECTED,
                creation_date__gte=timezone.now() - timedelta(days=30),
            ).count(),
            "conversions": Deal.objects.filter(
                campaign=campaign,
                state=DealState.COMPLETED,
                creation_date__gte=timezone.now() - timedelta(days=30),
            ).count(),
        }

        stats = {
            "connections_sent": connections_sent,
            "connections_accepted": connections_accepted,
            "connection_accept_rate": round(connection_accept_rate, 2),
            "connection_success_rate": round(connection_accept_rate, 2),
            "messages_sent": messages_sent,
            "messages_replied": messages_replied,
            "responses": messages_replied,  # Alias for frontend compatibility
            "response_rate": round(response_rate, 2),
            "conversions": conversions,
            "conversion_rate": round(conversion_rate, 2),
            "daily_connections": round(connections_sent / period_days, 1),
            "daily_messages": round(messages_sent / period_days, 1),
            "last_7_days": last_7_days,
            "last_30_days": last_30_days,
            "total_connection_attempts": connections_sent,
            "total_messages_sent": messages_sent,
            "qualified_leads": pipeline["qualified"],
            "deals_closed": conversions,
            "errors": errors,
            "rate_limit_warnings": rate_limit_warnings,
        }

        return Response(
            {
                "data": {
                    "stats": stats,
                    "daily_breakdown": daily_breakdown,
                    "pipeline": pipeline,
                },
                "stats": stats,
                "period": period,
                "campaign_id": pk,
                "daily_breakdown": daily_breakdown,
                "pipeline": pipeline,
            }
        )


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
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """Get campaign state machine."""
        campaign = self.get_object(pk)

        from openoutreach.linkedin.models import CampaignStateGraph

        try:
            state_graph = campaign.state_graph

            # Serialize nodes with proper structure
            nodes = []
            for node in state_graph.nodes.all():
                nodes.append(
                    {
                        "id": str(node.id),
                        "name": node.name,
                        "type": node.node_type,
                        "config": node.config,
                        "x": node.x,
                        "y": node.y,
                        "description": node.description,
                        "is_active": node.is_active,
                    }
                )

            # Serialize transitions with proper structure
            transitions = []
            for transition in state_graph.transitions.all():
                transitions.append(
                    {
                        "id": str(transition.id),
                        "source_node": str(transition.source_node.id),
                        "target_node": str(transition.target_node.id),
                        "label": transition.label,
                        "condition_type": transition.condition_type,
                        "order": transition.order,
                        "is_active": transition.is_active,
                    }
                )

            return Response(
                {
                    "id": state_graph.id,
                    "campaign_id": campaign.id,
                    "name": state_graph.name,
                    "description": state_graph.description,
                    "is_active": state_graph.is_active,
                    "is_valid": state_graph.is_valid,
                    "validation_errors": state_graph.validation_errors,
                    "nodes": nodes,
                    "transitions": transitions,
                }
            )
        except CampaignStateGraph.DoesNotExist:
            return Response(
                {
                    "id": None,
                    "campaign_id": campaign.id,
                    "name": "",
                    "description": "",
                    "is_active": True,
                    "is_valid": False,
                    "validation_errors": [],
                    "nodes": [],
                    "transitions": [],
                }
            )

    def post(self, request, pk):
        """
        Update or create state machine for campaign, or validate if URL ends with /validate/.

        POST /api/campaigns/{id}/state-machine - Update/create state machine
        POST /api/campaigns/{id}/state-machine/validate - Validate state machine
        """
        campaign = self.get_object(pk)

        # Check if this is a validate request based on URL path
        if request.path.endswith("/validate/"):
            return self.post_validate(request, pk)

        from openoutreach.linkedin.models import (
            CampaignStateGraph,
            StateNode,
            StateTransition,
        )

        # Get state machine data
        name = request.data.get("name", campaign.name + " State Machine")
        description = request.data.get("description", "")
        graph_data = request.data.get("graph_data", {})

        # Create or update state graph
        state_graph, created = CampaignStateGraph.objects.get_or_create(
            campaign=campaign,
            defaults={
                "name": name,
                "description": description,
                "graph_data": graph_data,
            },
        )

        if not created:
            state_graph.name = name
            state_graph.description = description
            state_graph.graph_data = graph_data
            state_graph.is_valid = False  # Reset validation on update
            state_graph.save()

        # Parse nodes and transitions from graph_data
        nodes_data = graph_data.get("nodes", [])
        transitions_data = graph_data.get("transitions", [])

        # Clear existing nodes and transitions
        state_graph.nodes.all().delete()
        state_graph.transitions.all().delete()

        # Create nodes
        node_map = {}
        for node_data in nodes_data:
            node = StateNode.objects.create(
                state_graph=state_graph,
                name=node_data.get("name", ""),
                node_type=node_data.get("type", "message"),
                config=node_data.get("config", {}),
                x=node_data.get("x", 0),
                y=node_data.get("y", 0),
                description=node_data.get("description", ""),
                is_active=node_data.get("is_active", True),
            )
            node_map[node_data["id"]] = node

        # Create transitions
        for transition_data in transitions_data:
            source_node = node_map.get(transition_data["source_node"])
            target_node = node_map.get(transition_data["target_node"])

            if source_node and target_node:
                StateTransition.objects.create(
                    state_graph=state_graph,
                    source_node=source_node,
                    target_node=target_node,
                    label=transition_data.get("label", ""),
                    condition_type=transition_data.get("condition_type", "always"),
                    order=transition_data.get("order", 0),
                )

        state_graph.is_valid = True
        state_graph.save()

        # Serialize nodes with proper structure
        nodes = []
        for node in state_graph.nodes.all():
            nodes.append(
                {
                    "id": str(node.id),
                    "name": node.name,
                    "type": node.node_type,
                    "config": node.config,
                    "x": node.x,
                    "y": node.y,
                    "description": node.description,
                    "is_active": node.is_active,
                }
            )

        # Serialize transitions with proper structure
        transitions = []
        for transition in state_graph.transitions.all():
            transitions.append(
                {
                    "id": str(transition.id),
                    "source_node": str(transition.source_node.id),
                    "target_node": str(transition.target_node.id),
                    "label": transition.label,
                    "condition_type": transition.condition_type,
                    "order": transition.order,
                    "is_active": transition.is_active,
                }
            )

        return Response(
            {
                "id": state_graph.id,
                "campaign_id": campaign.id,
                "name": state_graph.name,
                "description": state_graph.description,
                "is_active": state_graph.is_active,
                "is_valid": state_graph.is_valid,
                "validation_errors": [],
                "nodes": nodes,
                "transitions": transitions,
            }
        )

    def post_validate(self, request, pk):
        """Validate state machine for campaign."""
        campaign = self.get_object(pk)

        from openoutreach.linkedin.models import CampaignStateGraph, StateNode

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
                all_node_ids = set(nodes.values_list("id", flat=True))
                source_node_ids = set(
                    transitions.values_list("source_node_id", flat=True)
                )
                target_node_ids = set(
                    transitions.values_list("target_node_id", flat=True)
                )

                # Check for unreachable nodes
                all_referenced = source_node_ids | target_node_ids
                for node_id in all_node_ids:
                    if node_id not in all_referenced:
                        warnings.append(f"Node {node_id} is not connected")

            state_graph.validation_errors = errors
            state_graph.is_valid = len(errors) == 0
            state_graph.save()

            return Response(
                {
                    "is_valid": len(errors) == 0,
                    "errors": errors,
                    "warnings": warnings,
                }
            )

        except CampaignStateGraph.DoesNotExist:
            return Response(
                {
                    "is_valid": False,
                    "errors": ["No state machine defined for this campaign"],
                    "warnings": [],
                },
                status=status.HTTP_404_NOT_FOUND,
            )


class CampaignGhostModeSimulationView(APIView):
    """
    API view for managing and viewing ghost mode simulations for a campaign.

    GET /api/campaigns/{id}/ghost-mode/simulations - Get simulation logs
    POST /api/campaigns/{id}/ghost-mode/start - Start ghost mode
    POST /api/campaigns/{id}/ghost-mode/stop - Stop ghost mode
    GET /api/campaigns/{id}/ghost-mode/export/csv - Export simulations as CSV
    GET /api/campaigns/{id}/ghost-mode/export/json - Export simulations as JSON
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """Get ghost mode simulation logs for a campaign."""
        campaign = self.get_object(pk)

        ghost_campaign = GhostCampaign.objects.filter(
            campaign=campaign, is_active=True
        ).first()
        if not ghost_campaign:
            return Response(
                {"success": False, "error": "No active ghost mode for this campaign"},
                status=status.HTTP_404_NOT_FOUND,
            )

        logs = GhostSimulationLog.objects.filter(
            ghost_campaign=ghost_campaign
        ).order_by("-started_at")

        return Response(
            {
                "success": True,
                "campaign_id": ghost_campaign.id,
                "total": logs.count(),
                "simulations": [
                    {
                        "id": log.id,
                        "action_type": log.action_type,
                        "target_name": log.target_name,
                        "target_url": log.target_url,
                        "result_data": log.result_data,
                        "rating": log.rating,
                        "score": log.score,
                        "started_at": log.started_at.isoformat(),
                        "completed_at": log.completed_at.isoformat(),
                        "simulated_action": log.simulated_action,
                    }
                    for log in logs[:100]
                ],
            }
        )

    def post(self, request, pk):
        """Start or stop ghost mode for a campaign."""
        campaign = self.get_object(pk)

        from django.utils import timezone

        action = request.data.get("action", "start")

        if action == "start":
            # Create or get ghost campaign
            ghost_campaign, created = GhostCampaign.objects.get_or_create(
                campaign=campaign,
                defaults={
                    "name": f"{campaign.name} - Ghost Mode",
                    "mode_type": GhostCampaign.ModeType.SIMULATION,
                    "start_time": timezone.now(),
                },
            )

            return Response(
                {
                    "success": True,
                    "ghost_campaign_id": ghost_campaign.id,
                    "message": f"Ghost mode started for {campaign.name}",
                    "created": created,
                }
            )

        elif action == "stop":
            ghost_campaign = GhostCampaign.objects.filter(
                campaign=campaign, is_active=True
            ).first()
            if not ghost_campaign:
                return Response(
                    {
                        "success": False,
                        "error": "No active ghost mode for this campaign",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            ghost_campaign.is_active = False
            ghost_campaign.end_time = timezone.now()
            ghost_campaign.save()

            return Response(
                {
                    "success": True,
                    "message": f"Ghost mode stopped for {campaign.name}",
                }
            )

        else:
            return Response(
                {"success": False, "error": 'Invalid action. Use "start" or "stop".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def get_export_csv(self, request, pk):
        """Export ghost mode simulations as CSV."""
        campaign = self.get_object(pk)

        ghost_campaign = GhostCampaign.objects.filter(
            campaign=campaign, is_active=True
        ).first()
        if not ghost_campaign:
            return Response(
                {"success": False, "error": "No active ghost mode for this campaign"},
                status=status.HTTP_404_NOT_FOUND,
            )

        import csv

        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="ghost-mode-{ghost_campaign.name}.csv"',
            },
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "timestamp",
                "action_type",
                "target_name",
                "target_url",
                "result_success",
                "rating",
                "score",
                "simulated_action",
            ]
        )

        logs = GhostSimulationLog.objects.filter(ghost_campaign=ghost_campaign)
        for log in logs:
            writer.writerow(
                [
                    log.started_at.isoformat(),
                    log.action_type,
                    log.target_name,
                    log.target_url,
                    log.result_data.get("success", False),
                    log.rating,
                    log.score,
                    log.simulated_action,
                ]
            )

        return response

    def get_export_json(self, request, pk):
        """Export ghost mode simulations as JSON."""
        campaign = self.get_object(pk)

        ghost_campaign = GhostCampaign.objects.filter(
            campaign=campaign, is_active=True
        ).first()
        if not ghost_campaign:
            return Response(
                {"success": False, "error": "No active ghost mode for this campaign"},
                status=status.HTTP_404_NOT_FOUND,
            )

        logs = GhostSimulationLog.objects.filter(ghost_campaign=ghost_campaign)

        return Response(
            {
                "campaign": {
                    "id": ghost_campaign.id,
                    "name": ghost_campaign.name,
                    "description": ghost_campaign.description,
                    "is_active": ghost_campaign.is_active,
                    "mode_type": ghost_campaign.mode_type,
                    "leads_processed": ghost_campaign.leads_processed,
                    "connections_simulated": ghost_campaign.connections_simulated,
                    "messages_simulated": ghost_campaign.messages_simulated,
                    "conversions_simulated": ghost_campaign.conversions_simulated,
                    "avg_rating": ghost_campaign.avg_rating,
                    "avg_score": ghost_campaign.avg_score,
                    "created_at": ghost_campaign.created_at.isoformat(),
                    "updated_at": ghost_campaign.updated_at.isoformat(),
                },
                "total_simulations": logs.count(),
                "simulations": [
                    {
                        "id": log.id,
                        "action_type": log.action_type,
                        "target_name": log.target_name,
                        "target_url": log.target_url,
                        "result_data": log.result_data,
                        "rating": log.rating,
                        "score": log.score,
                        "started_at": log.started_at.isoformat(),
                        "completed_at": log.completed_at.isoformat(),
                        "simulated_action": log.simulated_action,
                    }
                    for log in logs
                ],
            }
        )


class CampaignGhostModeSimulationListView(APIView):
    """
    API view for fetching ghost mode simulation logs for a campaign.

    GET /api/campaigns/{id}/ghost-mode/simulations - Get simulation logs
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """Get ghost mode simulation logs for a campaign."""
        campaign = self.get_object(pk)

        ghost_campaign = GhostCampaign.objects.filter(
            campaign=campaign, is_active=True
        ).first()
        if not ghost_campaign:
            return Response(
                {"success": False, "error": "No active ghost mode for this campaign"},
                status=status.HTTP_404_NOT_FOUND,
            )

        logs = GhostSimulationLog.objects.filter(
            ghost_campaign=ghost_campaign
        ).order_by("-started_at")

        return Response(
            {
                "success": True,
                "campaign_id": ghost_campaign.id,
                "total": logs.count(),
                "simulations": [
                    {
                        "id": log.id,
                        "action_type": log.action_type,
                        "target_name": log.target_name,
                        "target_url": log.target_url,
                        "result_data": log.result_data,
                        "rating": log.rating,
                        "score": log.score,
                        "started_at": log.started_at.isoformat(),
                        "completed_at": log.completed_at.isoformat(),
                        "simulated_action": log.simulated_action,
                    }
                    for log in logs[:100]
                ],
            }
        )


class CampaignGhostModeActionView(APIView):
    """
    API view for starting/stopping ghost mode for a campaign.

    POST /api/campaigns/{id}/ghost-mode/action - Start or stop ghost mode (action in body)
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def post(self, request, pk):
        """Start or stop ghost mode for a campaign."""
        campaign = self.get_object(pk)

        from django.utils import timezone

        action = request.data.get("action", "start")

        if action == "start":
            # Create or get ghost campaign
            ghost_campaign, created = GhostCampaign.objects.get_or_create(
                campaign=campaign,
                defaults={
                    "name": f"{campaign.name} - Ghost Mode",
                    "mode_type": GhostCampaign.ModeType.SIMULATION,
                    "start_time": timezone.now(),
                },
            )

            return Response(
                {
                    "success": True,
                    "ghost_campaign_id": ghost_campaign.id,
                    "message": f"Ghost mode started for {campaign.name}",
                    "created": created,
                }
            )

        elif action == "stop":
            ghost_campaign = GhostCampaign.objects.filter(
                campaign=campaign, is_active=True
            ).first()
            if not ghost_campaign:
                return Response(
                    {
                        "success": False,
                        "error": "No active ghost mode for this campaign",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            ghost_campaign.is_active = False
            ghost_campaign.end_time = timezone.now()
            ghost_campaign.save()

            return Response(
                {
                    "success": True,
                    "message": f"Ghost mode stopped for {campaign.name}",
                }
            )


class AnalyticsOverviewView(APIView):
    """
    API view for retrieving aggregated analytics across all campaigns.

    GET /api/analytics/overview - Get aggregated analytics with optional campaign and time range filters
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get aggregated analytics across all campaigns for the current user."""
        campaigns = Campaign.objects.filter(users=request.user).order_by("name")

        campaign_id_param = request.query_params.get("campaign_id")
        if campaign_id_param:
            campaigns = campaigns.filter(id=campaign_id_param)

        period = request.query_params.get("period", "30d")
        if period == "7d":
            period_days = 7
        elif period == "30d":
            period_days = 30
        elif period == "90d":
            period_days = 90
        else:
            period_days = 30
        since = timezone.now() - timedelta(days=period_days)

        deals = Deal.objects.filter(campaign__in=campaigns)

        total_qualified = deals.filter(state=DealState.QUALIFIED).count()
        total_ready_to_connect = deals.filter(state=DealState.READY_TO_CONNECT).count()
        total_pending = deals.filter(state=DealState.PENDING).count()
        total_connected = deals.filter(state=DealState.CONNECTED).count()
        total_completed = deals.filter(state=DealState.COMPLETED).count()
        total_failed = deals.filter(state=DealState.FAILED).count()
        total_no_email = deals.filter(state=DealState.NO_EMAIL).count()

        total_connections_sent = ActionLog.objects.filter(
            campaign__in=campaigns,
            action_type=ActionLog.ActionType.CONNECT,
            created_at__gte=since,
        ).count()
        total_connections_accepted = Deal.objects.filter(
            campaign__in=campaigns,
            state=DealState.CONNECTED,
            creation_date__gte=since,
        ).count()
        total_messages_sent = ActionLog.objects.filter(
            campaign__in=campaigns,
            action_type=ActionLog.ActionType.FOLLOW_UP,
            created_at__gte=since,
        ).count()
        total_messages_replied = (
            deals.filter(
                messages__is_outgoing=False,
                messages__creation_date__gte=since,
            )
            .distinct()
            .count()
        )
        total_conversions = Deal.objects.filter(
            campaign__in=campaigns,
            state=DealState.COMPLETED,
            creation_date__gte=since,
        ).count()

        connection_accept_rate = (
            round((total_connections_accepted / total_connections_sent * 100), 2)
            if total_connections_sent > 0
            else 0.0
        )
        response_rate = (
            round((total_messages_replied / total_messages_sent * 100), 2)
            if total_messages_sent > 0
            else 0.0
        )
        conversion_rate = (
            round((total_conversions / total_qualified * 100), 2)
            if total_qualified > 0
            else 0.0
        )

        campaigns_data = []
        for campaign in campaigns:
            campaign_deals = campaign.deals.all()
            qualified = campaign_deals.filter(state=DealState.QUALIFIED).count()
            ready_to_connect = campaign_deals.filter(
                state=DealState.READY_TO_CONNECT
            ).count()
            pending = campaign_deals.filter(state=DealState.PENDING).count()
            connected_current = campaign_deals.filter(state=DealState.CONNECTED).count()
            completed_current = campaign_deals.filter(state=DealState.COMPLETED).count()
            failed = campaign_deals.filter(state=DealState.FAILED).count()
            no_email = campaign_deals.filter(state=DealState.NO_EMAIL).count()

            connections_sent = ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.CONNECT,
                created_at__gte=since,
            ).count()
            connections_accepted = Deal.objects.filter(
                campaign=campaign,
                state=DealState.CONNECTED,
                creation_date__gte=since,
            ).count()
            messages_sent = ActionLog.objects.filter(
                campaign=campaign,
                action_type=ActionLog.ActionType.FOLLOW_UP,
                created_at__gte=since,
            ).count()
            messages_replied = (
                campaign_deals.filter(
                    messages__is_outgoing=False,
                    messages__creation_date__gte=since,
                )
                .distinct()
                .count()
            )
            conversions = Deal.objects.filter(
                campaign=campaign,
                state=DealState.COMPLETED,
                creation_date__gte=since,
            ).count()

            campaigns_data.append(
                {
                    "id": str(campaign.id),
                    "name": campaign.name,
                    "description": campaign.description,
                    "status": campaign.status,
                    "stats": {
                        "totalLeads": campaign_deals.count(),
                        "activeLeads": qualified
                        + ready_to_connect
                        + pending
                        + connected_current,
                        "qualified": qualified,
                        "readyToConnect": ready_to_connect,
                        "pending": pending,
                        "connected": connected_current,
                        "completed": completed_current,
                        "failed": failed,
                        "noEmail": no_email,
                        "connectionsSent": connections_sent,
                        "connectionsAccepted": connections_accepted,
                        "messagesSent": messages_sent,
                        "messagesReplied": messages_replied,
                        "responses": messages_replied,
                        "connectionAcceptRate": round(
                            (connections_accepted / connections_sent * 100), 2
                        )
                        if connections_sent > 0
                        else 0.0,
                        "responseRate": round(
                            (messages_replied / messages_sent * 100), 2
                        )
                        if messages_sent > 0
                        else 0.0,
                        "conversionRate": round((conversions / qualified * 100), 2)
                        if qualified > 0
                        else 0.0,
                    },
                }
            )

        pipeline = {
            "qualified": total_qualified,
            "ready_to_connect": total_ready_to_connect,
            "pending": total_pending,
            "connected": total_connected,
            "completed": total_completed,
            "failed": total_failed,
            "no_email": total_no_email,
        }
        totals = {
            "leads": total_qualified
            + total_ready_to_connect
            + total_pending
            + total_connected,
            "qualified": total_qualified,
            "readyToConnect": total_ready_to_connect,
            "connected": total_connected,
            "pending": total_pending,
            "failed": total_failed,
            "noEmail": total_no_email,
            "connectionAcceptRate": connection_accept_rate,
            "responseRate": response_rate,
            "conversionRate": conversion_rate,
        }
        stats = {
            "connectionsSent": total_connections_sent,
            "connectionsAccepted": total_connections_accepted,
            "connectionAcceptRate": connection_accept_rate,
            "messagesSent": total_messages_sent,
            "messagesReplied": total_messages_replied,
            "responseRate": response_rate,
            "conversions": total_conversions,
            "conversionRate": conversion_rate,
        }

        return Response(
            {
                "data": {
                    "period": period,
                    "stats": stats,
                    "pipeline": pipeline,
                    "totals": totals,
                    "campaigns": campaigns_data,
                },
                "period": period,
                "stats": stats,
                "pipeline": pipeline,
                "totals": totals,
                "campaigns": campaigns_data,
            }
        )


class CampaignActivityView(APIView):
    """Campaign activity log — completed actions + scheduled tasks.

    GET /api/campaigns/{id}/activity?page=1&limit=20
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Campaign.objects.filter(users=self.request.user).get(pk=pk)
        except Campaign.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        campaign = self.get_object(pk)

        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 20))
        limit = min(limit, 100)

        # --- Next scheduled task for this campaign ---
        next_task = (
            Task.objects.filter(
                status=Task.Status.PENDING,
                payload__campaign_id=campaign.pk,
            )
            .order_by("scheduled_at")
            .values("id", "task_type", "scheduled_at", "status")
            .first()
        )

        # Task type label mapping
        TASK_LABELS = {
            "connect": "Send Connection Request",
            "check_pending": "Check Pending Connections",
            "follow_up": "Send Follow-up Message",
            "send_manual_message": "Send Manual Message",
        }

        next_task_data = None
        if next_task:
            scheduled = next_task["scheduled_at"]
            now = timezone.now()
            eta_seconds = max(0, (scheduled - now).total_seconds())
            task_type = next_task["task_type"]
            next_task_data = {
                "id": next_task["id"],
                "task_type": task_type,
                "label": TASK_LABELS.get(task_type, task_type.replace("_", " ").title()),
                "scheduled_at": scheduled.isoformat(),
                "eta_seconds": int(eta_seconds),
            }

        # --- Activity entries: merge ActionLog + completed/failed Tasks ---
        # ActionLog entries (completed actions with details)
        action_logs = (
            ActionLog.objects.filter(campaign=campaign)
            .order_by("-created_at")
            .values(
                "id",
                "action_type",
                "status",
                "error_message",
                "duration_ms",
                "created_at",
            )
        )

        # Task entries (all states for full timeline)
        tasks = (
            Task.objects.filter(payload__campaign_id=campaign.pk)
            .exclude(status=Task.Status.PENDING)
            .order_by("-scheduled_at")
            .values(
                "id",
                "task_type",
                "status",
                "scheduled_at",
                "started_at",
                "completed_at",
                "payload",
            )
        )

        # Build unified timeline
        entries = []

        # Action type label mapping
        ACTION_LABELS = {
            "connect": "Connection Request",
            "check_pending": "Checked Pending Connections",
            "follow_up": "Follow-up Message",
            "send_manual_message": "Manual Message",
            "campaign_paused": "Campaign Paused",
            "campaign_started": "Campaign Started",
        }

        for log in action_logs:
            action_type = log["action_type"]
            entries.append(
                {
                    "id": f"action_{log['id']}",
                    "source": "action",
                    "type": action_type,
                    "label": ACTION_LABELS.get(action_type, action_type.replace("_", " ").title()),
                    "status": log["status"] or "completed",
                    "error": log["error_message"] or None,
                    "duration_ms": log["duration_ms"],
                    "timestamp": log["created_at"].isoformat(),
                }
            )

        for task in tasks:
            ts = task["completed_at"] or task["started_at"] or task["scheduled_at"]
            error = (task["payload"] or {}).get("last_error")
            task_type = task["task_type"]
            entries.append(
                {
                    "id": f"task_{task['id']}",
                    "source": "task",
                    "type": task_type,
                    "label": ACTION_LABELS.get(task_type, task_type.replace("_", " ").title()),
                    "status": task["status"],
                    "error": error,
                    "duration_ms": None,
                    "timestamp": ts.isoformat(),
                }
            )

        # Deduplicate: if an action_log and a task have the same type and
        # close timestamps (within 5s), keep only the action_log (richer).
        action_keys = set()
        for e in entries:
            if e["source"] == "action":
                action_keys.add((e["type"], e["timestamp"][:16]))

        deduped = []
        for e in entries:
            if e["source"] == "task":
                key = (e["type"], e["timestamp"][:16])
                if key in action_keys:
                    continue
            deduped.append(e)

        # Sort by timestamp descending
        deduped.sort(key=lambda e: e["timestamp"], reverse=True)

        total = len(deduped)
        start = (page - 1) * limit
        end = start + limit
        page_entries = deduped[start:end]

        # Pending task count for context
        pending_count = Task.objects.filter(
            status=Task.Status.PENDING,
            payload__campaign_id=campaign.pk,
        ).count()

        return Response(
            {
                "data": page_entries,
                "next_task": next_task_data,
                "pending_count": pending_count,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "has_more": end < total,
                },
            }
        )
