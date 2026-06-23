# Links API Views

from datetime import timedelta

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import Http404
from django.utils import timezone

from openoutreach.crm.models import TrackedLink, LinkClick


class LinksView(APIView):
    """
    API view for managing tracked links.
    
    GET /api/links - List tracked links
    POST /api/links - Create tracking link
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List tracked links with filtering."""
        # Query tracked links from database
        links = TrackedLink.objects.all().order_by('-created_at')
        
        # Apply filters
        campaign_id = request.query_params.get('campaign_id')
        if campaign_id:
            links = links.filter(campaign_id=campaign_id)
        
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            links = links.filter(is_active=is_active.lower() == 'true')
        
        # Pagination
        page = request.query_params.get('page')
        limit = request.query_params.get('limit')
        total = links.count()
        
        if page and limit:
            try:
                page_num = int(page)
                limit_num = int(limit)
                start = (page_num - 1) * limit_num
                end = start + limit_num
                links = links[start:end]
            except (ValueError, TypeError):
                pass
        
        # Serialize links
        links_data = []
        for link in links:
            links_data.append({
                'id': link.id,
                'campaign_id': link.campaign.id if link.campaign else None,
                'campaign_name': link.campaign.name if link.campaign else 'General',
                'original_url': link.original_url,
                'tracked_url': link.get_short_url(request),
                'tracked_url_code': f"https://yourdomain.com/l/{link.short_code}",
                'clicks': link.total_clicks,
                'unique_clicks': link.clicks.all().distinct().count() if hasattr(link.clicks, 'all') else link.total_clicks,
                'conversion_rate': link.conversion_rate,
                'created_at': link.created_at.isoformat(),
                'is_active': link.is_active,
                'utm_source': link.utm_source,
                'utm_medium': link.utm_medium,
                'utm_campaign': link.utm_campaign,
            })
        
        return Response({
            'data': links_data,
            'pagination': {
                'page': int(page) if page else 1,
                'limit': int(limit) if limit else len(links_data),
                'total': total,
            }
        })
    
    def post(self, request):
        """Create a new tracked link."""
        original_url = request.data.get('original_url')
        campaign_id = request.data.get('campaign_id')
        short_code = request.data.get('short_code')
        utm_source = request.data.get('utm_source', '')
        utm_medium = request.data.get('utm_medium', '')
        utm_campaign = request.data.get('utm_campaign', '')
        
        if not original_url:
            return Response({
                'success': False,
                'error': 'original_url is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate short code if not provided
        import random
        import string
        if not short_code:
            short_code = ''.join(
                random.choices(string.ascii_lowercase + string.digits, k=8)
            )
        
        # Check if short code exists
        if TrackedLink.objects.filter(short_code=short_code).exists():
            return Response({
                'success': False,
                'error': 'short_code already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create the tracked link
        link = TrackedLink.objects.create(
            original_url=original_url,
            short_code=short_code,
            campaign_id=campaign_id,
            utm_source=utm_source[:100],
            utm_medium=utm_medium[:100],
            utm_campaign=utm_campaign[:100],
        )
        
        return Response({
            'id': link.id,
            'original_url': link.original_url,
            'tracked_url': link.get_short_url(request),
            'tracked_url_code': f"https://yourdomain.com/l/{link.short_code}",
            'short_code': link.short_code,
            'campaign_id': link.campaign.id if link.campaign else None,
            'is_active': link.is_active,
            'created_at': link.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class LinkDetailView(APIView):
    """
    API view for link details and breakdown.
    
    GET /api/links/{id} - Get link details
    PATCH /api/links/{id} - Update link
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return TrackedLink.objects.get(pk=pk)
        except TrackedLink.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """Get link details with breakdown."""
        link = self.get_object(pk)
        
        # Calculate breakdown from clicks - already imported at top
        
        # Device breakdown
        device_breakdown = {}
        for click in link.clicks.all():
            device = click.device_type or 'unknown'
            device_breakdown[device] = device_breakdown.get(device, 0) + 1
        
        # Country breakdown (placeholder - would need geoip service in production)
        country_breakdown = {}
        
        # Source breakdown
        source_breakdown = {}
        
        # Daily breakdown (last 7 days)
        daily_breakdown = []
        for i in range(7):
            day_start = timezone.now() - timedelta(days=6-i)
            day_end = day_start + timedelta(days=1)
            
            day_clicks = link.clicks.filter(
                clicked_at__gte=day_start,
                clicked_at__lt=day_end
            ).count()
            
            daily_breakdown.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'clicks': day_clicks,
            })
        
        # Hourly breakdown
        hourly_breakdown = []
        for hour in range(24):
            hourly_clicks = link.clicks.filter(
                clicked_at__hour=hour
            ).count()
            
            hourly_breakdown.append({
                'hour': hour,
                'clicks': hourly_clicks,
            })
        
        return Response({
            'id': link.id,
            'campaign_id': link.campaign.id if link.campaign else None,
            'campaign_name': link.campaign.name if link.campaign else 'General',
            'original_url': link.original_url,
            'tracked_url': link.get_short_url(request),
            'tracked_url_code': f"https://yourdomain.com/l/{link.short_code}",
            'clicks': link.total_clicks,
            'unique_clicks': link.clicks.all().distinct().count() if hasattr(link.clicks, 'all') else link.total_clicks,
            'conversion_rate': link.conversion_rate,
            'created_at': link.created_at.isoformat(),
            'is_active': link.is_active,
            'breakdown': {
                'by_device': device_breakdown,
                'by_country': country_breakdown,
                'by_source': source_breakdown,
                'daily': daily_breakdown,
                'hourly': hourly_breakdown,
            },
            'utm_parameters': {
                'source': link.utm_source,
                'medium': link.utm_medium,
                'campaign': link.utm_campaign,
                'term': link.utm_term,
                'content': link.utm_content,
            },
        })
