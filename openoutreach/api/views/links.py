# API Views for Links Management

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view, permission_classes
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
import logging

from django.contrib.auth import get_user_model
User = get_user_model()
logger = logging.getLogger(__name__)


class LinksListView(APIView):
    """
    List all tracked links, or create a new link.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, format=None):
        """
        GET /api/links/
        Returns all tracked links available to the user.
        """
        from openoutreach.crm.models import TrackedLink
        
        # Get links from campaigns the user has access to
        user_campaigns = request.user.campaigns.all()
        links = TrackedLink.objects.filter(
            campaign__in=user_campaigns
        ).distinct()
        
        data = [{
            'id': link.id,
            'campaign': {
                'id': link.campaign.id,
                'name': link.campaign.name,
            } if link.campaign else None,
            'original_url': link.original_url,
            'short_code': link.short_code,
            'is_active': link.is_active,
            'total_clicks': link.total_clicks,
            'utm_source': link.utm_source,
            'utm_medium': link.utm_medium,
            'utm_campaign': link.utm_campaign,
            'created_at': link.created_at.isoformat(),
        } for link in links]
        
        return Response({
            'status': 'success',
            'count': links.count(),
            'results': data,
        }, status=status.HTTP_200_OK)
    
    def post(self, request, format=None):
        """
        POST /api/links/
        Create a new tracked link.
        Request: {
            "original_url": "https://example.com",
            "campaign_id": 1,
            "utm_source": "linkedin",
            "utm_medium": "message",
            "utm_campaign": "campaign_name"
        }
        """
        from openoutreach.crm.models import TrackedLink
        
        original_url = request.data.get('original_url')
        campaign_id = request.data.get('campaign_id')
        utm_source = request.data.get('utm_source', '')
        utm_medium = request.data.get('utm_medium', '')
        utm_campaign = request.data.get('utm_campaign', '')
        
        if not original_url:
            return Response({
                'status': 'error',
                'message': 'original_url is required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Validate URL format
            validate_email(original_url)  # This won't work for URLs
        except ValidationError:
            pass  # URL validation will be done by models.URLField
        
        try:
            # Validate URL format properly
            from django.core.validators import URLValidator
            validator = URLValidator()
            validator(original_url)
        except ValidationError:
            return Response({
                'status': 'error',
                'message': 'Invalid URL format',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get campaign (optional, for assignment)
        campaign = None
        if campaign_id:
            try:
                from openoutreach.core.models import Campaign
                campaign = Campaign.objects.get(id=campaign_id)
                
                # Check if user has access to this campaign
                if campaign not in request.user.campaigns.all():
                    return Response({
                        'status': 'error',
                        'message': 'You do not have access to this campaign',
                    }, status=status.HTTP_403_FORBIDDEN)
                    
            except Campaign.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Campaign not found',
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Create the link
        link = TrackedLink.objects.create(
            campaign=campaign,
            original_url=original_url,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
        )
        
        logger.info(f"Created tracked link: {link.short_code} for campaign: {campaign.name if campaign else 'global'}")
        
        return Response({
            'status': 'success',
            'id': link.id,
            'short_code': link.short_code,
            'url': f"/l/{link.short_code}",
        }, status=status.HTTP_201_CREATED)


class LinksDetailView(APIView):
    """
    Retrieve, update, or delete a tracked link.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self, pk):
        from openoutreach.crm.models import TrackedLink
        try:
            return TrackedLink.objects.get(pk=pk)
        except TrackedLink.DoesNotExist:
            return None
    
    def get(self, request, pk, format=None):
        """
        GET /api/links/{pk}/
        Returns details of a specific tracked link.
        """
        link = self.get_object(pk)
        if not link:
            return Response({
                'status': 'error',
                'message': 'Link not found',
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user has access to this link's campaign
        if link.campaign and link.campaign not in request.user.campaigns.all():
            return Response({
                'status': 'error',
                'message': 'You do not have access to this link',
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = {
            'id': link.id,
            'campaign': {
                'id': link.campaign.id,
                'name': link.campaign.name,
            } if link.campaign else None,
            'original_url': link.original_url,
            'short_code': link.short_code,
            'is_active': link.is_active,
            'total_clicks': link.total_clicks,
            'unique_clicks': link.unique_clicks,
            'utm_source': link.utm_source,
            'utm_medium': link.utm_medium,
            'utm_campaign': link.utm_campaign,
            'utm_term': link.utm_term,
            'utm_content': link.utm_content,
            'last_clicked_at': link.last_clicked_at.isoformat() if link.last_clicked_at else None,
            'last_ip': link.last_ip,
            'last_user_agent': link.last_user_agent,
            'created_at': link.created_at.isoformat(),
        }
        
        return Response({
            'status': 'success',
            'result': data,
        }, status=status.HTTP_200_OK)
    
    def put(self, request, pk, format=None):
        """
        PUT /api/links/{pk}/
        Update a tracked link.
        """
        link = self.get_object(pk)
        if not link:
            return Response({
                'status': 'error',
                'message': 'Link not found',
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user has access to this link's campaign
        if link.campaign and link.campaign not in request.user.campaigns.all():
            return Response({
                'status': 'error',
                'message': 'You do not have access to this link',
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Update fields
        if 'original_url' in request.data:
            link.original_url = request.data['original_url']
        if 'is_active' in request.data:
            link.is_active = request.data['is_active']
        if 'utm_source' in request.data:
            link.utm_source = request.data['utm_source']
        if 'utm_medium' in request.data:
            link.utm_medium = request.data['utm_medium']
        if 'utm_campaign' in request.data:
            link.utm_campaign = request.data['utm_campaign']
        if 'utm_term' in request.data:
            link.utm_term = request.data['utm_term']
        if 'utm_content' in request.data:
            link.utm_content = request.data['utm_content']
        
        link.save()
        
        return Response({
            'status': 'success',
            'id': link.id,
            'short_code': link.short_code,
            'is_active': link.is_active,
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, pk, format=None):
        """
        DELETE /api/links/{pk}/
        Delete a tracked link.
        """
        link = self.get_object(pk)
        if not link:
            return Response({
                'status': 'error',
                'message': 'Link not found',
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user has access to this link's campaign
        if link.campaign and link.campaign not in request.user.campaigns.all():
            return Response({
                'status': 'error',
                'message': 'You do not have access to this link',
            }, status=status.HTTP_403_FORBIDDEN)
        
        link.delete()
        
        return Response({
            'status': 'success',
            'message': 'Link deleted successfully',
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def link_redirect_view(request, short_code):
    """
    Redirect from short link to original URL and record the click.
    """
    from openoutreach.crm.models import TrackedLink, LinkClick
    from django.http import HttpResponseRedirect
    from django.utils import timezone
    
    try:
        link = TrackedLink.objects.get(short_code=short_code)
    except TrackedLink.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Link not found',
        }, status=status.HTTP_404_NOT_FOUND)
    
    if not link.is_active:
        return Response({
            'status': 'error',
            'message': 'Link is not active',
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Record the click
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    referrer = request.META.get('HTTP_REFERER', '')[:500]
    
    LinkClick.objects.create(
        link=link,
        ip_address=ip_address,
        user_agent=user_agent,
        referrer=referrer,
    )
    
    # Update link stats
    link.total_clicks += 1
    link.last_clicked_at = timezone.now()
    link.save(update_fields=['total_clicks', 'last_clicked_at'])
    
    # Redirect to original URL
    return HttpResponseRedirect(link.original_url)