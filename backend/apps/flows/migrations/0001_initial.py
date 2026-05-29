import django.db.models.deletion

from django.conf import settings
from django.db import migrations, models

import apps.flows.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FlowDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("flow_key", models.CharField(max_length=120, unique=True)),
                ("name", models.CharField(max_length=180)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("version", models.PositiveIntegerField(default=1)),
                ("status", models.CharField(choices=[("active", "Active"), ("deprecated", "Deprecated")], default="active", max_length=32)),
                ("entry_route", models.CharField(max_length=180)),
                ("steps", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["flow_key", "version"],
            },
        ),
        migrations.CreateModel(
            name="FlowRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_id", models.CharField(default=apps.flows.models.flow_run_reference, max_length=96, unique=True)),
                ("status", models.CharField(choices=[("not_started", "Not started"), ("active", "Active"), ("blocked", "Blocked"), ("completed", "Completed"), ("canceled", "Canceled")], default="not_started", max_length=32)),
                ("current_step_key", models.CharField(blank=True, max_length=120)),
                ("subject_type", models.CharField(blank=True, max_length=80)),
                ("subject_id", models.CharField(blank=True, max_length=80)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("flow_definition", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="runs", to="flows.flowdefinition")),
                ("started_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="started_flow_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="FlowStepRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("step_key", models.CharField(max_length=120)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("active", "Active"), ("blocked", "Blocked"), ("completed", "Completed"), ("skipped", "Skipped")], default="pending", max_length=32)),
                ("expected_route", models.CharField(max_length=180)),
                ("expected_action_id", models.CharField(max_length=120)),
                ("blocked_reason", models.CharField(blank=True, max_length=255)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("flow_run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="step_runs", to="flows.flowrun")),
            ],
            options={
                "ordering": ["flow_run", "sequence"],
            },
        ),
        migrations.CreateModel(
            name="FlowEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(default=apps.flows.models.flow_event_reference, max_length=96, unique=True)),
                ("step_key", models.CharField(blank=True, max_length=120)),
                ("event_type", models.CharField(choices=[("started", "Started"), ("resumed", "Resumed"), ("cta_intent", "CTA intent"), ("domain_completed", "Domain completed"), ("blocked", "Blocked"), ("unblocked", "Unblocked"), ("completed", "Completed"), ("canceled", "Canceled")], max_length=32)),
                ("route", models.CharField(blank=True, max_length=180)),
                ("action_id", models.CharField(blank=True, max_length=120)),
                ("object_type", models.CharField(blank=True, max_length=80)),
                ("object_id", models.CharField(blank=True, max_length=80)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="flow_events", to=settings.AUTH_USER_MODEL)),
                ("flow_run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="flows.flowrun")),
                ("step_run", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="flows.flowsteprun")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="flowdefinition",
            index=models.Index(fields=["flow_key", "status"], name="flows_flowd_flow_ke_bfc498_idx"),
        ),
        migrations.AddIndex(
            model_name="flowdefinition",
            index=models.Index(fields=["status", "updated_at"], name="flows_flowd_status_a77fd5_idx"),
        ),
        migrations.AddIndex(
            model_name="flowrun",
            index=models.Index(fields=["status", "current_step_key"], name="flows_flowr_status_e81986_idx"),
        ),
        migrations.AddIndex(
            model_name="flowrun",
            index=models.Index(fields=["subject_type", "subject_id"], name="flows_flowr_subject_e8ad80_idx"),
        ),
        migrations.AddIndex(
            model_name="flowrun",
            index=models.Index(fields=["flow_definition", "status", "created_at"], name="flows_flowr_flow_de_9d5491_idx"),
        ),
        migrations.AddIndex(
            model_name="flowsteprun",
            index=models.Index(fields=["flow_run", "status", "sequence"], name="flows_flows_flow_ru_2bba80_idx"),
        ),
        migrations.AddIndex(
            model_name="flowsteprun",
            index=models.Index(fields=["status", "expected_action_id"], name="flows_flows_status_7fdd21_idx"),
        ),
        migrations.AddConstraint(
            model_name="flowsteprun",
            constraint=models.UniqueConstraint(fields=("flow_run", "step_key"), name="unique_flow_run_step_key"),
        ),
        migrations.AddIndex(
            model_name="flowevent",
            index=models.Index(fields=["flow_run", "created_at"], name="flows_flowe_flow_ru_1fe3eb_idx"),
        ),
        migrations.AddIndex(
            model_name="flowevent",
            index=models.Index(fields=["event_type", "created_at"], name="flows_flowe_event_t_94cd65_idx"),
        ),
        migrations.AddIndex(
            model_name="flowevent",
            index=models.Index(fields=["created_at"], name="flows_flowe_created_e0f7cd_idx"),
        ),
    ]
