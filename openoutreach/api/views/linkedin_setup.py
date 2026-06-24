# openoutreach/api/views/linkedin_setup.py
"""LinkedIn OAuth and Cookie Setup API Views."""
from django.http import HttpRequest, JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated


class LinkedInCookieInstructionsView(APIView):
    """
    API view for LinkedIn cookie setup instructions.
    
    GET /api/linkedin-setup/cookie-instructions - Get instructions for extracting LinkedIn session cookies
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get instructions for extracting LinkedIn session cookies."""
        return Response({
            'success': True,
            'instructions': {
                'title': 'How to Get LinkedIn Session Cookies',
                'steps': [
                    {
                        'step': 1,
                        'title': 'Open LinkedIn in Your Browser',
                        'description': 'Navigate to https://www.linkedin.com and log in to your account.',
                        'note': 'Make sure you are using the correct LinkedIn account for your outreach campaigns.'
                    },
                    {
                        'step': 2,
                        'title': 'Open Developer Tools',
                        'description': 'Press F12 or right-click on the page and select "Inspect" to open developer tools.',
                        'note': 'Then go to the "Application" tab (Chrome/Edge) or "Storage" tab (Firefox).'
                    },
                    {
                        'step': 3,
                        'title': 'Find LinkedIn Cookies',
                        'description': 'In the left sidebar, expand "Cookies" and click on "https://www.linkedin.com".',
                        'note': 'Look for the following cookies: bcookie, lidc, JSESSIONID, sessid'
                    },
                    {
                        'step': 4,
                        'title': 'Copy Cookie Values',
                        'description': 'Click on each cookie and copy its value. You will need these for LinkedIn setup.',
                        'note': 'Keep your cookies secure and never share them with anyone.'
                    }
                ],
                'alternative_method': {
                    'title': 'Alternative: Using Browser Extensions',
                    'description': 'You can use browser extensions like "EditThisCookie" or "Cookie-Editor" to easily extract and manage cookies.',
                    'steps': [
                        'Install a cookie editor extension from your browser\'s web store',
                        'Navigate to LinkedIn and log in',
                        'Open the extension and export all LinkedIn cookies',
                        'Copy the cookie values to your clipboard'
                    ]
                },
                'security_note': 'LinkedIn session cookies are sensitive credentials. Keep them secure and never share them. The system stores them encrypted at rest using AES-256 encryption.',
                'verification': {
                    'title': 'Verifying Your Cookies',
                    'description': 'After entering your cookies, the system will automatically verify them by attempting a LinkedIn login.',
                    'success': 'If cookies are valid, the system will confirm your LinkedIn profile and make it available for campaign use.'
                }
            }
        })


class LinkedInSetupGuideView(APIView):
    """
    API view for comprehensive LinkedIn setup guide.
    
    GET /api/linkedin-setup/guide - Get the complete setup guide
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get the complete LinkedIn setup guide."""
        return Response({
            'success': True,
            'guide': {
                'introduction': {
                    'title': 'LinkedIn Setup Guide',
                    'description': 'This guide will help you set up LinkedIn for your outreach campaigns.'
                },
                'methods': [
                    {
                        'method': 'password',
                        'title': 'Method 1: Username & Password',
                        'description': 'Enter your LinkedIn email and password directly.',
                        'steps': [
                            'Click "Add Credential" below',
                            'Enter your LinkedIn email address',
                            'Enter your LinkedIn password',
                            'Click "Add Credentials"'
                        ],
                        ' pros': [
                            'Simple and straightforward',
                            'No technical knowledge required'
                        ],
                        'cons': [
                            'Password stored in encrypted format',
                            'May require 2FA for some accounts'
                        ]
                    },
                    {
                        'method': 'cookies',
                        'title': 'Method 2: Session Cookies',
                        'description': 'Extract and use your LinkedIn session cookies for authentication.',
                        'steps': [
                            'Click on "How to Get Cookies" below for detailed instructions',
                            'Open LinkedIn in your browser and log in',
                            'Open Developer Tools (F12) and go to the Application tab',
                            'Expand "Cookies" and find LinkedIn cookies',
                            'Copy the values and enter them in the system'
                        ],
                        'pros': [
                            'More secure (no password stored)',
                            'Works with 2FA-enabled accounts',
                            'Session can be managed externally'
                        ],
                        'cons': [
                            'Requires technical knowledge',
                            'Cookies may expire and need renewal'
                        ]
                    }
                ],
                'prerequisites': {
                    'title': 'Prerequisites',
                    'items': [
                        'A LinkedIn account (create one at https://www.linkedin.com)',
                        'A LinkedIn profile with a photo and headline',
                        'Access to your browser\'s developer tools',
                        'A campaign already created in this system'
                    ]
                },
                'security': {
                    'title': 'Security Best Practices',
                    'items': [
                        'Use a dedicated LinkedIn account for outreach campaigns',
                        'Never share your password or cookies with anyone',
                        'Enable 2FA on your LinkedIn account',
                        'Regularly rotate your credentials',
                        'Monitor your account for suspicious activity'
                    ]
                },
                'troubleshooting': {
                    'title': 'Common Issues',
                    'items': [
                        {
                            'issue': 'Account requiring 2FA',
                            'solution': 'Use cookie-based authentication instead of password'
                        },
                        {
                            'issue': 'Cookies not working',
                            'solution': 'Make sure all LinkedIn cookies are copied correctly, including bcookie, lidc, JSESSIONID, and sessid'
                        },
                        {
                            'issue': 'Verification failing',
                            'solution': 'Check that your LinkedIn account is not in a checkpoint state. Try logging in manually first.'
                        }
                    ]
                },
                'next_steps': {
                    'title': 'After Setupcomplete',
                    'items': [
                        'Create a LinkedIn profile in the system',
                        'Add your credentials to the profile',
                        'Start your first outreach campaign',
                        'Monitor your credentials\' health in the Settings section'
                    ]
                }
            }
        })


class LinkedInSetupStatusView(APIView):
    """
    API view for checking LinkedIn setup status.
    
    GET /api/linkedin-setup/status - Get current setup status
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get the current LinkedIn setup status."""
        from openoutreach.linkedin.models import LinkedInProfile
        from openoutreach.crm.models import LinkedInCredentials
        
        # Count profiles and credentials
        profile_count = LinkedInProfile.objects.filter(user=request.user).count()
        credential_count = LinkedInCredentials.objects.filter(
            linkedin_profile__user=request.user
        ).count()
        
        # Check for any active credentials
        has_active_credentials = LinkedInCredentials.objects.filter(
            linkedin_profile__user=request.user,
            status=LinkedInCredentials.STATUS_ACTIVE
        ).exists()
        
        return Response({
            'success': True,
            'status': {
                'linkedin_profile': {
                    'exists': profile_count > 0,
                    'count': profile_count,
                    'requires_attention': profile_count == 0
                },
                'linkedin_credentials': {
                    'exists': credential_count > 0,
                    'count': credential_count,
                    'active_count': credential_count if has_active_credentials else 0,
                    'requires_attention': credential_count == 0
                },
                'setup_complete': credential_count > 0 and has_active_credentials,
                'setup_progress': {
                    'current': 2 if credential_count > 0 else 1,
                    'total': 2
                }
            }
        })