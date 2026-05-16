# 13 — Phase 1 Operator Manual

## Purpose

This manual gives an operator a repeatable way to conduct Phase 1 planning end-to-end in the Dockerized Coalflow Tower system. It is written for the current Phase 1 product surface: the UI is the operating cockpit for review, inspection, approval visibility, audit, and export; the API and proof command are the governed mutation controls for repeatable UAT and pilot execution.

## 1. Start the system

From `F:\ocean`:

```powershell
docker compose up -d --build db redis object-store api frontend proxy worker beat
docker compose ps
Invoke-RestMethod http://localhost:8080/api/ready/
```

Expected readiness: `database.ok=true`, `cache.ok=true`, and `exportStorage.ok=true`.

Open the application at:

```text
http://localhost:8080
```

## 2. Login roles

| Role | User | Password | Operational use |
|---|---|---|---|
| Admin | `admin@coalflow.local` | `admin12345` | setup, proof/UAT execution, master data access |
| Berau Scheduler | `berau.scheduler@coalflow.local` | `welcome12345` | demand and cargo-layer responsibility |
| ABL Dispatcher | `abl.dispatcher@coalflow.local` | `welcome12345` | fleet, jetty, CTS, and availability responsibility |
| Joint Control Tower | `control.tower@coalflow.local` | `welcome12345` | approval visibility, publication, governed export |
| Viewer | `viewer@coalflow.local` | `welcome12345` | read-only operational observation |

Change all passwords before any shared environment.

## 3. Run the Phase 1 proof scenario

For UAT or handover validation, run:

```powershell
docker compose run --rm -e RUN_STARTUP_TASKS=0 api python manage.py phase1_e2e_proof --json
```

This creates the visible proof plan:

- plan: `PLAN-PHASE1-E2E`
- voyage: `VOY-PHASE1-HAPPY-001` / `MV Phase One Reliance`
- demand: `64,000 MT`
- cargo layers: `EBONY` then `AGATHIS`
- published snapshot: `LIVE-PLAN-PHASE1-E2E-V1`
- governed export: `coalflow-plan-plan-phase1-e2e-v1-...txt`

It also preserves the seeded constraint scenario `PLAN-2026-10-24`, which contains tide, bridge, barge, layer-sequence, jetty, and compatibility conflicts.

For API-driven steps below, collect the current runtime IDs after login:

```powershell
$overview = Invoke-RestMethod http://localhost:8080/api/scheduling/overview/ -WebSession $s
$planVersionId = $overview.activePlanVersion.id
$assignmentId = $overview.assignments[0].id
$approvalRequestId = $overview.approvalRequests[0].id
```

If the active plan is not the intended plan, use the `planVersions`, `assignments`, and
`approvalRequests` arrays from the same response to select the correct IDs.

## 4. Stage-by-stage operating procedure

### Stage 1 — Confirm role and organization

1. Login as the intended operator.
2. Confirm the top bar shows the expected organization and role context.
3. Confirm the sidebar only exposes modules allowed for that user.
4. If a user sees too much or too little, stop and have Admin review **Admin Console → Users & RBAC**.

Acceptance evidence: `/api/me/` returns the user, organization memberships, and permission list.

### Stage 2 — Review master data

1. Login as Admin or Berau Scheduler.
2. Open **Admin Console → Master Data Console**.
3. Review at minimum:
   - coal grades: `EBONY`, `MAHONI`, `AGATHIS`, `SUNGKAI`;
   - jetties: `JTY-SUARAN`, `JTY-LATI`, `JTY-GMB`;
   - fleet: `BER-TUG-08`, `BER-TUG-09`, `BRG-VAL-08`, `BRG-NUS-17`;
   - CTS: `CTS-BORNEO`, `CTS-JAVA`, `FC-CHLOE`;
   - route segments for `RTE-SUARAN-MUARA`.
4. Do not proceed if a required asset, grade, route, jetty, or CTS is inactive or missing.

Acceptance evidence: records are visible in **Master Data Console** and `/api/master-data/overview/`.

### Stage 3 — Upload or enter OGV demand and cargo layers

1. Login as Berau Scheduler.
2. Open **Planning → OGV Demand & Laycan**.
3. Verify the proof voyage appears after the proof run:
   - `VOY-PHASE1-HAPPY-001`
   - `MV Phase One Reliance`
   - `64,000 MT`
   - low risk
4. Inspect vessel detail and confirm two cargo-layer rows:
   - sequence 1: `EBONY`, hatch/layer `H1/L1`, `32,000 MT`;
   - sequence 2: `AGATHIS`, hatch/layer `H2/L1`, `32,000 MT`.
5. For API-driven intake, validate the demand file first:

```powershell
$csrf = (Invoke-RestMethod http://localhost:8080/api/auth/csrf/ -SessionVariable s).csrfToken
Invoke-RestMethod http://localhost:8080/api/auth/login/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf} -ContentType "application/json" -Body '{"username":"berau.scheduler@coalflow.local","password":"welcome12345"}'
Invoke-RestMethod http://localhost:8080/api/planning/import-jobs/validate-ogv-demand/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf} -ContentType "application/json" -Body '{"filename":"operator-demand.xlsx","rows":[{"voyage_id":"VOY-OPS-001","vessel_name":"MV Operator Test","customer_name":"Pilot Customer","laycan_start":"2026-11-05T00:00:00Z","laycan_end":"2026-11-08T00:00:00Z","eta":"2026-11-05T06:00:00Z","required_mt":64000}]}'
```

Acceptance evidence: an import job appears in **OGV Demand & Laycan** and audit logs show `planning_import_job.validate` or `phase1.proof.demand_uploaded`.

### Stage 4 — Enter availability, tide, and bridge windows

1. Login as ABL Dispatcher.
2. Open **Constraints → Tide & Bridge Window**.
3. Confirm proof windows:
   - tide: `TIDE-P1-E2E-RANTAU`;
   - bridge: `BRDG-P1-E2E-GATE-B`;
   - navigation checks for `BRG-VAL-08` and `BRG-NUS-17` are `can_cross`.
4. Review the seeded constraint examples in the same board:
   - `BRIDGE_WINDOW_MISSED` for `MV NORTH STAR`;
   - `TIDE_WINDOW_MISSED` warning for `MV TRITON STAR`.

Acceptance evidence: **Tide & Bridge Window** shows both happy-path open windows and seeded missed/marginal gates.

### Stage 5 — Generate a draft schedule

1. The repeatable proof command generates `PLAN-PHASE1-E2E V1`.
2. For direct API execution, create or choose a draft plan version, then call:

```powershell
Invoke-RestMethod http://localhost:8080/api/scheduling/plan-versions/{planVersionId}/generate/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf}
```

3. Confirm generation output:
   - status: `validated` before approval;
   - validation status: `feasible`;
   - conflicts: `0` for happy path.

Acceptance evidence: **Operations → Published Plan & Schedule** shows generated trips for `PLAN-PHASE1-E2E`.

### Stage 6 — Inspect trip chain and conflicts

1. Login as Joint Control Tower or ABL Dispatcher.
2. Open **Operations → Tug & Barge Assignment**.
3. Confirm the proof trip chain:
   - `PI-PLAN-PHASE1-E2E-0001` uses `BER-TUG-08` / `BRG-VAL-08` for `32,000 MT`;
   - `PI-PLAN-PHASE1-E2E-0002` uses `BER-TUG-08` / `BRG-NUS-17` for `32,000 MT`.
4. Open **Recovery Loop → Exception Center** to inspect conflict behavior in the seeded constraint plan.
5. Confirm examples include barge unavailability, bridge miss, layer sequence violation, tug/barge incompatibility, jetty overlap, and tide warning.

Acceptance evidence: trip chains and conflict cards reconcile with `/api/scheduling/overview/`.

### Stage 7 — Make governed adjustment with reason

1. Login as ABL Dispatcher.
2. Apply a controlled assignment override only against a non-published draft/proposed/validated plan.
3. Required fields:
   - reason code, e.g. `manual_correction`;
   - description, e.g. `Dispatcher confirmed tow readiness after manual VHF check.`;
   - changed assignment fields.
4. For API execution:

```powershell
Invoke-RestMethod http://localhost:8080/api/scheduling/assignments/{assignmentId}/apply-override/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf} -ContentType "application/json" -Body '{"reason_code":"manual_correction","description":"Dispatcher confirmed tow readiness after manual VHF check.","changes":{"next_action":"Dispatch chain on confirmed tide and bridge window.","next_constraint":"Operator clearance confirmed."}}'
```

Acceptance evidence: **Recovery Loop → Exception Center** and audit logs show the override with reason and before/after state.

### Stage 8 — Submit, approve, and publish

1. Submit the plan for approval.
2. Berau Scheduler approves demand and cargo-layer sequence.
3. ABL Dispatcher approves fleet, jetty, CTS, tide, and bridge readiness.
4. Joint Control Tower publishes after all blocking conflicts are resolved.
5. For API execution:

```powershell
Invoke-RestMethod http://localhost:8080/api/scheduling/plan-versions/{planVersionId}/request-approval/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf} -ContentType "application/json" -Body '{"reason":"Plan feasible and ready for dual-party publication."}'
Invoke-RestMethod http://localhost:8080/api/scheduling/approval-requests/{approvalRequestId}/decide/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf} -ContentType "application/json" -Body '{"authority_role":"berau_scheduler","decision":"approve","comments":"Berau accepts demand and cargo-layer sequence."}'
Invoke-RestMethod http://localhost:8080/api/scheduling/approval-requests/{approvalRequestId}/decide/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf} -ContentType "application/json" -Body '{"authority_role":"abl_dispatcher","decision":"approve","comments":"ABL accepts fleet readiness."}'
Invoke-RestMethod http://localhost:8080/api/scheduling/plan-versions/{planVersionId}/publish/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf}
```

Acceptance evidence: **Recovery Loop → Approvals & Publishing** shows the approval chain complete and published snapshot `LIVE-PLAN-PHASE1-E2E-V1`.

### Stage 9 — Retrieve live published version and audit trail

1. Open **Schedule → Published Plan & Schedule**.
2. Confirm the active published plan and trip chain.
3. Open **Admin Console → Audit & Logs**.
4. Confirm audit events exist for the proof or operator flow.
5. Confirm no one edits the published version directly. Create a successor draft/replan instead.

Acceptance evidence: `/api/scheduling/overview/` includes `publishedSnapshots`; audit logs include proof or lifecycle events.

### Stage 10 — Export governed schedule

1. Login as Joint Control Tower.
2. Open **Admin Console → Exports & Handoff**.
3. Select **Generate schedule** or generate through the API:

```powershell
Invoke-RestMethod http://localhost:8080/api/exports/generate/ -WebSession $s -Method Post -Headers @{"X-CSRFToken"=$csrf} -ContentType "application/json" -Body '{"export_type":"plan","export_format":"print","plan_version":{planVersionId}}'
```

4. Confirm export history shows:
   - export ID;
   - file name;
   - record count;
   - storage URI;
   - checksum;
   - download link.
5. Download the export. Do not manually edit the file as an operational substitute for plan governance.

Acceptance evidence: **Exports & Handoff** shows the generated export and `/api/exports/{id}/download/` returns the artifact.

## 5. Stop conditions

Stop the planning run and escalate if any of these occur:

- master data is missing, inactive, or contradictory;
- OGV demand validation fails;
- cargo-layer sequence is violated;
- tug/barge/jetty/CTS assignment is unavailable;
- tide or bridge window is missed and unresolved;
- approval request lacks either Berau or ABL approval;
- publish is attempted with unresolved blocking conflicts;
- export generation is attempted by a role without `export.generate`.

## 6. Completion checklist

A planning run is complete only when all are true:

- operator roles are correct;
- demand and cargo layers are visible;
- availability, tide, and bridge windows are visible;
- schedule has generated trips and events;
- conflicts are understood or resolved;
- overrides include reason, actor, and before/after state;
- dual approval is complete;
- live published snapshot exists;
- audit trail is retrievable;
- governed export is generated and downloadable.
