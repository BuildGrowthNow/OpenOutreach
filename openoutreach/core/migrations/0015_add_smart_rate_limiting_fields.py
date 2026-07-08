# Generated manually for smart rate limiting feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_add_active_hours_config'),
    ]

    operations = [
        # Add smart rate limiting fields to SiteConfig
        migrations.AddField(
            model_name='siteconfig',
            name='enable_smart_rate_limiting',
            field=models.BooleanField(
                default=False,
                help_text='Enable context-aware rate limiting (time-of-day, detectability, engagement patterns)'
            ),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='aggressiveness_preset',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('very_slow', 'Very Slow (Safest)'),
                    ('slow', 'Slow'),
                    ('average', 'Average'),
                    ('aggressive', 'Aggressive'),
                    ('very_aggressive', 'Very Aggressive (Riskiest)'),
                ],
                default='average',
                help_text='Smart rate limiting aggressiveness level (only used when Smart Rate Limiting is ON)'
            ),
        ),

        # Remove deprecated fields from Campaign and CampaignTemplate
        migrations.RemoveField(
            model_name='campaign',
            name='velocity',
        ),
        migrations.RemoveField(
            model_name='campaign',
            name='cooldown_minutes',
        ),
        migrations.RemoveField(
            model_name='campaigntemplate',
            name='velocity',
        ),
        migrations.RemoveField(
            model_name='campaigntemplate',
            name='cooldown_minutes',
        ),
    ]
