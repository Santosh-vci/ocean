from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0009_alter_exportjob_export_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="simulationscenario",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="simulationscenario",
            name="source_kind",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("conflict", "Conflict"),
                    ("override", "Override"),
                    ("tracking_alert", "Tracking alert"),
                ],
                default="manual",
                max_length=32,
            ),
        ),
    ]
