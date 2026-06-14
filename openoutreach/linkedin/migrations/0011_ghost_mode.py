# openoutreach/linkedin/migrations/0011_ghost_mode.py
"""Create Ghost Mode campaign models for safe testing without sending real actions."""
from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("linkedin", "0010_move_engine_models_to_core"),
    ]

    operations = [
        # GhostCampaign model
        migrations.CreateModel(
            name="GhostCampaign",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                (
                    "is_active",
                    models.BooleanField(default=True),
                ),
                (
                    "mode_type",
                    models.CharField(
                        choices=[
                            ("simulation", "Simulation only"),
                            ("validation", "Validation with warnings"),
                            ("dry_run", "Dry run with all checks"),
                        ],
                        default="simulation",
                        max_length=20,
                    ),
                ),
                ("test_seed_leads", models.TextField(blank=True, help_text="Comma-separated LinkedIn URLs to test")),
                ("test_keywords", models.TextField(blank=True, help_text="Keywords to search for")),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField(blank=True, null=True)),
                ("leads_processed", models.PositiveIntegerField(default=0)),
                ("connections_simulated", models.PositiveIntegerField(default=0)),
                ("messages_simulated", models.PositiveIntegerField(default=0)),
                ("conversions_simulated", models.PositiveIntegerField(default=0)),
                ("avg_rating", models.FloatField(default=0.0)),
                ("avg_score", models.FloatField(default=0.0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ghost_campaigns",
                        to="core.campaign",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name_plural": "Ghost campaigns",
            },
        ),
        # GhostSimulationLog model
        migrations.CreateModel(
            name="GhostSimulationLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("search", "Search for leads"),
                            ("qualify", "Qualify lead"),
                            ("connect", "Send connection"),
                            ("message", "Send message"),
                            ("follow_up", "Follow up message"),
                            ("conversion", "Conversion tracked"),
                        ],
                        max_length=20,
                    ),
                ),
                ("target_url", models.URLField(blank=True)),
                ("target_name", models.CharField(max_length=100, blank=True)),
                ("result_data", models.JSONField(default=dict)),
                ("rating", models.FloatField(blank=True, null=True)),
                ("score", models.FloatField(blank=True, null=True)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField()),
                ("simulated_action", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "ghost_campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="linkedin.ghostcampaign",
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        # GhostTestScenario model
        migrations.CreateModel(
            name="GhostTestScenario",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("test_cases", models.JSONField(default=dict)),
                ("is_public", models.BooleanField(default=False)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="auth.user",
                    ),
                ),
                ("runs_count", models.PositiveIntegerField(default=0)),
                ("avg_success_rate", models.FloatField(default=0.0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]