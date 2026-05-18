# 18 - Phase 3 Operator Runbook

## Purpose

Phase 3 adds GPS/AIS-style live tracking to the Coalflow Tower planning flow. In the current build this runs in **Synthetic Live Data Mode**: the data is deterministic seed and replay data shaped like GPS/AIS telemetry, not a connection to a live vendor feed.

Use this runbook to test whether live movement evidence is visible, explainable, and usable as a scenario input without mutating the active plan.

## Roles

| Role | User | What to test |
|---|---|---|
| Admin | `admin@coalflow.local` | Full Phase 3 proof, all screens, audit review |
| ABL Dispatcher | `abl.dispatcher@coalflow.local` | Start synthetic replay, inspect map, inspect alerts |
| Berau Scheduler | `berau.scheduler@coalflow.local` | Convert an observed delay into a scenario, run simulation |
| Joint Control Tower | `control.tower@coalflow.local` | View telemetry evidence and publish/governance context |
| Viewer | `viewer@coalflow.local` | Read-only map and schedule visibility |

## Reset And Proof Commands

Run commands from `F:\ocean`.

Start the stack:

```text
docker compose up -d --build db redis object-store api frontend proxy worker beat
docker compose ps
```

Run the repeatable Phase 3 proof:

```text
docker compose exec -T api python manage.py phase3_tracking_proof --json > docs\evidence\phase3\phase3_tracking_evidence.json
```

Capture browser evidence after the proof:

```text
node scripts\capture_phase3_browser_evidence.mjs
```

The browser capture writes:

- `docs/evidence/phase3/browser_visibility_evidence.json`
- `docs/evidence/phase3/screenshots/phase3-live-resource-map.png`
- `docs/evidence/phase3/screenshots/phase3-exception-alert-list.png`
- `docs/evidence/phase3/screenshots/phase3-scenario-handoff.png`
- `docs/evidence/phase3/screenshots/phase3-audit-evidence.png`

## What Phase 3 Proves

The Phase 3 proof is complete when the operator can verify all of the following:

- synthetic GPS/AIS pings are ingested;
- latest tug, barge, CTS, and OGV state is visible;
- signal freshness is calculated as fresh, aging, stale, or missing;
- geofence enter/exit movement events are derived;
- observed ETA is compared with the planned schedule event;
- tracking alerts are raised for delay, ETA risk, stale signal, and dwell risk;
- an observed delay can create a recovery scenario;
- the scenario carries the tracking alert evidence into a trip-delay assumption;
- the scenario can run without changing the active plan;
- proof and browser evidence are visible in Audit & Logs and the evidence folder.

## UI Flow

### Stage 1 - Open Live Resource Map

1. Open `http://localhost:8080`.
2. Log in as `admin@coalflow.local` or `abl.dispatcher@coalflow.local`.
3. Open **Map & Signals -> Live Resource Map**.
4. Confirm these signals:
   - **Assets tracked** is greater than zero;
   - **Geofences** is greater than zero;
   - **Movement events** is greater than zero;
   - **Open alerts** is greater than zero after replay/proof;
   - **Max ETA variance** shows the largest observed schedule variance.
5. Select a marker or signal-health row and confirm the right detail panel shows source, external ID, last seen, position, current zone, planned event, observed ETA, and ETA variance.

Acceptance evidence: the map is not decorative. It shows asset state, signal quality, geofence context, and schedule variance.

### Stage 2 - Start A Synthetic Replay Manually

Use this only when testing through the UI rather than the automated proof.

1. Stay on **Live Resource Map**.
2. In **Synthetic replay**, select one replay family:
   - `TRACK-ON-TIME`
   - `TRACK-JETTY-DELAY`
   - `TRACK-BRIDGE-WAIT`
   - `TRACK-STALE-SIGNAL`
   - `TRACK-OGV-ETA-SHIFT`
   - `TRACK-CTS-APPROACH`
3. Click **Start replay**.
4. Wait for the success banner.
5. Confirm map KPIs and observed alert rows update.

Acceptance evidence: the selected replay completes and produces pings, movement events, ETA projections, or alerts according to the replay family.

### Stage 3 - Review Observed Alerts

1. Open **Recovery Loop -> Exception Center**.
2. Confirm observed tracking alerts appear in the active queue.
3. Inspect:
   - alert type, such as `DELAY`, `ETA RISK`, `STALE SIGNAL`, or `GEOFENCE DWELL`;
   - affected OGV;
   - resource asset code;
   - impact text;
   - status and next action.
4. Select a row and inspect the right detail panel.

Important behavior: only `DELAY` alerts can be converted into scenarios in Phase 3. Other observed alerts are triage evidence for now.

### Stage 4 - Convert A Delay Alert To Scenario

If the automated proof has already run, the seeded delay alert may already be converted and no longer appear as an active delay row. In that case, open **Simulation Workspace** and inspect the tracking-origin scenario.

To test conversion manually from a fresh replay:

1. Reset or reseed the environment.
2. Start `TRACK-JETTY-DELAY`.
3. Open **Recovery Loop -> Exception Center**.
4. Select the `DELAY` alert for `BRG-VAL-08`.
5. Click **Create scenario** in the alert detail panel.
6. Open **Recovery Loop -> Simulation Workspace**.

Acceptance evidence: a scenario with source `TRACKING ALERT` is created, and its assumption list includes `TRIP DELAY` using the observed variance minutes.

### Stage 5 - Run The Scenario

1. Open **Recovery Loop -> Simulation Workspace**.
2. Select the scenario whose source is `TRACKING ALERT`.
3. Confirm:
   - scenario name references the observed delay;
   - source shows the tracking alert reference;
   - assumption list includes `TRIP DELAY`;
   - selected run exists after proof, or click **Run simulation** if testing manually.
4. Review:
   - changed trips;
   - max delay;
   - risk flags;
   - baseline vs scenario table;
   - projected event timeline;
   - constraint evaluations;
   - calculated impact chain.

Acceptance evidence: tracking evidence becomes a planning what-if without directly editing trips, assignments, or published schedule state.

### Stage 6 - Review Audit Evidence

1. Open **Admin Console -> Audit & Logs**.
2. Confirm `phase3.proof.*` audit actions exist:
   - `phase3.proof.replay_pack_seeded`;
   - `phase3.proof.replays_executed`;
   - `phase3.proof.observed_evidence_verified`;
   - `phase3.proof.scenario_handoff_verified`;
   - `phase3.proof.rerun_verified`.
3. Confirm the browser evidence file and screenshots exist under `docs/evidence/phase3/`.

Acceptance evidence: the telemetry-to-scenario chain is auditable and repeatable.

## Replay Families

| Replay | Operator meaning | Expected evidence |
|---|---|---|
| `TRACK-ON-TIME` | Tug reaches planned route points ahead of schedule | Fresh signal, movement events, no false delay |
| `TRACK-JETTY-DELAY` | Barge remains at jetty after planned departure | Delay and dwell evidence, scenario conversion path |
| `TRACK-BRIDGE-WAIT` | Tug reaches bridge late | ETA risk against bridge-cross event |
| `TRACK-STALE-SIGNAL` | Barge signal stops and ages out | Stale signal alert |
| `TRACK-OGV-ETA-SHIFT` | OGV AIS-style ETA changes | OGV latest state and observed signal evidence |
| `TRACK-CTS-APPROACH` | Loaded barge approaches CTS zone | CTS approach movement events and ETA projection |

## Current Limits

Phase 3 does not include:

- live third-party AIS/GPS provider integration;
- provider credential management;
- map tile basemap or nautical chart rendering;
- Phase 4 confirmation authority from downstream systems;
- Phase 5 optimizer and recovery recommendation engine;
- automatic fleet-wide recovery repair.

These are intentionally deferred. Phase 3 closes the visibility and evidence-to-scenario handoff layer.

## Troubleshooting

If the map shows zero tracked assets, run the Phase 3 proof command or start a replay. Also confirm the user has `telemetry.view`.

If **Start replay** is disabled, use a user with `telemetry.ingest`, such as Admin, ABL Dispatcher, or Joint Control Tower.

If no delay alert can be converted, check whether the automated proof already converted it. Converted delay alerts appear as tracking-origin scenarios in Simulation Workspace.

If screenshots fail on a local machine, set `CHROME_PATH` to a Chromium-compatible browser and rerun:

```text
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
node scripts\capture_phase3_browser_evidence.mjs
```

If map or alert payloads grow too large, use the bounded telemetry endpoints with `?limit=120`; the frontend does this by default for movement events, ETA projections, and alerts.
