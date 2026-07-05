from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_campaigntemplate_delete_customuser"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfig",
            name="ai_avoid_rules",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="siteconfig",
            name="ai_say_rules",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="siteconfig",
            name="ai_writing_style",
            field=models.TextField(blank=True, default=""),
        ),
    ]
