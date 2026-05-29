import apps.scheduling.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scheduling", "0012_rootcauserepairassessment"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublishabilityAssessment",
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
                    "assessment_id",
                    models.CharField(
                        default=apps.scheduling.models.publishability_assessment_reference,
                        max_length=96,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("publishable", "Publishable"),
                            ("warning", "Warning"),
                            ("blocked", "Blocked"),
                        ],
                        default="blocked",
                        max_length=32,
                    ),
                ),
                ("blocking_reason_count", models.PositiveIntegerField(default=0)),
                ("warning_count", models.PositiveIntegerField(default=0)),
                ("approval_status", models.CharField(blank=True, max_length=40)),
                ("conflict_status", models.CharField(blank=True, max_length=40)),
                ("telemetry_status", models.CharField(blank=True, max_length=40)),
                ("cargo_sequence_status", models.CharField(blank=True, max_length=40)),
                ("operating_window_status", models.CharField(blank=True, max_length=40)),
                ("recommendation_origin_status", models.CharField(blank=True, max_length=40)),
                ("checked_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("algorithm_version", models.CharField(max_length=96)),
                ("details", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "checked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="checked_publishability_assessments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "plan_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="publishability_assessments",
                        to="scheduling.planversion",
                    ),
                ),
            ],
            options={
                "ordering": ["-checked_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="publishabilityassessment",
            index=models.Index(
                fields=["plan_version", "status", "checked_at"],
                name="scheduling__plan_ve_7a398b_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="publishabilityassessment",
            index=models.Index(
                fields=["status", "checked_at"],
                name="scheduling__status_76d006_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="publishabilityassessment",
            index=models.Index(
                fields=["checked_at"],
                name="scheduling__checked_8c37b5_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="publishabilityassessment",
            index=models.Index(
                fields=["approval_status", "conflict_status"],
                name="scheduling__approva_115443_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="publishabilityassessment",
            index=models.Index(
                fields=["recommendation_origin_status", "telemetry_status"],
                name="scheduling__recomme_e1525c_idx",
            ),
        ),
    ]
