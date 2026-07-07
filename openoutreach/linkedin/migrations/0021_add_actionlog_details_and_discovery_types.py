# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('linkedin', '0020_add_campaign_status_action_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='actionlog',
            name='details',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='actionlog',
            name='action_type',
            field=models.CharField(
                choices=[
                    ('connect', 'Connect'),
                    ('check_pending', 'Check Pending'),
                    ('follow_up', 'Follow Up'),
                    ('send_manual_message', 'Send Manual Message'),
                    ('campaign_paused', 'Campaign Paused'),
                    ('campaign_started', 'Campaign Started'),
                    ('lead_discovered', 'Lead Discovered'),
                    ('lead_qualified', 'Lead Qualified'),
                    ('lead_disqualified', 'Lead Disqualified'),
                ],
                max_length=20,
            ),
        ),
    ]
