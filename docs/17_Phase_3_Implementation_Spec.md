# 17 - Phase 3 Implementation Spec

**Project:** Coalflow Tower / Berau-ABL Transshipment Scheduling Simulation and Live Planning Platform  
**Status:** draft implementation specification for product Phase 3  
**Generated:** 2026-05-18  
**Primary inputs:** `02_Planning_Tool_Scope.md`, `03_Data_Architecture_and_IoT_Scope.md`, `08_Phase_1_Implementation_Spec.md`, `14_Phase_2_Implementation_Spec.md`, `15_Phase_2_Scenario_Proof_Evidence.md`, and the current Phase 2 codebase.

---

## 1. Scope Interpretation

Product Phase 3 is **GPS/AIS live tracking**.

The objective is to connect the governed schedule to observed movement evidence:

1. ingest GPS/AIS-style position records for tugs, barges, CTS/floating cranes, and OGVs;
2. derive latest asset state, geofence events, ETA variance, and signal health;
3. display live position and planned-vs-observed movement on the Live Resource Map and Control Tower surfaces;
4. generate delay/stale-signal alerts from observed movement without mutating the approved schedule;
5. allow observed delay evidence to become a source for Phase 2 scenario assumptions.

The current implementation does not have real downstream AIS/GPS provider access. Therefore Phase 3 must be built with **Synthetic Live Data Mode** as the default proof path. The same ingestion contracts must later accept real vendor/API/device messages without changing downstream UI or scheduling logic.

### What Phase 3 Must Prove

- Seeded/simulated position feeds can be ingested through the same API contract planned for live data.
- Asset positions are visible on a map with route/geofence context.
- Latest state shows signal freshness, source, speed, heading, location zone, and confidence.
- Planned-vs-observed ETA variance is computed against the active published/proposed schedule.
- Geofence entry/exit events are derived from movement pings.
- Delay/stale-signal alerts are generated and auditable.
- An observed delay can prefill a Phase 2 scenario assumption without directly editing the plan.

### Explicitly Out of Scope For Phase 3

- Jetty/CTS/bridge/tide operational confirmation workflow. That is Phase 4.
- PLC, weighbridge, water-level, weather-station, and device-broker production integration. That is Phase 4 or later hardening.
- Automatic recovery recommendation or optimization. That remains Phase 5.
- Customer-facing live shipment visibility. That remains Phase 6.
- Production vendor certification, telecom/network hardware rollout, and SLA monitoring beyond seeded/simulated feed health.

---

## 2. Product Invariants

1. **Telemetry is evidence, not authority.** AIS/GPS pings never rewrite `Trip`, `Assignment`, or `ScheduleEvent` records directly.
2. **State layers stay separate.** Planned, projected, observed, confirmed, synthetic, and recommended state must remain distinguishable.
3. **Synthetic data must be labeled.** Seeded/replayed pings use `source_type = synthetic_gps` or `synthetic_ais`.
4. **Latest state is derived.** The platform stores raw pings and separately materializes latest asset state for fast UI queries.
5. **Geofence events are candidates.** Enter/exit/dwell events are observed evidence until Phase 4 confirmation rules make them operationally trusted events.
6. **Delay alerts are scenario inputs.** A delay alert can create a scenario draft or assumption proposal, but cannot directly publish a changed plan.
7. **No hidden dependency on live vendors.** Phase 3 proof must run from deterministic seed/replay data inside Docker.

---

## 3. Phase 1 And Phase 2 Baseline Carried Forward

| Existing capability | Phase 3 interpretation |
|---|---|
| `PlanVersion`, `Trip`, `Assignment`, `ScheduleEvent` | planned movement baseline for ETA comparison |
| route and route-segment masters | geometry and expected transit context |
| tide/bridge windows | ETA variance risk context |
| Simulation Scenario model | target for observed-delay what-if creation |
| Impact-chain assessment | reusable explanation model for observed movement impact |
| Live Resource Map MVP-lite | upgraded into real/synthetic live tracking surface |
| Audit and export infrastructure | trace telemetry-derived alerts and scenario handoff |

Phase 3 should not weaken the Phase 2 closure rule: scenario candidates must still promote through approval and publication governance.

---

## 4. User Journeys

### 4.1 Synthetic replay operator trial

1. Admin reseeds Phase 3 synthetic tracks.
2. Operator opens **Map & Signals -> Live Resource Map**.
3. Operator starts or selects a replay run.
4. Map shows tug/barge/CTS/OGV positions moving along route/geofence zones.
5. Operator opens an asset detail drawer to inspect signal source, last seen, ETA variance, linked trip, and paired asset.
6. Operator confirms whether delay/stale-signal alerts appear as expected.

### 4.2 Planned vs actual delay detection

1. A tug/barge pair is planned to depart jetty at a schedule timestamp.
2. Synthetic GPS pings show the pair still dwelling in the jetty zone after the planned departure tolerance.
3. System creates an observed delay alert.
4. Alert shows planned event, observed state, variance minutes, confidence, and source pings.
5. Operator can convert the alert into a Phase 2 scenario assumption such as `trip_delay`.

### 4.3 Geofence movement evidence

1. Asset position enters a jetty, bridge, tide gate, CTS, or OGV loading-zone geofence.
2. System derives `geofence_entered`.
3. If the asset remains longer than the configured dwell threshold, system derives `geofence_dwell`.
4. Exit creates `geofence_exited`.
5. These remain observed candidate events until Phase 4 confirms operational events.

### 4.4 Signal health supervision

1. Operator opens Control Tower or Live Resource Map.
2. System highlights stale, low-quality, or missing signals.
3. Operator can distinguish actual operational delay from missing telemetry.
4. Stale signal alerts are auditable but do not become schedule delays unless confirmed or converted to a scenario.

---

## 5. Capability Scope

### 5.1 Must Build

- telemetry ingestion API for GPS/AIS-style position records;
- synthetic replay seed data and replay command;
- asset identity mapping from internal assets to external IDs;
- raw position-ping persistence;
- latest asset-state materialization;
- geofence master model and point-in-zone detection;
- geofence event derivation;
- planned-vs-observed ETA comparison;
- delay and stale-signal alert model;
- Live Resource Map upgrade with asset positions, trails, geofences, freshness, and ETA variance;
- Control Tower summary signals for live tracking health;
- observed-delay-to-scenario handoff;
- proof command and evidence document for Phase 3.

### 5.2 Should Build

- replay speed controls for operator trials;
- position trail downsampling for UI performance;
- alert deduplication and suppression windows;
- source confidence scoring;
- CSV/JSON telemetry import for vendor sample dumps;
- map filter presets by asset type, voyage, trip, alert state, and signal source.

### 5.3 Should Defer

- production AIS receiver/NMEA integration;
- production GPS tracker fleet rollout;
- MQTT/Kafka event streaming as a required dependency;
- edge gateway offline buffering;
- jetty/CTS loading confirmation workflows;
- automatic recovery recommendation;
- full route/geofence visual editor if a simple admin table/import is enough for Phase 3.

---

## 6. Target Architecture

Phase 3 can keep the current Docker topology:

| Service | Phase 3 use |
|---|---|
| `api` | telemetry ingestion, geofence detection, latest state, alerts |
| `worker` | synthetic replay, periodic stale-signal checks, ETA recalculation |
| `db` | raw pings, geofences, state, alerts, replay metadata |
| `redis` | latest-state cache and alert deduplication, optional for Phase 3 |
| `object-store` | raw telemetry replay files and exports |
| `frontend` | live map, signal panels, alert drill-downs |

Do not add a hard dependency on Kafka/MQTT for Phase 3. Keep broker integration behind service interfaces so Phase 4 can add it cleanly.

### 6.1 Data Flow

```text
Synthetic replay / Vendor-like API payload
        |
        v
Telemetry ingestion API
        |
        v
Raw PositionPing + raw payload reference
        |
        v
LatestAssetState + GeofenceEvent + LiveEtaProjection
        |
        v
DelayAlert / StaleSignalAlert
        |
        v
Live Resource Map / Control Tower / Scenario handoff
```

---

## 7. Domain Model Blueprint

Keep models in a new Django app such as `telemetry` unless there is a strong reason to place them in `planning`.

### 7.1 `TelemetrySource`

Represents a feed source, real or synthetic.

Fields:
- `source_id`
- `name`
- `source_type`: `synthetic_gps | synthetic_ais | vendor_api | manual | device_gateway`
- `status`: `active | degraded | paused | retired`
- `freshness_threshold_seconds`
- `metadata`
- timestamps

### 7.2 `AssetIdentity`

Maps external telemetry identifiers to internal planning assets.

Fields:
- `asset_type`: `tug | barge | cts | ogv | service_boat`
- `asset_object_id`
- `asset_code`
- `source`
- `external_id`
- `external_id_type`: `mmsi | imo | tracker_id | device_serial | synthetic_id`
- `is_primary`
- `valid_from`, `valid_to`

The implementation may initially store `asset_object_id` and `asset_code` instead of a polymorphic relation to keep the MVP simple, but serializers must return a stable asset reference.

### 7.3 `PositionPing`

Immutable raw/normalized telemetry record.

Fields:
- `ping_id`
- `source`
- `asset_identity`
- `asset_type`
- `asset_code`
- `latitude`, `longitude`
- `speed_knots`
- `course_degrees`
- `heading_degrees`
- `device_timestamp`
- `received_timestamp`
- `signal_quality`: `good | weak | stale | invalid`
- `accuracy_m`
- `battery_level`
- `raw_payload`
- `raw_payload_ref`
- `is_synthetic`

Indexes:
- `(asset_code, device_timestamp)`
- `(source, received_timestamp)`
- geospatial index on point geometry

### 7.4 `TrackingGeofence`

Operational zones for live tracking.

Fields:
- `code`
- `name`
- `zone_type`: `jetty | bridge | tide_gate | route_segment | anchorage | cts | ogv_zone | maintenance | waiting_area`
- `geometry`
- `related_location`
- `related_route_segment`
- `dwell_threshold_minutes`
- `is_active`
- `metadata`

For Phase 3, seed geofences can be simple polygons/circles generated from existing locations.

### 7.5 `GeofenceEvent`

Derived observed movement event.

Fields:
- `event_id`
- `asset_code`, `asset_type`
- `geofence`
- `event_type`: `enter | exit | dwell | stale_inside`
- `started_at`, `ended_at`
- `source_ping`
- `confidence_score`
- `status`: `candidate | acknowledged | dismissed`
- `linked_trip`
- `metadata`

### 7.6 `LatestAssetState`

Fast read model for UI.

Fields:
- `asset_code`, `asset_type`
- `last_ping`
- `current_geofence`
- `derived_status`: `at_jetty | loading_candidate | underway | waiting_bridge | waiting_tide | at_cts | discharging_candidate | returning | maintenance_candidate | unknown`
- `latitude`, `longitude`
- `speed_knots`
- `heading_degrees`
- `last_seen_at`
- `freshness_status`: `fresh | aging | stale | missing`
- `confidence_score`
- `linked_trip`
- `paired_asset_code`
- `metadata`

### 7.7 `LiveEtaProjection`

Observed ETA versus planned schedule.

Fields:
- `projection_id`
- `asset_code`
- `trip`
- `schedule_event`
- `planned_at`
- `observed_eta`
- `variance_minutes`
- `calculation_method`: `route_remaining | geofence_sequence | simple_speed | synthetic_script`
- `confidence_score`
- `source_ping`
- `status`: `on_time | watch | delayed | unknown`

### 7.8 `TrackingAlert`

Operator-facing alert generated from tracking evidence.

Fields:
- `alert_id`
- `alert_type`: `delay | stale_signal | route_deviation | geofence_dwell | missing_asset | eta_risk`
- `severity`: `info | warning | critical`
- `asset_code`, `asset_type`
- `trip`
- `schedule_event`
- `message`
- `evidence`
- `status`: `open | acknowledged | converted_to_scenario | dismissed | resolved`
- `source_kind`: `synthetic | observed | vendor`
- `opened_at`, `resolved_at`
- `created_scenario`

### 7.9 `TelemetryReplayRun`

Controls deterministic synthetic data playback.

Fields:
- `replay_id`
- `name`
- `status`: `draft | running | completed | failed | canceled`
- `scenario_code`
- `started_at`, `completed_at`
- `speed_multiplier`
- `seed_start_at`
- `metadata`

---

## 8. Ingestion And Processing Services

### 8.1 Normalization

`ingest_position_ping(payload)` should:

1. validate required fields;
2. resolve `TelemetrySource`;
3. resolve or create `AssetIdentity` for synthetic sources;
4. normalize timestamps to timezone-aware UTC;
5. validate coordinates and speed ranges;
6. persist `PositionPing`;
7. update `LatestAssetState`;
8. evaluate geofence enter/exit/dwell;
9. update ETA projections;
10. generate alerts if thresholds are crossed.

### 8.2 Geofence Detection

For every accepted ping:

- find active geofences containing the point;
- compare with previous latest state;
- create enter/exit events;
- create dwell event once threshold is exceeded;
- store candidate status until Phase 4 confirmation exists.

### 8.3 ETA Calculation

Phase 3 ETA calculation can be intentionally simple:

- if asset is inside a target geofence, ETA is now;
- if moving, estimate ETA using distance to next planned geofence and current speed with minimum/maximum bounds;
- if speed is too low, mark as `unknown` or `watch`;
- compare observed ETA to `ScheduleEvent.planned_at`;
- emit variance minutes and confidence.

This can later be replaced by route-aware ETA without changing `LiveEtaProjection`.

### 8.4 Alert Rules

Initial rules:

| Rule | Condition | Alert |
|---|---|---|
| stale signal | no ping within threshold | `stale_signal` |
| late departure | asset remains in jetty geofence after planned depart tolerance | `delay` |
| bridge/tide watch | observed ETA exceeds gate/window margin | `eta_risk` |
| route deviation | asset enters unexpected zone | `route_deviation` |
| excessive dwell | dwell exceeds threshold | `geofence_dwell` |

Alerts must deduplicate by `(asset, trip, alert_type, schedule_event)` while open.

---

## 9. API Contract Additions

Use `/api/telemetry/` as the base path.

### 9.1 Ingestion

`POST /api/telemetry/position-pings/ingest/`

Request:

```json
{
  "source_id": "SYN-GPS-PHASE3",
  "source_type": "synthetic_gps",
  "external_id": "SYN-BER-TUG-08",
  "asset_type": "tug",
  "asset_code": "BER-TUG-08",
  "latitude": -1.2345,
  "longitude": 117.2345,
  "speed_knots": 5.4,
  "course_degrees": 91,
  "device_timestamp": "2026-06-01T08:15:00Z",
  "signal_quality": "good",
  "raw_payload": {}
}
```

Response:

```json
{
  "ping_id": "PNG-SYN-GPS-PHASE3-000001",
  "asset_code": "BER-TUG-08",
  "latest_state_updated": true,
  "geofence_events": [],
  "alerts": []
}
```

### 9.2 Read APIs

- `GET /api/telemetry/assets/latest/`
- `GET /api/telemetry/assets/{asset_code}/track/?from=&to=`
- `GET /api/telemetry/geofences/`
- `GET /api/telemetry/geofence-events/`
- `GET /api/telemetry/eta-projections/`
- `GET /api/telemetry/alerts/`
- `POST /api/telemetry/alerts/{id}/acknowledge/`
- `POST /api/telemetry/alerts/{id}/convert-to-scenario/`
- `POST /api/telemetry/replay-runs/`
- `POST /api/telemetry/replay-runs/{id}/start/`
- `POST /api/telemetry/replay-runs/{id}/stop/`

### 9.3 Scheduling Overview Extension

`/api/scheduling/overview/` should include:

- live tracking health summary;
- open tracking alert counts;
- latest state for assigned assets in the active plan;
- ETA variance summary by trip.

Do not embed full tracks in the scheduling overview response.

---

## 10. Frontend Scope

### 10.1 Live Resource Map

Upgrade the current MVP-lite map into the Phase 3 operator surface.

Required UI signals:

- route/geofence overlay;
- asset markers by type: tug, barge, CTS, OGV;
- paired tug/barge grouping where assignment exists;
- marker freshness color/state;
- latest speed, heading, source, and last seen timestamp;
- planned route/trip line and observed track tail;
- ETA variance badge;
- open alert count per asset;
- replay status when using synthetic data.

Asset detail drawer:

- asset identity and source;
- linked assignment/trip/voyage;
- planned next event;
- observed ETA and variance;
- current geofence and derived status;
- signal health and confidence;
- recent pings;
- recent geofence events;
- open alerts;
- button to convert delay alert to scenario.

### 10.2 Control Tower

Add compact live signal cards:

- assets tracked / stale / missing;
- open delay alerts;
- highest ETA variance;
- active synthetic replay state;
- latest telemetry received timestamp.

### 10.3 Exception Center Integration

Tracking alerts should be visible as observed exceptions, clearly labeled as:

- `source = synthetic_gps` during proof;
- `status = observed candidate`;
- not confirmed operational event.

### 10.4 Scenario Workspace Integration

From a delay alert:

- create scenario draft;
- prefill `trip_delay` assumption from ETA variance;
- attach telemetry evidence in metadata;
- keep operator-editable assumption values.

---

## 11. Synthetic Seed And Replay Strategy

### 11.1 Seed Families

Seed deterministic tracks for:

1. **TRACK-ON-TIME** - tug/barge follows plan and crosses geofences on time.
2. **TRACK-JETTY-DELAY** - tug/barge remains at jetty after planned departure.
3. **TRACK-BRIDGE-WAIT** - asset dwells near bridge approach and creates ETA risk.
4. **TRACK-STALE-SIGNAL** - signal stops mid-route and creates a stale alert.
5. **TRACK-OGV-ETA-SHIFT** - OGV AIS-style pings imply later arrival.
6. **TRACK-CTS-APPROACH** - tug/barge approaches CTS and enters OGV loading zone.

### 11.2 Relative Dates

All seed tracks must be generated relative to the active proof plan dates. Do not hard-code historical dates.

### 11.3 Replay Modes

- bulk-load all pings for proof assertions;
- timed replay for UI demo;
- accelerated replay with speed multiplier;
- reset replay state.

### 11.4 Source Labeling

Every replayed ping must include:

- `source_type = synthetic_gps` or `synthetic_ais`;
- `is_synthetic = true`;
- `replay_id`;
- raw payload metadata.

---

## 12. Delivery Chunks

### Chunk 3.0 - Telemetry Foundation

Goal: create durable live-tracking data contracts.

Backend:
- add telemetry app;
- add `TelemetrySource`, `AssetIdentity`, `PositionPing`;
- add ingestion serializer/service;
- add basic read APIs;
- seed source and identity mappings.

Tests:
- valid pings are persisted;
- invalid coordinates/timestamps are rejected;
- synthetic sources are labeled;
- asset identity resolves to internal asset code.

Exit criteria:
- `POST /api/telemetry/position-pings/ingest/` accepts a synthetic ping and returns a normalized ping ID.

### Chunk 3.1 - Latest State And Signal Health

Goal: make raw pings usable for the UI.

Backend:
- add `LatestAssetState`;
- materialize latest state on ingest;
- compute freshness status;
- add stale-signal scheduled check;
- add latest-state API.

Frontend:
- show tracked assets and freshness summary in Live Resource Map.

Tests:
- latest state updates only when incoming ping is newer;
- stale threshold changes state to stale;
- stale state does not mutate schedules.

Exit criteria:
- operator can see fresh/stale/missing tracked assets.

### Chunk 3.2 - Geofences And Derived Movement Events

Goal: convert positions into operational location evidence.

Backend:
- add `TrackingGeofence`;
- seed jetty, bridge, tide, CTS, anchorage, and OGV-zone geofences;
- derive enter/exit/dwell `GeofenceEvent`;
- expose geofence and event APIs.

Frontend:
- render geofence overlays;
- show current zone and recent geofence events.

Tests:
- point inside zone creates enter event;
- leaving zone creates exit event;
- dwell threshold creates dwell event;
- events are candidate/observed, not confirmed.

Exit criteria:
- synthetic track generates visible geofence events.

### Chunk 3.3 - Planned Vs Observed ETA And Alerts

Goal: connect observed movement to active schedule risk.

Backend:
- add `LiveEtaProjection`;
- add `TrackingAlert`;
- compare latest state with active trips/events;
- generate delay, ETA-risk, route-deviation, dwell, and stale-signal alerts;
- deduplicate open alerts.

Frontend:
- show ETA variance and alerts in map/detail panels;
- show tracking alert summary in Control Tower;
- expose tracking alerts in Exception Center with observed-source labels.

Tests:
- late departure produces delay alert;
- stale signal produces stale alert;
- on-time track produces no delay alert;
- alert evidence links to source pings and schedule events.

Exit criteria:
- operator can identify a delayed asset and see why the platform thinks it is late.

### Chunk 3.4 - Synthetic Replay Proof Flow

Goal: make Phase 3 testable without third-party systems.

Backend:
- add `TelemetryReplayRun`;
- add replay seed command;
- add proof command `phase3_tracking_proof`;
- create replay fixtures for all seed families.

Frontend:
- replay selector/status in Live Resource Map;
- optional replay speed/status badge.

Tests:
- proof command reseeds and produces deterministic pings, states, geofence events, ETA projections, and alerts;
- replay can be rerun without duplicate identity conflicts.

Exit criteria:
- Phase 3 can be demonstrated end-to-end from seed data only.

### Chunk 3.5 - Scenario Handoff

Goal: make observed delay actionable without bypassing governance.

Backend:
- `TrackingAlert.convert_to_scenario`;
- create `SimulationScenario` with source metadata from telemetry alert;
- prefill `ScenarioAssumption.Kind.TRIP_DELAY`;
- include telemetry evidence in scenario metadata;
- audit the handoff.

Frontend:
- button on delay alert: **Create scenario**;
- open Simulation Workspace with prefilled assumption;
- preserve editable operator values.

Tests:
- delay alert creates scenario draft;
- source telemetry evidence is retained;
- baseline plan is not mutated;
- scenario can be simulated through existing Phase 2 engine.

Exit criteria:
- observed movement delay can enter the Phase 2 scenario process.

### Chunk 3.6 - Browser Evidence, Hardening, And Documentation

Goal: make Phase 3 closable.

Build:
- browser screenshots for Live Resource Map, asset detail, alert list, scenario handoff;
- update operator manual;
- add Phase 3 proof evidence document;
- performance pass for map payload size and track downsampling.

Exit criteria:
- proof flow can be rerun and evidence is visible in the UI.

---

## 13. Test Plan

### Backend Unit Tests

- ingestion validation;
- asset identity resolution;
- latest-state update ordering;
- geofence enter/exit/dwell;
- ETA variance calculation;
- alert deduplication;
- scenario handoff creation;
- audit event creation.

### Backend Integration Tests

- seed replay creates deterministic pings;
- replay creates latest states for expected assets;
- replay creates expected geofence events;
- delay replay creates expected alert;
- on-time replay does not create false delay alert;
- alert-to-scenario creates draft scenario without mutating baseline.

### Frontend Tests

- map page renders assets from latest-state API;
- freshness badges use API state;
- asset drawer shows ETA variance and alert evidence;
- create-scenario action calls correct API;
- stale/unknown states are legible and not confused with actual delay.

### Browser Evidence

Capture:

- Live Resource Map with geofences and asset markers;
- asset detail drawer;
- tracking alert list;
- converted scenario in Simulation Workspace;
- audit log showing telemetry proof events.

---

## 14. Definition Of Done For Product Phase 3

Phase 3 is complete when an authorized operations user can, inside the Dockerized system:

1. seed or replay synthetic GPS/AIS movement data;
2. ingest pings through the same contract planned for real vendors/devices;
3. inspect latest position, source, freshness, and confidence for tracked assets;
4. see route/geofence context on the Live Resource Map;
5. inspect derived geofence enter/exit/dwell evidence;
6. compare observed ETA against planned schedule events;
7. receive delay and stale-signal alerts;
8. distinguish synthetic observed evidence from confirmed operational events;
9. convert an observed delay alert into a Phase 2 scenario draft;
10. retrieve audit and proof evidence showing the telemetry-to-scenario chain.

Phase 3 is not complete if the map is only decorative. The delivered value is live movement evidence tied back to the schedule and scenario workflow.

---

## 15. Compatibility With Later Phases

### Phase 4 - IoT/Event-Driven Operations

Phase 4 should consume Phase 3 observed evidence and add confirmation/authority:

- jetty loading start/end confirmation;
- CTS discharge confirmation;
- bridge/tide operator status;
- device/broker health;
- operational event trust workflow.

Phase 3 geofence events become candidate inputs for Phase 4 confirmation, not replacements for it.

### Phase 5 - Optimization And Recovery Recommendation

Phase 5 can use Phase 3 alerts as optimization inputs:

- observed delay creates optimizer scenario source;
- stale signal reduces confidence in recommendation;
- ETA variance changes recovery candidate scoring;
- recommendation still materializes through scenario/run/promotion governance.

### Phase 6 - Multi-Party Control Tower

Phase 6 can expose safe live-state views by organization/customer:

- Berau sees demand/commitment impacts;
- ABL sees fleet execution state;
- customers see approved external milestones only.

---

## 16. Frozen Build Decisions For Phase 3

1. **Synthetic Live Data Mode is first-class.** It is not a throwaway demo path.
2. **No direct schedule mutation from telemetry.** Movement evidence creates alerts or scenarios.
3. **PostgreSQL/PostGIS is enough for Phase 3 MVP.** Timescale/ClickHouse can be introduced only when volume requires it.
4. **No required MQTT/Kafka dependency yet.** HTTP ingestion and replay commands are enough for proof.
5. **Geofence events are observed candidates.** Phase 4 owns confirmation.
6. **All dates are relative.** Seed/replay data must stay current when rerun.
7. **Every synthetic source is visibly labeled.** Operators must never confuse replayed pings with vendor/live pings.
