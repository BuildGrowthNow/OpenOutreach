# Campaign Template API Views
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.db import models

from django.contrib.auth.models import User
from openoutreach.core.models import CampaignTemplate
from openoutreach.api.serializers.campaigns import (
    CampaignTemplateSerializer,
    CampaignTemplateCreateSerializer,
)
from openoutreach.api.utils import create_pagination_response


class CampaignTemplateListView(APIView):
    """
    API view for listing and creating campaign templates.

    GET /api/campaign-templates - List all templates (with filters)
    POST /api/campaign-templates - Create a new template
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List templates accessible by the current user with optional filters."""
        # Filter templates: user's own templates OR public templates
        templates = (
            CampaignTemplate.objects.filter(
                models.Q(created_by=request.user) | models.Q(is_public=True)
            )
            .select_related("created_by")
            .order_by("-created_at")
        )

        # Apply filters
        public_param = request.query_params.get("public")
        if public_param is not None:
            is_public = public_param.lower() == "true"
            templates = templates.filter(is_public=is_public)

        created_by_param = request.query_params.get("created_by")
        if created_by_param:
            templates = templates.filter(created_by__id=created_by_param)

        page = request.query_params.get("page")
        limit = request.query_params.get("limit")

        # Pagination
        if page and limit:
            try:
                page_num = int(page)
                limit_num = int(limit)
                start = (page_num - 1) * limit_num
                end = start + limit_num
                templates = templates[start:end]
            except (ValueError, TypeError):
                pass

        serializer = CampaignTemplateSerializer(templates, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {
                    "page": int(page) if page else 1,
                    "limit": int(limit) if limit else len(serializer.data),
                    "total": templates.count(),
                },
            }
        )

    def post(self, request):
        """Create a new template."""
        serializer = CampaignTemplateCreateSerializer(data=request.data)
        if serializer.is_valid():
            template = CampaignTemplate.objects.create(
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                campaign_objective=serializer.validated_data.get(
                    "campaign_objective", ""
                ),
                ghost_mode_enabled=serializer.validated_data.get(
                    "ghost_mode_enabled", False
                ),
                velocity=serializer.validated_data.get("velocity", 20),
                cooldown_minutes=serializer.validated_data.get("cooldown_minutes", 0),
                is_public=serializer.validated_data.get("is_public", False),
                created_by=request.user,
            )

            return Response(
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "campaign_objective": template.campaign_objective,
                    "ghost_mode_enabled": template.ghost_mode_enabled,
                    "velocity": template.velocity,
                    "cooldown_minutes": template.cooldown_minutes,
                    "is_public": template.is_public,
                    "created_by": {
                        "id": template.created_by.id,
                        "username": template.created_by.username,
                    },
                    "created_at": (
                        template.created_at.isoformat() if template.created_at else None
                    ),
                    "updated_at": (
                        template.updated_at.isoformat() if template.updated_at else None
                    ),
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignTemplateDetailView(APIView):
    """
    API view for retrieving, updating, and deleting a campaign template.

    GET /api/campaign-templates/{id} - Get template details
    PATCH /api/campaign-templates/{id} - Update template
    DELETE /api/campaign-templates/{id} - Delete template
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            # User can access their own templates OR public templates
            return CampaignTemplate.objects.filter(
                models.Q(created_by=self.request.user) | models.Q(is_public=True)
            ).get(pk=pk)
        except CampaignTemplate.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """Get template details."""
        template = self.get_object(pk)

        return Response(
            {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "campaign_objective": template.campaign_objective,
                "ghost_mode_enabled": template.ghost_mode_enabled,
                "velocity": template.velocity,
                "cooldown_minutes": template.cooldown_minutes,
                "is_public": template.is_public,
                "created_by": {
                    "id": template.created_by.id,
                    "username": template.created_by.username,
                },
                "created_at": (
                    template.created_at.isoformat() if template.created_at else None
                ),
                "updated_at": (
                    template.updated_at.isoformat() if template.updated_at else None
                ),
            }
        )

    def patch(self, request, pk):
        """Update template."""
        template = self.get_object(pk)

        # Only allow owner to update
        if template.created_by != request.user:
            return Response(
                {"error": "You do not have permission to edit this template."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CampaignTemplateCreateSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            # Update fields if provided
            for field, value in serializer.validated_data.items():
                if field == "created_by":
                    continue  # Can't change ownership
                setattr(template, field, value)

            template.save()

            return Response(
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description,
                    "campaign_objective": template.campaign_objective,
                    "ghost_mode_enabled": template.ghost_mode_enabled,
                    "velocity": template.velocity,
                    "cooldown_minutes": template.cooldown_minutes,
                    "is_public": template.is_public,
                    "created_by": {
                        "id": template.created_by.id,
                        "username": template.created_by.username,
                    },
                    "created_at": (
                        template.created_at.isoformat() if template.created_at else None
                    ),
                    "updated_at": (
                        template.updated_at.isoformat() if template.updated_at else None
                    ),
                }
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete template."""
        template = self.get_object(pk)

        # Only allow owner to delete
        if template.created_by != request.user:
            return Response(
                {"error": "You do not have permission to delete this template."},
                status=status.HTTP_403_FORBIDDEN,
            )

        template.delete()
        return Response({"success": True}, status=status.HTTP_204_NO_CONTENT)


class CampaignTemplateCloneView(APIView):
    """
    API view for cloning a campaign template.

    POST /api/campaign-templates/{id}/clone/ - Create a new template from an existing one
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            # User can access their own templates OR public templates
            return CampaignTemplate.objects.filter(
                models.Q(created_by=self.request.user) | models.Q(is_public=True)
            ).get(pk=pk)
        except CampaignTemplate.DoesNotExist:
            raise Http404

    def post(self, request, pk):
        """Clone a template."""
        template = self.get_object(pk)

        # Create new template with cloned data
        new_name = request.data.get("name", f"{template.name} (Clone)")
        is_public = request.data.get("is_public", False)

        cloned_template = CampaignTemplate.objects.create(
            name=new_name,
            description=template.description,
            campaign_objective=template.campaign_objective,
            ghost_mode_enabled=template.ghost_mode_enabled,
            velocity=template.velocity,
            cooldown_minutes=template.cooldown_minutes,
            is_public=is_public,
            created_by=request.user,
        )

        return Response(
            {
                "id": cloned_template.id,
                "name": cloned_template.name,
                "description": cloned_template.description,
                "campaign_objective": cloned_template.campaign_objective,
                "ghost_mode_enabled": cloned_template.ghost_mode_enabled,
                "velocity": cloned_template.velocity,
                "cooldown_minutes": cloned_template.cooldown_minutes,
                "is_public": cloned_template.is_public,
                "created_by": {
                    "id": cloned_template.created_by.id,
                    "username": cloned_template.created_by.username,
                },
                "created_at": (
                    cloned_template.created_at.isoformat()
                    if cloned_template.created_at
                    else None
                ),
                "updated_at": (
                    cloned_template.updated_at.isoformat()
                    if cloned_template.updated_at
                    else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class CampaignCreateFromTemplateView(APIView):
    """
    API view for creating a campaign directly from a template.

    POST /api/campaign-templates/{id}/create-campaign/ - Create a campaign from template
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            # User can access their own templates OR public templates
            return CampaignTemplate.objects.filter(
                models.Q(created_by=self.request.user) | models.Q(is_public=True)
            ).get(pk=pk)
        except CampaignTemplate.DoesNotExist:
            raise Http404

    def post(self, request, pk):
        """Create a campaign from template."""
        from openoutreach.core.models import Campaign

        template = self.get_object(pk)

        # Get campaign name from request
        campaign_name = request.data.get("name", f"{template.name} Campaign")
        description = request.data.get("description", template.description)

        # Create campaign from template
        campaign = Campaign.objects.create(
            name=campaign_name,
            description=description or template.description,
            campaign_objective=template.campaign_objective,
            ghost_mode_enabled=template.ghost_mode_enabled,
            velocity=template.velocity,
            cooldown_minutes=template.cooldown_minutes,
            is_freemium=False,
            is_paused=False,
            status="draft",
        )
        campaign.users.add(request.user)

        return Response(
            {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "campaign_objective": campaign.campaign_objective,
                "ghost_mode_enabled": campaign.ghost_mode_enabled,
                "velocity": campaign.velocity,
                "cooldown_minutes": campaign.cooldown_minutes,
                "status": campaign.status,
                "created_at": (
                    campaign.created_at.isoformat() if campaign.created_at else None
                ),
                "updated_at": (
                    campaign.updated_at.isoformat() if campaign.updated_at else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )
