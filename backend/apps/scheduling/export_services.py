from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import StringIO
from uuid import uuid4

from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.core.object_storage import put_export_object
from apps.organizations.models import Organization
from apps.rbac.models import DataScope, UserRoleAssignment
from apps.rbac.services import user_has_permission_code

from .models import Conflict, ExportJob, PlanVersion, Trip


@dataclass(frozen=True)
class ExportScope:
    scope_type: str
    label: str
    organization: Organization | None
    redactions: tuple[str, ...]

    @property
    def is_all_network(self) -> bool:
        return self.scope_type == DataScope.ScopeType.ALL_NETWORK

    def as_payload(self) -> dict:
        return {
            "scope_type": self.scope_type,
            "label": self.label,
            "organization_id": self.organization.id if self.organization else None,
            "organization_name": self.organization.name if self.organization else None,
            "redactions": list(self.redactions),
        }


EXPORT_TYPE_LABELS = {
    ExportJob.ExportType.PLAN: "Published plan and schedule handoff",
    ExportJob.ExportType.CONFLICT: "Open conflict register",
    ExportJob.ExportType.SCENARIO_DIFF: "Scenario diff evidence pack",
    ExportJob.ExportType.AUDIT: "Audit evidence pack",
}

CONTENT_TYPES = {
    ExportJob.ExportFormat.JSON: "application/json",
    ExportJob.ExportFormat.CSV: "text/csv",
    ExportJob.ExportFormat.PRINT: "text/plain",
}


def export_scope_for_user(user) -> ExportScope:
    if user.is_superuser:
        return ExportScope(
            scope_type=DataScope.ScopeType.ALL_NETWORK,
            label="All network",
            organization=None,
            redactions=(),
        )

    assignments = list(
        UserRoleAssignment.objects.filter(user=user, is_active=True, role__is_active=True)
        .select_related("organization", "data_scope", "data_scope__organization")
        .all()
    )
    if any(
        assignment.data_scope.scope_type == DataScope.ScopeType.ALL_NETWORK
        for assignment in assignments
    ):
        return ExportScope(
            scope_type=DataScope.ScopeType.ALL_NETWORK,
            label="All network",
            organization=None,
            redactions=(),
        )

    scoped_assignment = next(
        (
            assignment
            for assignment in assignments
            if assignment.data_scope.organization_id or assignment.organization_id
        ),
        None,
    )
    if scoped_assignment is None:
        return ExportScope(
            scope_type=DataScope.ScopeType.ASSIGNED_ONLY,
            label="Assigned-only",
            organization=None,
            redactions=("full_network_export",),
        )

    organization = scoped_assignment.data_scope.organization or scoped_assignment.organization
    return ExportScope(
        scope_type=DataScope.ScopeType.ORGANIZATION,
        label=f"{organization.name} scope",
        organization=organization,
        redactions=("full_network_export", "cross_party_audit_events"),
    )


def export_jobs_visible_to_user(user) -> QuerySet[ExportJob]:
    queryset = ExportJob.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "organization",
        "created_by",
    )
    if user.is_superuser:
        return queryset

    assignments = list(
        UserRoleAssignment.objects.filter(user=user, is_active=True, role__is_active=True)
        .select_related("organization", "data_scope", "data_scope__organization")
        .all()
    )
    if any(
        assignment.data_scope.scope_type == DataScope.ScopeType.ALL_NETWORK
        for assignment in assignments
    ):
        return queryset

    organization_ids = {
        assignment.data_scope.organization_id or assignment.organization_id
        for assignment in assignments
        if assignment.data_scope.organization_id or assignment.organization_id
    }
    return queryset.filter(Q(created_by=user) | Q(organization_id__in=organization_ids))


def export_overview_for_user(user) -> dict:
    queryset = export_jobs_visible_to_user(user)
    counts = queryset.aggregate(
        total=Count("id"),
        plan=Count("id", filter=Q(export_type=ExportJob.ExportType.PLAN)),
        conflict=Count("id", filter=Q(export_type=ExportJob.ExportType.CONFLICT)),
        scenario_diff=Count("id", filter=Q(export_type=ExportJob.ExportType.SCENARIO_DIFF)),
        audit=Count("id", filter=Q(export_type=ExportJob.ExportType.AUDIT)),
    )
    scope = export_scope_for_user(user)
    return {
        "summary": {
            "total": counts["total"] or 0,
            "plan": counts["plan"] or 0,
            "conflict": counts["conflict"] or 0,
            "scenario_diff": counts["scenario_diff"] or 0,
            "audit": counts["audit"] or 0,
        },
        "scope": scope.as_payload(),
        "canGenerate": user_has_permission_code(user, "export.generate"),
        "allowedTypes": [
            {"value": value, "label": EXPORT_TYPE_LABELS[value]}
            for value in (
                ExportJob.ExportType.PLAN,
                ExportJob.ExportType.CONFLICT,
                ExportJob.ExportType.SCENARIO_DIFF,
                ExportJob.ExportType.AUDIT,
            )
        ],
        "allowedFormats": [
            ExportJob.ExportFormat.JSON,
            ExportJob.ExportFormat.CSV,
            ExportJob.ExportFormat.PRINT,
        ],
    }


def create_governed_export(
    *,
    actor,
    export_type: str,
    export_format: str = ExportJob.ExportFormat.JSON,
    plan_version: PlanVersion | None = None,
    request=None,
) -> ExportJob:
    if not user_has_permission_code(actor, "export.generate"):
        raise PermissionDenied("You do not have permission to generate governed exports.")

    if export_type not in ExportJob.ExportType.values:
        raise ValidationError({"export_type": "Unsupported export type."})
    if export_format not in ExportJob.ExportFormat.values:
        raise ValidationError({"export_format": "Unsupported export format."})

    if export_type != ExportJob.ExportType.AUDIT and plan_version is None:
        plan_version = _latest_plan_version()
    if export_type != ExportJob.ExportType.AUDIT and plan_version is None:
        raise ValidationError({"plan_version": "No plan version is available for export."})

    scope = export_scope_for_user(actor)
    payload, record_count = _build_payload(
        export_type=export_type,
        plan_version=plan_version,
        scope=scope,
    )
    content = _render_payload(
        export_type=export_type,
        export_format=export_format,
        payload=payload,
    )
    now = timezone.now()
    extension = "txt" if export_format == ExportJob.ExportFormat.PRINT else export_format
    file_name = _file_name(
        export_type=export_type,
        export_format=extension,
        plan_version=plan_version,
        scope=scope,
        now=now,
    )
    storage_key = f"exports/{export_type}/{now:%Y/%m/%d}/{uuid4().hex}-{file_name}"
    stored_object = put_export_object(key=storage_key, content=content)
    export_id = f"EXP-{export_type.upper()}-{now:%Y%m%d%H%M%S}-{uuid4().hex[:6].upper()}"

    export_job = ExportJob.objects.create(
        export_id=export_id,
        export_type=export_type,
        export_format=export_format,
        status=ExportJob.Status.GENERATED,
        plan_version=plan_version,
        organization=None if scope.is_all_network else scope.organization,
        storage_bucket=stored_object.bucket,
        storage_key=stored_object.key,
        file_name=file_name,
        content_type=CONTENT_TYPES[export_format],
        checksum_sha256=stored_object.checksum_sha256,
        size_bytes=stored_object.size_bytes,
        record_count=record_count,
        scope=scope.as_payload(),
        payload=payload,
        created_by=actor,
    )

    record_audit_event(
        actor=actor,
        organization=export_job.organization,
        action="export.generated",
        object_type="export_job",
        object_id=export_job.export_id,
        object_repr=export_job.file_name,
        metadata={
            "export_type": export_job.export_type,
            "export_format": export_job.export_format,
            "record_count": export_job.record_count,
            "storage_bucket": export_job.storage_bucket,
            "storage_key": export_job.storage_key,
            "checksum_sha256": export_job.checksum_sha256,
            "scope": export_job.scope,
        },
        request=request,
    )
    return export_job


def _latest_plan_version() -> PlanVersion | None:
    return (
        PlanVersion.objects.select_related("plan", "created_by")
        .order_by("-published_at", "-generated_at", "-created_at")
        .first()
    )


def _build_payload(
    *,
    export_type: str,
    plan_version: PlanVersion | None,
    scope: ExportScope,
) -> tuple[dict, int]:
    generated_at = timezone.now().isoformat()
    base_payload = {
        "generatedAt": generated_at,
        "exportType": export_type,
        "scope": scope.as_payload(),
    }

    if export_type == ExportJob.ExportType.PLAN:
        assert plan_version is not None
        return _plan_payload(base_payload=base_payload, plan_version=plan_version, scope=scope)
    if export_type == ExportJob.ExportType.CONFLICT:
        assert plan_version is not None
        return _conflict_payload(base_payload=base_payload, plan_version=plan_version, scope=scope)
    if export_type == ExportJob.ExportType.SCENARIO_DIFF:
        assert plan_version is not None
        return _scenario_diff_payload(
            base_payload=base_payload,
            plan_version=plan_version,
        )
    return _audit_payload(base_payload=base_payload, scope=scope)


def _scoped_trips(plan_version: PlanVersion, scope: ExportScope) -> QuerySet[Trip]:
    queryset = (
        Trip.objects.filter(plan_version=plan_version)
        .select_related(
            "plan_version",
            "plan_version__plan",
            "voyage",
            "voyage__organization",
            "cargo_layer_step",
            "cargo_layer_step__coal_grade",
            "origin_jetty",
            "destination_location",
            "assignment",
            "assignment__tug",
            "assignment__barge",
            "assignment__jetty",
            "assignment__cts",
            "assignment__owner_organization",
        )
        .prefetch_related("events")
    )
    if scope.is_all_network or scope.organization is None:
        return queryset
    return queryset.filter(
        Q(voyage__organization=scope.organization)
        | Q(assignment__owner_organization=scope.organization)
    ).distinct()


def _plan_payload(
    *,
    base_payload: dict,
    plan_version: PlanVersion,
    scope: ExportScope,
) -> tuple[dict, int]:
    trips = list(_scoped_trips(plan_version, scope).order_by("sequence", "trip_id"))
    payload = {
        **base_payload,
        "plan": {
            "code": plan_version.plan.code,
            "name": plan_version.plan.name,
            "versionNo": plan_version.version_no,
            "status": plan_version.status,
            "validationStatus": plan_version.validation_status,
            "publishedAt": _iso(plan_version.published_at),
            "generatedAt": _iso(plan_version.generated_at),
        },
        "summary": {
            "tripCount": len(trips),
            "plannedMt": sum(trip.planned_quantity_mt for trip in trips),
            "loadedMt": sum(trip.loaded_quantity_mt for trip in trips),
        },
        "scenarioLineage": plan_version.summary.get("scenarioLineage"),
        "scenarioDiff": plan_version.summary.get("scenarioDiff"),
        "trips": [_trip_row(trip) for trip in trips],
    }
    return payload, len(trips)


def _conflict_payload(
    *,
    base_payload: dict,
    plan_version: PlanVersion,
    scope: ExportScope,
) -> tuple[dict, int]:
    scoped_trip_ids = _scoped_trips(plan_version, scope).values_list("id", flat=True)
    conflicts = (
        Conflict.objects.filter(plan_version=plan_version)
        .select_related("trip", "trip__voyage")
        .order_by("-is_blocking", "severity", "code")
    )
    if not scope.is_all_network:
        conflicts = conflicts.filter(trip_id__in=scoped_trip_ids)
    rows = [_conflict_row(conflict) for conflict in conflicts]
    payload = {
        **base_payload,
        "plan": {
            "code": plan_version.plan.code,
            "versionNo": plan_version.version_no,
        },
        "summary": {
            "conflictCount": len(rows),
            "blockingCount": sum(1 for row in rows if row["isBlocking"]),
            "criticalCount": sum(
                1 for row in rows if row["severity"] == Conflict.Severity.CRITICAL
            ),
        },
        "conflicts": rows,
    }
    return payload, len(rows)


def _scenario_diff_payload(
    *,
    base_payload: dict,
    plan_version: PlanVersion,
) -> tuple[dict, int]:
    scenario_lineage = plan_version.summary.get("scenarioLineage")
    scenario_diff = plan_version.summary.get("scenarioDiff")
    if not scenario_lineage or not scenario_diff:
        raise ValidationError(
            {"plan_version": "Selected plan version does not carry promoted scenario lineage."}
        )
    rows = scenario_diff.get("rows", [])
    payload = {
        **base_payload,
        "plan": {
            "code": plan_version.plan.code,
            "versionNo": plan_version.version_no,
            "status": plan_version.status,
        },
        "scenarioLineage": scenario_lineage,
        "summary": scenario_diff.get("summary", {}),
        "rows": rows,
    }
    return payload, len(rows)


def _audit_payload(*, base_payload: dict, scope: ExportScope) -> tuple[dict, int]:
    events = AuditEvent.objects.select_related("actor", "organization").order_by("-created_at")
    if not scope.is_all_network:
        if scope.organization is None:
            events = events.none()
        else:
            events = events.filter(organization=scope.organization)
    rows = [_audit_row(event) for event in events[:250]]
    payload = {
        **base_payload,
        "summary": {
            "eventCount": len(rows),
            "limitedToLatest": 250,
        },
        "events": rows,
    }
    return payload, len(rows)


def _render_payload(*, export_type: str, export_format: str, payload: dict) -> bytes:
    if export_format == ExportJob.ExportFormat.JSON:
        return json.dumps(payload, indent=2, sort_keys=True).encode()
    if export_format == ExportJob.ExportFormat.PRINT:
        return _render_printable(export_type, payload).encode()
    return _render_csv(export_type, payload).encode()


def _render_csv(export_type: str, payload: dict) -> str:
    rows_key = {
        ExportJob.ExportType.PLAN: "trips",
        ExportJob.ExportType.CONFLICT: "conflicts",
        ExportJob.ExportType.SCENARIO_DIFF: "rows",
        ExportJob.ExportType.AUDIT: "events",
    }[export_type]
    rows = payload.get(rows_key, [])
    headers = {
        ExportJob.ExportType.PLAN: [
            "tripId",
            "sequence",
            "vesselName",
            "voyageId",
            "coalGrade",
            "plannedQuantityMt",
            "loadedQuantityMt",
            "plannedStart",
            "plannedEnd",
            "tug",
            "barge",
            "jetty",
            "cts",
            "status",
        ],
        ExportJob.ExportType.CONFLICT: [
            "code",
            "severity",
            "tripId",
            "vesselName",
            "message",
            "isBlocking",
            "resolvedAt",
        ],
        ExportJob.ExportType.SCENARIO_DIFF: [
            "key",
            "state",
            "sourceTrip",
            "targetTrip",
            "sourceVessel",
            "targetVessel",
            "delayDeltaMinutes",
            "quantityDeltaMt",
        ],
        ExportJob.ExportType.AUDIT: [
            "createdAt",
            "actor",
            "organization",
            "action",
            "objectType",
            "objectId",
            "objectRepr",
        ],
    }[export_type]
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _render_printable(export_type: str, payload: dict) -> str:
    lines = [
        "COALFLOW GOVERNED EXPORT",
        f"Type: {EXPORT_TYPE_LABELS[export_type]}",
        f"Generated: {payload['generatedAt']}",
        f"Scope: {payload['scope']['label']}",
        "",
    ]
    if export_type == ExportJob.ExportType.PLAN:
        plan = payload["plan"]
        lines += [
            f"Plan: {plan['code']} V{plan['versionNo']} ({plan['status']})",
            (
                f"Trips: {payload['summary']['tripCount']} | "
                f"Planned MT: {payload['summary']['plannedMt']}"
            ),
            "-" * 96,
        ]
        for trip in payload["trips"]:
            lines.append(
                f"{trip['sequence']:02d} {trip['tripId']} | {trip['vesselName']} | "
                f"{trip['coalGrade']} | {trip['plannedQuantityMt']} MT | "
                f"{trip['plannedStart']} -> {trip['plannedEnd']} | "
                f"{trip['tug']}/{trip['barge']} | {trip['status']}"
            )
        return "\n".join(lines) + "\n"

    if export_type == ExportJob.ExportType.SCENARIO_DIFF:
        plan = payload["plan"]
        lineage = payload["scenarioLineage"]
        summary = payload["summary"]
        lines += [
            f"Plan: {plan['code']} V{plan['versionNo']} ({plan['status']})",
            f"Scenario: {lineage['scenarioId']} | Run: {lineage['selectedRunRef']}",
            (
                f"Changed trips: {summary.get('changedTripCount', 0)} | "
                f"Delay delta: {summary.get('delayDeltaMinutes', 0)} minutes"
            ),
            "-" * 96,
        ]
        for row in payload["rows"]:
            lines.append(
                f"{row['state']} {row.get('sourceTrip', '-')} -> {row.get('targetTrip', '-')} | "
                f"delay {row.get('delayDeltaMinutes', 0)}m | "
                f"qty {row.get('quantityDeltaMt', 0)} MT"
            )
        return "\n".join(lines) + "\n"

    rows_key = "conflicts" if export_type == ExportJob.ExportType.CONFLICT else "events"
    for row in payload.get(rows_key, []):
        lines.append(" | ".join(str(value) for value in row.values()))
    return "\n".join(lines) + "\n"


def _file_name(
    *,
    export_type: str,
    export_format: str,
    plan_version: PlanVersion | None,
    scope: ExportScope,
    now,
) -> str:
    scope_slug = (
        "all-network"
        if scope.is_all_network
        else (scope.organization.slug if scope.organization else "scoped")
    )
    if plan_version is None:
        base = f"coalflow-{export_type}-{scope_slug}-{now:%Y%m%d%H%M%S}"
    else:
        base = (
            f"coalflow-{export_type}-{plan_version.plan.code.lower()}-v"
            f"{plan_version.version_no}-{scope_slug}-{now:%Y%m%d%H%M%S}"
        )
    return f"{base}.{export_format}"


def _trip_row(trip: Trip) -> dict:
    assignment = getattr(trip, "assignment", None)
    coal_grade = trip.cargo_layer_step.coal_grade.code if trip.cargo_layer_step else ""
    return {
        "tripId": trip.trip_id,
        "sequence": trip.sequence,
        "vesselName": trip.voyage.vessel_name,
        "voyageId": trip.voyage.voyage_id,
        "customerName": trip.voyage.customer_name,
        "coalGrade": coal_grade,
        "plannedQuantityMt": trip.planned_quantity_mt,
        "loadedQuantityMt": trip.loaded_quantity_mt,
        "plannedStart": _iso(trip.planned_start),
        "plannedEnd": _iso(trip.planned_end),
        "originJetty": trip.origin_jetty.code if trip.origin_jetty else "",
        "destination": trip.destination_location.name if trip.destination_location else "",
        "tug": assignment.tug.code if assignment and assignment.tug else "",
        "barge": assignment.barge.code if assignment and assignment.barge else "",
        "jetty": assignment.jetty.code if assignment and assignment.jetty else "",
        "cts": assignment.cts.code if assignment and assignment.cts else "",
        "ownerOrganization": (
            assignment.owner_organization.name
            if assignment and assignment.owner_organization
            else ""
        ),
        "nextConstraint": assignment.next_constraint if assignment else "",
        "nextAction": assignment.next_action if assignment else "",
        "status": trip.status,
    }


def _conflict_row(conflict: Conflict) -> dict:
    return {
        "code": conflict.code,
        "severity": conflict.severity,
        "tripId": conflict.trip.trip_id if conflict.trip else "",
        "vesselName": conflict.trip.voyage.vessel_name if conflict.trip else "",
        "objectType": conflict.object_type,
        "objectId": conflict.object_id,
        "message": conflict.message,
        "isBlocking": conflict.is_blocking,
        "resolvedAt": _iso(conflict.resolved_at),
        "createdAt": _iso(conflict.created_at),
    }


def _audit_row(event: AuditEvent) -> dict:
    return {
        "createdAt": _iso(event.created_at),
        "actor": event.actor.email if event.actor else "system",
        "organization": event.organization.name if event.organization else "",
        "action": event.action,
        "objectType": event.object_type,
        "objectId": event.object_id,
        "objectRepr": event.object_repr,
        "requestId": str(event.request_id) if event.request_id else "",
    }


def _iso(value) -> str | None:
    return value.isoformat() if value else None
