import apps.scheduling.models
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0011_recoveryinputsnapshot_optimizerrun_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RootCauseRepairAssessment",
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
                        default=apps.scheduling.models.root_cause_assessment_reference,
                        max_length=96,
                        unique=True,
                    ),
                ),
                ("source_kind", models.CharField(blank=True, max_length=40)),
                ("source_ref", models.CharField(blank=True, max_length=120)),
                ("source_cause_type", models.CharField(blank=True, max_length=80)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("addresses_cause", "Addresses cause"),
                            ("mitigates_cause", "Mitigates cause"),
                            ("does_not_address_cause", "Does not address cause"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        max_length=40,
                    ),
                ),
                ("required_resolution", models.JSONField(blank=True, default=dict)),
                ("observed_resolution", models.JSONField(blank=True, default=dict)),
                ("residual_risk", models.JSONField(blank=True, default=dict)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("assessed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("assessed_by_algorithm_version", models.CharField(max_length=96)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "recommendation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="root_cause_assessment",
                        to="scheduling.recoveryrecommendation",
                    ),
                ),
            ],
            options={
                "ordering": ["-assessed_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="rootcauserepairassessment",
            index=models.Index(
                fields=["source_cause_type", "status"],
                name="scheduling__source__ead94c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="rootcauserepairassessment",
            index=models.Index(
                fields=["status", "assessed_at"],
                name="scheduling__status_16cbff_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="rootcauserepairassessment",
            index=models.Index(
                fields=["assessed_at"],
                name="scheduling__assesse_6c609e_idx",
            ),
        ),
    ]
