from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from openoutreach.mongodb.models import UserProfile
import json
from datetime import datetime

class Command(BaseCommand):
    help = 'Test complete MongoDB profile functionality'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Get or create a test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(self.style.SUCCESS('Created test user: testuser'))
        else:
            self.stdout.write(self.style.SUCCESS('Using existing test user: testuser'))
        
        # Test creating/updating a profile using the correct UserProfile model structure
        profile_data = {
            'user_id': str(user.pk),  # Use pk instead of id
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'company': 'Test Company',
            'position': 'Test Position',
            'timezone': 'UTC',
            # Added missing fields with correct types
            'notification_preferences': {
                'email_notifications': True,
                'sms_notifications': False,
                'push_notifications': True,
                'marketing_emails': False
            },
            'ui_preferences': {
                'theme': 'light',
                'language': 'en',
                'sidebar_collapsed': False
            },
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Create and save profile to MongoDB
        profile = UserProfile(**profile_data)
        profile.save()
        
        self.stdout.write(self.style.SUCCESS(f'Created/Updated profile: {profile.first_name} {profile.last_name}'))
        
        # Retrieve and display the profile
        retrieved_profile = UserProfile.get(str(user.pk))  # Use pk instead of id
        if retrieved_profile:
            self.stdout.write(self.style.SUCCESS('Retrieved profile data:'))
            self.stdout.write(json.dumps(retrieved_profile.to_dict(), indent=2, default=str))
        else:
            self.stdout.write(self.style.ERROR('Failed to retrieve profile'))
        
        self.stdout.write(self.style.SUCCESS('MongoDB profile test completed successfully!'))
