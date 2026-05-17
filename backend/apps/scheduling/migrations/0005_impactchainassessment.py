from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0004_approvalrequest_scheduling__plan_ve_5d9e3f_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImpactChainAssessment",
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
                ("assessment_id", models.CharField(max_length=96, unique=True)),
                (
                    "source_kind",
                    models.CharField(
                        choices=[
                            ("override", "Override"),
                            ("conflict", "Conflict"),
                            ("planning_forecast", "Planning forecast"),
                            ("simulation", "Simulation"),
                        ],
                        default="override",
                        max_length=40,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ok", "OK"),
                            ("warning", "Warning"),
                            ("critical", "Critical"),
                        ],
                        default="ok",
                        max_length=32,
                    ),
                ),
                ("delay_minutes", models.IntegerField(default=0)),
                ("nodes", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assignment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="impact_chain_assessments",
                        to="scheduling.assignment",
                    ),
                ),
                (
                    "override_request",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="impact_assessment",
                        to="scheduling.overriderequest",
                    ),
                ),
                (
                    "plan_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="impact_chain_assessments",
                        to="scheduling.planversion",
                    ),
                ),
                (
                    "trip",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="impact_chain_assessments",
                        to="scheduling.trip",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="impactchainassessment",
            index=models.Index(
                fields=["plan_version", "source_kind", "status"],
                name="scheduling__plan_ve_78ab56_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="impactchainassessment",
            index=models.Index(
                fields=["trip", "source_kind", "status"],
                name="scheduling__trip_id_750f6f_idx",
            ),
        ),
    ]
