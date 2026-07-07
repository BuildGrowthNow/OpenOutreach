# Generated manually to add DISCOVERED state

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0021_fix_credential_default_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deal',
            name='state',
            field=models.CharField(
                choices=[
                    ('Discovered', 'Discovered'),
                    ('Qualified', 'Qualified'),
                    ('Ready to Connect', 'Ready To Connect'),
                    ('Pending', 'Pending'),
                    ('Connected', 'Connected'),
                    ('Completed', 'Completed'),
                    ('Failed', 'Failed'),
                    ('No Email', 'No Email'),
                ],
                default='Discovered',
                max_length=20,
            ),
        ),
    ]
