from collections import Counter, defaultdict
from dataclasses import dataclass

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from apps.masters.models import Barge, CTSAsset, Tug
from apps.organizations.models import Organization
from apps.rbac.models import DataScope, UserRoleAssignment
from apps.rbac.services import permission_codes_for_user

from .models import (
    ApprovalRequest,
    Assignment,
    Conflict,
    OverrideRequest,
    PlanVersion,
    PublishedPlanSnapshot,
    SimulationScenario,
    Trip,
)

SEVERITY_WEIGHT = {
    Conflict.Severity.CRITICAL: 3,
    Conflict.Severity.WARNING: 2,
    Conflict.Severity.INFO: 1,
}


@dataclass(frozen=True)
class DashboardRoleShape:
    profile: str
    organization_name: str
    organization_kind: str
    data_scope: str
    sections: dict[str, bool]
    redactions: list[str]


def build_dashboard_read_model(user) -> dict:
    """Build the read-optimized situation board contract.

    The dashboard is intentionally shaped by the user's operating role. It does not
    mutate planning data and it keeps derived control-tower numbers reconciled to
    the active schedule read side.
    """

    role_shape = _role_shape_for(user)
    active_version = _latest_operational_version()
    live_snapshot = (
        PublishedPlanSnapshot.objects.select_related(
            "plan",
            "plan_version",
            "published_by",
            "approval_request",
        )
        .filter(status=PublishedPlanSnapshot.Status.ACTIVE)
        .order_by("-published_at")
        .first()
    )

    if active_version is None:
        return _empty_dashboard(role_shape=role_shape, live_snapshot=live_snapshot)

    trips = _visible_trips(active_version, role_shape)
    trip_ids = list(trips.values_list("id", flat=True))
    assignments = _visible_assignments(active_version, role_shape, trip_ids)
    conflicts = _visible_conflicts(active_version, role_shape, trip_ids)

    trip_totals = trips.aggregate(
        planned=Sum("planned_quantity_mt"),
        loaded=Sum("loaded_quantity_mt"),
    )
    planned_mt = trip_totals["planned"] or 0
    loaded_mt = trip_totals["loaded"] or 0
    remaining_mt = max(planned_mt - loaded_mt, 0)
    unresolved_conflicts = list(conflicts.filter(resolved_at__isnull=True))
    blocking_count = sum(1 for conflict in unresolved_conflicts if conflict.is_blocking)
    critical_count = sum(
        1 for conflict in unresolved_conflicts if conflict.severity == Conflict.Severity.CRITICAL
    )
    warning_count = sum(
        1 for conflict in unresolved_conflicts if conflict.severity == Conflict.Severity.WARNING
    )

    highest_risk = _highest_risk_conflict(unresolved_conflicts)
    highest_risk_ogv = _highest_risk_ogv(highest_risk, trips)
    most_constrained_resource = _most_constrained_resource(unresolved_conflicts)
    queue_pressure = _queue_pressure(assignments, conflicts)
    plan_risk = _plan_risk(
        active_version=active_version,
        highest_risk=highest_risk,
        highest_risk_ogv=highest_risk_ogv,
        most_constrained_resource=most_constrained_resource,
        blocking_count=blocking_count,
        critical_count=critical_count,
        warning_count=warning_count,
        live_snapshot=live_snapshot,
    )
    approvals = ApprovalRequest.objects.filter(plan_version=active_version)
    pending_approvals = approvals.filter(status=ApprovalRequest.Status.PENDING).count()
    scenario_count = SimulationScenario.objects.filter(baseline_version=active_version).count()
    override_count = OverrideRequest.objects.filter(plan_version=active_version).count()

    return {
        "generatedAt": timezone.now().isoformat(),
        "roleShape": {
            "profile": role_shape.profile,
            "organizationName": role_shape.organization_name,
            "organizationKind": role_shape.organization_kind,
            "dataScope": role_shape.data_scope,
            "sections": role_shape.sections,
            "redactions": role_shape.redactions,
        },
        "latestVersion": _version_payload(active_version, live_snapshot),
        "kpis": [
            {
                "key": "highestRiskOgv",
                "label": "Highest-risk OGV",
                "value": highest_risk_ogv["vesselName"],
                "detail": highest_risk_ogv["detail"],
                "tone": highest_risk_ogv["tone"],
                "href": "/schedule/ogv-demand",
            },
            {
                "key": "cargoRemainingMt",
                "label": "Cargo remaining",
                "value": remaining_mt,
                "unit": "MT",
                "detail": f"{loaded_mt:,} MT loaded of {planned_mt:,} MT planned",
                "tone": "pending" if remaining_mt else "ok",
                "href": "/schedule/coal-grade-sequence",
            },
            {
                "key": "queuePressure",
                "label": "Queue pressure",
                "value": queue_pressure["peakResource"],
                "detail": queue_pressure["summary"],
                "tone": queue_pressure["tone"],
                "href": queue_pressure["href"],
            },
            {
                "key": "currentLiveVersion",
                "label": "Live / latest version",
                "value": plan_risk["liveLabel"],
                "detail": plan_risk["publishState"],
                "tone": plan_risk["tone"],
                "href": "/schedule/published-plan",
            },
            {
                "key": "blockingConflicts",
                "label": "Open blockers",
                "value": blocking_count,
                "detail": f"{critical_count} critical / {warning_count} warning",
                "tone": "critical" if blocking_count else "ok",
                "href": "/exceptions/center",
            },
            {
                "key": "approvalPressure",
                "label": "Governance queue",
                "value": pending_approvals,
                "detail": f"{scenario_count} scenario(s), {override_count} override(s)",
                "tone": "pending" if pending_approvals else "ok",
                "href": "/approvals/publishing",
            },
        ],
        "planRisk": plan_risk,
        "queuePressure": queue_pressure,
        "conflictAggregation": _conflict_aggregation(conflicts),
        "priorityActions": _priority_actions(
            highest_risk=highest_risk,
            pending_approvals=pending_approvals,
            blocking_count=blocking_count,
            role_shape=role_shape,
        ),
        "resourceTimeline": _resource_timeline(trips, conflicts),
        "drilldowns": _drilldowns(plan_risk, queue_pressure, blocking_count),
    }


def _latest_operational_version():
    return (
        PlanVersion.objects.select_related("plan", "created_by", "source_version")
        .annotate(
            open_blockers=Count(
                "conflicts",
                filter=Q(conflicts__is_blocking=True, conflicts__resolved_at__isnull=True),
            )
        )
        .order_by(F("generated_at").desc(nulls_last=True), "-created_at")
        .first()
    )


def _role_shape_for(user) -> DashboardRoleShape:
    permissions = permission_codes_for_user(user)
    assignment = (
        UserRoleAssignment.objects.select_related("organization", "data_scope", "role")
        .filter(user=user, is_active=True, role__is_active=True)
        .order_by("id")
        .first()
    )

    if "*" in permissions or assignment is None:
        return DashboardRoleShape(
            profile="network_control",
            organization_name="Coalflow Platform",
            organization_kind=Organization.Kind.PLATFORM,
            data_scope=DataScope.ScopeType.ALL_NETWORK,
            sections=_sections(all_network=True),
            redactions=[],
        )

    organization = assignment.organization
    data_scope = assignment.data_scope.scope_type
    if organization.kind == Organization.Kind.BERAU:
        return DashboardRoleShape(
            profile="demand_control",
            organization_name=organization.name,
            organization_kind=organization.kind,
            data_scope=data_scope,
            sections=_sections(demand=True),
            redactions=["assetCommercialOwner", "fleetMaintenanceDetail"],
        )
    if organization.kind == Organization.Kind.ABL:
        return DashboardRoleShape(
            profile="dispatch_control",
            organization_name=organization.name,
            organization_kind=organization.kind,
            data_scope=data_scope,
            sections=_sections(dispatch=True),
            redactions=["customerCommercialExposure"],
        )

    return DashboardRoleShape(
        profile="network_control",
        organization_name=organization.name,
        organization_kind=organization.kind,
        data_scope=data_scope,
        sections=_sections(all_network=True),
        redactions=[],
    )


def _sections(*, all_network: bool = False, demand: bool = False, dispatch: bool = False):
    return {
        "kpiStrip": True,
        "demandRisk": all_network or demand or dispatch,
        "assetQueue": all_network or dispatch,
        "constraintRisk": True,
        "governance": all_network or demand,
        "publishedPlan": True,
    }


def _visible_trips(active_version: PlanVersion, role_shape: DashboardRoleShape):
    trips = Trip.objects.filter(plan_version=active_version).select_related(
        "plan_version",
        "plan_version__plan",
        "voyage",
        "voyage__organization",
        "cargo_requirement",
        "cargo_requirement__coal_grade",
        "cargo_layer_step",
        "cargo_layer_step__coal_grade",
        "origin_jetty",
        "assignment",
        "assignment__tug",
        "assignment__barge",
        "assignment__jetty",
        "assignment__cts",
        "assignment__owner_organization",
    )
    if role_shape.data_scope == DataScope.ScopeType.ALL_NETWORK:
        return trips
    if role_shape.organization_kind == Organization.Kind.BERAU:
        return trips.filter(voyage__organization__name=role_shape.organization_name)
    if role_shape.organization_kind == Organization.Kind.ABL:
        return trips.filter(assignment__owner_organization__name=role_shape.organization_name)
    return trips


def _visible_assignments(
    active_version: PlanVersion,
    role_shape: DashboardRoleShape,
    trip_ids: list[int],
):
    assignments = Assignment.objects.filter(
        trip__plan_version=active_version,
        trip_id__in=trip_ids,
    ).select_related(
        "trip",
        "trip__voyage",
        "tug",
        "barge",
        "jetty",
        "cts",
        "owner_organization",
    )
    if role_shape.data_scope == DataScope.ScopeType.ALL_NETWORK:
        return assignments
    if role_shape.organization_kind == Organization.Kind.ABL:
        return assignments.filter(owner_organization__name=role_shape.organization_name)
    return assignments


def _visible_conflicts(
    active_version: PlanVersion,
    role_shape: DashboardRoleShape,
    trip_ids: list[int],
):
    conflicts = Conflict.objects.filter(
        plan_version=active_version,
        trip_id__in=trip_ids,
    ).select_related(
        "trip",
        "trip__voyage",
    )
    if role_shape.data_scope == DataScope.ScopeType.ALL_NETWORK:
        return conflicts
    return conflicts.filter(trip_id__in=trip_ids)


def _highest_risk_conflict(conflicts: list[Conflict]) -> Conflict | None:
    if not conflicts:
        return None
    return sorted(
        conflicts,
        key=lambda conflict: (
            -int(conflict.is_blocking),
            -SEVERITY_WEIGHT.get(conflict.severity, 0),
            conflict.trip.sequence if conflict.trip_id else 9999,
            conflict.created_at,
        ),
    )[0]


def _highest_risk_ogv(highest_risk: Conflict | None, trips):
    if highest_risk and highest_risk.trip_id:
        return {
            "tripId": highest_risk.trip.trip_id,
            "vesselName": highest_risk.trip.voyage.vessel_name,
            "detail": highest_risk.message,
            "tone": "critical" if highest_risk.is_blocking else "pending",
        }
    trip = max(
        trips,
        key=lambda candidate: candidate.planned_quantity_mt - candidate.loaded_quantity_mt,
        default=None,
    )
    if trip is None:
        return {
            "tripId": None,
            "vesselName": "No active OGV",
            "detail": "No scheduled demand",
            "tone": "ok",
        }
    return {
        "tripId": trip.trip_id,
        "vesselName": trip.voyage.vessel_name,
        "detail": "No unresolved blocker; ranked by remaining planned tonnage.",
        "tone": "ok",
    }


def _most_constrained_resource(conflicts: list[Conflict]):
    if not conflicts:
        return {"label": "No constrained resource", "count": 0, "tone": "ok"}
    counter: Counter[str] = Counter()
    code_by_key: dict[str, str] = {}
    for conflict in conflicts:
        key = conflict.object_id or conflict.object_type or conflict.code
        counter[key] += 1
        code_by_key[key] = conflict.code
    resource, count = counter.most_common(1)[0]
    return {
        "label": resource,
        "code": code_by_key[resource],
        "count": count,
        "tone": "critical" if count > 1 else "pending",
    }


def _queue_pressure(assignments, conflicts):
    jetty_counts: Counter[str] = Counter()
    cts_counts: Counter[str] = Counter()
    tug_barge_pairs = set()
    for assignment in assignments:
        jetty_counts[assignment.jetty.code if assignment.jetty else "UNASSIGNED"] += 1
        cts_counts[assignment.cts.code if assignment.cts else "UNASSIGNED"] += 1
        if assignment.tug_id and assignment.barge_id:
            tug_barge_pairs.add((assignment.tug_id, assignment.barge_id))

    peak_jetty, peak_jetty_count = jetty_counts.most_common(1)[0] if jetty_counts else ("NONE", 0)
    peak_cts, peak_cts_count = cts_counts.most_common(1)[0] if cts_counts else ("NONE", 0)
    navigation_conflicts = conflicts.filter(
        code__in=["TIDE_WINDOW_MISSED", "BRIDGE_WINDOW_MISSED"],
        resolved_at__isnull=True,
    ).count()
    blocked_assets = conflicts.filter(
        object_type__in=["barge", "tug", "assignment"],
        resolved_at__isnull=True,
    ).count()
    tone = "critical" if blocked_assets else "pending" if navigation_conflicts else "ok"
    return {
        "peakResource": peak_jetty,
        "summary": f"{peak_jetty_count} jetty moves / {peak_cts_count} CTS moves",
        "tone": tone,
        "href": "/operations/jetty-loading",
        "jetties": [
            {"code": code, "queuedTrips": count, "tone": "critical" if count > 2 else "ok"}
            for code, count in jetty_counts.most_common()
        ],
        "cts": [
            {"code": code, "queuedTrips": count, "tone": "pending" if count > 2 else "ok"}
            for code, count in cts_counts.most_common()
        ],
        "fleet": {
            "activeTugs": assignments.exclude(tug__isnull=True).values("tug_id").distinct().count(),
            "totalTugs": Tug.objects.filter(is_active=True).count(),
            "activeBarges": assignments.exclude(barge__isnull=True)
            .values("barge_id")
            .distinct()
            .count(),
            "totalBarges": Barge.objects.filter(is_active=True).count(),
            "activeCts": assignments.exclude(cts__isnull=True).values("cts_id").distinct().count(),
            "totalCts": CTSAsset.objects.filter(is_active=True).count(),
            "tugBargePairs": len(tug_barge_pairs),
            "blockedAssets": blocked_assets,
        },
        "navigationRisk": {
            "openTideBridgeConflicts": navigation_conflicts,
            "label": (
                "High"
                if navigation_conflicts > 1
                else "Moderate"
                if navigation_conflicts
                else "Low"
            ),
        },
    }


def _plan_risk(
    *,
    active_version: PlanVersion,
    highest_risk: Conflict | None,
    highest_risk_ogv: dict,
    most_constrained_resource: dict,
    blocking_count: int,
    critical_count: int,
    warning_count: int,
    live_snapshot: PublishedPlanSnapshot | None,
):
    risk_score = min(100, critical_count * 18 + blocking_count * 12 + warning_count * 5)
    if blocking_count:
        tone = "critical"
    elif warning_count:
        tone = "pending"
    else:
        tone = "ok"
    live_label = (
        f"{live_snapshot.plan.code} V{live_snapshot.plan_version.version_no}"
        if live_snapshot
        else f"{active_version.plan.code} V{active_version.version_no}"
    )
    publish_state = "Published / live" if live_snapshot else f"Latest {active_version.status}"
    return {
        "riskScore": risk_score,
        "tone": tone,
        "blockingConflicts": blocking_count,
        "criticalConflicts": critical_count,
        "warningConflicts": warning_count,
        "highestRiskOgv": highest_risk_ogv,
        "mostConstrainedResource": most_constrained_resource,
        "firstBlockingConstraint": highest_risk.code if highest_risk else "NONE",
        "publishState": publish_state,
        "liveLabel": live_label,
    }


def _version_payload(active_version: PlanVersion, live_snapshot: PublishedPlanSnapshot | None):
    return {
        "id": active_version.id,
        "planCode": active_version.plan.code,
        "planName": active_version.plan.name,
        "versionNo": active_version.version_no,
        "status": active_version.status,
        "validationStatus": active_version.validation_status,
        "generatedAt": (
            active_version.generated_at.isoformat() if active_version.generated_at else None
        ),
        "publishedAt": (
            active_version.published_at.isoformat() if active_version.published_at else None
        ),
        "liveSnapshotId": live_snapshot.snapshot_id if live_snapshot else None,
        "liveVersionNo": live_snapshot.plan_version.version_no if live_snapshot else None,
    }


def _conflict_aggregation(conflicts):
    rows = []
    grouped = conflicts.values("code", "severity", "object_type").annotate(
        total=Count("id"),
        blocking=Count("id", filter=Q(is_blocking=True, resolved_at__isnull=True)),
    ).order_by("-blocking", "-total", "code")
    for row in grouped:
        rows.append(
            {
                "code": row["code"],
                "severity": row["severity"],
                "objectType": row["object_type"] or "plan",
                "total": row["total"],
                "blocking": row["blocking"],
                "tone": "critical" if row["blocking"] else "pending",
                "href": "/exceptions/center",
            }
        )
    return rows


def _priority_actions(
    *,
    highest_risk: Conflict | None,
    pending_approvals: int,
    blocking_count: int,
    role_shape: DashboardRoleShape,
):
    actions = []
    if highest_risk:
        actions.append(
            {
                "label": "Simulate recovery",
                "detail": highest_risk.message,
                "severity": "critical" if highest_risk.is_blocking else "warning",
                "href": "/simulation/workspace"
                if role_shape.sections.get("assetQueue")
                else "/exceptions/center",
                "sourceType": "conflict",
                "sourceId": highest_risk.id,
            }
        )
    if pending_approvals:
        actions.append(
            {
                "label": "Complete approval chain",
                "detail": f"{pending_approvals} approval request(s) pending",
                "severity": "warning",
                "href": "/approvals/publishing",
                "sourceType": "approval_request",
                "sourceId": None,
            }
        )
    if blocking_count:
        actions.append(
            {
                "label": "Clear publish blockers",
                "detail": f"{blocking_count} unresolved blocking conflict(s)",
                "severity": "critical",
                "href": "/exceptions/center",
                "sourceType": "plan_version",
                "sourceId": None,
            }
        )
    return actions[:4]


def _resource_timeline(trips, conflicts):
    conflict_by_trip = {conflict.trip_id: conflict for conflict in conflicts if conflict.trip_id}
    rows_by_category: dict[str, list[dict]] = defaultdict(list)
    for index, trip in enumerate(trips.order_by("planned_start", "sequence")):
        conflict = conflict_by_trip.get(trip.id)
        tone = "critical" if conflict and conflict.is_blocking else "pending" if conflict else "ok"
        offset = (index % 8) * 9
        width = 18 + min(26, int((trip.planned_quantity_mt or 0) / 4000))
        rows_by_category["OGV"].append(
            {
                "label": trip.voyage.vessel_name,
                "tripId": trip.trip_id,
                "status": trip.status,
                "start": trip.planned_start.isoformat(),
                "end": trip.planned_end.isoformat(),
                "tone": tone,
                "offsetPct": offset,
                "widthPct": width,
            }
        )
        assignment = getattr(trip, "assignment", None)
        if assignment:
            rows_by_category["Jetty"].append(
                {
                    "label": assignment.jetty.code if assignment.jetty else "UNASSIGNED JETTY",
                    "tripId": trip.trip_id,
                    "status": assignment.status,
                    "start": assignment.planned_departure.isoformat(),
                    "end": assignment.planned_arrival.isoformat(),
                    "tone": tone,
                    "offsetPct": min(76, offset + 3),
                    "widthPct": max(14, width - 6),
                }
            )
            rows_by_category["Tug/Barge"].append(
                {
                    "label": (
                        f"{assignment.tug.code if assignment.tug else 'NO-TUG'} / "
                        f"{assignment.barge.code if assignment.barge else 'NO-BARGE'}"
                    ),
                    "tripId": trip.trip_id,
                    "status": assignment.status,
                    "start": assignment.planned_departure.isoformat(),
                    "end": assignment.planned_arrival.isoformat(),
                    "tone": tone,
                    "offsetPct": min(76, offset + 6),
                    "widthPct": max(12, width - 8),
                }
            )
            rows_by_category["CTS"].append(
                {
                    "label": assignment.cts.code if assignment.cts else "UNASSIGNED CTS",
                    "tripId": trip.trip_id,
                    "status": assignment.status,
                    "start": assignment.planned_departure.isoformat(),
                    "end": assignment.planned_arrival.isoformat(),
                    "tone": tone,
                    "offsetPct": min(76, offset + 10),
                    "widthPct": max(10, width - 10),
                }
            )
    return [
        {"category": category, "rows": rows[:8]}
        for category, rows in rows_by_category.items()
    ]


def _drilldowns(plan_risk, queue_pressure, blocking_count: int):
    return [
        {
            "label": "Open demand board",
            "href": "/schedule/ogv-demand",
            "detail": plan_risk["highestRiskOgv"]["vesselName"],
        },
        {
            "label": "Inspect asset queue",
            "href": "/operations/tug-barge-assignment",
            "detail": queue_pressure["summary"],
        },
        {
            "label": "Review constraints",
            "href": "/constraints/tide-bridge",
            "detail": queue_pressure["navigationRisk"]["label"],
        },
        {
            "label": "Open plan contract",
            "href": "/schedule/published-plan",
            "detail": f"{blocking_count} blocker(s)",
        },
    ]


def _empty_dashboard(
    *,
    role_shape: DashboardRoleShape,
    live_snapshot: PublishedPlanSnapshot | None,
):
    return {
        "generatedAt": timezone.now().isoformat(),
        "roleShape": {
            "profile": role_shape.profile,
            "organizationName": role_shape.organization_name,
            "organizationKind": role_shape.organization_kind,
            "dataScope": role_shape.data_scope,
            "sections": role_shape.sections,
            "redactions": role_shape.redactions,
        },
        "latestVersion": None,
        "kpis": [],
        "planRisk": {
            "riskScore": 0,
            "tone": "ok",
            "blockingConflicts": 0,
            "criticalConflicts": 0,
            "warningConflicts": 0,
            "highestRiskOgv": {
                "vesselName": "No plan",
                "detail": "No active plan version",
                "tone": "ok",
            },
            "mostConstrainedResource": {
                "label": "No constrained resource",
                "count": 0,
                "tone": "ok",
            },
            "firstBlockingConstraint": "NONE",
            "publishState": "No active plan version",
            "liveLabel": live_snapshot.snapshot_id if live_snapshot else "No live plan",
        },
        "queuePressure": {
            "peakResource": "NONE",
            "summary": "No active queue",
            "tone": "ok",
            "href": "/dashboard/situation",
            "jetties": [],
            "cts": [],
            "fleet": {
                "activeTugs": 0,
                "totalTugs": Tug.objects.filter(is_active=True).count(),
                "activeBarges": 0,
                "totalBarges": Barge.objects.filter(is_active=True).count(),
                "activeCts": 0,
                "totalCts": CTSAsset.objects.filter(is_active=True).count(),
                "tugBargePairs": 0,
                "blockedAssets": 0,
            },
            "navigationRisk": {"openTideBridgeConflicts": 0, "label": "Low"},
        },
        "conflictAggregation": [],
        "priorityActions": [],
        "resourceTimeline": [],
        "drilldowns": [],
    }
