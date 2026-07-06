# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_alter_campaign_follow_up_strategy_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfig',
            name='enable_active_hours',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='active_start_hour',
            field=models.PositiveSmallIntegerField(default=9, help_text='Start hour (0-23, inclusive)'),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='active_end_hour',
            field=models.PositiveSmallIntegerField(default=19, help_text='End hour (0-23, exclusive)'),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='active_timezone',
            field=models.CharField(default='UTC', help_text='IANA timezone (e.g., America/New_York)', max_length=100),
        ),
        migrations.AddField(
            model_name='siteconfig',
            name='active_days',
            field=models.CharField(default='1,2,3,4,5', help_text='Active weekdays as comma-separated integers (1=Monday, 7=Sunday)', max_length=50),
        ),
    ]
