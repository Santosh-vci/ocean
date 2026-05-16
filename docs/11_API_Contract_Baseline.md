# 11 — API Contract Baseline

## Purpose

This document freezes the Phase 1 API surface required by the pilot cockpit. It is intentionally concise:
the source of truth remains Django serializers and tests, but this table gives operators and implementers a stable map.

## Common rules

- All mutation endpoints require an authenticated session and CSRF token.
- Backend permissions are authoritative; frontend route hiding is only a usability layer.
- JSON keys use the serializer contract already consumed by the React app.
- Audit-sensitive mutations record `AuditEvent` rows.

## Observability

| Endpoint | Method | Auth | Purpose |
|---|---:|---|---|
| `/api/health/` | GET | public | liveness |
| `/api/ready/` | GET | public | database/cache/export-storage readiness |
| `/api/metrics/` | GET | `admin.view` | safe count-only operational metrics |

## Authentication and RBAC

| Endpoint | Method | Permission |
|---|---:|---|
| `/api/auth/csrf/` | GET | public |
| `/api/auth/login/` | POST | public with CSRF |
| `/api/auth/logout/` | POST | authenticated |
| `/api/me/` | GET | authenticated |
| `/api/rbac/overview/` | GET | `admin.view` |
| `/api/users/`, `/api/roles/`, `/api/permissions/`, `/api/data-scopes/` | GET | `admin.view` |

## Planning

| Endpoint | Method | Permission | Notes |
|---|---:|---|---|
| `/api/planning/overview/` | GET | `schedule.view` | demand, layer, availability, navigation summary |
| `/api/planning/ogv-voyages/` | GET/POST | `schedule.view` / `schedule.edit` | OGV demand records |
| `/api/planning/cargo-requirements/` | GET/POST | `schedule.view` / `schedule.edit` | cargo grade quantities |
| `/api/planning/cargo-layer-steps/` | GET/POST | `schedule.view` / `schedule.edit` | hatch/layer sequence |
| `/api/planning/import-jobs/validate-ogv-demand/` | POST | `schedule.edit` | row validation and import audit |

## Scheduling and recovery

| Endpoint | Method | Permission | Notes |
|---|---:|---|---|
| `/api/scheduling/overview/` | GET | `schedule.view` | active plan, trips, assignments, conflicts, approvals |
| `/api/scheduling/plan-versions/{id}/generate/` | POST | `schedule.edit` | deterministic schedule generation |
| `/api/scheduling/plan-versions/{id}/clone/` | POST | `schedule.edit` | successor draft |
| `/api/scheduling/plan-versions/{id}/diff/?against={id}` | GET | `schedule.view` | version diff |
| `/api/scheduling/plan-versions/{id}/request-approval/` | POST | `schedule.edit` | approval request |
| `/api/scheduling/approval-requests/{id}/decide/` | POST | `schedule.approve` | Berau/ABL authority decision |
| `/api/scheduling/plan-versions/{id}/publish/` | POST | `schedule.publish` | immutable live snapshot |
| `/api/scheduling/assignments/{id}/apply-override/` | POST | `schedule.edit` | governed operational override |
| `/api/scheduling/scenarios/{id}/simulate/` | POST | `schedule.edit` | recovery simulation |
| `/api/scheduling/scenarios/{id}/promote/` | POST | `schedule.edit` | promote scenario output |

## Control tower and exports

| Endpoint | Method | Permission | Notes |
|---|---:|---|---|
| `/api/dashboard/situation/` | GET | `dashboard.view` | role-shaped read model |
| `/api/exports/overview/` | GET | `export.view` | export history and scope |
| `/api/exports/generate/` | POST | `export.generate` | plan/conflict/audit artifact generation |
| `/api/exports/{id}/download/` | GET | `export.view` | permission-gated artifact download |

Export generation accepts:

```json
{
  "export_type": "plan | conflict | audit",
  "export_format": "json | csv | print",
  "plan_version": 1
}
```

Export records return:

- `export_id`
- `file_name`
- `storage_bucket`
- `storage_key`
- `storage_uri`
- `checksum_sha256`
- `record_count`
- `scope`
- `download_url`

## Audit

| Endpoint | Method | Permission |
|---|---:|---|
| `/api/audit-events/` | GET | `audit.view` |
| `/api/audit-events/{id}/` | GET | `audit.view` |

Audit API output must not be treated as an export substitute. Full handoff artifacts use `/api/exports/`.
