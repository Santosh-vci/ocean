import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";
import { visibleNavItems } from "./lib/navigation";
import { JettyLoadingPage } from "./pages/LogisticsPages";
import { ExceptionCenterPage, SimulationWorkspacePage } from "./pages/RecoveryPages";
import type { SchedulingOverview } from "./types";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((input: string) => {
      if (input.endsWith("/me/")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 1,
            username: "admin@coalflow.local",
            email: "admin@coalflow.local",
            is_active: true,
            memberships: [],
            assignments: [],
            permissions: ["dashboard.view"],
          }),
        });
      }

      return Promise.resolve({
        ok: true,
        json: async () => [],
      });
    }),
  );
});

test("filters navigation by permission", () => {
  expect(visibleNavItems(["dashboard.view"]).map((item) => item.label)).toEqual([
    "Network Situation",
  ]);
});

test("shows implemented admin submodules without exposing future locked routes", () => {
  expect(
    visibleNavItems(["dashboard.view", "masterdata.view", "schedule.view"]).map(
      (item) => item.label,
    ),
  ).toEqual([
    "Network Situation",
    "OGV Demand & Laycan",
    "Coal Grade Sequence",
    "Tide & Bridge Window",
    "Tug/Barge Assignment",
    "Jetty Loading",
    "CTS / Floating Crane",
    "Published Plan & Schedule",
    "Exception Center",
    "Master Data Console",
  ]);
});

test("exposes recovery routes by workflow permission", () => {
  expect(
    visibleNavItems([
      "dashboard.view",
      "schedule.view",
      "schedule.edit",
      "schedule.approve",
    ]).map((item) => item.label),
  ).toContain("Simulation Workspace");
  expect(
    visibleNavItems([
      "dashboard.view",
      "schedule.view",
      "schedule.edit",
      "schedule.approve",
    ]).map((item) => item.label),
  ).toContain("Approvals & Publishing");
});

test("exposes live map through fleet visibility", () => {
  expect(visibleNavItems(["dashboard.view", "fleet.view"]).map((item) => item.label)).toContain(
    "Live Resource Map",
  );
});

test("exposes governed exports through export visibility", () => {
  expect(visibleNavItems(["dashboard.view", "export.view"]).map((item) => item.label)).toContain(
    "Exports & Handoff",
  );
});

test("renders the role-aware dashboard shell", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Network Situation" })).toBeInTheDocument();
  expect(screen.queryByText("Users & RBAC")).not.toBeInTheDocument();
});

function stageSevenOverview(): SchedulingOverview {
  return {
    activePlanVersion: { plan_code: "PLAN-UI", status: "validated", version_no: 1 },
    assignments: [{
      id: 101,
      trip: 201,
      trip_ref: "PI-PLAN-UI-0001",
      vessel_name: "MV Operator UI Import",
      planned_quantity_mt: 32000,
      jetty: { code: "JTY-SUARAN", status: "available" },
      barge: { code: "BRG-VAL-08" },
      tug: { code: "BER-TUG-08", name: "Tug 08" },
      cts: null,
      route_segment: 1,
      owner_organization: null,
      planned_departure: "2026-05-17T03:30:00.000Z",
      planned_arrival: "2026-05-17T09:30:00.000Z",
      tug_status: "READY",
      barge_status: "READY",
      next_constraint: "Ready",
      next_action: "Dispatch chain on planned window.",
      status: "assigned",
      created_at: "2026-05-16T08:00:00.000Z",
      updated_at: "2026-05-16T08:00:00.000Z",
    }],
    trips: [{
      id: 201,
      trip_id: "PI-PLAN-UI-0001",
      voyage: { vessel_name: "MV Operator UI Import" },
      planned_start: "2026-05-17T01:30:00.000Z",
      planned_end: "2026-05-17T11:30:00.000Z",
      planned_quantity_mt: 32000,
      loaded_quantity_mt: 0,
      status: "planned",
      cargo_layer_step: { coal_grade: { code: "EBONY" }, hatch_no: 1, layer_no: 1 },
      assignment: null,
      events: [{ event_type: "load_start", planned_at: "2026-05-17T01:30:00.000Z" }],
    }],
    conflicts: [],
    overrideRequests: [],
    validation: { tripCount: 1, assignmentCount: 1, eventCount: 1 },
  } as unknown as SchedulingOverview;
}

test("force-start jetty captures an effective start time", () => {
  const onForceStartJetty = vi.fn();
  render(
    <JettyLoadingPage
      canEdit
      onForceStartJetty={onForceStartJetty}
      overview={stageSevenOverview()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Force start jetty" }));
  expect(screen.getByLabelText("Effective start time")).toBeRequired();
  fireEvent.click(screen.getByRole("button", { name: "Apply governed override" }));

  expect(onForceStartJetty).toHaveBeenCalledWith(101, expect.stringContaining("T"));
});

test("exception center renders calculated impact chain nodes", () => {
  const overview = stageSevenOverview();
  overview.overrideRequests = [{
    id: 50,
    plan_version: 1,
    plan_version_ref: "PLAN-UI V1",
    trip: 201,
    trip_ref: "PI-PLAN-UI-0001",
    vessel_name: "MV Operator UI Import",
    assignment: 101,
    reason_code: "jetty_delay",
    description: "Force-started JTY-SUARAN from operator cockpit.",
    requested_change: { status: "loading" },
    before_state: { status: "assigned" },
    after_state: { status: "loading" },
    status: "applied",
    requested_by: 1,
    requested_by_email: "berau.scheduler@coalflow.local",
    applied_by: 1,
    applied_by_email: "berau.scheduler@coalflow.local",
    applied_at: "2026-05-16T08:29:00.000Z",
    created_at: "2026-05-16T08:29:00.000Z",
    impact_assessment: {
      id: 1,
      assessment_id: "ICA-PLAN-UI-OR0050",
      plan_version: 1,
      plan_version_ref: "PLAN-UI V1",
      trip: 201,
      trip_ref: "PI-PLAN-UI-0001",
      assignment: 101,
      assignment_ref: "PI-PLAN-UI-0001 assignment",
      override_request: 50,
      override_request_ref: "jetty_delay override on PLAN-UI V1",
      source_kind: "override",
      status: "critical",
      delay_minutes: 120,
      metadata: { actualStartAt: "2026-05-17T03:30:00.000Z" },
      created_at: "2026-05-16T08:29:00.000Z",
      updated_at: "2026-05-16T08:29:00.000Z",
      nodes: [
        { id: "source", type: "source_event", label: "JETTY DELAY", value: "May 17, 03:30", status: "warning", detail: "Effective start against planned load." },
        { id: "logistics", type: "logistics_delay", label: "BARGE DELAY", value: "+120m", status: "warning", detail: "Current-trip event times shifted." },
        { id: "tide", type: "tide_window", label: "TIDE WINDOW MISSED", value: "by 90m", status: "critical", detail: "Projected gate misses TIDE-IMPACT-TEST." },
      ],
    },
  }];

  render(<ExceptionCenterPage overview={overview} />);

  expect(screen.getByText("BARGE DELAY")).toBeInTheDocument();
  expect(screen.getAllByText("+120m").length).toBeGreaterThan(0);
  expect(screen.getByText("TIDE WINDOW MISSED")).toBeInTheDocument();
  expect(screen.queryByText("Barge delay (+2h)")).not.toBeInTheDocument();
});

test("simulation workspace renders computed run results and impact nodes", () => {
  const overview = stageSevenOverview();
  overview.simulationScenarios = [{
    id: 301,
    scenario_id: "SCN-PLAN-UI-0001",
    name: "Jetty recovery scenario",
    scenario_type: "recovery",
    baseline_version: 1,
    baseline_version_ref: "PLAN-UI V1",
    scenario_version: null,
    scenario_version_ref: null,
    source_conflict: null,
    source_conflict_code: null,
    source_conflict_message: null,
    source_override: 50,
    source_override_reason_code: "jetty_delay",
    source_override_description: "Force-started JTY-SUARAN from operator cockpit.",
    source_kind: "override",
    status: "draft",
    recovery_actions: ["Hold tug chain until bridge slot is confirmed."],
    impact_summary: {},
    delta_summary: {
      delayDeltaMinutes: 120,
      demurrageDeltaUsd: "2500.00",
      fleetUtilizationPct: "4.5",
      remainingViolations: 0,
    },
    created_by: 1,
    created_by_email: "berau.scheduler@coalflow.local",
    assumptions: [{
      id: 401,
      scenario: 301,
      scenario_ref: "SCN-PLAN-UI-0001",
      assumption_id: "ASSUMP-001",
      kind: "trip_delay",
      scope_type: "trip",
      scope_id: 201,
      payload: { delay_minutes: 120 },
      effective_from: null,
      effective_to: null,
      created_by: 1,
      created_by_email: "berau.scheduler@coalflow.local",
      created_at: "2026-05-16T08:29:00.000Z",
      updated_at: "2026-05-16T08:29:00.000Z",
    }],
    runs: [{
      id: 501,
      scenario: 301,
      scenario_ref: "SCN-PLAN-UI-0001",
      run_id: "RUN-PLAN-UI-0001",
      baseline_version: 1,
      baseline_version_ref: "PLAN-UI V1",
      status: "completed",
      algorithm_version: "sim-impact-v1",
      input_hash: "abcdef1234567890",
      started_at: "2026-05-16T08:30:00.000Z",
      completed_at: "2026-05-16T08:30:30.000Z",
      summary: {
        constraintSummary: { critical: 0, warning: 1 },
        projectionSummary: { changedTripCount: 1, maxDelayMinutes: 120 },
        ogvSummary: { demurrageDeltaUsd: 2500 },
        utilizationSummary: { averageUtilizationDeltaPct: 4.5 },
      },
      created_by: 1,
      created_by_email: "berau.scheduler@coalflow.local",
      trip_projections: [{
        id: 601,
        run: 501,
        trip: 201,
        trip_ref: "PI-PLAN-UI-0001",
        baseline_start: "2026-05-17T01:30:00.000Z",
        baseline_end: "2026-05-17T11:30:00.000Z",
        projected_start: "2026-05-17T03:30:00.000Z",
        projected_end: "2026-05-17T13:30:00.000Z",
        projected_status: "planned",
        delay_minutes: 120,
        assignment_delta: {},
        metadata: {},
        created_at: "2026-05-16T08:30:30.000Z",
      }],
      constraint_evaluations: [{
        id: 701,
        run: 501,
        evaluation_id: "EVAL-001",
        trip: 201,
        trip_ref: "PI-PLAN-UI-0001",
        code: "TIDE_WINDOW_MISSED",
        severity: "warning",
        affected_object_type: "tide_window",
        affected_object_id: "TIDE-OPERATING-01",
        baseline_value: {},
        projected_value: {},
        margin_minutes: -15,
        source_assumption_ids: ["ASSUMP-001"],
        message: "Projected tide gate is 15 minutes outside the active operating window.",
        metadata: {},
        created_at: "2026-05-16T08:30:30.000Z",
      }],
      ogv_projections: [{
        id: 801,
        run: 501,
        voyage: 901,
        voyage_ref: "VOY-001",
        vessel_name: "MV Operator UI Import",
        baseline_completion_at: "2026-05-17T11:30:00.000Z",
        projected_completion_at: "2026-05-17T13:30:00.000Z",
        completion_delta_minutes: 120,
        laycan_end: "2026-05-18T00:00:00.000Z",
        baseline_demurrage_minutes: 0,
        projected_demurrage_minutes: 0,
        demurrage_delta_usd: "2500.00",
        risk_status: "warning",
        metadata: {},
        created_at: "2026-05-16T08:30:30.000Z",
      }],
      resource_utilizations: [{
        id: 901,
        run: 501,
        resource_type: "barge",
        resource_code: "BRG-VAL-08",
        baseline_occupied_minutes: 600,
        projected_occupied_minutes: 720,
        baseline_idle_minutes: 120,
        projected_idle_minutes: 60,
        waiting_minutes: 60,
        utilization_delta_pct: "4.50",
        metadata: {},
        created_at: "2026-05-16T08:30:30.000Z",
      }],
      impact_assessments: [{
        id: 1001,
        assessment_id: "ICA-RUN-PLAN-UI-0001-201",
        plan_version: 1,
        plan_version_ref: "PLAN-UI V1",
        trip: 201,
        trip_ref: "PI-PLAN-UI-0001",
        assignment: 101,
        assignment_ref: "PI-PLAN-UI-0001 assignment",
        override_request: null,
        override_request_ref: null,
        source_kind: "simulation",
        status: "warning",
        delay_minutes: 120,
        metadata: {},
        nodes: [
          { id: "source", type: "source_event", label: "JETTY DELAY", value: "+120m", status: "warning", detail: "Scenario effective start against baseline." },
          { id: "barge", type: "logistics_delay", label: "BARGE DELAY", value: "+120m", status: "warning", detail: "Trip schedule shifted by simulation." },
          { id: "target", type: "final_target", label: "MV Operator UI Import", value: "WARNING", status: "warning", detail: "Projected completion risk." },
        ],
        created_at: "2026-05-16T08:30:30.000Z",
        updated_at: "2026-05-16T08:30:30.000Z",
      }],
      created_at: "2026-05-16T08:30:00.000Z",
      updated_at: "2026-05-16T08:30:30.000Z",
    }],
    created_at: "2026-05-16T08:29:00.000Z",
    updated_at: "2026-05-16T08:30:30.000Z",
  }];

  render(<SimulationWorkspacePage canEdit overview={overview} />);

  expect(screen.getByText("Selected run projection")).toBeInTheDocument();
  expect(screen.getAllByText("Constraint evaluations").length).toBeGreaterThan(0);
  expect(screen.getAllByText("TIDE_WINDOW_MISSED").length).toBeGreaterThan(0);
  expect(screen.getByText("OGV completion & demurrage")).toBeInTheDocument();
  expect(screen.getByText("Asset utilization")).toBeInTheDocument();
  expect(screen.getByText("BARGE DELAY")).toBeInTheDocument();
  expect(screen.getByText(/BRG-VAL-08/)).toBeInTheDocument();
  expect(screen.queryByText("OUT OF SERVICE")).not.toBeInTheDocument();
  expect(screen.queryByText("RECOVERY WINDOW")).not.toBeInTheDocument();
});
