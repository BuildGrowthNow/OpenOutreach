# Messages API Views

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from openoutreach.crm.models import Message


class MessagesView(APIView):
    """
    API view for managing messages.
    
    GET /api/messages - List messages with filters
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request) -> Response:
        """List messages with optional filters."""
        # Get query parameters
        campaign_id = request.query_params.get('campaign_id')
        deal_id = request.query_params.get('deal_id')
        page = request.query_params.get('page')
        limit = request.query_params.get('limit')
        
        # Query Message model with filters
        messages = Message.objects.select_related('deal__lead', 'deal__campaign').all()
        
        # Filter by campaign or deal if provided
        if campaign_id:
            try:
                messages = messages.filter(deal__campaign_id=int(campaign_id))
            except ValueError:
                pass
        
        if deal_id:
            try:
                messages = messages.filter(deal_id=int(deal_id))
            except ValueError:
                pass
        
        # Apply ordering for stable message order (oldest first)
        messages = messages.order_by('created_at')
        
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
                'deal_id': str(msg.deal_id),
                'deal_urn': msg.deal.lead.public_identifier if msg.deal and msg.deal.lead else '',
                'content': msg.content,
                'is_outgoing': msg.is_outgoing,
                'sender': 'me' if msg.is_outgoing else 'them',
                'creationDate': msg.created_at.isoformat() if msg.created_at else None,
                'recipientName': str(msg.deal.lead) if msg.deal and msg.deal.lead else 'Unknown',
                'recipientUrl': msg.deal.lead.linkedin_url if msg.deal and msg.deal.lead else '',
            })
        
        return Response({
            'data': messages_data,
            'pagination': {
                'page': int(page) if page else 1,
                'limit': int(limit) if limit else len(messages_data),
                'total': total,
            }
        })


class MessagesDetailView(APIView):
    """
    API view for individual message details.
    
    GET /api/messages/{id} - Get message details
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk: str | int) -> Response:
        """Get message details."""
        try:
            message = Message.objects.select_related('deal__lead', 'deal__campaign').get(pk=pk)
        except Message.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'id': message.id,
            'deal_id': str(message.deal_id),
            'deal_urn': message.deal.lead.public_identifier if message.deal and message.deal.lead else '',
            'content': message.content,
            'is_outgoing': message.is_outgoing,
            'sender': 'me' if message.is_outgoing else 'them',
            'creationDate': message.created_at.isoformat() if message.created_at else None,
            'recipientName': str(message.deal.lead) if message.deal and message.deal.lead else 'Unknown',
            'recipientUrl': message.deal.lead.linkedin_url if message.deal and message.deal.lead else '',
        })