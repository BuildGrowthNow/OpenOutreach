# openoutreach/api/views/linkedin_profiles.py
"""LinkedIn Profiles API Views."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from openoutreach.linkedin.models import LinkedInProfile


class LinkedInProfilesListView(APIView):
    """
    API view for listing LinkedIn profiles available to the current user.
    
    GET /api/linkedin-profiles - Get all LinkedIn profiles for the authenticated user
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get LinkedIn profiles accessible by the current user."""
        # Get profiles based on user's campaign or user's own profile
        profiles = LinkedInProfile.objects.all()
        
        # Filter by user's own profile if user has one
        if hasattr(request.user, 'linkedin_profile'):
            profiles = profiles.filter(user=request.user)
        
        return Response({
            'profiles': [
                {
                    'id': profile.pk,
                    'linkedin_username': profile.linkedin_username,
                    'active': profile.active,
                    'connect_daily_limit': profile.connect_daily_limit,
                    'follow_up_daily_limit': profile.follow_up_daily_limit,
                }
                for profile in profiles
            ],
            'count': profiles.count(),
        })