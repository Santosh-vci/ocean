import os
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.masters.models import (
    AssetCompatibilityRule,
    Barge,
    CoalGrade,
    CTSAsset,
    Jetty,
    LoadingRateProfile,
    Location,
    Mine,
    Route,
    RouteSegment,
    Stockpile,
    Tug,
)
from apps.organizations.models import Organization
from apps.planning.models import (
    AssetAvailabilityWindow,
    BridgeWindow,
    CargoLayerStep,
    CargoRequirement,
    ImportJob,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    OGVVoyage,
    TideWindow,
)
from apps.rbac.models import (
    AccessPermission,
    DataScope,
    OrganizationMembership,
    Role,
    UserRoleAssignment,
)
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    ExportJob,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    ScenarioAssumption,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)
from apps.scheduling.services import (
    create_scenario_assumption,
    generate_plan_version,
    simulate_scenario,
)
from apps.telemetry.models import (
    AssetIdentity,
    GeofenceZone,
    LatestAssetState,
    LiveEtaProjection,
    MovementEvent,
    PositionPing,
    TelemetrySource,
    TrackingAlert,
)
from apps.telemetry.services import ensure_missing_latest_state, ingest_position_ping


class Command(BaseCommand):
    help = "Seed the baseline local-development data required by the current build."

    def add_arguments(self, parser):
        parser.add_argument(
            "--master-data-only",
            action="store_true",
            help=(
                "Seed organizations, roles, users, and master data only. "
                "Operational planning/scheduling/export/audit records are cleared first."
            ),
        )
        parser.add_argument(
            "--reset-operational-data",
            action="store_true",
            help=(
                "Clear operational planning, scheduling, export, and audit records before seeding."
            ),
        )

    def handle(self, *args, **options):
        email = os.getenv("SEED_ADMIN_EMAIL", "admin@coalflow.local")
        password = os.getenv("SEED_ADMIN_PASSWORD", "admin12345")
        user_model = get_user_model()
        default_user_password = os.getenv("SEED_USER_PASSWORD", "welcome12345")
        reset_seed_passwords = os.getenv("SEED_RESET_PASSWORDS", "1") != "0"

        platform, _ = Organization.objects.get_or_create(
            slug="coalflow-platform",
            defaults={"name": "Coalflow Platform", "kind": Organization.Kind.PLATFORM},
        )
        berau, _ = Organization.objects.get_or_create(
            slug="berau-coal",
            defaults={"name": "Berau Coal", "kind": Organization.Kind.BERAU},
        )
        abl, _ = Organization.objects.get_or_create(
            slug="abl",
            defaults={"name": "ABL", "kind": Organization.Kind.ABL},
        )

        permission_rows = [
            ("dashboard.view", "dashboard", "view", "View the control-tower dashboard"),
            ("schedule.view", "schedule", "view", "View schedules"),
            ("schedule.edit", "schedule", "edit", "Edit draft schedules"),
            ("schedule.approve", "schedule", "approve", "Approve proposed schedules"),
            ("schedule.publish", "schedule", "publish", "Publish approved schedules"),
            ("simulation.run", "simulation", "run", "Run recovery simulations"),
            ("fleet.view", "fleet", "view", "View fleet state"),
            ("fleet.assign", "fleet", "assign", "Assign fleet resources"),
            ("masterdata.view", "masterdata", "view", "View master data"),
            ("masterdata.manage", "masterdata", "manage", "Manage master data"),
            ("audit.view", "audit", "view", "View audit events"),
            ("export.view", "export", "view", "View governed export history"),
            ("export.generate", "export", "generate", "Generate governed export artifacts"),
            ("telemetry.view", "telemetry", "view", "View live tracking telemetry"),
            ("telemetry.ingest", "telemetry", "ingest", "Ingest telemetry pings"),
            ("admin.view", "admin", "view", "View admin consoles"),
            ("admin.manage_users", "admin", "manage_users", "Manage users and organizations"),
        ]
        permissions = {}
        for code, module, action, description in permission_rows:
            permission, _ = AccessPermission.objects.update_or_create(
                code=code,
                defaults={
                    "module": module,
                    "action": action,
                    "description": description,
                },
            )
            permissions[code] = permission

        all_network_scope, _ = DataScope.objects.update_or_create(
            code="all-network",
            defaults={
                "name": "All network",
                "scope_type": DataScope.ScopeType.ALL_NETWORK,
            },
        )
        berau_scope, _ = DataScope.objects.update_or_create(
            code="berau-only",
            defaults={
                "name": "Berau only",
                "scope_type": DataScope.ScopeType.ORGANIZATION,
                "organization": berau,
            },
        )
        abl_scope, _ = DataScope.objects.update_or_create(
            code="abl-only",
            defaults={
                "name": "ABL only",
                "scope_type": DataScope.ScopeType.ORGANIZATION,
                "organization": abl,
            },
        )

        role_rows = {
            "admin": {
                "name": "Admin",
                "description": "Platform administration and configuration.",
                "permissions": permissions.values(),
            },
            "berau-scheduler": {
                "name": "Berau Scheduler",
                "description": "Demand, grade sequence, and schedule review.",
                "permissions": [
                    permissions["dashboard.view"],
                    permissions["schedule.view"],
                    permissions["schedule.edit"],
                    permissions["schedule.approve"],
                    permissions["simulation.run"],
                    permissions["masterdata.view"],
                    permissions["telemetry.view"],
                    permissions["audit.view"],
                    permissions["export.view"],
                ],
            },
            "abl-dispatcher": {
                "name": "ABL Dispatcher",
                "description": "Fleet dispatch and execution control.",
                "permissions": [
                    permissions["dashboard.view"],
                    permissions["schedule.view"],
                    permissions["schedule.edit"],
                    permissions["fleet.view"],
                    permissions["fleet.assign"],
                    permissions["schedule.approve"],
                    permissions["simulation.run"],
                    permissions["telemetry.view"],
                    permissions["telemetry.ingest"],
                    permissions["audit.view"],
                    permissions["export.view"],
                ],
            },
            "joint-control-tower-manager": {
                "name": "Joint Control Tower Manager",
                "description": "Shared cross-party control and publication authority.",
                "permissions": [
                    permissions["dashboard.view"],
                    permissions["schedule.view"],
                    permissions["schedule.approve"],
                    permissions["schedule.publish"],
                    permissions["simulation.run"],
                    permissions["fleet.view"],
                    permissions["telemetry.view"],
                    permissions["telemetry.ingest"],
                    permissions["audit.view"],
                    permissions["export.view"],
                    permissions["export.generate"],
                ],
            },
            "read-only-viewer": {
                "name": "Read-only Viewer",
                "description": "Safe observation without mutation rights.",
                "permissions": [
                    permissions["dashboard.view"],
                    permissions["schedule.view"],
                    permissions["fleet.view"],
                    permissions["telemetry.view"],
                ],
            },
        }

        roles = {}
        for code, data in role_rows.items():
            role, _ = Role.objects.update_or_create(
                code=code,
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "is_system_role": True,
                    "is_active": True,
                },
            )
            role.permissions.set(data["permissions"])
            roles[code] = role

        admin_user = self._upsert_user(
            user_model=user_model,
            username=email,
            email=email,
            password=password,
            is_staff=True,
            is_superuser=True,
            reset_password=reset_seed_passwords,
        )
        self._assign(admin_user, platform, roles["admin"], all_network_scope, "Platform Admin")

        seeded_users = [
            (
                "berau.scheduler@coalflow.local",
                berau,
                roles["berau-scheduler"],
                berau_scope,
                "Berau Scheduler",
            ),
            (
                "abl.dispatcher@coalflow.local",
                abl,
                roles["abl-dispatcher"],
                abl_scope,
                "ABL Dispatcher",
            ),
            (
                "control.tower@coalflow.local",
                platform,
                roles["joint-control-tower-manager"],
                all_network_scope,
                "Joint Control Tower Manager",
            ),
            (
                "viewer@coalflow.local",
                platform,
                roles["read-only-viewer"],
                all_network_scope,
                "Read-only Viewer",
            ),
        ]

        for username, organization, role, scope, title in seeded_users:
            user = self._upsert_user(
                user_model=user_model,
                username=username,
                email=username,
                password=default_user_password,
                reset_password=reset_seed_passwords,
            )
            self._assign(user, organization, role, scope, title)

        if options["master_data_only"] or options["reset_operational_data"]:
            self._reset_operational_data()

        self._seed_master_data(berau=berau, abl=abl)
        self._seed_telemetry_foundation()
        if options["master_data_only"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "Seeded Phase 1 organizations, roles, users, and master data only. "
                    "Operational planning, scheduling, export, and audit records are empty."
                )
            )
            return

        self._seed_planning_data(berau=berau, abl=abl, created_by=admin_user)
        self._seed_schedule_data(abl=abl, created_by=admin_user)
        self._seed_telemetry_sample_movements()

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded Phase 1 pilot organizations, roles, planning data, schedule, "
                "governance loop, dashboard context, and export handoff permissions."
            )
        )

    def _upsert_user(
        self,
        *,
        user_model,
        username: str,
        email: str,
        password: str,
        is_staff: bool = False,
        is_superuser: bool = False,
        reset_password: bool = False,
    ):
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
            },
        )
        changed_fields = []
        if created or reset_password:
            user.set_password(password)
            changed_fields.append("password")
        if user.email != email:
            user.email = email
            changed_fields.append("email")
        if user.is_staff != is_staff:
            user.is_staff = is_staff
            changed_fields.append("is_staff")
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            changed_fields.append("is_superuser")
        if changed_fields:
            user.save(update_fields=changed_fields)
        return user

    def _assign(self, user, organization, role, scope, title):
        OrganizationMembership.objects.update_or_create(
            user=user,
            organization=organization,
            defaults={
                "title": title,
                "is_default": True,
                "is_active": True,
            },
        )
        UserRoleAssignment.objects.update_or_create(
            user=user,
            role=role,
            organization=organization,
            data_scope=scope,
            defaults={"is_active": True},
        )

    def _reset_operational_data(self):
        LatestAssetState.objects.all().delete()
        TrackingAlert.objects.all().delete()
        LiveEtaProjection.objects.all().delete()
        MovementEvent.objects.all().delete()
        PositionPing.objects.all().delete()

        ExportJob.objects.all().delete()
        PublishedPlanSnapshot.objects.all().delete()
        ApprovalDecision.objects.all().delete()
        ApprovalRequest.objects.all().delete()
        SimulationScenario.objects.all().delete()
        OverrideRequest.objects.all().delete()
        ScheduleEvent.objects.all().delete()
        Assignment.objects.all().delete()
        Conflict.objects.all().delete()
        Trip.objects.all().delete()
        PlanVersion.objects.all().delete()
        Plan.objects.all().delete()

        NavigationConstraintCheck.objects.all().delete()
        BridgeWindow.objects.all().delete()
        TideWindow.objects.all().delete()
        JettyAvailabilityWindow.objects.all().delete()
        AssetAvailabilityWindow.objects.all().delete()
        CargoLayerStep.objects.all().delete()
        CargoRequirement.objects.all().delete()
        OGVVoyage.objects.all().delete()
        ImportJob.objects.all().delete()

        AuditEvent.objects.all().delete()

    def _seed_telemetry_foundation(self):
        gps_source, _ = TelemetrySource.objects.update_or_create(
            source_id="SYN-GPS-PHASE3",
            defaults={
                "name": "Phase 3 Synthetic GPS Replay",
                "source_type": TelemetrySource.SourceType.SYNTHETIC_GPS,
                "status": TelemetrySource.Status.ACTIVE,
                "freshness_threshold_seconds": 900,
                "metadata": {
                    "seeded": True,
                    "purpose": "Phase 3 telemetry foundation identity mapping",
                },
            },
        )
        ais_source, _ = TelemetrySource.objects.update_or_create(
            source_id="SYN-AIS-PHASE3",
            defaults={
                "name": "Phase 3 Synthetic AIS Replay",
                "source_type": TelemetrySource.SourceType.SYNTHETIC_AIS,
                "status": TelemetrySource.Status.ACTIVE,
                "freshness_threshold_seconds": 900,
                "metadata": {
                    "seeded": True,
                    "purpose": "Phase 3 telemetry foundation identity mapping",
                },
            },
        )

        for tug in Tug.objects.order_by("code"):
            identity, _ = AssetIdentity.objects.update_or_create(
                source=gps_source,
                external_id=tug.gps_device_id or f"SYN-{tug.code}",
                defaults={
                    "asset_type": AssetIdentity.AssetType.TUG,
                    "asset_object_id": tug.id,
                    "asset_code": tug.code,
                    "external_id_type": AssetIdentity.ExternalIdType.TRACKER_ID,
                    "is_primary": True,
                    "metadata": {"seeded": True},
                },
            )
            ensure_missing_latest_state(asset_identity=identity)
            if tug.ais_mmsi:
                AssetIdentity.objects.update_or_create(
                    source=ais_source,
                    external_id=tug.ais_mmsi,
                    defaults={
                        "asset_type": AssetIdentity.AssetType.TUG,
                        "asset_object_id": tug.id,
                        "asset_code": tug.code,
                        "external_id_type": AssetIdentity.ExternalIdType.MMSI,
                        "is_primary": False,
                        "metadata": {"seeded": True},
                    },
                )
        for barge in Barge.objects.order_by("code"):
            identity, _ = AssetIdentity.objects.update_or_create(
                source=gps_source,
                external_id=f"SYN-{barge.code}",
                defaults={
                    "asset_type": AssetIdentity.AssetType.BARGE,
                    "asset_object_id": barge.id,
                    "asset_code": barge.code,
                    "external_id_type": AssetIdentity.ExternalIdType.SYNTHETIC_ID,
                    "is_primary": True,
                    "metadata": {"seeded": True},
                },
            )
            ensure_missing_latest_state(asset_identity=identity)
        for cts in CTSAsset.objects.order_by("code"):
            identity, _ = AssetIdentity.objects.update_or_create(
                source=gps_source,
                external_id=f"SYN-{cts.code}",
                defaults={
                    "asset_type": AssetIdentity.AssetType.CTS,
                    "asset_object_id": cts.id,
                    "asset_code": cts.code,
                    "external_id_type": AssetIdentity.ExternalIdType.SYNTHETIC_ID,
                    "is_primary": True,
                    "metadata": {"seeded": True},
                },
            )
            ensure_missing_latest_state(asset_identity=identity)

        for location in Location.objects.order_by("code"):
            GeofenceZone.objects.update_or_create(
                zone_id=f"GEO-{location.code}",
                defaults={
                    "name": location.name,
                    "zone_type": location.location_type,
                    "source_location": location,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "radius_m": location.geofence_radius_m,
                    "status": GeofenceZone.Status.ACTIVE,
                    "metadata": {
                        "parentArea": location.parent_area,
                        "operationalNotes": location.operational_notes,
                        "source": "master_location_seed",
                    },
                },
            )

    def _seed_start_date(self):
        return timezone.localdate() + timedelta(days=1)

    def _seed_telemetry_sample_movements(self):
        source = TelemetrySource.objects.get(source_id="SYN-GPS-PHASE3")
        locations = {location.code: location for location in Location.objects.all()}
        active_version = (
            PlanVersion.objects.filter(status=PlanVersion.Status.APPROVED)
            .order_by("-created_at")
            .first()
            or PlanVersion.objects.filter(
                status__in=[
                    PlanVersion.Status.DRAFT,
                    PlanVersion.Status.VALIDATED,
                    PlanVersion.Status.PROPOSED,
                ]
            )
            .order_by("-created_at")
            .first()
            or PlanVersion.objects.order_by("-created_at").first()
        )
        assignments = list(
            Assignment.objects.select_related(
                "trip",
                "tug",
                "barge",
                "jetty",
                "cts",
            )
            .prefetch_related("trip__events")
            .filter(trip__plan_version=active_version)
            .order_by("trip__plan_version__created_at", "trip__sequence")
        )
        latest_assignment_for_barge = next(
            (item for item in assignments if item.barge and item.barge.code == "BRG-VAL-08"),
            None,
        )
        latest_assignment_for_tug = next(
            (item for item in assignments if item.tug and item.tug.code == "BER-TUG-08"),
            None,
        )
        latest_assignment_for_cts = next(
            (item for item in assignments if item.cts and item.cts.code == "CTS-BORNEO"),
            None,
        )
        brg_depart = self._event_at(
            assignment=latest_assignment_for_barge,
            event_type=ScheduleEvent.EventType.DEPART_JETTY,
            fallback=timezone.now(),
        )
        tug_depart = self._event_at(
            assignment=latest_assignment_for_tug,
            event_type=ScheduleEvent.EventType.DEPART_JETTY,
            fallback=timezone.now(),
        )
        tug_bridge = self._event_at(
            assignment=latest_assignment_for_tug,
            event_type=ScheduleEvent.EventType.BRIDGE_CROSS,
            fallback=tug_depart + timedelta(minutes=20),
        )
        cts_arrival = self._event_at(
            assignment=latest_assignment_for_cts,
            event_type=ScheduleEvent.EventType.ARRIVE_CTS,
            fallback=timezone.now(),
        )
        tug_jetty_location = self._location_code_for_jetty(latest_assignment_for_tug)
        barge_jetty_location = self._location_code_for_jetty(latest_assignment_for_barge)
        cts_location = self._location_code_for_cts(latest_assignment_for_cts)
        sample_rows = [
            (
                "GPS-768",
                AssetIdentity.AssetType.TUG,
                "BER-TUG-08",
                tug_jetty_location,
                tug_depart - timedelta(minutes=12),
                "0.20",
                "095.00",
            ),
            (
                "GPS-768",
                AssetIdentity.AssetType.TUG,
                "BER-TUG-08",
                "LOC-BRIDGE-GATE-B",
                tug_bridge - timedelta(minutes=5),
                "5.40",
                "090.00",
            ),
            (
                "SYN-BRG-VAL-08",
                AssetIdentity.AssetType.BARGE,
                "BRG-VAL-08",
                barge_jetty_location,
                brg_depart + timedelta(minutes=45),
                "0.30",
                "090.00",
            ),
            (
                "SYN-CTS-BORNEO",
                AssetIdentity.AssetType.CTS,
                "CTS-BORNEO",
                cts_location,
                cts_arrival + timedelta(minutes=5),
                "0.00",
                "180.00",
            ),
        ]
        sample_asset_codes = {row[2] for row in sample_rows}
        TrackingAlert.objects.filter(
            asset_code__in=sample_asset_codes,
            source_kind=TrackingAlert.SourceKind.SYNTHETIC,
        ).delete()
        LiveEtaProjection.objects.filter(asset_code__in=sample_asset_codes).delete()
        PositionPing.objects.filter(raw_payload__seed="phase_3_sample_movement").delete()
        LatestAssetState.objects.filter(asset_code__in=sample_asset_codes).update(
            last_ping=None,
            current_geofence=None,
            last_movement_event=None,
            derived_status=LatestAssetState.DerivedStatus.UNKNOWN,
            latitude=None,
            longitude=None,
            speed_knots=None,
            heading_degrees=None,
            last_seen_at=None,
            freshness_status=LatestAssetState.FreshnessStatus.MISSING,
            confidence_score=0,
        )
        for (
            external_id,
            asset_type,
            asset_code,
            location_code,
            timestamp,
            speed,
            heading,
        ) in sample_rows:
            location = locations[location_code]
            ingest_position_ping(
                payload={
                    "source_id": source.source_id,
                    "source_type": source.source_type,
                    "external_id": external_id,
                    "asset_type": asset_type,
                    "asset_code": asset_code,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "speed_knots": speed,
                    "course_degrees": heading,
                    "heading_degrees": heading,
                    "device_timestamp": timestamp,
                    "signal_quality": PositionPing.SignalQuality.GOOD,
                    "raw_payload": {
                        "seed": "phase_3_sample_movement",
                        "locationCode": location_code,
                    },
                }
            )

    def _event_at(self, *, assignment, event_type, fallback):
        if not assignment:
            return fallback
        event = next(
            (
                item
                for item in assignment.trip.events.all()
                if item.event_type == event_type
            ),
            None,
        )
        return event.planned_at if event else fallback

    def _location_code_for_jetty(self, assignment):
        if not assignment or not assignment.jetty:
            return "LOC-SUARAN-PORT"
        return {
            "JTY-SUARAN": "LOC-SUARAN-PORT",
            "JTY-LATI": "LOC-LATI-PORT",
            "JTY-GMB": "LOC-GURIMBANG",
        }.get(assignment.jetty.code, "LOC-SUARAN-PORT")

    def _location_code_for_cts(self, assignment):
        if not assignment or not assignment.cts:
            return "LOC-CTS-ALPHA"
        return {
            "CTS-BORNEO": "LOC-CTS-ALPHA",
            "CTS-JAVA": "LOC-CTS-BRAVO",
            "FC-CHLOE": "LOC-CTS-BRAVO",
        }.get(assignment.cts.code, "LOC-CTS-ALPHA")

    def _seed_datetime(self, start_date, day_offset, hour, minute=0):
        target_date = start_date + timedelta(days=day_offset)
        return timezone.make_aware(datetime.combine(target_date, time(hour, minute)))

    def _upsert_single(self, model, lookup: dict, defaults: dict):
        records = model.objects.filter(**lookup).order_by("id")
        record = records.first()
        if record is None:
            return model.objects.create(**lookup, **defaults)

        records.exclude(pk=record.pk).delete()
        for key, value in defaults.items():
            setattr(record, key, value)
        update_fields = list(defaults.keys())
        if any(field.name == "updated_at" for field in model._meta.fields):
            update_fields.append("updated_at")
        record.save(update_fields=update_fields)
        return record

    def _seed_master_data(self, *, berau, abl):
        location_rows = [
            (
                "LOC-LATI-MINE",
                "Lati Mine",
                Location.LocationType.MINE,
                "-2.189500",
                "117.401200",
                2000,
                "Lati",
                "Source mine for Agathis and Sungkai planning flows.",
            ),
            (
                "LOC-LATI-CPP",
                "Lati CPP",
                Location.LocationType.CPP,
                "-2.167800",
                "117.421300",
                800,
                "Lati",
                "Processing and quality-readiness checkpoint before Lati Port.",
            ),
            (
                "LOC-LATI-PORT",
                "Lati Port",
                Location.LocationType.JETTY,
                "-2.147200",
                "117.500900",
                500,
                "Lati",
                "Barge loading point for Lati-origin cargo.",
            ),
            (
                "LOC-BINUNGAN-MINE",
                "Binungan Mine",
                Location.LocationType.MINE,
                "-2.081400",
                "117.443100",
                2200,
                "Binungan",
                "Source cluster feeding CPP Binungan and Suaran terminal.",
            ),
            (
                "LOC-CPP-BINUNGAN",
                "CPP Binungan",
                Location.LocationType.CPP,
                "-2.050900",
                "117.472500",
                900,
                "Binungan",
                "Processing plant and stockpile handoff to Suaran flow.",
            ),
            (
                "LOC-SUARAN-PORT",
                "Suaran Port",
                Location.LocationType.JETTY,
                "-2.023100",
                "117.596700",
                600,
                "Suaran",
                "Primary river loading terminal for Binungan flows.",
            ),
            (
                "LOC-SAMBARATA-MINE",
                "Sambarata Mine",
                Location.LocationType.MINE,
                "-2.291200",
                "117.296300",
                2200,
                "Sambarata",
                "Source cluster for Ebony flows.",
            ),
            (
                "LOC-SAMBARATA-PORT",
                "Sambarata Port",
                Location.LocationType.JETTY,
                "-2.227800",
                "117.360500",
                600,
                "Sambarata",
                "Barge loading point feeding Berau River corridor.",
            ),
            (
                "LOC-GURIMBANG",
                "Gurimbang Checkpoint",
                Location.LocationType.CHECKPOINT,
                "-2.192400",
                "117.557900",
                350,
                "Berau River",
                "River checkpoint and route-control handoff.",
            ),
            (
                "LOC-KM30-SUARAN",
                "KM30 Suaran Checkpoint",
                Location.LocationType.CHECKPOINT,
                "-2.036700",
                "117.664800",
                300,
                "Suaran Corridor",
                "Intermediate checkpoint before the Rantau Delta gate.",
            ),
            (
                "LOC-BRIDGE-GATE-B",
                "Bridge Gate B",
                Location.LocationType.BRIDGE,
                "-2.119100",
                "117.720300",
                300,
                "Berau River",
                "Restricted bridge crossing; requires configured bridge window.",
            ),
            (
                "LOC-RANTAU-DELTA",
                "Rantau Delta Gate",
                Location.LocationType.TIDE_GATE,
                "-2.042900",
                "117.823500",
                1200,
                "Rantau Delta",
                "Tide-sensitive estuary gate for loaded barges.",
            ),
            (
                "LOC-MUARA-PANTAI",
                "Muara Pantai Transshipment Point",
                Location.LocationType.TRANSSHIPMENT,
                "-1.937200",
                "118.053900",
                2200,
                "Muara Pantai",
                "Offshore transshipment point for OGV and CTS operations.",
            ),
            (
                "LOC-ANCHORAGE-SOUTH",
                "Anchorage South",
                Location.LocationType.ANCHORAGE,
                "-1.988100",
                "118.015600",
                1500,
                "Muara Pantai",
                "Waiting and resequencing anchorage.",
            ),
            (
                "LOC-CTS-ALPHA",
                "CTS Zone Alpha",
                Location.LocationType.CTS_ZONE,
                "-1.928800",
                "118.074200",
                1500,
                "Muara Pantai",
                "Floating transfer station operating area.",
            ),
            (
                "LOC-CTS-BRAVO",
                "CTS Zone Bravo",
                Location.LocationType.CTS_ZONE,
                "-1.917100",
                "118.095400",
                1500,
                "Muara Pantai",
                "Floating crane and backup CTS operating area.",
            ),
            (
                "LOC-MAINT-DOCK-01",
                "Maintenance Dock 01",
                Location.LocationType.MAINTENANCE,
                "-2.157600",
                "117.531700",
                500,
                "Berau River",
                "Fleet maintenance and outage staging point.",
            ),
        ]
        for code, name, location_type, lat, lon, radius, parent_area, notes in location_rows:
            Location.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": berau,
                    "location_type": location_type,
                    "latitude": lat,
                    "longitude": lon,
                    "geofence_radius_m": radius,
                    "parent_area": parent_area,
                    "operational_notes": notes,
                },
            )

        grades = {
            "EBONY": ("Ebony", "Ebony", 5000, 0.45, 5.20, 1),
            "MAHONI": ("Mahoni", "Mahoni", 4700, 0.40, 5.80, 2),
            "AGATHIS": ("Agathis", "Agathis", 4300, 0.35, 6.10, 3),
            "SUNGKAI": ("Sungkai", "Sungkai", 4100, 0.34, 6.50, 4),
        }
        grade_records = {}
        for code, (name, family, cv, sulfur, ash, priority) in grades.items():
            grade_records[code], _ = CoalGrade.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": berau,
                    "brand_family": family,
                    "typical_cv_kcal": cv,
                    "sulfur_pct": sulfur,
                    "ash_pct": ash,
                    "sequence_priority": priority,
                    "is_active": True,
                },
            )

        mines = {
            "LATI": ("Lati Mine", "East Kalimantan", 11.0),
            "BINUNGAN": ("Binungan Mine", "East Kalimantan", 26.0),
            "SAMBARATA": ("Sambarata Mine", "East Kalimantan", 2.0),
        }
        mine_records = {}
        for code, (name, region, haul) in mines.items():
            mine_records[code], _ = Mine.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": berau,
                    "region": region,
                    "default_haul_distance_km": haul,
                },
            )

        stockpile_rows = [
            ("SP-LATI-AGT", "Lati Agathis Stockpile", "LATI", "AGATHIS", 180000, 15000),
            ("SP-BIN-EBY", "Binungan Ebony Stockpile", "BINUNGAN", "EBONY", 220000, 24000),
            ("SP-SAM-EBY", "Sambarata Ebony Stockpile", "SAMBARATA", "EBONY", 165000, 18000),
            ("SP-LATI-SGK", "Lati Sungkai Stockpile", "LATI", "SUNGKAI", 120000, 8000),
        ]
        for code, name, mine, grade, available, reserved in stockpile_rows:
            Stockpile.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": berau,
                    "mine": mine_records[mine],
                    "coal_grade": grade_records[grade],
                    "available_quantity_mt": available,
                    "reserved_quantity_mt": reserved,
                },
            )

        jetty_rows = [
            ("JTY-SUARAN", "Suaran Jetty", "Suaran terminal", 2800, 4.8, Jetty.Status.AVAILABLE),
            ("JTY-LATI", "Lati Jetty", "Lati river loading", 2200, 4.4, Jetty.Status.AVAILABLE),
            ("JTY-GMB", "Gurimbang Jetty", "Gurimbang BLC", 1800, 4.0, Jetty.Status.AVAILABLE),
        ]
        for code, name, location, rate, draft, status in jetty_rows:
            Jetty.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": berau,
                    "location_name": location,
                    "loading_rate_tph": rate,
                    "max_barge_draft_m": draft,
                    "status": status,
                },
            )

        tug_rows = [
            (
                "BER-TUG-09",
                "Harbor Sentinel 09",
                3300,
                42.5,
                "525001209",
                "GPS-770",
                Tug.Status.AVAILABLE,
            ),
            (
                "BER-TUG-08",
                "Coastal Sentry 08",
                2800,
                36.0,
                "525001232",
                "GPS-768",
                Tug.Status.AVAILABLE,
            ),
            (
                "BER-TUG-04",
                "Mahakam Puller 04",
                2200,
                29.4,
                "525001198",
                "GPS-612",
                Tug.Status.MAINTENANCE,
            ),
        ]
        for code, name, hp, pull, mmsi, gps, status in tug_rows:
            Tug.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": abl,
                    "horsepower": hp,
                    "bollard_pull_tonnes": pull,
                    "ais_mmsi": mmsi,
                    "gps_device_id": gps,
                    "status": status,
                },
            )

        barge_rows = [
            ("BRG-VAL-08", "Barge Valiant 08", 8500, "300ft", 4.2, Barge.Status.AVAILABLE),
            ("BRG-NUS-17", "Barge Nusantara 17", 7800, "300ft", 4.0, Barge.Status.AVAILABLE),
            ("BRG-KAL-22", "Barge Kalimantan 22", 9200, "330ft", 4.6, Barge.Status.ASSIGNED),
        ]
        for code, name, capacity, barge_class, draft, status in barge_rows:
            Barge.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": abl,
                    "capacity_mt": capacity,
                    "barge_class": barge_class,
                    "max_draft_m": draft,
                    "status": status,
                },
            )

        cts_rows = [
            ("CTS-BORNEO", "FTS Bulk Borneo", CTSAsset.CtsType.CONVEYOR, 32000, "Muara Pantai"),
            ("CTS-JAVA", "FTS Bulk Java", CTSAsset.CtsType.CONVEYOR, 28000, "Muara Pantai"),
            (
                "FC-CHLOE",
                "Floating Crane Chloe",
                CTSAsset.CtsType.FLOATING_CRANE,
                30000,
                "Anchorage A",
            ),
        ]
        for code, name, cts_type, capacity, area in cts_rows:
            CTSAsset.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": abl,
                    "cts_type": cts_type,
                    "daily_capacity_mt": capacity,
                    "operating_area": area,
                    "is_available": True,
                },
            )

        route, _ = Route.objects.update_or_create(
            code="RTE-SUARAN-MUARA",
            defaults={
                "name": "Suaran to Muara Transshipment",
                "organization": abl,
                "origin": "Suaran Jetty",
                "destination": "Muara Pantai Anchorage",
                "default_loaded_duration_minutes": 480,
                "default_empty_duration_minutes": 390,
            },
        )
        segments = [
            (1, "Suaran Jetty", "Bridge Approach", 22.5, 160, 130, False, True),
            (2, "Bridge Approach", "Tide Chokepoint", 18.0, 150, 120, True, True),
            (3, "Tide Chokepoint", "Muara Pantai", 34.2, 170, 140, True, False),
        ]
        for seq, start, end, distance, loaded, empty, tide, bridge in segments:
            RouteSegment.objects.update_or_create(
                route=route,
                sequence=seq,
                defaults={
                    "from_location": start,
                    "to_location": end,
                    "distance_nm": distance,
                    "loaded_duration_minutes": loaded,
                    "empty_duration_minutes": empty,
                    "requires_tide_window": tide,
                    "requires_bridge_window": bridge,
                },
            )

        rate_rows = [
            ("LR-JTY-SUARAN-EBONY", "Suaran Ebony Loading", "jetty", "JTY-SUARAN", "EBONY", 2800),
            ("LR-JTY-LATI-AGT", "Lati Agathis Loading", "jetty", "JTY-LATI", "AGATHIS", 2200),
            (
                "LR-CTS-BORNEO-EBONY",
                "Borneo Ebony Transshipment",
                "cts",
                "CTS-BORNEO",
                "EBONY",
                1350,
            ),
        ]
        for code, name, resource_type, resource_code, grade, rate in rate_rows:
            LoadingRateProfile.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": abl if resource_type == "cts" else berau,
                    "resource_type": resource_type,
                    "resource_code": resource_code,
                    "coal_grade": grade_records[grade],
                    "rate_tph": rate,
                },
            )

        rules = [
            (
                "CMP-TUG09-BRGVAL08",
                "Tug 09 with Valiant 08",
                "tug_barge",
                "BER-TUG-09",
                "BRG-VAL-08",
                True,
                "",
            ),
            (
                "CMP-TUG08-BRGKAL22",
                "Tug 08 with Kalimantan 22",
                "tug_barge",
                "BER-TUG-08",
                "BRG-KAL-22",
                True,
                "",
            ),
            (
                "CMP-EBONY-SUARAN",
                "Ebony through Suaran",
                "grade_jetty",
                "EBONY",
                "JTY-SUARAN",
                True,
                "",
            ),
            (
                "CMP-AGT-LATI",
                "Agathis through Lati",
                "grade_jetty",
                "AGATHIS",
                "JTY-LATI",
                True,
                "",
            ),
        ]
        for code, name, rule_type, left, right, compatible, reason in rules:
            AssetCompatibilityRule.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "organization": abl,
                    "rule_type": rule_type,
                    "left_code": left,
                    "right_code": right,
                    "is_compatible": compatible,
                    "reason": reason,
                },
            )

    def _seed_planning_data(self, *, berau, abl, created_by):
        start_date = self._seed_start_date()

        def dt(day, hour, minute=0):
            return self._seed_datetime(start_date, day - 24, hour, minute)

        locations = {record.code: record for record in Location.objects.all()}
        grades = {record.code: record for record in CoalGrade.objects.all()}
        jetties = {record.code: record for record in Jetty.objects.all()}
        barges = {record.code: record for record in Barge.objects.all()}
        cts_assets = {record.code: record for record in CTSAsset.objects.all()}
        segments = {
            record.sequence: record for record in RouteSegment.objects.select_related("route")
        }

        voyage_rows = [
            {
                "voyage_id": "VOY-PACIFIC-PRIDE",
                "vessel_name": "MV PACIFIC PRIDE",
                "customer_name": "GLENCORE",
                "vessel_class": "Panamax",
                "eta": dt(24, 3),
                "etb": dt(24, 8),
                "etc_target": dt(26, 18),
                "laycan_start": dt(24, 0),
                "laycan_end": dt(27, 23),
                "required_mt": 165000,
                "loaded_mt": 142500,
                "in_transit_mt": 12000,
                "discharged_mt": 0,
                "priority": 1,
                "demurrage_rate_usd_per_day": 14200,
                "anchorage_location": locations["LOC-MUARA-PANTAI"],
                "organization": berau,
                "status": OGVVoyage.Status.ACTIVE,
                "risk_status": OGVVoyage.RiskStatus.LOW,
                "current_stage": "H5 STAGE",
                "next_blocking_constraint": "No critical blockers",
            },
            {
                "voyage_id": "VOY-OCEAN-VOYAGER",
                "vessel_name": "MV OCEAN VOYAGER",
                "customer_name": "VITOL",
                "vessel_class": "Supramax",
                "eta": dt(24, 6),
                "etb": dt(24, 11),
                "etc_target": dt(26, 9),
                "laycan_start": dt(24, 0),
                "laycan_end": dt(26, 20),
                "required_mt": 120000,
                "loaded_mt": 118200,
                "in_transit_mt": 0,
                "discharged_mt": 0,
                "priority": 2,
                "demurrage_rate_usd_per_day": 12800,
                "anchorage_location": locations["LOC-MUARA-PANTAI"],
                "organization": berau,
                "status": OGVVoyage.Status.AT_RISK,
                "risk_status": OGVVoyage.RiskStatus.HIGH,
                "current_stage": "FINAL TOP-OFF",
                "next_blocking_constraint": "LOW TIDE DRAFT RESTR.",
            },
            {
                "voyage_id": "VOY-NORTH-STAR",
                "vessel_name": "MV NORTH STAR",
                "customer_name": "NIPPON STEEL",
                "vessel_class": "Handymax",
                "eta": dt(25, 1),
                "etb": dt(25, 9),
                "etc_target": dt(27, 4),
                "laycan_start": dt(25, 0),
                "laycan_end": dt(28, 8),
                "required_mt": 98000,
                "loaded_mt": 54000,
                "in_transit_mt": 18500,
                "discharged_mt": 0,
                "priority": 2,
                "demurrage_rate_usd_per_day": 10900,
                "anchorage_location": locations["LOC-ANCHORAGE-SOUTH"],
                "organization": berau,
                "status": OGVVoyage.Status.AT_RISK,
                "risk_status": OGVVoyage.RiskStatus.MEDIUM,
                "current_stage": "H2/L2",
                "next_blocking_constraint": "GRADE SEQUENCE VIOLATION",
            },
            {
                "voyage_id": "VOY-GOLDEN-ORIOLE",
                "vessel_name": "MV GOLDEN ORIOLE",
                "customer_name": "KOREA POWER",
                "vessel_class": "Capesize",
                "eta": dt(27, 15),
                "etb": dt(28, 6),
                "etc_target": dt(31, 18),
                "laycan_start": dt(27, 0),
                "laycan_end": dt(31, 23),
                "required_mt": 210000,
                "loaded_mt": 0,
                "in_transit_mt": 0,
                "discharged_mt": 0,
                "priority": 4,
                "demurrage_rate_usd_per_day": 15600,
                "anchorage_location": locations["LOC-ANCHORAGE-SOUTH"],
                "organization": berau,
                "status": OGVVoyage.Status.PLANNED,
                "risk_status": OGVVoyage.RiskStatus.LOW,
                "current_stage": "PRE-LAYCAN",
                "next_blocking_constraint": "Awaiting ETA confirm",
            },
            {
                "voyage_id": "VOY-TRITON-STAR",
                "vessel_name": "MV TRITON STAR",
                "customer_name": "TRAFIGURA",
                "vessel_class": "Panamax",
                "eta": dt(24, 22),
                "etb": dt(25, 5),
                "etc_target": dt(28, 20),
                "laycan_start": dt(24, 12),
                "laycan_end": dt(28, 12),
                "required_mt": 180000,
                "loaded_mt": 22000,
                "in_transit_mt": 14500,
                "discharged_mt": 0,
                "priority": 1,
                "demurrage_rate_usd_per_day": 15100,
                "anchorage_location": locations["LOC-MUARA-PANTAI"],
                "organization": berau,
                "status": OGVVoyage.Status.AT_RISK,
                "risk_status": OGVVoyage.RiskStatus.DEMURRAGE,
                "current_stage": "H1/L1",
                "next_blocking_constraint": "Feeder delay (+4h)",
            },
        ]
        voyages = {}
        for row in voyage_rows:
            voyage, _ = OGVVoyage.objects.update_or_create(
                voyage_id=row["voyage_id"],
                defaults={key: value for key, value in row.items() if key != "voyage_id"},
            )
            voyages[row["voyage_id"]] = voyage

        requirement_rows = [
            ("VOY-PACIFIC-PRIDE", "EBONY", "LOC-SAMBARATA-PORT", "JTY-SUARAN", 98000, 86000, 6000),
            ("VOY-PACIFIC-PRIDE", "AGATHIS", "LOC-LATI-PORT", "JTY-LATI", 67000, 56500, 6000),
            ("VOY-OCEAN-VOYAGER", "MAHONI", "LOC-SUARAN-PORT", "JTY-SUARAN", 120000, 118200, 0),
            ("VOY-NORTH-STAR", "SUNGKAI", "LOC-LATI-PORT", "JTY-LATI", 52000, 31000, 9000),
            ("VOY-NORTH-STAR", "AGATHIS", "LOC-LATI-PORT", "JTY-LATI", 46000, 23000, 9500),
            ("VOY-GOLDEN-ORIOLE", "EBONY", "LOC-SAMBARATA-PORT", "JTY-SUARAN", 130000, 0, 0),
            ("VOY-GOLDEN-ORIOLE", "MAHONI", "LOC-SUARAN-PORT", "JTY-SUARAN", 80000, 0, 0),
            ("VOY-TRITON-STAR", "EBONY", "LOC-SAMBARATA-PORT", "JTY-SUARAN", 180000, 22000, 14500),
        ]
        requirements = {}
        for voyage_id, grade, source, jetty, required, loaded, in_transit in requirement_rows:
            requirement, _ = CargoRequirement.objects.update_or_create(
                voyage=voyages[voyage_id],
                coal_grade=grades[grade],
                defaults={
                    "source_location": locations[source],
                    "preferred_jetty": jetties[jetty],
                    "required_mt": required,
                    "loaded_mt": loaded,
                    "in_transit_mt": in_transit,
                    "discharged_mt": 0,
                    "status": CargoRequirement.Status.LOADING
                    if loaded
                    else CargoRequirement.Status.PLANNED,
                },
            )
            requirements[(voyage_id, grade)] = requirement

        layer_rows = [
            (
                "VOY-PACIFIC-PRIDE",
                "EBONY",
                1,
                1,
                1,
                32000,
                0,
                "BRG-VAL-08",
                "JTY-SUARAN",
                "CTS-BORNEO",
                CargoLayerStep.Status.COMPLETED,
                "",
                "DISCHARGED",
                False,
                dt(24, 8),
                dt(24, 18),
            ),
            (
                "VOY-PACIFIC-PRIDE",
                "AGATHIS",
                1,
                2,
                2,
                28000,
                6500,
                "BRG-NUS-17",
                "JTY-LATI",
                "CTS-JAVA",
                CargoLayerStep.Status.LOADING,
                "",
                "CTS FEED ACTIVE",
                False,
                dt(24, 19),
                dt(25, 4),
            ),
            (
                "VOY-PACIFIC-PRIDE",
                "EBONY",
                2,
                1,
                3,
                34000,
                34000,
                "BRG-KAL-22",
                "JTY-SUARAN",
                "CTS-BORNEO",
                CargoLayerStep.Status.BLOCKED,
                "Waiting for tide window at Rantau Delta",
                "TIDE GATE HOLD",
                False,
                dt(25, 6),
                dt(25, 17),
            ),
            (
                "VOY-NORTH-STAR",
                "SUNGKAI",
                2,
                2,
                1,
                26000,
                26000,
                "BRG-NUS-17",
                "JTY-LATI",
                "FC-CHLOE",
                CargoLayerStep.Status.BLOCKED,
                "Mahoni layer cannot precede Sungkai approval",
                "SEQUENCE VIOLATION",
                True,
                dt(25, 9),
                dt(25, 17),
            ),
            (
                "VOY-TRITON-STAR",
                "EBONY",
                1,
                1,
                1,
                36000,
                36000,
                "BRG-VAL-08",
                "JTY-SUARAN",
                "CTS-BORNEO",
                CargoLayerStep.Status.QUEUED,
                "Feeder delay (+4h)",
                "BARGE QUEUE",
                False,
                dt(25, 2),
                dt(25, 12),
            ),
            (
                "VOY-GOLDEN-ORIOLE",
                "MAHONI",
                1,
                1,
                1,
                42000,
                42000,
                "BRG-KAL-22",
                "JTY-SUARAN",
                "CTS-JAVA",
                CargoLayerStep.Status.PLANNED,
                "ETA not confirmed",
                "PRE-LAYCAN",
                False,
                dt(28, 6),
                dt(28, 18),
            ),
        ]
        for (
            voyage_id,
            grade,
            hatch,
            layer,
            sequence,
            required,
            remaining,
            barge,
            jetty,
            cts,
            status,
            blocking_reason,
            chain_status,
            violation,
            planned_start,
            planned_end,
        ) in layer_rows:
            CargoLayerStep.objects.update_or_create(
                voyage=voyages[voyage_id],
                required_sequence_no=sequence,
                defaults={
                    "cargo_requirement": requirements[(voyage_id, grade)],
                    "hatch_no": hatch,
                    "layer_no": layer,
                    "coal_grade": grades[grade],
                    "required_mt": required,
                    "remaining_mt": remaining,
                    "planned_barge": barges[barge],
                    "planned_jetty": jetties[jetty],
                    "planned_cts": cts_assets[cts],
                    "status": status,
                    "blocking_reason": blocking_reason,
                    "chain_status": chain_status,
                    "sequence_violation": violation,
                    "planned_start": planned_start,
                    "planned_end": planned_end,
                },
            )

        asset_windows = [
            (
                AssetAvailabilityWindow.AssetType.TUG,
                "BER-TUG-04",
                dt(24, 0),
                dt(26, 8),
                AssetAvailabilityWindow.Status.MAINTENANCE,
                "Planned maintenance at Dock 01",
            ),
            (
                AssetAvailabilityWindow.AssetType.BARGE,
                "BRG-KAL-22",
                dt(25, 0),
                dt(25, 10),
                AssetAvailabilityWindow.Status.UNAVAILABLE,
                "Awaiting bridge pass",
            ),
            (
                AssetAvailabilityWindow.AssetType.CTS,
                "CTS-JAVA",
                dt(24, 0),
                dt(29, 0),
                AssetAvailabilityWindow.Status.AVAILABLE,
                "Primary conveyor online",
            ),
        ]
        for asset_type, asset_code, start, end, status, reason in asset_windows:
            self._upsert_single(
                AssetAvailabilityWindow,
                {
                    "asset_type": asset_type,
                    "asset_code": asset_code,
                    "reason": reason,
                },
                {"window_start": start, "window_end": end, "status": status},
            )

        jetty_windows = [
            ("JTY-SUARAN", dt(24, 0), dt(26, 0), JettyAvailabilityWindow.Status.WORKING, 2800, ""),
            (
                "JTY-LATI",
                dt(24, 16),
                dt(25, 7),
                JettyAvailabilityWindow.Status.REDUCED,
                1500,
                "Shift handover and conveyor inspection",
            ),
            (
                "JTY-GMB",
                dt(25, 6),
                dt(26, 6),
                JettyAvailabilityWindow.Status.BLOCKED,
                None,
                "Silt clearance",
            ),
        ]
        for jetty, start, end, status, rate, reason in jetty_windows:
            self._upsert_single(
                JettyAvailabilityWindow,
                {"jetty": jetties[jetty], "reason": reason},
                {
                    "window_start": start,
                    "window_end": end,
                    "status": status,
                    "loading_rate_override_tph": rate,
                },
            )

        tide_rows = [
            (
                "TIDE-RANTAU-01",
                "LOC-RANTAU-DELTA",
                dt(24, 7),
                dt(24, 12),
                "2.40",
                "4.40",
                2,
                TideWindow.RiskLevel.NORMAL,
            ),
            (
                "TIDE-RANTAU-02",
                "LOC-RANTAU-DELTA",
                dt(25, 8),
                dt(25, 10),
                "2.10",
                "4.20",
                2,
                TideWindow.RiskLevel.TIGHT,
            ),
            (
                "TIDE-DEEP-01",
                "LOC-MUARA-PANTAI",
                dt(25, 18),
                dt(25, 23),
                "2.90",
                "4.80",
                3,
                TideWindow.RiskLevel.NORMAL,
            ),
        ]
        for code, location, start, end, water_level, draft, segment, risk in tide_rows:
            self._upsert_single(
                TideWindow,
                {"code": code},
                {
                    "location": locations[location],
                    "window_start": start,
                    "window_end": end,
                    "min_water_level_m": water_level,
                    "max_loaded_draft_m": draft,
                    "applicable_route_segment": segments[segment],
                    "risk_level": risk,
                    "source": "seeded_tide_calendar",
                    "is_active": True,
                },
            )

        bridge_rows = [
            (
                "BRDG-GATE-B-01",
                dt(24, 6),
                dt(24, 9),
                "12.50",
                "300ft barge",
                BridgeWindow.Status.OPEN,
                "Normal lift slot",
            ),
            (
                "BRDG-GATE-B-02",
                dt(25, 4),
                dt(25, 5),
                "10.80",
                "300ft barge",
                BridgeWindow.Status.RESTRICTED,
                "Pilot approval required",
            ),
            (
                "BRDG-GATE-B-03",
                dt(25, 9),
                dt(25, 13),
                "0.00",
                "",
                BridgeWindow.Status.CLOSED,
                "Maintenance hold",
            ),
        ]
        for code, start, end, clearance, allowed_class, status, notes in bridge_rows:
            self._upsert_single(
                BridgeWindow,
                {"code": code},
                {
                    "location": locations["LOC-BRIDGE-GATE-B"],
                    "window_start": start,
                    "window_end": end,
                    "clearance_m": clearance,
                    "allowed_asset_class": allowed_class,
                    "status": status,
                    "notes": notes,
                    "is_active": True,
                },
            )

        checks = [
            (
                "VOY-PACIFIC-PRIDE",
                "BRG-VAL-08",
                2,
                NavigationConstraintCheck.ConstraintType.TIDE,
                dt(24, 8),
                dt(24, 7),
                dt(24, 12),
                "4.10",
                118,
                NavigationConstraintCheck.Status.CAN_CROSS,
                "Proceed through Rantau Delta on current slot.",
            ),
            (
                "VOY-OCEAN-VOYAGER",
                "BRG-KAL-22",
                2,
                NavigationConstraintCheck.ConstraintType.TIDE,
                dt(25, 10, 40),
                dt(25, 8),
                dt(25, 10),
                "4.50",
                -40,
                NavigationConstraintCheck.Status.MISSED,
                "Split load or resequence against TIDE-DEEP-01.",
            ),
            (
                "VOY-NORTH-STAR",
                "BRG-NUS-17",
                1,
                NavigationConstraintCheck.ConstraintType.BRIDGE,
                dt(25, 9, 45),
                dt(25, 4),
                dt(25, 5),
                "4.00",
                -285,
                NavigationConstraintCheck.Status.MISSED,
                "Hold upstream and request next bridge lift.",
            ),
            (
                "VOY-TRITON-STAR",
                "BRG-VAL-08",
                3,
                NavigationConstraintCheck.ConstraintType.TIDE,
                dt(25, 18, 20),
                dt(25, 18),
                dt(25, 23),
                "4.60",
                22,
                NavigationConstraintCheck.Status.MARGINAL,
                "Use priority tow and reduce loading target if delayed.",
            ),
            (
                "VOY-GOLDEN-ORIOLE",
                "BRG-KAL-22",
                1,
                NavigationConstraintCheck.ConstraintType.BRIDGE,
                dt(25, 4, 25),
                dt(25, 4),
                dt(25, 5),
                "4.40",
                35,
                NavigationConstraintCheck.Status.WAITING,
                "Await pilot confirmation before dispatch.",
            ),
        ]
        for (
            voyage_id,
            asset,
            segment,
            kind,
            eta,
            window_start,
            window_end,
            draft,
            margin,
            status,
            hint,
        ) in checks:
            self._upsert_single(
                NavigationConstraintCheck,
                {
                    "voyage": voyages[voyage_id],
                    "asset_code": asset,
                    "constraint_type": kind,
                },
                {
                    "eta_gate": eta,
                    "route_segment": segments[segment],
                    "window_start": window_start,
                    "window_end": window_end,
                    "draft_m": draft,
                    "margin_minutes": margin,
                    "status": status,
                    "recovery_hint": hint,
                },
            )

        ImportJob.objects.update_or_create(
            filename="seed_ogv_demand_v1.xlsx",
            import_type=ImportJob.ImportType.OGV_DEMAND,
            defaults={
                "source": "seed_phase0",
                "status": ImportJob.Status.IMPORTED,
                "total_rows": 5,
                "valid_rows": 5,
                "error_rows": 0,
                "errors": [],
                "created_by": created_by,
            },
        )

    def _seed_schedule_data(self, *, abl, created_by):
        start_date = self._seed_start_date()
        plan_code = f"PLAN-{start_date:%Y-%m-%d}"
        approval_request_id = f"APR-{plan_code}-V1"
        baseline_plan = Plan.objects.filter(name="Berau-ABL Feasible Schedule Horizon").first()
        if baseline_plan and baseline_plan.code != plan_code:
            baseline_plan.code = plan_code
            baseline_plan.save(update_fields=["code", "updated_at"])

        plan, _ = Plan.objects.update_or_create(
            code=plan_code,
            defaults={
                "name": "Berau-ABL Feasible Schedule Horizon",
                "organization": abl,
                "horizon_start": self._seed_datetime(start_date, 0, 0),
                "horizon_end": self._seed_datetime(start_date, 7, 23, 59),
                "status": Plan.Status.ACTIVE,
            },
        )
        version, _ = PlanVersion.objects.update_or_create(
            plan=plan,
            version_no=1,
            defaults={
                "status": PlanVersion.Status.DRAFT,
                "validation_status": PlanVersion.ValidationStatus.FEASIBLE,
                "created_by": created_by,
                "summary": {},
            },
        )
        SimulationScenario.objects.filter(baseline_version=version).delete()
        ApprovalRequest.objects.filter(plan_version=version).delete()
        OverrideRequest.objects.filter(plan_version=version).delete()
        generate_plan_version(version)
        assignments = list(
            Assignment.objects.select_related("trip", "trip__voyage", "tug")
            .filter(trip__plan_version=version)
            .order_by("trip__sequence")
            .all()
        )
        first_assignment = assignments[0] if assignments else None
        first_trip = first_assignment.trip if first_assignment else None
        first_override = None
        if first_trip and first_assignment:
            OverrideRequest.objects.filter(
                plan_version=version,
                trip=first_trip,
                reason_code=OverrideRequest.ReasonCode.TUG_BREAKDOWN,
            ).delete()
            first_override = OverrideRequest.objects.create(
                plan_version=version,
                trip=first_trip,
                reason_code=OverrideRequest.ReasonCode.TUG_BREAKDOWN,
                assignment=first_assignment,
                description="Tug availability correction captured for governed replan.",
                requested_change={
                    "status": first_assignment.status,
                    "next_action": "Convert blocker to simulation before dispatch.",
                },
                before_state={
                    "tripId": first_trip.trip_id,
                    "tug": first_assignment.tug.code if first_assignment.tug else "",
                    "status": first_assignment.status,
                },
                after_state={
                    "tripId": first_trip.trip_id,
                    "status": first_assignment.status,
                    "nextAction": "Convert blocker to simulation before dispatch.",
                },
                status=OverrideRequest.Status.APPLIED,
                requested_by=created_by,
                applied_by=created_by,
                applied_at=timezone.now(),
            )

        approval_request, _ = ApprovalRequest.objects.update_or_create(
            request_id=approval_request_id,
            defaults={
                "plan_version": version,
                "status": ApprovalRequest.Status.PENDING,
                "required_authorities": [
                    ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
                    ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
                ],
                "reason": (
                    "Approval pending day: ABL has reviewed recovery impacts; "
                    "Berau sign-off remains open."
                ),
                "requested_by": created_by,
            },
        )
        ApprovalDecision.objects.update_or_create(
            approval_request=approval_request,
            authority_role=ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
            defaults={
                "decision": ApprovalDecision.Decision.APPROVE,
                "comments": "ABL dispatch accepts fleet recovery assumptions.",
                "actor": created_by,
                "organization": abl,
            },
        )
        version.status = PlanVersion.Status.PROPOSED
        version.save(update_fields=["status", "updated_at"])

        self._seed_phase2_scenario_pack(
            version=version,
            created_by=created_by,
            first_override=first_override,
        )

    def _seed_phase2_scenario_pack(self, *, version, created_by, first_override):
        assignments = list(
            Assignment.objects.select_related(
                "trip",
                "trip__voyage",
                "tug",
                "barge",
                "jetty",
                "cts",
            )
            .filter(trip__plan_version=version)
            .order_by("trip__sequence")
            .all()
        )
        if not assignments:
            return

        first_assignment = assignments[0]
        first_trip = first_assignment.trip
        second_assignment = assignments[1] if len(assignments) > 1 else first_assignment
        last_assignment = assignments[-1]
        first_tide_window = TideWindow.objects.order_by("window_start").first()
        replacement_tug = (
            Tug.objects.exclude(code=first_assignment.tug.code if first_assignment.tug else "")
            .filter(status=Tug.Status.AVAILABLE)
            .order_by("code")
            .first()
        )
        cts_assignment = next((item for item in assignments if item.cts), first_assignment)
        cts_code = cts_assignment.cts.code if cts_assignment.cts else ""

        jetty_override = self._seed_override(
            plan_version=version,
            trip=first_trip,
            assignment=first_assignment,
            reason_code=OverrideRequest.ReasonCode.JETTY_DELAY,
            description="Seeded jetty delay scenario source for Phase 2 proof.",
            actor=created_by,
        )

        scenario_specs = [
            {
                "scenario_id": "SIM-JETTY-DELAY",
                "name": "Jetty delay propagation",
                "scenario_type": "jetty_delay",
                "source_override": jetty_override,
                "source_kind": SimulationScenario.SourceKind.OVERRIDE,
                "assumptions": [
                    {
                        "kind": ScenarioAssumption.Kind.TRIP_DELAY,
                        "scope_type": ScenarioAssumption.ScopeType.TRIP,
                        "scope_id": first_trip.id,
                        "payload": {"delay_minutes": 120},
                    }
                ],
            },
            {
                "scenario_id": "SIM-TUG-OUTAGE",
                "name": "Tug outage recovery",
                "scenario_type": "tug_breakdown_recovery",
                "source_override": first_override,
                "source_kind": SimulationScenario.SourceKind.OVERRIDE,
                "assumptions": [
                    {
                        "kind": ScenarioAssumption.Kind.ASSET_OUTAGE,
                        "scope_type": ScenarioAssumption.ScopeType.ASSET,
                        "scope_id": None,
                        "payload": {"asset_code": first_assignment.tug.code},
                        "effective_from": first_trip.planned_start,
                        "effective_to": first_trip.planned_start + timedelta(hours=3),
                    }
                ] if first_assignment.tug else [],
            },
            {
                "scenario_id": "SIM-TIDE-RECOVERY",
                "name": "Tide recovery gate shift",
                "scenario_type": "tide_bridge_recovery",
                "source_kind": SimulationScenario.SourceKind.MANUAL,
                "assumptions": [
                    {
                        "kind": ScenarioAssumption.Kind.WINDOW_CHANGE,
                        "scope_type": ScenarioAssumption.ScopeType.WINDOW,
                        "scope_id": None,
                        "payload": {"window_code": first_tide_window.code},
                        "effective_from": first_trip.planned_start - timedelta(hours=2),
                        "effective_to": first_trip.planned_start - timedelta(hours=1),
                    }
                ] if first_tide_window else [],
            },
            {
                "scenario_id": "SIM-CTS-RATE",
                "name": "CTS rate degradation",
                "scenario_type": "cts_rate_degradation",
                "source_kind": SimulationScenario.SourceKind.MANUAL,
                "assumptions": [
                    {
                        "kind": ScenarioAssumption.Kind.RATE_CHANGE,
                        "scope_type": ScenarioAssumption.ScopeType.ASSET,
                        "scope_id": None,
                        "payload": {"asset_code": cts_code, "rate_tph": 950},
                        "effective_from": cts_assignment.trip.planned_start,
                        "effective_to": cts_assignment.trip.planned_end + timedelta(hours=12),
                    }
                ] if cts_code else [],
            },
            {
                "scenario_id": "SIM-TOPUP-DEMAND",
                "name": "Top-up demand queue impact",
                "scenario_type": "topup_demand_successor",
                "source_kind": SimulationScenario.SourceKind.MANUAL,
                "assumptions": [
                    {
                        "kind": ScenarioAssumption.Kind.TRIP_DELAY,
                        "scope_type": ScenarioAssumption.ScopeType.TRIP,
                        "scope_id": last_assignment.trip.id,
                        "payload": {"delay_minutes": 90},
                    },
                    {
                        "kind": ScenarioAssumption.Kind.OGV_ETA_CHANGE,
                        "scope_type": ScenarioAssumption.ScopeType.OGV,
                        "scope_id": last_assignment.trip.voyage_id,
                        "payload": {
                            "eta": (
                                last_assignment.trip.voyage.eta + timedelta(hours=6)
                            ).isoformat()
                        },
                    },
                ],
            },
            {
                "scenario_id": "SIM-MANUAL-REASSIGNMENT",
                "name": "Manual tug reassignment",
                "scenario_type": "manual_reassignment",
                "source_kind": SimulationScenario.SourceKind.MANUAL,
                "assumptions": [
                    {
                        "kind": ScenarioAssumption.Kind.MANUAL_REASSIGNMENT,
                        "scope_type": ScenarioAssumption.ScopeType.ASSIGNMENT,
                        "scope_id": first_assignment.id,
                        "payload": {
                            "assignment_id": first_assignment.id,
                            "tug_code": replacement_tug.code,
                        },
                    }
                ] if replacement_tug else [],
            },
            {
                "scenario_id": "SIM-MULTI-CANDIDATE",
                "name": "Multi-run recovery comparison",
                "scenario_type": "multi_scenario_comparison",
                "source_kind": SimulationScenario.SourceKind.MANUAL,
                "assumptions": [
                    {
                        "kind": ScenarioAssumption.Kind.TRIP_DELAY,
                        "scope_type": ScenarioAssumption.ScopeType.TRIP,
                        "scope_id": second_assignment.trip.id,
                        "payload": {"delay_minutes": 60},
                    }
                ],
                "second_run_assumptions": [
                    {
                        "kind": ScenarioAssumption.Kind.TRIP_DELAY,
                        "scope_type": ScenarioAssumption.ScopeType.TRIP,
                        "scope_id": first_trip.id,
                        "payload": {"delay_minutes": 120},
                    }
                ],
            },
        ]

        for spec in scenario_specs:
            scenario = self._create_seed_scenario(
                version=version,
                created_by=created_by,
                spec=spec,
            )
            if scenario.assumptions.exists():
                simulate_scenario(scenario=scenario, actor=created_by)
            for assumption in spec.get("second_run_assumptions", []):
                create_scenario_assumption(
                    scenario=scenario,
                    actor=created_by,
                    kind=assumption["kind"],
                    scope_type=assumption["scope_type"],
                    scope_id=assumption.get("scope_id"),
                    payload=assumption.get("payload", {}),
                    effective_from=assumption.get("effective_from"),
                    effective_to=assumption.get("effective_to"),
                )
            if spec.get("second_run_assumptions"):
                simulate_scenario(scenario=scenario, actor=created_by)

    def _seed_override(
        self,
        *,
        plan_version,
        trip,
        assignment,
        reason_code,
        description,
        actor,
    ):
        if not trip or not assignment:
            return None
        override, _ = OverrideRequest.objects.update_or_create(
            plan_version=plan_version,
            trip=trip,
            reason_code=reason_code,
            defaults={
                "assignment": assignment,
                "description": description,
                "requested_change": {
                    "status": assignment.status,
                    "next_action": "Convert source event to simulation before dispatch.",
                },
                "before_state": {
                    "tripId": trip.trip_id,
                    "status": assignment.status,
                },
                "after_state": {
                    "tripId": trip.trip_id,
                    "status": assignment.status,
                    "nextAction": "Convert source event to simulation before dispatch.",
                },
                "status": OverrideRequest.Status.APPLIED,
                "requested_by": actor,
                "applied_by": actor,
                "applied_at": timezone.now(),
            },
        )
        return override

    def _create_seed_scenario(self, *, version, created_by, spec):
        SimulationScenario.objects.filter(scenario_id=spec["scenario_id"]).delete()
        scenario = SimulationScenario.objects.create(
            scenario_id=spec["scenario_id"],
            name=spec["name"],
            scenario_type=spec["scenario_type"],
            baseline_version=version,
            scenario_version=None,
            source_conflict=None,
            source_override=spec.get("source_override"),
            source_kind=spec.get("source_kind", SimulationScenario.SourceKind.MANUAL),
            status=SimulationScenario.Status.DRAFT,
            created_by=created_by,
        )
        for assumption in spec.get("assumptions", []):
            create_scenario_assumption(
                scenario=scenario,
                actor=created_by,
                kind=assumption["kind"],
                scope_type=assumption["scope_type"],
                scope_id=assumption.get("scope_id"),
                payload=assumption.get("payload", {}),
                effective_from=assumption.get("effective_from"),
                effective_to=assumption.get("effective_to"),
            )
        return scenario
