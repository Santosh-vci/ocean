# 04 — RBAC and Django Architecture Addendum

## 1. Purpose of this addendum

This addendum extends the Berau–ABL scheduling simulation exploration pack with the recommended application architecture and role-based access-control model.

The scheduling and live-planning tool will be used by multiple organizations and functional teams, including upstream coal production/scheduling users, ABL/AGPL fleet and transshipment users, jetty teams, control-tower users, maintenance teams, commercial users, and selected customer-facing users. Because these users will interact with the same operational network but with different authority levels, RBAC must be treated as a core business capability, not a later admin feature.

## 2. Recommended backend architecture

The recommended architecture is:

```text
Django + Django REST Framework
PostgreSQL
Redis
Celery
ClickHouse or TimescaleDB for GPS/AIS/time-series history
React or Next.js frontend
MQTT / Kafka / Redpanda event layer for IoT and live movement feeds
```

Django is preferred because this product is not only a live map or analytics dashboard. It is an operations system of record with users, organizations, roles, planning versions, approvals, overrides, audit trails, master data, and transactional workflow governance.

FastAPI can still be used later for high-throughput ingestion services, but Django should remain the core platform for RBAC-heavy workflow management.

## 3. Why Django is suitable

Django is suitable for this project because the platform requires:

- multi-organization user management;
- strong admin and master-data controls;
- role, permission, and object-scope enforcement;
- transactional schedule planning and versioning;
- approval workflows;
- manual override capture;
- audit logs;
- operational event history;
- background simulation jobs;
- integration with GPS/AIS/IoT feeds;
- controlled exposure of data to different business parties.

The system should be API-first using Django REST Framework, with a separate frontend for the control-tower experience.

## 4. High-level system layout

```text
Frontend / Control Tower
        |
        v
Django REST API
        |
        +-- PostgreSQL: system of record
        +-- Redis: cache, locks, live state
        +-- Celery: background simulation and alert jobs
        +-- ClickHouse / TimescaleDB: GPS, AIS, telemetry, time-series history
        +-- MQTT / Kafka / Redpanda: IoT and event ingestion
        +-- Object Storage: reports, raw payloads, generated files
```

## 5. Suggested Django app structure

```text
backend/
  apps/
    accounts/
    organizations/
    rbac/
    masters/
    fleet/
    coal/
    ogv/
    jetties/
    routes/
    constraints/
    scheduling/
    simulation/
    live_tracking/
    iot_events/
    alerts/
    approvals/
    audit/
    reports/
    integrations/
```

Each app should have clear ownership. Scheduling logic should not be mixed with user management. Live tracking should not directly mutate approved schedules without passing through the scheduling/event workflow.

## 6. Multi-organization model

The system should support multiple organizations from day one.

Core entities:

```text
Organization
BusinessUnit
Department
User
Role
Permission
UserRoleAssignment
OrganizationRelationship
SharedOperation
SharedSchedule
DataAccessPolicy
```

Example organization categories:

- Berau Coal Energy / upstream production and coal scheduling teams;
- ABL / AGPL transshipment and fleet operating teams;
- customer organizations;
- port, jetty, and support-service organizations;
- platform administrators.

The logic should not hardcode one company as the owner of the whole system. Instead, ownership should be defined at object and workflow level.

## 7. RBAC design principle

The access model should combine three layers:

### Layer 1 — Feature permission

Controls what module or action the user can access.

Examples:

- view schedule;
- edit schedule;
- run simulation;
- create scenario;
- approve schedule;
- assign tug/barge;
- confirm loading;
- publish ETA;
- manage fleet;
- manage users;
- export data.

### Layer 2 — Data scope

Controls which data the user can access.

Examples:

- all Berau data;
- all ABL data;
- assigned jetty only;
- assigned vessel only;
- assigned OGV only;
- own customer shipment only;
- read-only network view.

### Layer 3 — Workflow authority

Controls what operational decision the user can make.

Examples:

- propose a schedule;
- lock a schedule;
- approve a plan;
- override a constraint;
- mark vessel breakdown;
- confirm dispatch;
- close loading event;
- publish customer ETA.

This layered model is necessary because a user may be allowed to see a schedule but not change, approve, override, or publish it.

## 8. Example RBAC matrix

| Function | Berau Planner | ABL/AGPL Dispatcher | Jetty Operator | Customer Viewer | Admin |
|---|---:|---:|---:|---:|---:|
| View OGV schedule | Yes | Yes | Limited | Own shipment only | Yes |
| Edit OGV demand | Yes | No | No | No | Yes |
| View fleet status | Yes | Yes | Limited | Shipment only | Yes |
| Assign tug/barge | Propose / limited | Yes | No | No | Yes |
| Confirm jetty loading | View only | View only | Yes | No | Yes |
| Run what-if simulation | Yes | Yes | No | No | Yes |
| Approve final plan | Role-based | Role-based | No | No | Yes |
| View live map | Yes | Yes | Assigned area | Own shipment only | Yes |
| View commercial risk | Yes | Limited | No | Limited | Yes |
| Manage users | Tenant admin only | Tenant admin only | No | No | Super admin |

## 9. Role groups to define upfront

### Berau-side roles

- Berau Super Admin
- Berau Demand Planner
- Berau Coal Quality Planner
- Berau Jetty Coordinator
- Berau Commercial Viewer
- Berau Executive Viewer

### ABL/AGPL-side roles

- ABL/AGPL Super Admin
- ABL/AGPL Fleet Dispatcher
- ABL/AGPL CTS Coordinator
- ABL/AGPL Tug/Barge Operator
- ABL/AGPL Maintenance Coordinator
- ABL/AGPL Operations Manager
- ABL/AGPL Commercial Viewer

### Shared control-tower roles

- Joint Control Tower Manager
- Exception Manager
- Simulation Analyst
- Read-only Network Viewer

### Customer roles

- Customer Shipment Viewer
- Customer ETA Viewer
- Customer Document Viewer

### System roles

- Platform Super Admin
- Integration Admin
- Device Admin
- Auditor

## 10. Planning workflow governance

The planning workflow should be versioned and approval-driven.

Recommended lifecycle:

```text
Draft Plan
   ↓
Simulated Plan
   ↓
Proposed Plan
   ↓
Joint Review
   ↓
Approved Plan
   ↓
Published Plan
   ↓
Live Execution
   ↓
Exception / Replan
   ↓
Revised Approved Plan
```

Every plan change should record:

- who changed it;
- what changed;
- why it changed;
- previous value;
- new value;
- timestamp;
- impacted OGV, vessel, jetty, CTS, customer, or coal grade;
- whether the change was system-generated or manually overridden;
- whether the change required approval.

## 11. Database split

### PostgreSQL

PostgreSQL should remain the system of record for:

- users;
- organizations;
- roles and permissions;
- vessels;
- jetties;
- OGV demand;
- coal grades;
- schedules;
- planning versions;
- approvals;
- assignments;
- alerts;
- audit logs.

### ClickHouse or TimescaleDB

A time-series/analytical store should be used for:

- GPS pings;
- AIS messages;
- vessel telemetry;
- geofence events;
- speed history;
- route history;
- device health logs;
- performance dashboards.

For simpler early operations, PostgreSQL plus TimescaleDB is easier. For large historical analytics and heavy dashboarding, PostgreSQL plus ClickHouse is preferred.

## 12. Backend service design

Django should own the core transactional platform:

```text
Django Core Backend
  ├── User/RBAC
  ├── Master data
  ├── Scheduling workflow
  ├── Simulation orchestration
  ├── Approval workflow
  ├── Audit trail
  └── API layer
```

Celery workers should handle background processing:

```text
Celery Workers
  ├── Run schedule simulation
  ├── Recalculate ETA
  ├── Generate alerts
  ├── Process GPS/AIS batches
  ├── Rebuild KPIs
  └── Generate reports
```

A separate ingestion service can be introduced for high-volume live feeds:

```text
IoT/AIS Ingestion Service
  ├── MQTT / HTTP / TCP listener
  ├── Raw payload validation
  ├── Asset matching
  ├── Geofence detection
  ├── Event generation
  └── Push to Django/event stream
```

## 13. Frontend recommendation

Use a separate React or Next.js frontend.

Core UI modules:

- control tower dashboard;
- live fleet map;
- OGV schedule board;
- tug/barge assignment board;
- jetty loading board;
- CTS queue board;
- tide/bridge window board;
- exception center;
- simulation comparison screen;
- approval workflow screen;
- customer ETA portal;
- admin/RBAC console.

The frontend should not be only a vessel map. The primary workspace should be a planning board, exception cockpit, simulation comparison screen, and approval console.

## 14. Security and access-control requirements

Plan the following upfront:

| Security requirement | Recommendation |
|---|---|
| Authentication | Username/password for MVP; SSO/SAML/OIDC later |
| Organization isolation | Tenant-aware data access |
| Role permissions | Django groups plus custom role assignments |
| Object-level permissions | Required |
| API authorization | Enforce in service/API layer, not only frontend |
| Audit trail | Mandatory |
| Approval signatures | Required for published plans |
| Session/device logs | Recommended |
| Export control | Limit CSV/Excel downloads by role |
| Customer access | Separate restricted portal |
| Data masking | Mask commercial fields for operational users |
| Admin action logging | Mandatory |

## 15. Access-control enforcement stack

Do not enforce RBAC only at the UI level.

Use layered enforcement:

```text
UI Route Permission
    ↓
API Endpoint Permission
    ↓
Service Method Permission
    ↓
Object/Data Scope Permission
    ↓
Audit Logging
```

Example: a user may access the schedule screen but may still be blocked from editing Berau demand, assigning ABL/AGPL tugs, viewing customer commercial fields, overriding tide constraints, or exporting the complete schedule.

## 16. MVP architecture recommendation

For the first production-grade MVP:

```text
Django + Django REST Framework
PostgreSQL
Redis
Celery
React / Next.js
Docker Compose
Basic GPS/AIS ingestion API
Role + organization + object-scope RBAC
Schedule versioning
Manual override audit
```

Later extensions:

```text
ClickHouse
MQTT broker
Kafka / Redpanda
Edge gateway sync
Advanced optimizer
SSO
Mobile/tablet mode
```

## 17. Final recommendation

Use Django as the core backend.

The reason is simple: the product is a multi-organization, permission-heavy, audit-heavy, workflow-heavy operational planning platform. Django provides a strong foundation for this while still allowing Python-based simulation and optimization engines around it.

The long-term architecture should be:

```text
Django Core Platform
+ Python Simulation Engine
+ Event/IoT Ingestion Layer
+ Time-Series Store
+ React Control Tower
+ Strong RBAC and Audit Layer
```

RBAC should be part of the core domain model because Berau, ABL/AGPL, customers, jetty teams, dispatchers, maintenance, commercial users, and control-tower users will all interact with the same operational network from different authority levels.
