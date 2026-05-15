import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

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
from apps.rbac.models import (
    AccessPermission,
    DataScope,
    OrganizationMembership,
    Role,
    UserRoleAssignment,
)


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
            ("fleet.view", "fleet", "view", "View fleet state"),
            ("fleet.assign", "fleet", "assign", "Assign fleet resources"),
            ("masterdata.view", "masterdata", "view", "View master data"),
            ("masterdata.manage", "masterdata", "manage", "Manage master data"),
            ("audit.view", "audit", "view", "View audit events"),
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
                    permissions["masterdata.view"],
                    permissions["audit.view"],
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
                    permissions["audit.view"],
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
                    permissions["fleet.view"],
                    permissions["audit.view"],
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

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded Chunk 2 organizations, roles, users, and Berau/ABL master data."
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
