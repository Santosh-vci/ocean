from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduling", "0008_scenarioconstraintevaluation_scenarioogvprojection_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="exportjob",
            name="export_type",
            field=models.CharField(
                choices=[
                    ("plan", "Plan"),
                    ("conflict", "Conflict"),
                    ("scenario_diff", "Scenario diff"),
                    ("audit", "Audit"),
                ],
                max_length=32,
            ),
        ),
    ]
