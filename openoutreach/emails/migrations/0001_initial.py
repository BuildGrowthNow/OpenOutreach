# Generated manually
# This migration marks emails.Mailbox as properly migrated.
# The table was created before migrations were added to the emails app.

from django.db import migrations, models
import openoutreach.emails.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    # Mark this as a no-op migration since the table already exists in production.
    # Django will apply this and update django_migrations, fixing the dependency order.
    run_before = [
        ('crm', '0018_deal_email_sent_at_deal_mailbox'),
    ]

    operations = [
        migrations.CreateModel(
            name='Mailbox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host', models.CharField(default='smtp.gmail.com', max_length=255)),
                ('port', models.PositiveIntegerField(default=587)),
                ('username', models.CharField(max_length=320, unique=True)),
                ('password', models.CharField(max_length=255)),
                ('from_address', models.EmailField(max_length=320)),
                ('daily_limit', models.PositiveIntegerField(default=50)),
            ],
            options={
                'verbose_name_plural': 'Mailboxes',
            },
            managers=[
                ('objects', openoutreach.emails.models.MailboxManager()),
            ],
        ),
    ]
