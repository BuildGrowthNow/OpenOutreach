from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0022_add_discovered_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='cached_profile',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
