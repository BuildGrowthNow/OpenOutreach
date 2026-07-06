# Generated manually to fix credential status defaults

from django.db import migrations


def fix_credential_statuses(apps, schema_editor):
    """Update existing credentials with 'active' status to 'stored' if never verified."""
    LinkedInCredentials = apps.get_model('crm', 'LinkedInCredentials')

    # Fix credentials that are marked active but have never been verified
    LinkedInCredentials.objects.filter(
        status='active',
        last_verified__isnull=True
    ).update(status='stored')


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0020_alter_deal_lead'),
    ]

    operations = [
        migrations.RunPython(fix_credential_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='linkedincredentials',
            name='status',
            field=migrations.CharField(
                choices=[
                    ('stored', 'Stored - not yet verified'),
                    ('tested', 'Tested - login attempted'),
                    ('active', 'Active - verified and working'),
                    ('invalid', 'Invalid - verification failed'),
                    ('expired', 'Expired - needs rotation'),
                    ('locked', 'Locked - checkpoint/challenge detected'),
                    ('backup', 'Backup credential')
                ],
                default='stored',
                help_text='Credential status and validity',
                max_length=20
            ),
        ),
    ]
