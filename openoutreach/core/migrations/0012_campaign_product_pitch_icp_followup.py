from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_siteconfig_ai_prompt_guardrails"),
    ]

    operations = [
        # Rename product_docs -> product_pitch on Campaign
        migrations.RenameField(
            model_name="campaign",
            old_name="product_docs",
            new_name="product_pitch",
        ),
        # Add new fields to Campaign
        migrations.AddField(
            model_name="campaign",
            name="icp_titles",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="campaign",
            name="follow_up_strategy",
            field=models.TextField(blank=True, default=""),
        ),
        # Add new fields to CampaignTemplate
        migrations.AddField(
            model_name="campaigntemplate",
            name="product_pitch",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="campaigntemplate",
            name="booking_link",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="campaigntemplate",
            name="icp_titles",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="campaigntemplate",
            name="follow_up_strategy",
            field=models.TextField(blank=True, default=""),
        ),
    ]
