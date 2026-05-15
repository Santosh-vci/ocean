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

