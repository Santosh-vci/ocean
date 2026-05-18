# 20 - Phase 4 Implementation Spec

**Status:** draft implementation specification for product Phase 4  
**Phase:** IoT/event-driven operations  
**Primary goal:** convert live field/device evidence into trusted operational events that can update actual execution state without letting noisy telemetry mutate the schedule silently.

---

## 1. Executive Summary

Phase 3 proved GPS/AIS-shaped telemetry, geofence events, ETA variance, tracking alerts, and observed-delay scenario handoff. Phase 4 must add the missing trust layer: **operator/device confirmation of real operational milestones**.

The key product distinction is:

- Phase 3 says: "The system observed evidence that something probably happened."
- Phase 4 says: "An authorized source confirmed this operational event, and the plan actuals/audit trail now reflect it."

Phase 4 should be built with **Synthetic Event Feed Mode** first, because the current environment does not have live PLC, weighbridge, MQTT, bridge, tide, CTS, or jetty hardware integrations. The contracts and services should still be shaped so real MQTT/HTTP/device feeds can be attached later without changing downstream scheduling or UI logic.

---

## 2. Business Scope

### 2.1 In Scope

Phase 4 covers confirmed execution events for the active published or active operational plan:

- jetty loading start and loading complete;
- actual loaded quantity and optional coal grade/stockpile confirmation;
- jetty departure readiness and actual departure;
- bridge open/close status and crossing confirmation;
- tide/water-level observations and operational gate status;
- CTS/floating-crane discharge start, rate update, stoppage, and discharge complete;
- equipment/device health and feed health;
- offline/edge-buffered event replay;
- event trust workflow: candidate, confirmed, rejected, superseded;
- actualization of `ScheduleEvent.actual_at` only from confirmed events;
- exceptions created from confirmed operational events where required;
- audit trail for every candidate, confirmation, actualization, rejection, and replay.

### 2.2 Out Of Scope

Phase 4 does not implement:

- optimizer-driven recovery recommendation;
- automatic resource reassignment;
- automatic publication of revised plans;
- full vendor production contracts;
- full historian/time-series database migration;
- customer portal or external ETA sharing;
- demurrage billing workflow.

Those belong to later Phase 5 and Phase 6 work.

---

## 3. Design Rule

Phase 4 must preserve the existing separation:

| Layer | Meaning | Can mutate schedule actuals? |
|---|---|---|
| Planned schedule | Baseline generated plan | No |
| Phase 3 telemetry | Observed position, geofence, ETA evidence | No |
| Phase 4 candidate event | A possible operational event inferred or received | No |
| Phase 4 confirmed event | Trusted operational fact | Yes, scoped to actual fields and execution state |
| Phase 2/5 scenario | What-if or recovery proposal | No direct active-plan mutation |
| Governed override | Explicit manual adjustment with reason | Yes, only through existing governance |

This prevents GPS/AIS noise, duplicate sensor messages, or weak device signals from corrupting the operational schedule.

---

## 4. Target Operator Flow

1. Operator opens **Operations -> Jetty Loading** or **Operations -> CTS / Floating Crane**.
2. A field event arrives from synthetic feed, operator action, or device feed.
3. The event appears as a candidate with evidence, source, confidence, trip, assignment, and planned milestone match.
4. If source trust rules allow auto-confirmation, the system confirms it and records why.
5. If manual confirmation is required, the authorized operator confirms or rejects it with reason.
6. Confirmed event updates `ScheduleEvent.actual_at` and relevant execution state.
7. If confirmed event creates a variance, stoppage, low rate, missed gate, or stale feed risk, Exception Center receives a governed operational exception.
8. Audit & Logs shows candidate ingestion, trust decision, confirmation, actualization, and exception creation.
9. Scenario Workspace can still create what-if scenarios from resulting exceptions, but Phase 4 does not auto-optimize recovery.

---

## 5. Core Domain Model

Create a new backend app or module named `operations` unless an implementation pass finds a cleaner existing boundary. It should depend on scheduling and telemetry, not replace them.

### 5.1 `IntegrationFeed`

Tracks event-producing systems.

Fields:

- `feed_id`
- `name`
- `feed_type`: `synthetic | mqtt | http | plc | weighbridge | tide_sensor | bridge_operator | jetty_operator | cts_operator | manual`
- `status`: `active | degraded | paused | retired`
- `trust_mode`: `manual_review | auto_confirm | auto_confirm_with_threshold`
- `freshness_threshold_seconds`
- `metadata`
- timestamps

Relationship to Phase 3: `TelemetrySource` remains for position feeds. `IntegrationFeed` covers operational event feeds and device health. A future refactor can share a base registry, but Phase 4 should avoid destabilizing Phase 3 telemetry.

### 5.2 `DeviceEndpoint`

Represents an event-capable device or operator terminal.

Fields:

- `device_id`
- `feed`
- `device_type`: `edge_gateway | jetty_plc | weighbridge | operator_tablet | tide_sensor | bridge_console | cts_plc | ais_receiver | gps_tracker`
- `asset_type`, `asset_code`
- `location`, optional `geofence`
- `status`
- `last_seen_at`
- `firmware_version`
- `metadata`

### 5.3 `DeviceHealthSnapshot`

Stores latest and historical health observations.

Fields:

- `snapshot_id`
- `device`
- `observed_at`, `received_at`
- `health_status`: `healthy | warning | critical | offline | unknown`
- `battery_level`
- `power_status`
- `network_status`
- `latency_ms`
- `gap_seconds`
- `metadata`

Latest health should be available in the UI and should be summarized in scheduling overview.

### 5.4 `OperationalEventCandidate`

Stores raw or inferred event candidates before trust confirmation.

Fields:

- `candidate_id`
- `feed`
- `device`
- `source_kind`: `synthetic | device | operator | telemetry_inferred | vendor`
- `event_kind`
- `asset_type`, `asset_code`
- `trip`, nullable
- `assignment`, nullable
- `schedule_event`, nullable
- `event_at`
- `received_at`
- `confidence_score`
- `dedupe_key`
- `status`: `pending | auto_confirmed | confirmed | rejected | superseded | duplicate`
- `payload`
- `raw_payload_ref`
- `metadata`

Important event kinds:

- `jetty_arrived`
- `jetty_loading_started`
- `jetty_loading_completed`
- `jetty_departed`
- `bridge_opened`
- `bridge_closed`
- `bridge_crossed`
- `tide_level_observed`
- `tide_gate_passed`
- `cts_arrived`
- `cts_discharge_started`
- `cts_rate_updated`
- `cts_discharge_stopped`
- `cts_discharge_completed`
- `equipment_breakdown`
- `device_offline`
- `manual_status_update`

### 5.5 `ConfirmedOperationalEvent`

Represents trusted execution truth.

Fields:

- `event_id`
- `candidate`
- `event_kind`
- `plan_version`
- `trip`
- `assignment`
- `schedule_event`
- `actual_at`
- `confirmed_quantity_mt`
- `confirmed_rate_tph`
- `confirmed_grade_code`
- `confirmed_by`
- `confirmed_at`
- `confirmation_mode`: `manual | auto_trusted_source | auto_threshold | replay_proof`
- `reason_code`
- `before_state`
- `after_state`
- `metadata`

Confirmed events are append-only. Corrections should create a new correction/superseding event rather than editing the old event silently.

### 5.6 `OperationalActualization`

Records exactly what changed after a confirmed event.

Fields:

- `actualization_id`
- `confirmed_event`
- `target_type`: `schedule_event | trip | assignment | constraint_window | asset_health`
- `target_id`
- `before_state`
- `after_state`
- `status`: `applied | skipped | failed`
- `error_message`
- timestamps

This table protects auditability when one confirmed event updates multiple operational read models.

### 5.7 `EdgeEventBatch`

Supports local buffering and deterministic replay.

Fields:

- `batch_id`
- `feed`
- `device`
- `batch_sequence`
- `captured_from`
- `captured_to`
- `received_at`
- `message_count`
- `status`: `received | processed | partial | failed`
- `checksum_sha256`
- `metadata`

---

## 6. Trust And Actualization Rules

### 6.1 Candidate Matching

Candidate events should match to the active plan using:

1. direct `trip_id`, `assignment_id`, or `schedule_event_id` when provided;
2. asset code plus nearest active assignment window;
3. geofence/location plus event kind;
4. planned event proximity;
5. fallback to unlinked candidate requiring manual resolution.

Candidates must preserve all raw source references even when matched.

### 6.2 Deduplication

Deduplicate by:

- `feed_id`;
- external source event id if provided;
- device id;
- event kind;
- asset code;
- event timestamp bucket;
- schedule event id.

Duplicate candidates should be marked `duplicate`, linked to the original, and excluded from actualization.

### 6.3 Auto-Confirmation

Auto-confirm only when all are true:

- feed is configured for trusted auto-confirm;
- device is healthy;
- candidate confidence is above threshold;
- candidate matches exactly one schedule event;
- event is inside a reasonable tolerance window;
- event is not a correction or high-impact exception.

Manual review is required for:

- low confidence;
- stale device;
- conflicting candidates;
- unmatched trip/assignment;
- large planned-vs-actual variance;
- equipment breakdown;
- quantity or grade mismatch;
- events that would close a major milestone early/late beyond threshold.

### 6.4 Schedule Actualization

Confirmed events may update:

- `ScheduleEvent.actual_at`;
- `ScheduleEvent.status`;
- selected `Trip` execution status fields if added;
- selected `Assignment` execution status fields already used by boards;
- read models for dashboard, map, and operations pages.

Confirmed events must not:

- change planned timestamps;
- create a new plan version;
- publish a plan;
- reorder trips;
- reassign assets;
- resolve planning conflicts silently.

If actuals expose a planning issue, create an exception or scenario source.

---

## 7. Backend Services

### 7.1 Event Ingestion Service

`ingest_operational_event(payload, source)` should:

1. normalize source payload;
2. resolve feed and device;
3. validate event kind and timestamp;
4. create `OperationalEventCandidate`;
5. match candidate to plan objects;
6. dedupe;
7. evaluate trust policy;
8. auto-confirm or leave pending;
9. record audit event.

Input contracts should support:

- HTTP POST;
- synthetic replay command;
- future MQTT consumer;
- future edge batch replay.

### 7.2 Confirmation Service

`confirm_operational_event(candidate, actor, reason_code)` should:

1. validate actor permission and authority;
2. lock candidate;
3. create `ConfirmedOperationalEvent`;
4. update candidate status;
5. actualize schedule/assignment state;
6. create exception if thresholds are breached;
7. record audit event.

`reject_operational_event(candidate, actor, reason_code)` should mark the candidate rejected with reason and audit it.

### 7.3 Actualization Service

`apply_confirmed_event(event)` should:

- update `ScheduleEvent.actual_at` and status;
- update assignment status where relevant;
- calculate variance minutes;
- create `OperationalActualization` rows;
- create or update operational exceptions.

### 7.4 Device Health Service

`ingest_device_health(payload)` should:

- upsert device endpoint;
- create health snapshot;
- mark feed/device degraded when thresholds are exceeded;
- raise device health candidates/exceptions for critical outages;
- feed UI health KPIs.

### 7.5 Synthetic Event Replay

Create `phase4_operations_proof` management command.

It should:

1. reseed Phase 3/active schedule baseline;
2. seed integration feeds and devices;
3. replay jetty/bridge/tide/CTS/device events;
4. create candidates;
5. auto-confirm trusted events;
6. leave selected low-confidence events pending for manual workflow proof;
7. verify actualization;
8. verify exceptions;
9. verify audit trail;
10. emit JSON evidence.

---

## 8. API Surface

Add routes under `/api/operations/`.

Recommended endpoints:

- `GET /api/operations/overview/`
- `GET /api/operations/event-candidates/`
- `POST /api/operations/event-candidates/ingest/`
- `POST /api/operations/event-candidates/{id}/confirm/`
- `POST /api/operations/event-candidates/{id}/reject/`
- `GET /api/operations/confirmed-events/`
- `GET /api/operations/device-health/`
- `POST /api/operations/device-health/ingest/`
- `GET /api/operations/edge-batches/`
- `POST /api/operations/edge-batches/replay/`

Serializer contracts must expose:

- source/feed/device identity;
- event kind;
- matching trip/assignment/schedule event;
- planned time vs actual/candidate time;
- variance minutes;
- confidence and trust decision;
- confirmation authority;
- before/after state;
- audit references.

---

## 9. Frontend Scope

Phase 4 UI should extend existing operational boards rather than create a separate decorative dashboard.

### 9.1 Operations Event Console

Add a dense working surface under **Operations** or **Map & Signals**:

- candidate event queue;
- confirmed event ledger;
- feed/device health strip;
- candidate detail drawer;
- confirm/reject controls;
- evidence panel with telemetry/source payload;
- planned-vs-actual delta;
- reason capture.

This can be a new page if existing boards become too crowded.

### 9.2 Jetty Loading Board

Enhance with:

- candidate load start/end rows;
- actual loading start/end;
- actual loaded MT;
- grade/source confirmation;
- departure readiness;
- feed confidence/status;
- confirm/reject action for authorized jetty operators.

### 9.3 CTS / Floating Crane Board

Enhance with:

- discharge start/stop/complete actuals;
- actual rate vs planned rate;
- low-rate candidate events;
- equipment stoppage;
- queue impact signal;
- confirm/reject action for CTS coordinators.

### 9.4 Tide & Bridge Window Board

Enhance with:

- bridge open/closed observed state;
- actual crossing confirmations;
- tide/water-level observed state;
- gate pass/fail actuals;
- stale/missing sensor indicators;
- active operational constraint state.

### 9.5 Exception Center

Add event-driven exception rows for:

- loading not started;
- loading complete late;
- loaded quantity mismatch;
- CTS low rate;
- bridge closed unexpectedly;
- tide sensor below threshold;
- device offline;
- conflicting confirmations.

Rows should distinguish:

- telemetry observed;
- event candidate;
- confirmed operational fact;
- manual override.

### 9.6 Live Resource Map

Overlay confirmed operational events on top of telemetry:

- candidate markers remain distinct from confirmed event markers;
- selected asset detail shows latest confirmed event and latest observed telemetry separately;
- feed health is visible but not dominant.

---

## 10. RBAC And Governance

New permissions:

- `operations.view`
- `operations.ingest`
- `operations.confirm_jetty`
- `operations.confirm_cts`
- `operations.confirm_bridge`
- `operations.confirm_tide`
- `operations.manage_feeds`
- `operations.replay`

Suggested role mapping:

| Role | Permissions |
|---|---|
| Admin | All operations permissions |
| ABL Dispatcher | view, ingest, confirm CTS/bridge/tide where applicable, replay |
| Berau Scheduler | view, confirm jetty where applicable |
| Joint Control Tower | view, manage feeds, publish/audit correlation |
| Viewer | view only |

Every confirmation/rejection must require actor, authority, reason, timestamp, and before/after state.

---

## 11. Seed And Proof Data

Phase 4 synthetic proof should include:

1. Jetty loading start confirmed on time.
2. Jetty loading complete late with actual quantity.
3. Barge departure confirmed by operator and geofence exit evidence.
4. Bridge open event and crossing confirmation.
5. Tide level observed below threshold creating active constraint.
6. CTS discharge started and rate updated below plan.
7. CTS discharge complete.
8. Device heartbeat healthy.
9. Device offline/stale health event.
10. Edge batch replay with duplicate messages proving idempotence.

Candidate event examples:

```json
{
  "feed_id": "SYN-JETTY-EVENTS-PHASE4",
  "device_id": "JETTY-SUARAN-TABLET-01",
  "event_kind": "jetty_loading_started",
  "asset_code": "BRG-VAL-08",
  "trip_ref": "PI-PLAN-2026-05-19-0001",
  "event_at": "relative-plan-load-start-plus-10m",
  "confidence_score": 92,
  "payload": {
    "operator": "jetty.operator.synthetic",
    "source_grade": "EBONY"
  }
}
```

---

## 12. Delivery Chunks

### Chunk 4.0 - Operations Event Foundation

Build:

- `operations` app;
- models/migrations for feed, device, candidate, confirmed event, actualization, edge batch;
- admin registration;
- base serializers/viewsets;
- RBAC permissions;
- unit tests for model constraints and permissions.

Exit criteria:

- candidates and confirmed events can be created through API;
- unauthorized users cannot confirm;
- audit events are recorded.

### Chunk 4.1 - Event Matching, Trust, And Actualization

Build:

- ingestion service;
- candidate-to-plan matching;
- dedupe logic;
- trust policy service;
- confirmation/rejection services;
- schedule actualization service.

Exit criteria:

- confirmed loading event updates `ScheduleEvent.actual_at`;
- duplicate payloads do not create duplicate confirmed events;
- low-confidence candidate remains pending;
- high-confidence trusted candidate auto-confirms only under policy.

### Chunk 4.2 - Device And Feed Health

Build:

- device endpoint and health ingestion APIs;
- latest health summary;
- degraded/offline status rules;
- dashboard/overview read model fields;
- health exceptions for critical outages.

Exit criteria:

- stale/offline device creates visible health risk;
- healthy device supports auto-confirm policy;
- feed health is visible in API and UI.

### Chunk 4.3 - Synthetic Event Replay And Edge Buffer

Build:

- deterministic Phase 4 event seed pack;
- `phase4_operations_proof` command;
- edge batch replay;
- duplicate/idempotence verification;
- JSON evidence output.

Exit criteria:

- proof runs without external systems;
- replay creates candidates, confirmed events, actuals, health snapshots, and audit events;
- rerun is idempotent.

### Chunk 4.4 - Operator UI For Event Confirmation

Build:

- Operations Event Console or equivalent event panel;
- candidate queue;
- confirmed event ledger;
- detail drawer;
- confirm/reject controls with reason;
- feed/device health strip;
- planned-vs-actual variance display.

Exit criteria:

- operator can confirm a pending candidate from UI;
- event actualizes schedule state;
- rejected event remains audited;
- visual language distinguishes candidate vs confirmed event.

### Chunk 4.5 - Board Integration

Build:

- Jetty Loading actuals and confirmation panel;
- CTS actuals and low-rate signals;
- Tide/Bridge actual state;
- Live Map confirmed-event overlay;
- Exception Center event-driven exception rows.

Exit criteria:

- confirmed jetty, CTS, bridge, and tide events appear in the correct operational boards;
- Exception Center shows event-driven operational exceptions;
- actuals are visible beside planned schedule without changing planned timestamps.

### Chunk 4.6 - Browser Evidence, Runbook, And Closure

Build:

- Phase 4 operator runbook;
- Phase 4 completion evidence doc;
- repeatable browser screenshots for event console, jetty actuals, CTS actuals, tide/bridge state, exception row, audit logs;
- performance pass for event queues and health payloads.

Exit criteria:

- proof flow can be rerun;
- browser evidence is checked into `docs/evidence/phase4/`;
- docs clearly explain Synthetic Event Feed Mode vs real hardware mode.

---

## 13. Test Plan

Backend tests:

- candidate ingestion creates normalized event candidate;
- candidate matching links to correct trip/assignment/schedule event;
- duplicate messages are suppressed;
- trusted source auto-confirms when policy permits;
- low-confidence event requires manual confirmation;
- manual confirmation requires correct permission;
- confirmed event updates `ScheduleEvent.actual_at`;
- confirmed event creates operational actualization row;
- rejection records reason and audit;
- device health stale/offline creates health exception;
- edge batch replay is idempotent;
- `phase4_operations_proof --json` returns PASS.

Frontend tests:

- event queue renders candidates and confirmed events;
- confirm action requires reason;
- reject action requires reason;
- jetty board displays planned vs actual loading;
- CTS board displays actual rate/low-rate status;
- tide/bridge board displays observed gate status;
- Exception Center differentiates event candidate vs confirmed operational fact;
- no static hardcoded proof labels appear when API has no events.

Browser evidence:

- run synthetic event proof;
- open event console;
- confirm/reject at least one pending event;
- verify actualized jetty/CTS/tide/bridge state;
- verify Exception Center event-driven row;
- verify Audit & Logs event chain.

---

## 14. Definition Of Done

Phase 4 is complete when an authorized operations user can, inside the Dockerized system:

1. replay synthetic jetty/CTS/bridge/tide/device events;
2. see candidate events separately from confirmed events;
3. inspect source, device, confidence, payload, and matched schedule event;
4. confirm or reject a pending operational event with reason;
5. see confirmed events update actual execution fields;
6. see device/feed health and stale/offline risks;
7. see event-driven exceptions in Exception Center;
8. see audit trail for candidate ingestion, confirmation/rejection, actualization, and replay;
9. rerun the proof idempotently;
10. understand from the UI and docs that synthetic events are not live hardware events.

Phase 4 is not complete if telemetry candidates directly mutate schedule actuals without confirmation, or if confirmed actuals are not auditable.

---

## 15. Compatibility With Later Phases

### Phase 5

Phase 5 optimizer should consume confirmed operational events and event-driven exceptions as stronger signals than Phase 3 observations.

Examples:

- confirmed CTS low rate becomes optimizer input for recovery scoring;
- confirmed bridge closure affects route sequencing;
- confirmed late loading changes downstream trip projections;
- device health reduces confidence in recommended recovery.

Phase 5 should not bypass Phase 4 governance. Recommended recovery still needs scenario/run/promotion/approval flow.

### Phase 6

Phase 6 can expose safe views of confirmed events externally:

- Berau sees cargo and jetty actuals;
- ABL sees fleet and CTS execution;
- customers see approved milestone updates only.

Candidate events and raw device payloads should remain internal unless explicitly exposed by role and data scope.

---

## 16. Frozen Build Decisions For Phase 4

1. Synthetic Event Feed Mode is first-class for proof.
2. Phase 3 telemetry remains candidate evidence, not operational truth.
3. Confirmed events are append-only operational facts.
4. Actualization updates actual fields only; planned schedule remains unchanged.
5. MQTT/broker integration can be simulated first through HTTP/management command contracts.
6. Device/feed health is separate from asset operational status.
7. Every confirmation, rejection, and actualization is audited.
8. Phase 4 creates stronger inputs for Phase 5 but does not implement optimization.
