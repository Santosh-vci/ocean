import os
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

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
    OverrideRequest,
    Plan,
    PlanVersion,
    SimulationScenario,
)
from apps.scheduling.services import clone_plan_version, generate_plan_version, simulate_scenario


class Command(BaseCommand):
    help = "Seed the baseline local-development data required by the current build."

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

        self._seed_master_data(berau=berau, abl=abl)
        self._seed_planning_data(berau=berau, abl=abl, created_by=admin_user)
        self._seed_schedule_data(abl=abl, created_by=admin_user)

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
            ("JTY-GMB", "Gurimbang Jetty", "Gurimbang BLC", 1800, 4.0, Jetty.Status.DEGRADED),
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
            ("BER-TUG-08", "Coastal Sentry 08", 2800, 36.0, "525001232", "", Tug.Status.AVAILABLE),
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
                False,
                "Power/draft ratio below rule",
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
        def dt(day, hour, minute=0):
            return timezone.make_aware(datetime(2026, 10, day, hour, minute))

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
            AssetAvailabilityWindow.objects.update_or_create(
                asset_type=asset_type,
                asset_code=asset_code,
                window_start=start,
                defaults={"window_end": end, "status": status, "reason": reason},
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
            JettyAvailabilityWindow.objects.update_or_create(
                jetty=jetties[jetty],
                window_start=start,
                defaults={
                    "window_end": end,
                    "status": status,
                    "loading_rate_override_tph": rate,
                    "reason": reason,
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
            TideWindow.objects.update_or_create(
                code=code,
                defaults={
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
            BridgeWindow.objects.update_or_create(
                code=code,
                defaults={
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
            NavigationConstraintCheck.objects.update_or_create(
                voyage=voyages[voyage_id],
                asset_code=asset,
                constraint_type=kind,
                eta_gate=eta,
                defaults={
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
        plan, _ = Plan.objects.update_or_create(
            code="PLAN-2026-10-24",
            defaults={
                "name": "Berau-ABL Feasible Schedule Horizon",
                "organization": abl,
                "horizon_start": timezone.make_aware(datetime(2026, 10, 24, 0, 0)),
                "horizon_end": timezone.make_aware(datetime(2026, 10, 31, 23, 59)),
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
        first_assignment = (
            Assignment.objects.select_related("trip", "trip__voyage", "tug")
            .filter(trip__plan_version=version)
            .order_by("trip__sequence")
            .first()
        )
        first_trip = first_assignment.trip if first_assignment else None
        first_conflict = version.conflicts.select_related("trip", "trip__voyage").first()
        if first_trip and first_assignment:
            OverrideRequest.objects.filter(
                plan_version=version,
                trip=first_trip,
                reason_code=OverrideRequest.ReasonCode.TUG_BREAKDOWN,
            ).delete()
            OverrideRequest.objects.create(
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
            request_id="APR-PLAN-2026-10-24-V1",
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

        scenario_version = PlanVersion.objects.filter(plan=plan, version_no=2).first()
        if scenario_version is None:
            scenario_version = clone_plan_version(source_version=version, created_by=created_by)
        scenario, _ = SimulationScenario.objects.update_or_create(
            scenario_id="SIM-PLAN-2026-10-24-A",
            defaults={
                "name": "Tug reassignment A",
                "scenario_type": "tug_breakdown_recovery",
                "baseline_version": version,
                "scenario_version": scenario_version,
                "source_conflict": first_conflict,
                "status": SimulationScenario.Status.SIMULATED,
                "created_by": created_by,
            },
        )
        simulate_scenario(scenario=scenario)
