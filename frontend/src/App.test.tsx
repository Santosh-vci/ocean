import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";
import { visibleNavItems } from "./lib/navigation";
import { CoalGradeSequencePage } from "./pages/CoalGradeSequencePage";
import { CtsOperationsPage, JettyLoadingPage, PublishedPlanPage } from "./pages/LogisticsPages";
import { LiveResourceMapPage } from "./pages/MapPage";
import { OgvDemandPage } from "./pages/OgvDemandPage";
import { OperationsEventConsolePage } from "./pages/OperationsEventConsolePage";
import {
  CommercialProjectionPage,
  ExceptionCenterPage,
  GlobalOptimizationReviewPage,
  RecommendationConsolePage,
  SimulationWorkspacePage,
} from "./pages/RecoveryPages";
import { TideBridgePage } from "./pages/TideBridgePage";
import type { ActionRecommendation } from "./types/assistant";
import type {
  ConfirmedOperationalEventRecord,
  DeviceEndpointRecord,
  LatestAssetStateRecord,
  OperationalEventCandidateRecord,
  PlanningOverview,
  SchedulingOverview,
} from "./types";

beforeEach(() => {
  window.localStorage.clear();
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

function assistantAction(overrides: Partial<ActionRecommendation> = {}): ActionRecommendation {
  return {
    actionId: "IMPORT_OGV_DEMAND",
    label: "Import OGV demand",
    priority: "warning",
    rankScore: 760,
    enabled: true,
    route: "/schedule/ogv-demand",
    ctaLabel: "Import demand",
    reason: "No active OGV demand is available for planning.",
    hoverHint: "",
    detailText: "",
    impactIfIgnored: "",
    ownerRole: "berau-scheduler",
    requiredPermission: "schedule.edit",
    auditRequired: true,
    targetObjectType: null,
    targetObjectId: null,
    blockedReason: "",
    source: "planning.no_demand",
    expiresAt: null,
    metadata: {},
    ...overrides,
  };
}

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
    "Recommendation Console",
    "Global Optimization Review",
    "Commercial Projections",
    "Master Data Console",
  ]);
});

test("exposes event confirmation through operations visibility", () => {
  expect(visibleNavItems(["dashboard.view", "operations.view"]).map((item) => item.label)).toContain(
    "Event Confirmation",
  );
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
  ).toContain("Recommendation Console");
  expect(
    visibleNavItems([
      "dashboard.view",
      "schedule.view",
      "schedule.edit",
      "schedule.approve",
    ]).map((item) => item.label),
  ).toContain("Global Optimization Review");
  expect(
    visibleNavItems([
      "dashboard.view",
      "schedule.view",
      "schedule.edit",
      "schedule.approve",
    ]).map((item) => item.label),
  ).toContain("Approvals & Publishing");
  expect(
    visibleNavItems([
      "dashboard.view",
      "schedule.view",
      "schedule.edit",
      "schedule.approve",
    ]).map((item) => item.label),
  ).toContain("Commercial Projections");
});

test("exposes live map through telemetry visibility", () => {
  expect(visibleNavItems(["dashboard.view", "telemetry.view"]).map((item) => item.label)).toContain(
    "Live Resource Map",
  );
  expect(visibleNavItems(["dashboard.view", "fleet.view"]).map((item) => item.label)).not.toContain(
    "Live Resource Map",
  );
});

test("exposes governed exports through export visibility", () => {
  expect(visibleNavItems(["dashboard.view", "export.view"]).map((item) => item.label)).toContain(
    "Exports & Handoff",
  );
});

test("OGV demand page renders route-specific assistant guidance", () => {
  render(
    <OgvDemandPage
      assistantPageActions={[assistantAction()]}
      canEdit
      canExport={false}
      isActionRunning={false}
      onExportBoard={vi.fn()}
      onImportDemand={vi.fn()}
      overview={null}
    />,
  );

  expect(screen.getByText("Assistant guidance")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /Import OGV.*demand/ })).toBeInTheDocument();
});

test("coal sequence page renders with assistant data absent and present", () => {
  const { rerender } = render(
    <CoalGradeSequencePage
      canEdit={false}
      canExport={false}
      isActionRunning={false}
      onExport={vi.fn()}
      overview={null}
    />,
  );

  expect(screen.getByRole("heading", { name: "Coal Grade Sequence" })).toBeInTheDocument();
  expect(screen.queryByText("Assistant guidance")).not.toBeInTheDocument();

  rerender(
    <CoalGradeSequencePage
      assistantPageActions={[
        assistantAction({
          actionId: "REVIEW_COAL_SEQUENCE",
          label: "Review coal grade sequence",
          route: "/schedule/coal-grade-sequence",
          ctaLabel: "Review sequence",
          reason: "Cargo layer sequence issues need review.",
          requiredPermission: "schedule.view",
          auditRequired: false,
        }),
      ]}
      canEdit={false}
      canExport={false}
      isActionRunning={false}
      onExport={vi.fn()}
      overview={null}
    />,
  );

  expect(screen.getByText("Review coal grade sequence")).toBeInTheDocument();
});

test("coal sequence page does not show recovery state for clear layers", () => {
  const now = "2026-05-19T00:00:00.000Z";
  const baseMaster = {
    id: 1,
    code: "BASE",
    name: "Base",
    organization: null,
    is_active: true,
    effective_from: null,
    effective_to: null,
    created_at: now,
    updated_at: now,
  };
  const overview = {
    voyages: [],
    cargoRequirements: [],
    cargoLayerSteps: [{
      id: 10,
      voyage: 20,
      voyage_ref: "VOY-CLEAR",
      vessel_name: "MV Clear Layer",
      cargo_requirement: null,
      hatch_no: 1,
      layer_no: 1,
      required_sequence_no: 1,
      coal_grade: {
        ...baseMaster,
        code: "SUNGKAI",
        brand_family: "Thermal",
        typical_cv_kcal: 4200,
        sulfur_pct: null,
        ash_pct: null,
        sequence_priority: 1,
      },
      required_mt: 31000,
      remaining_mt: 31000,
      planned_barge: {
        ...baseMaster,
        code: "BRG-NUS-17",
        capacity_mt: 31000,
        barge_class: "standard",
        max_draft_m: null,
        status: "available",
      },
      planned_jetty: {
        ...baseMaster,
        code: "JTY-LATI",
        location_name: "Lati",
        loading_rate_tph: 2000,
        max_barge_draft_m: null,
        status: "available",
      },
      planned_cts: {
        ...baseMaster,
        code: "CTS-JAVA",
        cts_type: "floating_crane",
        daily_capacity_mt: 25000,
        operating_area: "Delta",
        is_available: true,
      },
      status: "planned",
      blocking_reason: "",
      chain_status: "WAITING RECOVERY",
      sequence_violation: false,
      planned_start: null,
      planned_end: null,
      created_at: now,
      updated_at: now,
    }],
    assetAvailability: [],
    jettyAvailability: [],
    tideWindows: [],
    bridgeWindows: [],
    constraintChecks: [],
    importJobs: [],
    validation: {
      highRiskVoyages: 0,
      sequenceViolations: 0,
      missedWindows: 0,
      activeDemandMt: 31000,
      remainingDemandMt: 31000,
    },
  } as PlanningOverview;

  render(
    <CoalGradeSequencePage
      canEdit={false}
      canExport={false}
      isActionRunning={false}
      onExport={vi.fn()}
      overview={overview}
    />,
  );

  expect(screen.getByRole("columnheader", { name: "Severity" })).toBeInTheDocument();
  expect(screen.queryByText("WAITING RECOVERY")).not.toBeInTheDocument();
  expect(screen.getAllByText("PLANNED").length).toBeGreaterThan(0);
  expect(screen.getByText("No recovery needed for this layer.")).toBeInTheDocument();
});

test("coal sequence page does not overwrite clear cargo layers with active plan exceptions", () => {
  const now = "2026-05-19T00:00:00.000Z";
  const baseMaster = {
    id: 1,
    code: "BASE",
    name: "Base",
    organization: null,
    is_active: true,
    effective_from: null,
    effective_to: null,
    created_at: now,
    updated_at: now,
  };
  const overview = {
    voyages: [],
    cargoRequirements: [],
    cargoLayerSteps: [{
      id: 10,
      voyage: 20,
      voyage_ref: "VOY-ACTIVE",
      vessel_name: "MV Active Layer",
      cargo_requirement: null,
      hatch_no: 1,
      layer_no: 1,
      required_sequence_no: 1,
      coal_grade: {
        ...baseMaster,
        code: "EBONY",
        brand_family: "Thermal",
        typical_cv_kcal: 4200,
        sulfur_pct: null,
        ash_pct: null,
        sequence_priority: 1,
      },
      required_mt: 46000,
      remaining_mt: 46000,
      planned_barge: null,
      planned_jetty: null,
      planned_cts: null,
      status: "planned",
      blocking_reason: "",
      chain_status: "PLANNED",
      sequence_violation: false,
      planned_start: now,
      planned_end: now,
      created_at: now,
      updated_at: now,
    }],
    assetAvailability: [],
    jettyAvailability: [],
    tideWindows: [],
    bridgeWindows: [],
    constraintChecks: [],
    importJobs: [],
    validation: {
      highRiskVoyages: 0,
      sequenceViolations: 0,
      missedWindows: 0,
      activeDemandMt: 46000,
      remainingDemandMt: 46000,
    },
  } as PlanningOverview;
  const schedulingOverview = {
    trips: [{
      id: 101,
      cargo_layer_step: { id: 10 },
    }],
    conflicts: [
      {
        id: 901,
        plan_version: 1,
        plan_version_ref: "PLAN V1",
        trip: 101,
        trip_ref: "PI-001",
        vessel_name: "MV Active Layer",
        code: "TIDE_WINDOW_MISSED",
        severity: "critical",
        object_type: "barge",
        object_id: "BRG-VAL-08",
        message: "Tide window missed; recovery recommendation required",
        is_blocking: true,
        resolved_at: null,
        created_at: now,
      },
      {
        id: 902,
        plan_version: 1,
        plan_version_ref: "PLAN V1",
        trip: 101,
        trip_ref: "PI-001",
        vessel_name: "MV Active Layer",
        code: "BRIDGE_WINDOW_MISSED",
        severity: "critical",
        object_type: "barge",
        object_id: "BRG-VAL-08",
        message: "Bridge window missed; recovery recommendation required",
        is_blocking: true,
        resolved_at: null,
        created_at: now,
      },
    ],
  } as unknown as SchedulingOverview;

  render(
    <CoalGradeSequencePage
      canEdit={false}
      canExport={false}
      isActionRunning={false}
      onExport={vi.fn()}
      overview={overview}
      schedulingOverview={schedulingOverview}
    />,
  );

  expect(screen.getAllByText("Open exceptions").length).toBeGreaterThan(0);
  expect(screen.queryByText("WAITING RECOVERY")).not.toBeInTheDocument();
  expect(screen.queryByText("Tide window missed")).not.toBeInTheDocument();
  expect(screen.getAllByText("PLANNED").length).toBeGreaterThan(0);
  expect(screen.getByText("No recovery needed for this layer.")).toBeInTheDocument();
  expect(screen.getAllByText("2").length).toBeGreaterThan(0);
});

test("coal sequence page keeps non-blocking warning exceptions out of journey status", () => {
  const now = "2026-05-19T00:00:00.000Z";
  const baseMaster = {
    id: 1,
    code: "BASE",
    name: "Base",
    organization: null,
    is_active: true,
    effective_from: null,
    effective_to: null,
    created_at: now,
    updated_at: now,
  };
  const overview = {
    voyages: [],
    cargoRequirements: [],
    cargoLayerSteps: [{
      id: 11,
      voyage: 21,
      voyage_ref: "VOY-WATCH",
      vessel_name: "MV Watch Layer",
      cargo_requirement: null,
      hatch_no: 1,
      layer_no: 1,
      required_sequence_no: 1,
      coal_grade: {
        ...baseMaster,
        code: "AGATHIS",
        brand_family: "Thermal",
        typical_cv_kcal: 4200,
        sulfur_pct: null,
        ash_pct: null,
        sequence_priority: 1,
      },
      required_mt: 31000,
      remaining_mt: 31000,
      planned_barge: null,
      planned_jetty: null,
      planned_cts: null,
      status: "planned",
      blocking_reason: "",
      chain_status: "PLANNED",
      sequence_violation: false,
      planned_start: now,
      planned_end: now,
      created_at: now,
      updated_at: now,
    }],
    assetAvailability: [],
    jettyAvailability: [],
    tideWindows: [],
    bridgeWindows: [],
    constraintChecks: [],
    importJobs: [],
    validation: {
      highRiskVoyages: 0,
      sequenceViolations: 0,
      missedWindows: 0,
      activeDemandMt: 31000,
      remainingDemandMt: 31000,
    },
  } as PlanningOverview;
  const schedulingOverview = {
    trips: [{
      id: 111,
      cargo_layer_step: { id: 11 },
    }],
    conflicts: [{
      id: 904,
      plan_version: 1,
      plan_version_ref: "PLAN V1",
      trip: 111,
      trip_ref: "PI-003",
      vessel_name: "MV Watch Layer",
      code: "TIDE_WINDOW_MISSED",
      severity: "warning",
      object_type: "barge",
      object_id: "BRG-NUS-17",
      message: "Marginal tide margin; monitor after recovery candidate is simulated.",
      is_blocking: false,
      resolved_at: null,
      created_at: now,
    }],
  } as unknown as SchedulingOverview;

  render(
    <CoalGradeSequencePage
      canEdit={false}
      canExport={false}
      isActionRunning={false}
      onExport={vi.fn()}
      overview={overview}
      schedulingOverview={schedulingOverview}
    />,
  );

  expect(screen.queryByText("MONITOR")).not.toBeInTheDocument();
  expect(screen.queryByText("WAITING RECOVERY")).not.toBeInTheDocument();
  expect(screen.queryByText("Marginal tide margin")).not.toBeInTheDocument();
  expect(screen.getAllByText("PLANNED").length).toBeGreaterThan(0);
  expect(screen.getByText("Layer clear")).toBeInTheDocument();
  expect(screen.getByText("No recovery needed for this layer.")).toBeInTheDocument();
});

test("OGV demand board overlays active plan exceptions on stored low-risk demand", () => {
  const now = "2026-05-19T00:00:00.000Z";
  const baseMaster = {
    id: 1,
    code: "BASE",
    name: "Base",
    organization: null,
    is_active: true,
    effective_from: null,
    effective_to: null,
    created_at: now,
    updated_at: now,
  };
  const overview = {
    voyages: [{
      id: 501,
      voyage_id: "VOY-RISK-001",
      vessel_name: "MV Demand Risk",
      customer_name: "Pilot Customer",
      vessel_class: "Panamax",
      eta: now,
      etb: null,
      etc_target: null,
      laycan_start: now,
      laycan_end: now,
      required_mt: 46000,
      loaded_mt: 0,
      in_transit_mt: 0,
      discharged_mt: 0,
      remaining_mt: 46000,
      priority: 1,
      demurrage_rate_usd_per_day: "42000.00",
      anchorage_location: null,
      organization: null,
      status: "planned",
      risk_status: "low",
      current_stage: "PLANNED",
      next_blocking_constraint: "Ready for scheduling",
      created_at: now,
      updated_at: now,
    }],
    cargoRequirements: [],
    cargoLayerSteps: [{
      id: 502,
      voyage: 501,
      voyage_ref: "VOY-RISK-001",
      vessel_name: "MV Demand Risk",
      cargo_requirement: null,
      hatch_no: 1,
      layer_no: 1,
      required_sequence_no: 1,
      coal_grade: {
        ...baseMaster,
        code: "EBONY",
        brand_family: "Thermal",
        typical_cv_kcal: 4200,
        sulfur_pct: null,
        ash_pct: null,
        sequence_priority: 1,
      },
      required_mt: 46000,
      remaining_mt: 46000,
      planned_barge: null,
      planned_jetty: null,
      planned_cts: null,
      status: "planned",
      blocking_reason: "",
      chain_status: "PLANNED",
      sequence_violation: false,
      planned_start: now,
      planned_end: now,
      created_at: now,
      updated_at: now,
    }],
    assetAvailability: [],
    jettyAvailability: [],
    tideWindows: [],
    bridgeWindows: [],
    constraintChecks: [],
    importJobs: [],
    validation: {
      highRiskVoyages: 0,
      sequenceViolations: 0,
      missedWindows: 0,
      activeDemandMt: 46000,
      remainingDemandMt: 46000,
    },
  } as PlanningOverview;
  const schedulingOverview = {
    trips: [{
      id: 601,
      voyage: { id: 501 },
      cargo_layer_step: { id: 502 },
    }],
    conflicts: [{
      id: 903,
      plan_version: 1,
      plan_version_ref: "PLAN V1",
      trip: 601,
      trip_ref: "PI-002",
      vessel_name: "MV Demand Risk",
      code: "BRIDGE_WINDOW_MISSED",
      severity: "critical",
      object_type: "barge",
      object_id: "BRG-VAL-08",
      message: "Bridge window needs recovery before publishing.",
      is_blocking: true,
      resolved_at: null,
      created_at: now,
    }],
    trackingAlerts: [],
  } as unknown as SchedulingOverview;

  render(
    <OgvDemandPage
      canEdit={false}
      canExport={false}
      isActionRunning={false}
      onExportBoard={vi.fn()}
      onImportDemand={vi.fn()}
      overview={overview}
      schedulingOverview={schedulingOverview}
    />,
  );

  expect(screen.getAllByText("Bridge window needs recovery before publishing.").length)
    .toBeGreaterThan(0);
  expect(screen.getByText("high")).toBeInTheDocument();
  expect(screen.queryByText("WAITING RECOVERY")).not.toBeInTheDocument();
  expect(screen.getAllByText("PLANNED").length).toBeGreaterThan(0);
});

test("live map exposes seeded replay controls", () => {
  const onStartReplay = vi.fn();
  render(
    <LiveResourceMapPage
      canRunReplay
      canRunSimulation={false}
      etaProjections={[]}
      geofenceZones={[]}
      isActionRunning={false}
      latestAssetStates={[]}
      movementEvents={[]}
      onNavigate={vi.fn()}
      onStartReplay={onStartReplay}
      overview={null}
      replayRuns={[{
        id: 1,
        replay_id: "RPL-TRACK-ON-TIME",
        name: "On-time route proof",
        status: "draft",
        scenario_code: "TRACK-ON-TIME",
        started_at: null,
        completed_at: null,
        speed_multiplier: "4.00",
        seed_start_at: "2026-05-19T00:00:00.000Z",
        metadata: {},
        created_at: "2026-05-18T00:00:00.000Z",
        updated_at: "2026-05-18T00:00:00.000Z",
      }]}
      trackingAlerts={[]}
    />,
  );

  expect(screen.getByText("Synthetic replay")).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "TRACK-ON-TIME" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Start replay" }));
  expect(onStartReplay).toHaveBeenCalledWith("RPL-TRACK-ON-TIME");
});

test("live map renders telemetry trust state", () => {
  const now = "2026-05-18T00:00:00.000Z";
  const overview = {
    assignments: [],
    conflicts: [],
    telemetryTrustSummary: {
      profileKey: "telemetry_trust_default_v1",
      latestAssessmentCount: 1,
      trustedCount: 0,
      degradedCount: 0,
      blockingCount: 1,
      unknownCount: 0,
      latestAssessedAt: now,
      latestAssessments: [{
        id: 1,
        assessment_id: "TTA-UI-001",
        profile: 1,
        profile_ref: "telemetry_trust_default_v1",
        source: 1,
        source_id: "GPS-GW",
        asset_identity: 1,
        external_id: "BRG-TRUST-01",
        external_id_type: "internal",
        latest_state: 1,
        latest_state_ref: "BRG-TRUST-01",
        asset_type: "barge",
        asset_code: "BRG-TRUST-01",
        trust_status: "quarantined",
        freshness_status: "fresh",
        confidence_score: "18.00",
        identity_match_status: "matched",
        source_rank: 2,
        reasons: ["Low confidence signal quarantined."],
        evidence: {},
        assessed_at: now,
        algorithm_version: "phase6.6-telemetry-trust",
        created_at: now,
      }],
    },
  } as unknown as SchedulingOverview;

  render(
    <LiveResourceMapPage
      canRunReplay={false}
      canRunSimulation={false}
      etaProjections={[]}
      geofenceZones={[]}
      isActionRunning={false}
      latestAssetStates={[{
        id: 1,
        asset_type: "barge",
        asset_code: "BRG-TRUST-01",
        source: 1,
        source_id: "GPS-GW",
        source_type: "device_gateway",
        asset_identity: 1,
        external_id: "BRG-TRUST-01",
        external_id_type: "internal",
        latitude: "-3.2100",
        longitude: "115.6100",
        speed_knots: "0.0",
        heading_degrees: "90.0",
        last_seen_at: now,
        freshness_status: "fresh",
        age_seconds: 30,
        current_geofence_ref: null,
        current_geofence_name: null,
        last_movement_event_type: null,
        last_ping: null,
        last_ping_ref: null,
        derived_status: "active",
        current_geofence: null,
        current_geofence_type: null,
        last_movement_event: null,
        last_movement_event_ref: null,
        last_movement_event_at: null,
        confidence_score: "18.00",
        paired_asset_code: "",
        metadata: {},
        created_at: now,
        updated_at: now,
      } as unknown as LatestAssetStateRecord]}
      movementEvents={[]}
      onNavigate={vi.fn()}
      onStartReplay={vi.fn()}
      overview={overview}
      replayRuns={[]}
      trackingAlerts={[]}
    />,
  );

  expect(screen.getByText("Telemetry trust")).toBeInTheDocument();
  expect(screen.getByText("telemetry_trust_default_v1")).toBeInTheDocument();
  expect(screen.getAllByText("QUARANTINED").length).toBeGreaterThan(0);
  expect(screen.getByText("Low confidence signal quarantined.")).toBeInTheDocument();
});

test("renders the role-aware dashboard shell", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Network Situation" })).toBeInTheDocument();
  expect(screen.queryByText("Users & RBAC")).not.toBeInTheDocument();
});

test("operator trial import CTA refreshes DB-truth flow metadata before selecting pack", async () => {
  window.location.hash = "#/schedule/ogv-demand";
  const planningOverview = {
    voyages: [],
    cargoRequirements: [],
    cargoLayerSteps: [],
    assetAvailability: [],
    jettyAvailability: [],
    tideWindows: [],
    bridgeWindows: [],
    constraintChecks: [],
    importJobs: [],
    validation: {
      highRiskVoyages: 0,
      sequenceViolations: 0,
      missedWindows: 0,
      activeDemandMt: 0,
      remainingDemandMt: 0,
    },
  };
  const schedulingOverview = {
    plans: [],
    planVersions: [],
    activePlanVersion: null,
    trips: [],
    assignments: [],
    events: [],
    conflicts: [],
    overrideRequests: [],
    approvalRequests: [],
    publishedSnapshots: [],
    simulationScenarios: [],
    recoveryInputSnapshots: [],
    optimizerRuns: [],
    recoveryRecommendations: [],
    globalOptimizationRuns: [],
    globalOptimizationCandidates: [],
    liveEtaProjections: [],
    trackingAlerts: [],
    publishabilityAssessment: null,
    trackingSummary: {
      projectionCount: 0,
      openAlertCount: 0,
      criticalAlertCount: 0,
      highestVarianceMinutes: 0,
    },
    operationsHealthSummary: {},
    validation: {
      tripCount: 0,
      assignmentCount: 0,
      eventCount: 0,
      conflictCount: 0,
      blockingConflictCount: 0,
      criticalConflictCount: 0,
      overrideCount: 0,
      approvalPendingCount: 0,
      scenarioCount: 0,
      optimizerRunCount: 0,
      recoveryRecommendationCount: 0,
      trackingAlertCount: 0,
      openTrackingAlertCount: 0,
      plannedMt: 0,
      loadedMt: 0,
    },
  };
  const nextActions = {
    generated_at: "2026-05-29T00:00:00.000Z",
    mode: "supervisor",
    context: {},
    global_next_action: {
      action_id: "IMPORT_OGV_DEMAND",
      label: "Import OGV demand",
      priority: "normal",
      rank_score: 970,
      enabled: true,
      route: "/schedule/ogv-demand",
      cta_label: "Import demand",
      reason: "Operator happy path is waiting at Import OGV demand.",
      hover_hint: "",
      detail_text: "",
      impact_if_ignored: "",
      owner_role: "berau-scheduler",
      required_permission: "schedule.edit",
      audit_required: true,
      target_object_type: null,
      target_object_id: null,
      blocked_reason: "",
      source: "flow.current_step",
      expires_at: null,
      metadata: {},
    },
    page_actions: [],
    row_actions: [],
    blocked_actions: [],
    checklist: [],
    flow: {
      active_flow: "operator_happy_path_v1",
      flow_run_id: "FLOW-123",
      flow_name: "Operator happy path",
      flow_status: "active",
      current_step: "import_ogv_demand",
      current_step_label: "Import OGV demand",
      step_status: "active",
      expected_route: "/schedule/ogv-demand",
      expected_action_id: "IMPORT_OGV_DEMAND",
      blocked_reason: "",
      expected_action_ids: ["IMPORT_OGV_DEMAND"],
    },
  };
  const fetchMock = vi.fn().mockImplementation((input: string, init?: RequestInit) => {
    if (input.endsWith("/me/")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          id: 1,
          username: "admin@coalflow.local",
          email: "admin@coalflow.local",
          is_active: true,
          memberships: [],
          assignments: [],
          permissions: ["dashboard.view", "schedule.view", "schedule.edit"],
        }),
      });
    }
    if (input.includes("/assistant/next-actions/")) {
      return Promise.resolve({ ok: true, status: 200, json: async () => nextActions });
    }
    if (input.endsWith("/flows/active/")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          flow: {
            run_id: "FLOW-123",
            flow_definition: {
              flow_key: "operator_happy_path_v1",
              name: "Operator happy path",
            },
            status: "active",
            current_step_key: "import_ogv_demand",
            metadata: {
              trial_pack: "operator_happy_path_v1",
              evidence_run_id: "operator-trial-happy-path",
              expected_action_ids: ["IMPORT_OGV_DEMAND"],
            },
            step_runs: [{
              step_key: "import_ogv_demand",
              status: "active",
              expected_route: "/schedule/ogv-demand",
              expected_action_id: "IMPORT_OGV_DEMAND",
              blocked_reason: "",
            }],
          },
        }),
      });
    }
    if (input.endsWith("/auth/csrf/")) {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ csrfToken: "csrf" }) });
    }
    if (input.endsWith("/planning/overview/")) {
      return Promise.resolve({ ok: true, status: 200, json: async () => planningOverview });
    }
    if (input.endsWith("/scheduling/overview/")) {
      return Promise.resolve({ ok: true, status: 200, json: async () => schedulingOverview });
    }
    if (input.endsWith("/dashboard/situation/")) {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    }
    if (input.endsWith("/planning/import-jobs/import-trial-demand/")) {
      expect(JSON.parse(String(init?.body))).toMatchObject({ pack: "operator_happy_path_v1" });
      return Promise.resolve({
        ok: true,
        status: 201,
        json: async () => ({
          id: 9,
          filename: "operator_happy_path_ogv_demand.xlsx",
          valid_rows: 2,
          total_rows: 2,
        }),
      });
    }
    if (input.endsWith("/planning/import-jobs/validate-ogv-demand/")) {
      return Promise.resolve({ ok: false, status: 599, json: async () => ({}) });
    }
    if (input.endsWith("/flows/FLOW-123/events/")) {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ run_id: "FLOW-123" }) });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => [] });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: /^Import demand$/i }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/planning/import-jobs/import-trial-demand/",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });
  expect(fetchMock).not.toHaveBeenCalledWith(
    "/api/planning/import-jobs/validate-ogv-demand/",
    expect.anything(),
  );
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
      selection_reason: {},
      cargo_layer_step: { coal_grade: { code: "EBONY" }, hatch_no: 1, layer_no: 1 },
      assignment: null,
      events: [{ event_type: "load_start", planned_at: "2026-05-17T01:30:00.000Z" }],
    }],
    conflicts: [],
    overrideRequests: [],
    validation: { tripCount: 1, assignmentCount: 1, eventCount: 1 },
  } as unknown as SchedulingOverview;
}

test("published plan gantt uses planned trip dates for its axis", () => {
  render(
    <PublishedPlanPage
      canCreateDraft={false}
      isActionRunning={false}
      overview={stageSevenOverview()}
    />,
  );

  expect(screen.getByText("Operating schedule gantt")).toBeInTheDocument();
  expect(screen.queryByText("24 OCT 04:00")).not.toBeInTheDocument();
  expect(screen.getAllByText(/MAY/).length).toBeGreaterThan(0);
});

test("published plan ignores resolved conflicts in active schedule status", () => {
  const overview = stageSevenOverview();
  overview.conflicts = [{
    id: 1001,
    plan_version: 1,
    plan_version_ref: "PLAN-UI V1",
    trip: 201,
    trip_ref: "PI-PLAN-UI-0001",
    vessel_name: "MV Operator UI Import",
    code: "BRIDGE_WINDOW_MISSED",
    severity: "critical",
    object_type: "barge",
    object_id: "BRG-VAL-08",
    message: "Resolved bridge conflict should not remain active.",
    is_blocking: true,
    resolved_at: "2026-05-17T12:00:00.000Z",
    created_at: "2026-05-17T02:00:00.000Z",
  }];

  render(
    <PublishedPlanPage
      canCreateDraft={false}
      isActionRunning={false}
      overview={overview}
    />,
  );

  expect(screen.queryByText("Resolved bridge conflict should not remain active."))
    .not.toBeInTheDocument();
  expect(screen.getByText("No active conflict on this trip.")).toBeInTheDocument();
});

function phaseFiveOverview(): SchedulingOverview {
  const overview = stageSevenOverview();
  overview.recoveryInputSnapshots = [{
    id: 601,
    snapshot_id: "RIS-PHASE5-UI",
    plan_version: 1,
    plan_version_ref: "PLAN-UI V1",
    source_kind: "override",
    source_ref: "OR-0050",
    source_conflict: null,
    source_conflict_code: null,
    source_override: 50,
    source_override_reason_code: "jetty_delay",
    source_tracking_alert: null,
    source_tracking_alert_ref: null,
    source_operational_event: null,
    source_operational_event_ref: null,
    source_scenario: null,
    source_scenario_ref: null,
    input_hash: "phase5-input",
    active_conflict_count: 1,
    confirmed_event_count: 0,
    tracking_alert_count: 0,
    resource_state: {},
    event_state: {},
    constraint_state: {},
    metadata: {},
    captured_by: 1,
    captured_by_email: "berau.scheduler@coalflow.local",
    generated_at: "2026-05-18T03:30:00.000Z",
  }];
  overview.optimizerRuns = [{
    id: 701,
    run_id: "OPT-PHASE5-UI",
    input_snapshot: 601,
    input_snapshot_ref: "RIS-PHASE5-UI",
    plan_version: 1,
    plan_version_ref: "PLAN-UI V1",
    status: "succeeded",
    algorithm_version: "phase5.3-scored-deterministic-repair",
    objective_weights: {},
    summary: { bestScore: 92.4 },
    error_message: "",
    started_by: 1,
    started_by_email: "berau.scheduler@coalflow.local",
    started_at: "2026-05-18T03:31:00.000Z",
    completed_at: "2026-05-18T03:31:10.000Z",
    recommendations: [{
      id: 801,
      recommendation_id: "REC-PHASE5-UI-01",
      optimizer_run: 701,
      optimizer_run_ref: "OPT-PHASE5-UI",
      rank: 1,
      status: "candidate",
      risk_level: "low",
      score: "92.400",
      summary: "Move PI-PLAN-UI-0001 to the next feasible gate window.",
      explanation: [{
        id: "EXP-01",
        sortOrder: 1,
        kind: "source",
        label: "Input snapshot",
        value: "RIS-PHASE5-UI / OR-0050",
        severity: "info",
        detail: "Calculated from override OR-0050.",
      }],
      scenario: null,
      scenario_ref: null,
      metadata: {
        strategy: "next_window_repair",
        scoreSummary: "92.4 / 100 because delay exposure is low.",
      },
      actions: [{
        id: 901,
        action_id: "ACT-PHASE5-UI-01",
        recommendation: 801,
        recommendation_ref: "REC-PHASE5-UI-01",
        sequence: 1,
        action_type: "shift_window",
        target_trip: 201,
        target_trip_ref: "PI-PLAN-UI-0001",
        target_assignment: 101,
        target_assignment_ref: "Assignment 101",
        before_state: { window: "TIDE-A" },
        after_state: { window: "TIDE-B" },
        constraints_checked: ["tide_window_evaluated", "bridge_window_evaluated"],
        metadata: {},
        created_at: "2026-05-18T03:31:10.000Z",
      }],
      evaluation: {
        id: 1001,
        evaluation_id: "EVAL-PHASE5-UI-01",
        recommendation: 801,
        recommendation_ref: "REC-PHASE5-UI-01",
        delay_minutes: 35,
        missed_windows: 0,
        resource_conflicts: 0,
        utilization_delta_pct: "1.50",
        confidence_score: "94.00",
        hard_constraints_passed: true,
        score_breakdown: {},
        metadata: {
          hardConstraintEvidence: ["tide_window_evaluated", "bridge_window_evaluated"],
        },
        created_at: "2026-05-18T03:31:10.000Z",
      },
      root_cause_assessment: null,
      created_at: "2026-05-18T03:31:10.000Z",
      updated_at: "2026-05-18T03:31:10.000Z",
    }],
    created_at: "2026-05-18T03:31:00.000Z",
    updated_at: "2026-05-18T03:31:10.000Z",
  }];
  overview.recoveryRecommendations = overview.optimizerRuns[0].recommendations;
  return overview;
}

function phaseFourCandidate(
  overrides: Partial<OperationalEventCandidateRecord> = {},
): OperationalEventCandidateRecord {
  return {
    id: 1,
    candidate_id: "OEC-001",
    feed: 1,
    feed_ref: "SYN-OPS-PHASE4",
    device: 1,
    device_ref: "JETTY-JTY-SUARAN-OPS",
    source_kind: "synthetic",
    event_kind: "jetty_loading_completed",
    asset_type: "jetty",
    asset_code: "JTY-SUARAN",
    trip: 201,
    trip_ref: "PI-PLAN-UI-0001",
    assignment: 101,
    assignment_ref: "PI-PLAN-UI-0001",
    schedule_event: 301,
    schedule_event_type: "load_complete",
    schedule_event_planned_at: "2026-05-17T03:30:00.000Z",
    schedule_event_actual_at: null,
    event_at: "2026-05-17T04:05:00.000Z",
    received_at: "2026-05-17T04:06:00.000Z",
    confidence_score: "65.00",
    dedupe_key: "phase4-load-complete",
    status: "pending",
    payload: {},
    raw_payload_ref: "",
    metadata: {},
    confirmed_event_ref: null,
    created_at: "2026-05-17T04:06:00.000Z",
    updated_at: "2026-05-17T04:06:00.000Z",
    ...overrides,
  };
}

function phaseFourConfirmedEvent(
  overrides: Partial<ConfirmedOperationalEventRecord> = {},
): ConfirmedOperationalEventRecord {
  return {
    id: 10,
    event_id: "OPE-0010",
    candidate: 1,
    candidate_ref: "OEC-001",
    feed_ref: "SYN-OPS-PHASE4",
    device_ref: "JETTY-JTY-SUARAN-OPS",
    event_kind: "jetty_loading_completed",
    asset_type: "jetty",
    asset_code: "JTY-SUARAN",
    plan_version: 1,
    plan_version_ref: "PLAN-UI V1",
    trip: 201,
    trip_ref: "PI-PLAN-UI-0001",
    assignment: 101,
    assignment_ref: "PI-PLAN-UI-0001",
    schedule_event: 301,
    schedule_event_type: "load_complete",
    schedule_event_planned_at: "2026-05-17T03:30:00.000Z",
    schedule_event_actual_at: "2026-05-17T04:05:00.000Z",
    actual_at: "2026-05-17T04:05:00.000Z",
    confirmed_quantity_mt: "12650.00",
    confirmed_rate_tph: null,
    confirmed_grade_code: "EBONY",
    confirmed_by: 1,
    confirmed_by_email: "admin@coalflow.local",
    confirmed_at: "2026-05-17T04:06:00.000Z",
    confirmation_mode: "manual_confirmed",
    reason_code: "operator_verified",
    before_state: {},
    after_state: {},
    metadata: {},
    created_at: "2026-05-17T04:06:00.000Z",
    ...overrides,
  };
}

function phaseFourDevice(
  overrides: Partial<DeviceEndpointRecord> = {},
): DeviceEndpointRecord {
  return {
    id: 1,
    device_id: "JETTY-JTY-SUARAN-OPS",
    feed: 1,
    feed_ref: "SYN-OPS-PHASE4",
    device_type: "plc",
    asset_type: "jetty",
    asset_code: "JTY-SUARAN",
    location: 1,
    location_code: "LOC-SUARAN-PORT",
    geofence: 1,
    geofence_ref: "GEO-LOC-SUARAN-PORT",
    status: "active",
    last_seen_at: "2026-05-17T04:06:00.000Z",
    latest_health: {
      snapshotId: "DHS-001",
      healthStatus: "healthy",
      observedAt: "2026-05-17T04:06:00.000Z",
      receivedAt: "2026-05-17T04:06:00.000Z",
      ageSeconds: 10,
      gapSeconds: 0,
      batteryLevel: null,
      networkStatus: "online",
      powerStatus: "mains",
    },
    firmware_version: "1.0.0",
    metadata: {},
    created_at: "2026-05-17T04:06:00.000Z",
    updated_at: "2026-05-17T04:06:00.000Z",
    ...overrides,
  };
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

test("jetty and CTS boards surface operational actuals and pending review", () => {
  const overview = stageSevenOverview();
  overview.assignments[0].cts = { code: "CTS-BORNEO" } as never;
  overview.trips[0].events = [
    { event_type: "load_start", planned_at: "2026-05-17T01:30:00.000Z", actual_at: "2026-05-17T01:40:00.000Z" },
    { event_type: "load_complete", planned_at: "2026-05-17T03:30:00.000Z", actual_at: "2026-05-17T04:05:00.000Z" },
    { event_type: "arrive_cts", planned_at: "2026-05-17T07:30:00.000Z", actual_at: null },
    { event_type: "discharge_start", planned_at: "2026-05-17T07:45:00.000Z", actual_at: null },
    { event_type: "discharge_complete", planned_at: "2026-05-17T10:30:00.000Z", actual_at: null },
  ] as never;

  const { rerender } = render(
    <JettyLoadingPage
      confirmedOperationalEvents={[phaseFourConfirmedEvent()]}
      operationCandidates={[phaseFourCandidate()]}
      operationDevices={[phaseFourDevice()]}
      overview={overview}
    />,
  );

  expect(screen.getByText("Confirmed jetty events")).toBeInTheDocument();
  expect(screen.getAllByText(/JETTY LOADING COMPLETED/).length).toBeGreaterThan(0);
  expect(screen.getByText("Confirmation panel")).toBeInTheDocument();

  rerender(
    <CtsOperationsPage
      operationCandidates={[phaseFourCandidate({
        id: 2,
        candidate_id: "OEC-CTS-002",
        event_kind: "cts_rate_updated",
        asset_type: "cts",
        asset_code: "CTS-BORNEO",
        device_ref: "CTS-BORNEO-OPS",
        payload: { planned_rate_tph: "2200.00" },
      })]}
      operationDevices={[phaseFourDevice({
        id: 2,
        device_id: "CTS-BORNEO-OPS",
        asset_type: "cts",
        asset_code: "CTS-BORNEO",
      })]}
      overview={overview}
    />,
  );

  expect(screen.getByText("Low-rate signals")).toBeInTheDocument();
  expect(screen.getByText(/CTS RATE UPDATED/)).toBeInTheDocument();
});

test("tide and bridge board shows observed gate state beside planned windows", () => {
  const overview = {
    tideWindows: [],
    bridgeWindows: [],
    constraintChecks: [],
  } as unknown as PlanningOverview;
  render(
    <TideBridgePage
      canEdit={false}
      confirmedOperationalEvents={[
        phaseFourConfirmedEvent({
          id: 20,
          event_id: "OPE-BRIDGE-20",
          event_kind: "bridge_crossed",
          asset_type: "bridge",
          asset_code: "BRDG-UI-OPERATING-01",
          schedule_event_type: "bridge_cross",
        }),
        phaseFourConfirmedEvent({
          id: 21,
          event_id: "OPE-TIDE-21",
          event_kind: "tide_gate_passed",
          asset_type: "tide_gate",
          asset_code: "TIDE-UI-OPERATING-01",
          schedule_event_type: "tide_gate",
        }),
      ]}
      isActionRunning={false}
      onEnterOperatingWindows={vi.fn()}
      operationDevices={[
        phaseFourDevice({
          id: 3,
          device_id: "BRIDGE-GATE-B-OPS",
          asset_type: "bridge",
          asset_code: "BRDG-UI-OPERATING-01",
        }),
        phaseFourDevice({
          id: 4,
          device_id: "TIDE-RANTAU-OPS",
          asset_type: "tide_gate",
          asset_code: "TIDE-UI-OPERATING-01",
        }),
      ]}
      overview={overview}
    />,
  );

  expect(screen.getByText("Observed gate state")).toBeInTheDocument();
  expect(screen.getByText("BRIDGE CROSSED")).toBeInTheDocument();
  expect(screen.getByText("TIDE GATE PASSED")).toBeInTheDocument();
});

test("live map shows operational overlays for instrumented assets", () => {
  render(
    <LiveResourceMapPage
      canRunReplay={false}
      canRunSimulation={false}
      confirmedOperationalEvents={[phaseFourConfirmedEvent()]}
      etaProjections={[]}
      geofenceZones={[{
        id: 1,
        zone_id: "GEO-LOC-SUARAN-PORT",
        name: "Suaran Port",
        zone_type: "jetty",
        source_location: 1,
        source_location_code: "LOC-SUARAN-PORT",
        source_location_name: "Suaran Port",
        latitude: "0.6000",
        longitude: "117.1000",
        radius_m: 500,
        status: "active",
        metadata: {},
        created_at: "2026-05-17T04:06:00.000Z",
        updated_at: "2026-05-17T04:06:00.000Z",
      }]}
      isActionRunning={false}
      latestAssetStates={[]}
      movementEvents={[]}
      onNavigate={vi.fn()}
      onStartReplay={vi.fn()}
      operationDevices={[phaseFourDevice()]}
      overview={null}
      replayRuns={[]}
      trackingAlerts={[]}
    />,
  );

  expect(screen.getByText("Operational overlays")).toBeInTheDocument();
  expect(screen.getByText("JETTY LOADING COMPLETED")).toBeInTheDocument();
});

test("operations event console confirms pending evidence with reason capture", () => {
  const onConfirm = vi.fn();
  render(
    <OperationsEventConsolePage
      candidates={[{
        id: 1,
        candidate_id: "OEC-001",
        feed: 1,
        feed_ref: "SYN-OPS-PHASE4",
        device: 1,
        device_ref: "JETTY-JTY-SUARAN-OPS",
        source_kind: "synthetic",
        event_kind: "jetty_loading_started",
        asset_type: "jetty",
        asset_code: "JTY-SUARAN",
        trip: 201,
        trip_ref: "PI-PLAN-UI-0001",
        assignment: 101,
        assignment_ref: "PI-PLAN-UI-0001",
        schedule_event: 301,
        schedule_event_type: "load_start",
        schedule_event_planned_at: "2026-05-17T01:30:00.000Z",
        schedule_event_actual_at: null,
        event_at: "2026-05-17T01:42:00.000Z",
        received_at: "2026-05-17T01:43:00.000Z",
        confidence_score: "94.00",
        dedupe_key: "phase4-event-1",
        status: "pending",
        payload: { source_event_id: "PLC-LOAD-START-1" },
        raw_payload_ref: "",
        metadata: {},
        confirmed_event_ref: null,
        created_at: "2026-05-17T01:43:00.000Z",
        updated_at: "2026-05-17T01:43:00.000Z",
      }]}
      confirmedEvents={[]}
      devices={[]}
      onConfirm={onConfirm}
      overview={null}
      permissions={["operations.confirm_jetty"]}
    />,
  );

  expect(screen.getByText("Operations Event Console")).toBeInTheDocument();
  expect(screen.getAllByText("+12m").length).toBeGreaterThan(0);
  expect(screen.getByLabelText("Confirmation reason")).toHaveValue("operator_verified");
  fireEvent.click(screen.getByRole("button", { name: "Confirm event" }));
  expect(onConfirm).toHaveBeenCalledWith(1, expect.stringContaining("T"), "operator_verified");
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

test("exception center renders operational event-driven triage rows", () => {
  const overview = stageSevenOverview();
  render(
    <ExceptionCenterPage
      confirmedOperationalEvents={[phaseFourConfirmedEvent()]}
      overview={overview}
    />,
  );

  expect(screen.getAllByText("LOADING_COMPLETE_LATE").length).toBeGreaterThan(0);
  expect(screen.getByText("Loading complete late")).toBeInTheDocument();
  expect(screen.getAllByText("+35m").length).toBeGreaterThan(0);
});

test("exception center converts a delay tracking alert into a scenario", () => {
  const onCreateScenario = vi.fn();
  const overview = stageSevenOverview();
  overview.trackingAlerts = [{
    id: 88,
    alert_id: "ALT-DELAY-0088",
    alert_type: "delay",
    severity: "warning",
    asset_type: "barge",
    asset_code: "BRG-VAL-08",
    source: 1,
    source_id: "SYN-GPS-PHASE3",
    asset_identity: 1,
    external_id: "SYN-BRG-VAL-08",
    source_ping: 10,
    source_ping_ref: "PNG-SYN-GPS-PHASE3-0010",
    trip: 201,
    trip_ref: "PI-PLAN-UI-0001",
    vessel_name: "MV Operator UI Import",
    schedule_event: 11,
    schedule_event_type: "depart_jetty",
    schedule_event_planned_at: "2026-05-17T03:30:00.000Z",
    eta_projection: 12,
    eta_projection_ref: "ETA-0012",
    message: "BRG-VAL-08 is still at jetty with observed departure 45 minutes after plan.",
    evidence: {
      varianceMinutes: 45,
      observedEta: "2026-05-17T04:15:00.000Z",
    },
    status: "open",
    source_kind: "synthetic",
    opened_at: "2026-05-17T03:45:00.000Z",
    resolved_at: null,
    created_scenario: null,
    created_at: "2026-05-17T03:45:00.000Z",
    updated_at: "2026-05-17T03:45:00.000Z",
  }];

  render(<ExceptionCenterPage canEdit onCreateScenario={onCreateScenario} overview={overview} />);

  fireEvent.click(screen.getByRole("button", { name: "Create scenario" }));
  expect(onCreateScenario).toHaveBeenCalledWith({ kind: "tracking_alert", id: 88 });
});

test("exception center generates recovery options from a governed override", () => {
  const onGenerateRecoveryOptions = vi.fn();
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
    impact_assessment: null,
  }];

  render(
    <ExceptionCenterPage
      canEdit
      onGenerateRecoveryOptions={onGenerateRecoveryOptions}
      overview={overview}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Generate recovery options" }));
  expect(onGenerateRecoveryOptions).toHaveBeenCalledWith({ kind: "override", id: 50 });
});

test("recommendation console renders ranking evidence and materializes a scenario", () => {
  const onMaterializeRecommendation = vi.fn();
  render(
    <RecommendationConsolePage
      canEdit
      onMaterializeRecommendation={onMaterializeRecommendation}
      overview={phaseFiveOverview()}
    />,
  );

  expect(screen.getByRole("heading", { name: "Recommendation Console" })).toBeInTheDocument();
  expect(screen.getAllByText("REC-PHASE5-UI-01").length).toBeGreaterThan(0);
  expect(screen.getAllByText("NEXT WINDOW REPAIR").length).toBeGreaterThan(0);
  expect(screen.getByText("Before / after actions")).toBeInTheDocument();
  expect(screen.getAllByText("Input snapshot").length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Test as scenario" }));
  expect(onMaterializeRecommendation).toHaveBeenCalledWith(801);
});

test("recommendation console validates and renders root-cause assessment", () => {
  const onValidateRootCause = vi.fn();
  const overview = phaseFiveOverview();
  overview.optimizerRuns[0].recommendations[0].root_cause_assessment = {
    id: 1201,
    assessment_id: "RCA-PHASE6-UI",
    recommendation: 801,
    recommendation_ref: "REC-PHASE5-UI-01",
    source_kind: "conflict",
    source_ref: "BARGE_UNAVAILABLE:99",
    source_cause_type: "BARGE_UNAVAILABLE",
    status: "does_not_address_cause",
    required_resolution: {},
    observed_resolution: {
      resolutionEvidence: [{
        kind: "unrelated_action_family",
        detail: "CTS reassignment does not repair BARGE_UNAVAILABLE.",
      }],
    },
    residual_risk: {
      level: "high",
      count: 1,
      items: [{ severity: "critical", message: "BARGE_UNAVAILABLE remains physically unresolved." }],
    },
    evidence: {},
    assessed_at: "2026-05-18T03:31:30.000Z",
    assessed_by_algorithm_version: "phase6.3-root-cause-repair-assessment",
    created_at: "2026-05-18T03:31:30.000Z",
    updated_at: "2026-05-18T03:31:30.000Z",
  };
  overview.recoveryRecommendations = overview.optimizerRuns[0].recommendations;

  render(
    <RecommendationConsolePage
      canEdit
      onValidateRootCause={onValidateRootCause}
      overview={overview}
    />,
  );

  expect(screen.getByText("Root-cause validation")).toBeInTheDocument();
  expect(screen.getByText(/BARGE UNAVAILABLE/)).toBeInTheDocument();
  expect(screen.getByText(/DOES NOT ADDRESS CAUSE/)).toBeInTheDocument();
  expect(screen.getByText(/CTS reassignment does not repair/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Re-run validation" }));
  expect(onValidateRootCause).toHaveBeenCalledWith(801);
});

test("global optimization review renders candidate contracts read-only", () => {
  const overview = stageSevenOverview();
  overview.globalOptimizationRuns = [{
    id: 901,
    run_id: "GOPT-PHASE6-UI",
    status: "succeeded",
    plan_version: 1,
    plan_version_ref: "PLAN-UI V1",
    objective_profile: 1,
    objective_profile_ref: "global_optimizer_default_v1",
    objective_weights: {
      delay_minutes: 0.3,
      laycan_risk: 0.25,
      asset_balance: 0.2,
      demurrage_exposure: 0.15,
      residual_risk: 0.1,
    },
    input_signature: "abcdef1234567890",
    input_summary: {},
    algorithm_version: "phase6.5-global-optimizer-scaffold",
    audit_lineage: {
      eventAction: "global_optimizer.run.generate",
      candidateCount: 1,
    },
    started_by: 1,
    started_by_email: "berau.scheduler@coalflow.local",
    started_at: "2026-05-18T03:31:00.000Z",
    completed_at: "2026-05-18T03:31:10.000Z",
    error_message: "",
    candidates: [{
      id: 902,
      candidate_id: "GCAN-PHASE6-UI-01",
      run: 901,
      run_ref: "GOPT-PHASE6-UI",
      rank: 1,
      score: "88.500",
      risk_level: "low",
      summary: "Prioritize earliest laycan and highest priority OGVs.",
      objective_score_breakdown: {
        weights: { delay_minutes: 0.3, laycan_risk: 0.25 },
      },
      changed_assignments: [{
        kind: "candidate_priority_shift",
        voyageId: "OGV-001",
        reason: "Laycan priority receives earlier network attention.",
      }],
      trip_sequence_changes: [{
        kind: "candidate_sequence_priority",
        voyageId: "OGV-001",
      }],
      projected_impacts: {
        delayMinutesDelta: -30,
        laycanRiskDelta: -1,
        demurrageExposureDeltaUsd: -5000,
      },
      unresolved_risks: [],
      approval_lineage: {
        approvalCreated: false,
        manualPublishRequired: true,
      },
      metadata: { candidateKind: "laycan_priority" },
      created_at: "2026-05-18T03:31:10.000Z",
      updated_at: "2026-05-18T03:31:10.000Z",
    }],
    created_at: "2026-05-18T03:31:00.000Z",
    updated_at: "2026-05-18T03:31:10.000Z",
  }];
  overview.globalOptimizationCandidates = overview.globalOptimizationRuns[0].candidates;

  render(<GlobalOptimizationReviewPage overview={overview} />);

  expect(screen.getByRole("heading", { name: "Global Optimization Review" })).toBeInTheDocument();
  expect(screen.getAllByText("GCAN-PHASE6-UI-01").length).toBeGreaterThan(0);
  expect(screen.getByText("Read-only candidates")).toBeInTheDocument();
  expect(screen.getByText(/does not create a plan, approval, or publish event/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Generate|Promote|Publish|Approve|Materialize/i }))
    .not.toBeInTheDocument();
});

test("commercial projection page renders projection-only customer-safe output", () => {
  const overview = stageSevenOverview();
  overview.telemetryTrustSummary = {
    profileKey: "telemetry_trust_default_v1",
    latestAssessmentCount: 1,
    trustedCount: 1,
    degradedCount: 0,
    blockingCount: 0,
    unknownCount: 0,
    latestAssessedAt: "2026-05-18T03:32:00.000Z",
    latestAssessments: [],
  };
  overview.commercialProjectionRun = {
    id: 1001,
    run_id: "CPR-PHASE6-UI",
    status: "succeeded",
    plan_version: 1,
    plan_version_ref: "PLAN-UI V1",
    telemetry_trust_profile: 1,
    telemetry_trust_profile_ref: "telemetry_trust_default_v1",
    input_signature: "commercialabcdef123",
    input_summary: {},
    summary: {
      projectedDemurrageExposureUsd: "12500.00",
    },
    algorithm_version: "phase6.6-commercial-projection",
    audit_lineage: {
      eventAction: "commercial_projection.run.generate",
    },
    generated_by: 1,
    generated_by_email: "berau.scheduler@coalflow.local",
    started_at: "2026-05-18T03:31:00.000Z",
    completed_at: "2026-05-18T03:31:10.000Z",
    error_message: "",
    projections: [{
      id: 1002,
      projection_id: "CSP-PHASE6-UI",
      run: 1001,
      run_ref: "CPR-PHASE6-UI",
      voyage: 501,
      voyage_ref: "OGV-UI-001",
      vessel_name: "MV Customer Safe",
      customer_name: "North Asia Utility",
      trip: 201,
      trip_ref: "PI-PLAN-UI-0001",
      status: "at_risk",
      customer_safe_eta: "2026-05-19T10:00:00.000Z",
      eta_band_start: "2026-05-19T08:00:00.000Z",
      eta_band_end: "2026-05-19T12:00:00.000Z",
      laycan_status: "late",
      laycan_variance_minutes: 180,
      projected_demurrage_exposure_minutes: 180,
      projected_demurrage_exposure_usd: "12500.00",
      commitment_risk_level: "high",
      telemetry_trust_status: "trusted",
      confidence_score: "88.00",
      customer_safe_to_share: true,
      projection_only_disclaimer: "Projection only: not a customer commitment, invoice, laytime calculation, NOR/SOF determination, demurrage settlement, or despatch settlement.",
      details: {
        etaSource: "live_eta_projection",
      },
      created_at: "2026-05-18T03:31:10.000Z",
      updated_at: "2026-05-18T03:31:10.000Z",
    }],
    created_at: "2026-05-18T03:31:00.000Z",
    updated_at: "2026-05-18T03:31:10.000Z",
  };
  overview.commercialProjections = overview.commercialProjectionRun.projections;
  overview.commercialProjectionSummary = {
    runId: "CPR-PHASE6-UI",
    status: "succeeded",
    projectionCount: 1,
    atRiskCount: 1,
    customerSafeToShareCount: 1,
    projectionOnly: true,
  };

  render(<CommercialProjectionPage overview={overview} />);

  expect(screen.getByRole("heading", { name: "Commercial Projections" })).toBeInTheDocument();
  expect(screen.getAllByText("MV Customer Safe").length).toBeGreaterThan(0);
  expect(screen.getByText(/exposure proxies only/)).toBeInTheDocument();
  expect(screen.getByText(/not a customer commitment/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Settle|Invoice|Commit|Publish|Materialize|Approve/i }))
    .not.toBeInTheDocument();
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
    metadata: {},
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
  expect(screen.getByText((_content, element) => (
    element?.tagName.toLowerCase() === "strong"
    && element.textContent === "OGV completion & demurrage"
  ))).toBeInTheDocument();
  expect(screen.getByText("Asset utilization")).toBeInTheDocument();
  expect(screen.getByText("BARGE DELAY")).toBeInTheDocument();
  expect(screen.getByText(/BRG-VAL-08/)).toBeInTheDocument();
  expect(screen.queryByText("OUT OF SERVICE")).not.toBeInTheDocument();
  expect(screen.queryByText("RECOVERY WINDOW")).not.toBeInTheDocument();
});

test("simulation workspace opens telemetry-origin scenarios with editable seeded assumptions", () => {
  const overview = stageSevenOverview();
  overview.simulationScenarios = [{
    id: 777,
    scenario_id: "SIM-PLAN-UI-V1-07",
    name: "Observed delay PI-PLAN-UI-0001",
    scenario_type: "observed_delay_recovery",
    baseline_version: 1,
    baseline_version_ref: "PLAN-UI V1",
    scenario_version: null,
    scenario_version_ref: null,
    source_conflict: null,
    source_conflict_code: null,
    source_conflict_message: null,
    source_override: null,
    source_override_reason_code: null,
    source_override_description: null,
    source_kind: "tracking_alert",
    status: "draft",
    recovery_actions: [],
    impact_summary: {},
    delta_summary: {},
    metadata: {
      source: {
        trackingAlertRef: "ALT-DELAY-0088",
      },
    },
    created_by: 1,
    created_by_email: "berau.scheduler@coalflow.local",
    assumptions: [{
      id: 778,
      scenario: 777,
      scenario_ref: "SIM-PLAN-UI-V1-07",
      assumption_id: "ASM-SIM-PLAN-UI-V1-07-01",
      kind: "trip_delay",
      scope_type: "trip",
      scope_id: 201,
      payload: { delay_minutes: 45 },
      effective_from: "2026-05-17T03:30:00.000Z",
      effective_to: null,
      created_by: 1,
      created_by_email: "berau.scheduler@coalflow.local",
      created_at: "2026-05-17T03:45:00.000Z",
      updated_at: "2026-05-17T03:45:00.000Z",
    }],
    runs: [],
    created_at: "2026-05-17T03:45:00.000Z",
    updated_at: "2026-05-17T03:45:00.000Z",
  }];

  render(<SimulationWorkspacePage canEdit overview={overview} />);

  expect(screen.getByText("ALT-DELAY-0088")).toBeInTheDocument();
  expect(screen.getByLabelText("Delay minutes")).toHaveValue(45);
  fireEvent.change(screen.getByLabelText("Delay minutes"), { target: { value: "60" } });
  expect(screen.getByLabelText("Delay minutes")).toHaveValue(60);
});

test("simulation workspace surfaces recommendation handoff lineage", () => {
  const overview = stageSevenOverview();
  overview.simulationScenarios = [{
    id: 888,
    scenario_id: "SIM-REC-001",
    name: "Recommendation recovery",
    scenario_type: "recovery_recommendation",
    baseline_version: 1,
    baseline_version_ref: "PLAN-UI V1",
    scenario_version: null,
    scenario_version_ref: null,
    source_conflict: null,
    source_conflict_code: null,
    source_conflict_message: null,
    source_override: null,
    source_override_reason_code: null,
    source_override_description: null,
    source_kind: "manual",
    status: "simulated",
    recovery_actions: [],
    impact_summary: {},
    delta_summary: {},
    metadata: {
      source: {
        kind: "recovery_recommendation",
        recommendationId: "REC-PHASE5-UI-01",
        snapshotId: "RIS-PHASE5-UI",
        snapshotSourceKind: "override",
        strategy: "next_window_repair",
      },
    },
    created_by: 1,
    created_by_email: "berau.scheduler@coalflow.local",
    assumptions: [],
    runs: [],
    created_at: "2026-05-18T03:40:00.000Z",
    updated_at: "2026-05-18T03:40:00.000Z",
  }];

  render(<SimulationWorkspacePage overview={overview} />);

  expect(screen.getByText("Recommendation handoff")).toBeInTheDocument();
  expect(screen.getAllByText("REC-PHASE5-UI-01").length).toBeGreaterThan(0);
  expect(screen.getByText("next_window_repair")).toBeInTheDocument();
});
