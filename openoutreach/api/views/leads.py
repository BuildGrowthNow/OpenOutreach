# Leads API Views

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import Http404

from openoutreach.crm.models import Lead, Deal


def _extract_lead_name(lead: Lead) -> str | None:
    """Extract lead name from contact info or public identifier."""
    if lead.contact_info and isinstance(lead.contact_info, dict):
        email = lead.contact_info.get('email')
        if email and '@' in email:
            return email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
    # Fall back to public identifier (e.g., "john-doe-12345" -> "John Doe")
    if lead.public_identifier:
        return lead.public_identifier.replace('-', ' ').replace('_', ' ').title()
    return None


def _extract_lead_info(lead: Lead) -> tuple[str | None, str | None, str | None]:
    """Extract company and title from contact info or profile data."""
    company = None
    title = None
    
    if lead.contact_info and isinstance(lead.contact_info, dict):
        # Try job_info field (from enrichment API)
        job_info = lead.contact_info.get('job_info', {})
        if isinstance(job_info, dict):
            company = job_info.get('company') or company
            title = job_info.get('title') or title
        
        # Also check generic fields
        if not company:
            company = lead.contact_info.get('company')
        if not title:
            title = lead.contact_info.get('title')
    
    # If no contact info, fall back to api_email if available
    if not company and lead.api_email:
        # Extract company name from email domain
        domain = lead.api_email.split('@')[-1] if '@' in lead.api_email else None
        if domain:
            company = domain.split('.')[0].replace('-', ' ').title()
    
    # Third return value is a fallback field for future use
    return company, title, None


class LeadListView(APIView):
    """
    API view for listing leads.
    
    GET /api/leads - List all leads (with filters & pagination)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all leads with optional filters."""
        leads = Lead.objects.all().order_by('-creation_date')
        
        # Apply filters
        status_param = request.query_params.get('status')
        search_param = request.query_params.get('search')
        disqualified_param = request.query_params.get('disqualified')
        
        if status_param:
            # Filter by deal status
            leads = leads.filter(deals__state=status_param).distinct()
        
        if search_param:
            leads = leads.filter(
                public_identifier__icontains=search_param
            ) | leads.filter(linkedin_url__icontains=search_param)
        
        if disqualified_param == 'true':
            leads = leads.filter(disqualified=True)
        elif disqualified_param == 'false':
            leads = leads.filter(disqualified=False)
        
        # Serialization: Use select_related to optimize queries
        leads = leads.select_related().prefetch_related('deals')
        total = leads.count()
        
        # Pagination
        page = request.query_params.get('page')
        limit = request.query_params.get('limit')
        
        if page and limit:
            try:
                page_num = int(page)
                limit_num = int(limit)
                start = (page_num - 1) * limit_num
                end = start + limit_num
                leads = leads[start:end]
            except (ValueError, TypeError):
                pass
        
        # Serialize leads with all required fields for frontend
        leads_data = []
        for lead in leads:
            # Get latest deal for this lead
            deal = lead.deals.order_by('-creation_date').first()
            
            # Extract name, company, title from contact info
            name = _extract_lead_name(lead)
            company, title, _ = _extract_lead_info(lead)
            
            leads_data.append({
                'id': lead.id,
                'publicIdentifier': lead.public_identifier,
                'linkedinUrl': lead.linkedin_url,
                'name': name,
                'company': company,
                'title': title,
                'state': deal.state if deal else None,
                'outcome': deal.outcome if deal else None,
                'creationDate': lead.creation_date.isoformat() if lead.creation_date else None,
                'updateDate': lead.update_date.isoformat() if lead.update_date else None,
                'contactInfo': lead.contact_info if lead.contact_info else None,
                'apiEmail': lead.api_email,
                'messagesCount': 0,  # Will be populated below
                'lastMessageAt': None,
                'disqualified': lead.disqualified,
            })
        
        return Response({
            'data': leads_data,
            'pagination': {
                'page': int(page) if page else 1,
                'limit': int(limit) if limit else len(leads_data),
                'total': total,
            }
        })
    
    def post(self, request):
        """Create a new lead."""
        linkedin_url = request.data.get('linkedinUrl')
        public_identifier = request.data.get('publicIdentifier')
        
        # Validate required fields
        if not linkedin_url:
            return Response({
                'success': False,
                'error': 'LinkedIn URL is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not public_identifier:
            return Response({
                'success': False,
                'error': 'Public identifier is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create the lead with required fields only
        lead = Lead.objects.create(
            linkedin_url=linkedin_url,
            public_identifier=public_identifier,
        )
        
        # Extract name, company, title for response
        lead_name = _extract_lead_name(lead)
        company, title, _ = _extract_lead_info(lead)
        
        # Create a default deal for this lead
        from openoutreach.crm.models import Deal
        deal = Deal.objects.create(
            lead=lead,
            campaign=None,  # Will be assigned when lead is added to a campaign
            state=Deal.State.QUALIFIED,
            outcome='',
        )
        
        return Response({
            'id': lead.id,
            'publicIdentifier': lead.public_identifier,
            'linkedinUrl': lead.linkedin_url,
            'name': lead_name,
            'company': company,
            'title': title,
            'state': deal.state,
            'outcome': deal.outcome,
            'creationDate': lead.creation_date.isoformat(),
            'updateDate': lead.update_date.isoformat(),
            'contactInfo': lead.contact_info if lead.contact_info else None,
            'apiEmail': lead.api_email,
            'disqualified': lead.disqualified,
        }, status=status.HTTP_201_CREATED)


class LeadDetailView(APIView):
    """
    API view for retrieving and updating a lead.
    
    GET /api/leads/{id} - Get lead details
    PATCH /api/leads/{id} - Update lead
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Lead.objects.get(pk=pk)
        except Lead.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """Get lead details."""
        lead = self.get_object(pk)
        
        # Get all deals for this lead
        deals = lead.deals.select_related('campaign').all()
        
        # Calculate message count and last message date
        from openoutreach.crm.models import Message
        message_count = Message.objects.filter(deal__lead=lead).count()
        last_message = Message.objects.filter(deal__lead=lead).order_by('-created_at').first()
        
        # Extract name, company, title from contact info
        name = _extract_lead_name(lead)
        company, title, _ = _extract_lead_info(lead)
        
        deals_data = []
        for deal in deals:
            deals_data.append({
                'id': deal.id,
                'campaignId': deal.campaign.id,
                'campaignName': deal.campaign.name,
                'state': deal.state,
                'outcome': deal.outcome,
                'creationDate': deal.creation_date.isoformat() if deal.creation_date else None,
                'updateDate': deal.update_date.isoformat() if deal.update_date else None,
            })
        
        return Response({
            'id': lead.id,
            'publicIdentifier': lead.public_identifier,
            'linkedinUrl': lead.linkedin_url,
            'name': name,
            'company': company,
            'title': title,
            'disqualified': lead.disqualified,
            'creationDate': lead.creation_date.isoformat() if lead.creation_date else None,
            'updateDate': lead.update_date.isoformat() if lead.update_date else None,
            'deals': deals_data,
            'contactInfo': lead.contact_info if lead.contact_info else None,
            'apiEmail': lead.api_email,
            'messagesCount': message_count,
            'lastMessageAt': last_message.created_at.isoformat() if last_message else None,
            'linkedinUrn': lead.urn,
        })
    
    def patch(self, request, pk):
        """Update lead."""
        lead = self.get_object(pk)
        
        # Get fields to update
        disqualified = request.data.get('disqualified')
        
        if disqualified is not None:
            lead.disqualified = bool(disqualified)
            lead.save(update_fields=['disqualified'])
        
        # Extract name, company, title from contact info
        name = _extract_lead_name(lead)
        company, title, _ = _extract_lead_info(lead)
        
        return Response({
            'id': lead.id,
            'publicIdentifier': lead.public_identifier,
            'linkedinUrl': lead.linkedin_url,
            'name': name,
            'company': company,
            'title': title,
            'disqualified': lead.disqualified,
            'creationDate': lead.creation_date.isoformat() if lead.creation_date else None,
            'updateDate': lead.update_date.isoformat() if lead.update_date else None,
            'contactInfo': lead.contact_info if lead.contact_info else None,
            'apiEmail': lead.api_email,
            'linkedinUrn': lead.urn,
        })


class LeadProfileView(APIView):
    """
    API view for re-scraping a lead's profile.
    
    POST /api/leads/{id}/profile - Re-scrape lead profile
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Lead.objects.get(pk=pk)
        except Lead.DoesNotExist:
            raise Http404
    
    def post(self, request, pk):
        """Re-scrape lead profile."""
        lead = self.get_object(pk)
        
        try:
            from openoutreach.linkedin.db.leads import fetch_profile
            from openoutreach.linkedin.browser.registry import SessionRegistry
            
            registry = SessionRegistry()
            session = registry.acquire_session()
            
            profile = lead.get_profile(session)
            
            if profile:
                return Response({
                    'success': True,
                    'profile': {
                        'firstName': profile.get('first_name'),
                        'lastName': profile.get('last_name'),
                        'headline': profile.get('headline'),
                        'summary': profile.get('summary'),
                        'location': profile.get('location'),
                        'experience': profile.get('experience', []),
                        'education': profile.get('education', []),
                    }
                })
            else:
                return Response({
                    'success': False,
                    'profile': None,
                    'error': 'Could not fetch profile'
                }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({
                'success': False,
                'profile': None,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LeadMessagesView(APIView):
    """
    API view for managing messages with a lead.
    
    GET /api/leads/{id}/messages - Get lead messages
    POST /api/leads/{id}/messages - Send message to lead
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Lead.objects.get(pk=pk)
        except Lead.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """Get lead messages."""
        lead = self.get_object(pk)
        
        from openoutreach.crm.models import Message
        
        messages = Message.objects.filter(
            deal__lead=lead
        ).select_related('deal').order_by('-created_at')
        
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
        
        # Serialize messages with correct field names
        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'dealId': str(msg.deal.id),
                'dealUrn': msg.deal.lead.public_identifier if msg.deal and msg.deal.lead else '',
                'content': msg.content,
                'isOutgoing': msg.is_outgoing,
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
    
    def post(self, request, pk):
        """Send message to lead."""
        lead = self.get_object(pk)
        
        content = request.data.get('content')
        is_outgoing = request.data.get('is_outgoing', True)
        
        if not content:
            return Response({
                'success': False,
                'error': 'Content is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create a deal for this lead
        deal, created = Deal.objects.get_or_create(
            lead=lead,
            campaign=lead.deals.first().campaign if lead.deals.exists() else None,
            defaults={
                'state': Deal.State.QUALIFIED,
                'outcome': '',
            }
        )
        
        # Create message
        from openoutreach.crm.models import Message
        
        message = Message.objects.create(
            deal=deal,
            content=content,
            is_outgoing=is_outgoing,
        )
        
        return Response({
            'success': True,
            'message': {
                'id': message.id,
                'dealId': str(message.deal.id),
                'dealUrn': message.deal.lead.public_identifier if message.deal and message.deal.lead else '',
                'content': message.content,
                'isOutgoing': message.is_outgoing,
                'sender': 'me' if message.is_outgoing else 'them',
                'creationDate': message.created_at.isoformat() if message.created_at else None,
                'recipientName': str(message.deal.lead) if message.deal and message.deal.lead else 'Unknown',
                'recipientUrl': message.deal.lead.linkedin_url if message.deal and message.deal.lead else '',
            }
        }, status=status.HTTP_201_CREATED)


class LeadCreateView(APIView):
    """
    API view for creating a new lead.
    
    POST /api/leads - Create a new lead
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Create a new lead."""
        linkedin_url = request.data.get('linkedinUrl')
        public_identifier = request.data.get('publicIdentifier')
        
        # Validate required fields
        if not linkedin_url:
            return Response({
                'success': False,
                'error': 'LinkedIn URL is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not public_identifier:
            return Response({
                'success': False,
                'error': 'Public identifier is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create the lead with required fields only
        lead = Lead.objects.create(
            linkedin_url=linkedin_url,
            public_identifier=public_identifier,
        )
        
        # Extract name, company, title for response
        lead_name = _extract_lead_name(lead)
        company, title, _ = _extract_lead_info(lead)
        
        # Create a default deal for this lead
        from openoutreach.crm.models import Deal
        deal = Deal.objects.create(
            lead=lead,
            campaign=None,  # Will be assigned when lead is added to a campaign
            state=Deal.State.QUALIFIED,
            outcome='',
        )
        
        return Response({
            'id': lead.id,
            'publicIdentifier': lead.public_identifier,
            'linkedinUrl': lead.linkedin_url,
            'name': lead_name,
            'company': company,
            'title': title,
            'state': deal.state,
            'outcome': deal.outcome,
            'creationDate': lead.creation_date.isoformat(),
            'updateDate': lead.update_date.isoformat(),
            'contactInfo': lead.contact_info if lead.contact_info else None,
            'apiEmail': lead.api_email,
            'disqualified': lead.disqualified,
        }, status=status.HTTP_201_CREATED)


class LeadNotesView(APIView):
    """
    API view for managing notes on a lead.
    
    GET /api/leads/{id}/notes - Get lead notes
    POST /api/leads/{id}/notes - Create a note
    PATCH /api/leads/{id}/notes/{note_id} - Update a note
    DELETE /api/leads/{id}/notes/{note_id} - Delete a note
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        try:
            return Lead.objects.get(pk=pk)
        except Lead.DoesNotExist:
            raise Http404
    
    def get(self, request, pk):
        """Get lead notes."""
        lead = self.get_object(pk)
        
        from openoutreach.crm.models import Note
        
        notes = Note.objects.filter(deal__lead=lead).select_related(
            'deal', 'created_by'
        ).order_by('-created_at')
        
        page = request.query_params.get('page')
        limit = request.query_params.get('limit')
        
        # Pagination
        total = notes.count()
        if page and limit:
            try:
                page_num = int(page)
                limit_num = int(limit)
                start = (page_num - 1) * limit_num
                end = start + limit_num
                notes = notes[start:end]
            except (ValueError, TypeError):
                pass
        
        # Serialize notes with camelCase field names for frontend compatibility
        notes_data = []
        for note in notes:
            notes_data.append({
                'id': note.id,
                'content': note.content,
                'createdBy': note.created_by.username if note.created_by else None,
                'createdAt': note.created_at.isoformat() if note.created_at else None,
                'updatedAt': note.updated_at.isoformat() if note.updated_at else None,
            })
        
        return Response({
            'data': notes_data,
            'pagination': {
                'page': int(page) if page else 1,
                'limit': int(limit) if limit else len(notes_data),
                'total': total,
            }
        })
    
    def post(self, request, pk):
        """Create a note for lead."""
        lead = self.get_object(pk)
        content = request.data.get('content')
        
        if not content:
            return Response({
                'success': False,
                'error': 'Content is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create a deal for this lead
        deal, created = Deal.objects.get_or_create(
            lead=lead,
            campaign=lead.deals.first().campaign if lead.deals.exists() else None,
            defaults={
                'state': Deal.State.QUALIFIED,
                'outcome': '',
            }
        )
        
        from openoutreach.crm.models import Note
        
        note = Note.objects.create(
            deal=deal,
            content=content,
            created_by=request.user,
        )
        
        return Response({
            'id': note.id,
            'content': note.content,
            'createdBy': note.created_by.username if note.created_by else None,
            'createdAt': note.created_at.isoformat() if note.created_at else None,
            'updatedAt': note.updated_at.isoformat() if note.updated_at else None,
        }, status=status.HTTP_201_CREATED)
    
    def patch(self, request, pk, note_id):
        """Update a note."""
        lead = self.get_object(pk)
        
        from openoutreach.crm.models import Note
        
        try:
            note = Note.objects.get(id=note_id, deal__lead=lead)
        except Note.DoesNotExist:
            raise Http404
        
        content = request.data.get('content')
        
        if content is not None:
            note.content = content
            note.save(update_fields=['content'])
        
        return Response({
            'id': note.id,
            'content': note.content,
            'createdBy': note.created_by.username if note.created_by else None,
            'createdAt': note.created_at.isoformat() if note.created_at else None,
            'updatedAt': note.updated_at.isoformat() if note.updated_at else None,
        })
    
    def delete(self, request, pk, note_id):
        """Delete a note."""
        lead = self.get_object(pk)
        
        from openoutreach.crm.models import Note
        
        try:
            note = Note.objects.get(id=note_id, deal__lead=lead)
        except Note.DoesNotExist:
            raise Http404
        
        note.delete()
        return Response({'success': True})