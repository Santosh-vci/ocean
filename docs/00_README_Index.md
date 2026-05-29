# Berau Coal × ABL Scheduling Simulation Exploration Pack

Generated: 2026-05-15

## Purpose

This document pack summarizes the operational ground reality for a scheduling simulation and live planning tool covering the coal movement chain from Berau Coal production/loading points to ABL-led barging/transshipment/Ocean Going Vessel interfaces.

The pack is based on:

- The uploaded BRD: `BRD - Schedulling Simulation.docx`
- Berau Coal Energy public website pages
- ABL public website pages

## Documents

1. `01_Ground_Reality_Operations.md`  
   Operational context: coal source, mine-to-barge flow, product/market context, transshipment assets, and ABL capability.

2. `02_Planning_Tool_Scope.md`  
   Scope of the scheduling simulation/live planning tool: users, planning objects, constraints, decision flows, exception handling, and phased product scope.

3. `03_Data_Architecture_and_IoT_Scope.md`  
   Data, GPS/AIS/IoT, hardware, integration, and system architecture scope required to support the planning platform.

4. `04_RBAC_and_Django_Architecture_Addendum.md`  
   RBAC, multi-organization governance, and recommended Django-based architecture.

7. `07_Frontend_Build_Handoff_and_Phasewise_Plan.md`  
   Consolidated frontend screen inventory, validation status, MVP prioritization, phase-wise implementation plan, component checklist, and coding handoff rules.

8. `08_Phase_1_Implementation_Spec.md`  
   Product Phase 1 implementation specification: Dockerized target stack, domain model, schedule engine rules, API surface, chunked delivery plan, testing strategy, and phase-exit criteria.

9. `09_Ch0_Ch6_Implementation_Validation.md`
   Validation matrix for the first six implementation chunks and the gaps closed in the dashboard/read-model pass.

10. `10_Pilot_Readiness_Runbook.md`
    Docker deployment, health checks, seeded pilot users, UAT scripts, backup rehearsal, restore, and logging rules.

11. `11_API_Contract_Baseline.md`
    Baseline Phase 1 API contract for authentication, planning, scheduling, dashboard, exports, and audit.

12. `12_Phase_1_Completion_Evidence.md`
    Runtime proof evidence for the ten Phase 1 definition-of-done stages, with the latest machine-readable evidence file under `docs/evidence/phase1/`.

13. `13_Phase_1_Operator_Manual.md`
    Stage-by-stage operator instructions for conducting end-to-end Phase 1 planning.

14. `14_Phase_2_Implementation_Spec.md`
    Product Phase 2 implementation specification for simulation and scenario planning: assumption model, run architecture, projection engine, UI/API expansion, delivery chunks, and later-phase compatibility.

15. `15_Phase_2_Scenario_Proof_Evidence.md`
    Runtime proof evidence for the Phase 2 scenario-planning flow, including the seeded scenario pack, selected-run promotion, governed export, audit lineage, and browser-visible evidence.

16. `16_Phase_2_Scenario_Operator_Guide.md`
    Operator-facing explanation of each seeded Phase 2 what-if scenario, manual scenario-building steps, and the governance path after scenarios exist.

17. `17_Phase_3_Implementation_Spec.md`
    Product Phase 3 implementation specification for GPS/AIS live tracking using Synthetic Live Data Mode, telemetry ingestion, geofence events, ETA variance, delay alerts, live map upgrades, and scenario handoff.

18. `18_Phase_3_Operator_Runbook.md`
    Operator-facing runbook for using Phase 3 telemetry, synthetic replay, observed tracking alerts, and tracking-alert scenario handoff.

19. `19_Phase_3_Completion_Evidence.md`
    Runtime closure evidence for Phase 3, including the five-stage proof command, browser evidence, screenshots, audit evidence, and remaining deferred scope.

20. `20_Phase_4_Implementation_Spec.md`
    Product Phase 4 implementation specification for IoT/event-driven operations: event candidates, trusted confirmations, device/feed health, edge replay, actualization, board integration, and closure evidence.

21. `21_Phase_4_Operator_Runbook.md`
    Operator-facing runbook for using Phase 4 Synthetic Event Feed Mode, event confirmation, actualized operations boards, event-driven exceptions, and audit evidence.

22. `22_Phase_4_Completion_Evidence.md`
    Runtime closure evidence for Phase 4, including the five-stage proof command, browser screenshots, performance evidence, audit evidence, and remaining deferred scope.

23. `23_Phase_5_Implementation_Spec.md`
    Product Phase 5 implementation specification for deterministic recovery recommendations, scenario materialization, approval handoff, and proof-pack closure.

24. `24_Phase_5_Operator_Runbook.md`
    Operator-facing runbook for generating recovery options, reviewing ranked recommendations, creating scenarios, and validating governance/audit evidence.

25. `25_Phase_5_Completion_Evidence.md`
    Runtime closure evidence for Phase 5, including the seven-stage proof command, proof-pack lineage, browser screenshots, governance handoff, and remaining deferred scope.

26. `26_Phase_6_Phase_5_Plus_Implementation_Spec.md`
    Phase 6 / Phase 5+ implementation specification for persistent flow runtime, flow-aware Next Action guidance, stronger recovery repair, publishability validation, DB-truth operator trial seeding, live telemetry trust, global optimization scaffolding, and projection-only commercial outputs.

## Important interpretation

This is not a generic fleet tracking product. The required tool is a constraint-aware transshipment planning and simulation engine where AIS/GPS/IoT are live-data inputs, not the full planning logic.

The planning logic must bind:

- OGV demand
- coal grade/product requirement
- mine/stockpile/jetty loading capability
- tug/barge/CTS availability
- river/tide/bridge constraints
- live position/status
- schedule disruption and recovery simulation
