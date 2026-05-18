import { useCallback, useEffect, useMemo, useState } from "react";

import { AuditStrip } from "./components/AuditStrip";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { apiFetch, getCsrfToken, login, logout } from "./lib/api";
import { canAccess, visibleNavItems, visibleNavModules } from "./lib/navigation";
import { AuditPage } from "./pages/AuditPage";
import { CoalGradeSequencePage } from "./pages/CoalGradeSequencePage";
import { DashboardPage } from "./pages/DashboardPage";
import { ExportHandoffPage } from "./pages/ExportHandoffPage";
import { LoginPage } from "./pages/LoginPage";
import {
  CtsOperationsPage,
  JettyLoadingPage,
  PublishedPlanPage,
  TugBargeAssignmentPage,
} from "./pages/LogisticsPages";
import { LiveResourceMapPage } from "./pages/MapPage";
import { MasterDataPage } from "./pages/MasterDataPage";
import { OgvDemandPage } from "./pages/OgvDemandPage";
import { RbacPage } from "./pages/RbacPage";
import {
  ApprovalsPublishingPage,
  ExceptionCenterPage,
  type ScenarioAssumptionDraft,
  type ScenarioSourceInput,
  SimulationWorkspacePage,
} from "./pages/RecoveryPages";
import { TideBridgePage } from "./pages/TideBridgePage";
import type {
  AuditEvent,
  CurrentUser,
  DashboardReadModel,
  ExportFormat,
  ExportJobRecord,
  ExportOverview,
  ExportType,
  GeofenceZoneRecord,
  ImportJobRecord,
  LatestAssetStateRecord,
  LiveEtaProjectionRecord,
  MasterDataCatalogs,
  MasterDataRecord,
  MasterDataOverview,
  MovementEventRecord,
  ApprovalRequestRecord,
  OverrideRequestRecord,
  PlanRecord,
  PlanVersionRecord,
  PlanningOverview,
  RbacOverview,
  SchedulingOverview,
  SimulationScenarioRecord,
  TelemetryReplayRunRecord,
  TrackingAlertRecord,
} from "./types";

function currentHashPath() {
  return window.location.hash.replace("#", "") || "/dashboard/situation";
}

function upcomingLocalIso(daysFromToday: number, hour: number, minute = 0) {
  const now = new Date();
  return new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() + daysFromToday,
    hour,
    minute,
    0,
    0,
  ).toISOString();
}

function operatorPlanningDates() {
  return {
    laycanStart: upcomingLocalIso(1, 0),
    laycanEnd: upcomingLocalIso(4, 0),
    eta: upcomingLocalIso(1, 6),
    horizonStart: upcomingLocalIso(1, 0),
    horizonEnd: upcomingLocalIso(8, 23, 59),
  };
}

type MasterDataCatalogKey = keyof MasterDataCatalogs;

const MASTER_DATA_ENDPOINTS: Record<MasterDataCatalogKey, string> = {
  barges: "barges",
  coalGrades: "coal-grades",
  compatibilityRules: "compatibility-rules",
  ctsAssets: "cts-assets",
  jetties: "jetties",
  loadingRateProfiles: "loading-rate-profiles",
  locations: "locations",
  mines: "mines",
  routes: "routes",
  stockpiles: "stockpiles",
  tugs: "tugs",
};

function masterDataImportRecord(record: MasterDataRecord) {
  const payload = { ...(record as unknown as Record<string, unknown>) };
  delete payload.id;
  delete payload.organization;
  delete payload.created_at;
  delete payload.updated_at;
  delete payload.mine_code;
  delete payload.coal_grade_code;
  delete payload.segments;
  payload.organization_id = record.organization?.id ?? null;
  return payload;
}

function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [activePath, setActivePath] = useState(currentHashPath());
  const [overview, setOverview] = useState<RbacOverview | null>(null);
  const [masterDataOverview, setMasterDataOverview] = useState<MasterDataOverview | null>(null);
  const [planningOverview, setPlanningOverview] = useState<PlanningOverview | null>(null);
  const [schedulingOverview, setSchedulingOverview] = useState<SchedulingOverview | null>(null);
  const [latestAssetStates, setLatestAssetStates] = useState<LatestAssetStateRecord[]>([]);
  const [geofenceZones, setGeofenceZones] = useState<GeofenceZoneRecord[]>([]);
  const [movementEvents, setMovementEvents] = useState<MovementEventRecord[]>([]);
  const [etaProjections, setEtaProjections] = useState<LiveEtaProjectionRecord[]>([]);
  const [trackingAlerts, setTrackingAlerts] = useState<TrackingAlertRecord[]>([]);
  const [telemetryReplayRuns, setTelemetryReplayRuns] = useState<TelemetryReplayRunRecord[]>([]);
  const [dashboardReadModel, setDashboardReadModel] = useState<DashboardReadModel | null>(null);
  const [exportOverview, setExportOverview] = useState<ExportOverview | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [exportError, setExportError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionInFlight, setActionInFlight] = useState<string | null>(null);
  const [isExportLoading, setIsExportLoading] = useState(false);
  const [isExportGenerating, setIsExportGenerating] = useState(false);
  const [isBooting, setIsBooting] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    apiFetch<CurrentUser>("/me/")
      .then(setCurrentUser)
      .catch(() => setCurrentUser(null))
      .finally(() => setIsBooting(false));
  }, []);

  useEffect(() => {
    function handleHashChange() {
      setActivePath(currentHashPath());
    }

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const navItems = useMemo(
    () => visibleNavItems(currentUser?.permissions ?? []),
    [currentUser],
  );
  const navModules = useMemo(
    () => visibleNavModules(currentUser?.permissions ?? []),
    [currentUser],
  );
  const canViewAudit = currentUser ? canAccess(currentUser.permissions, "audit.view") : false;
  const canViewDashboard = currentUser ? canAccess(currentUser.permissions, "dashboard.view") : false;
  const canViewExports = currentUser ? canAccess(currentUser.permissions, "export.view") : false;
  const canGenerateExports = currentUser
    ? canAccess(currentUser.permissions, "export.generate")
    : false;
  const canViewFleet = currentUser ? canAccess(currentUser.permissions, "fleet.view") : false;
  const canViewTelemetry = currentUser
    ? canAccess(currentUser.permissions, "telemetry.view")
    : false;
  const canRunTelemetryReplay = currentUser
    ? canAccess(currentUser.permissions, "telemetry.ingest")
    : false;
  const canViewAdmin = currentUser ? canAccess(currentUser.permissions, "admin.view") : false;
  const canViewMasterData = currentUser
    ? canAccess(currentUser.permissions, "masterdata.view")
    : false;
  const canManageMasterData = currentUser
    ? canAccess(currentUser.permissions, "masterdata.manage")
    : false;
  const canViewSchedule = currentUser ? canAccess(currentUser.permissions, "schedule.view") : false;
  const canEditSchedule = currentUser ? canAccess(currentUser.permissions, "schedule.edit") : false;
  const canApproveSchedule = currentUser
    ? canAccess(currentUser.permissions, "schedule.approve")
    : false;
  const canPublishSchedule = currentUser
    ? canAccess(currentUser.permissions, "schedule.publish")
    : false;
  const canRunSimulation = currentUser
    ? canEditSchedule && canAccess(currentUser.permissions, "simulation.run")
    : false;

  const refreshWorkspaceData = useCallback(async () => {
    if (!currentUser) {
      return;
    }

    const refreshes: Promise<unknown>[] = [];

    if (canViewDashboard) {
      refreshes.push(apiFetch<DashboardReadModel>("/dashboard/situation/")
        .then(setDashboardReadModel)
        .catch(() => setDashboardReadModel(null)));
    }

    if (canViewAdmin) {
      refreshes.push(apiFetch<RbacOverview>("/rbac/overview/")
        .then(setOverview)
        .catch(() => setOverview(null)));
    }

    if (canViewMasterData) {
      refreshes.push(apiFetch<MasterDataOverview>("/master-data/overview/")
        .then(setMasterDataOverview)
        .catch(() => setMasterDataOverview(null)));
    }

    if (canViewAudit) {
      refreshes.push(apiFetch<AuditEvent[]>("/audit-events/")
        .then(setAuditEvents)
        .catch(() => setAuditEvents([])));
    }

    if (canViewExports) {
      setIsExportLoading(true);
      setExportError(null);
      refreshes.push(apiFetch<ExportOverview>("/exports/overview/")
        .then(setExportOverview)
        .catch(() => {
          setExportOverview(null);
          setExportError("Export history is unavailable.");
        })
        .finally(() => setIsExportLoading(false)));
    }

    if (canViewSchedule) {
      refreshes.push(apiFetch<PlanningOverview>("/planning/overview/")
        .then(setPlanningOverview)
        .catch(() => setPlanningOverview(null)));
    }

    if (canViewSchedule) {
      refreshes.push(apiFetch<SchedulingOverview>("/scheduling/overview/")
        .then(setSchedulingOverview)
        .catch(() => setSchedulingOverview(null)));
    }

    if (canViewTelemetry) {
      refreshes.push(apiFetch<LatestAssetStateRecord[]>("/telemetry/latest-asset-states/")
        .then(setLatestAssetStates)
        .catch(() => setLatestAssetStates([])));
      refreshes.push(apiFetch<GeofenceZoneRecord[]>("/telemetry/geofence-zones/")
        .then(setGeofenceZones)
        .catch(() => setGeofenceZones([])));
      refreshes.push(apiFetch<MovementEventRecord[]>("/telemetry/movement-events/?limit=120")
        .then(setMovementEvents)
        .catch(() => setMovementEvents([])));
      refreshes.push(apiFetch<LiveEtaProjectionRecord[]>("/telemetry/eta-projections/?limit=120")
        .then(setEtaProjections)
        .catch(() => setEtaProjections([])));
      refreshes.push(apiFetch<TrackingAlertRecord[]>("/telemetry/alerts/?limit=120")
        .then(setTrackingAlerts)
        .catch(() => setTrackingAlerts([])));
      refreshes.push(apiFetch<TelemetryReplayRunRecord[]>("/telemetry/replay-runs/")
        .then(setTelemetryReplayRuns)
        .catch(() => setTelemetryReplayRuns([])));
    } else {
      setLatestAssetStates([]);
      setGeofenceZones([]);
      setMovementEvents([]);
      setEtaProjections([]);
      setTrackingAlerts([]);
      setTelemetryReplayRuns([]);
    }

    await Promise.all(refreshes);
  }, [
    canViewAdmin,
    canViewAudit,
    canViewDashboard,
    canViewExports,
    canViewMasterData,
    canViewSchedule,
    canViewTelemetry,
    currentUser,
  ]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    void refreshWorkspaceData();
  }, [currentUser, refreshWorkspaceData]);

  async function runWorkspaceAction(label: string, action: () => Promise<string>) {
    setActionInFlight(label);
    setActionError(null);
    setActionMessage(null);
    try {
      const message = await action();
      setActionMessage(message);
      await refreshWorkspaceData();
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setActionError(`${label} failed (${detail}). Check permissions, active plan state, and backend logs.`);
    } finally {
      setActionInFlight(null);
    }
  }

  async function handleLogin(username: string, password: string) {
    const user = await login(username, password);
    setCurrentUser(user);
  }

  async function handleLogout() {
    await logout();
    setCurrentUser(null);
    setOverview(null);
    setMasterDataOverview(null);
    setPlanningOverview(null);
    setSchedulingOverview(null);
    setLatestAssetStates([]);
    setGeofenceZones([]);
    setMovementEvents([]);
    setEtaProjections([]);
    setTrackingAlerts([]);
    setTelemetryReplayRuns([]);
    setDashboardReadModel(null);
    setExportOverview(null);
    setAuditEvents([]);
    setExportError(null);
  }

  async function handleSyncWorkspace() {
    await runWorkspaceAction("Sync workspace", async () => "Workspace synchronized");
  }

  function handleOpenNotifications() {
    if (canViewSchedule) {
      handleNavigate("/exceptions/center");
      return;
    }
    if (canViewAudit) {
      handleNavigate("/admin/audit-logs");
      return;
    }
    handleNavigate(navItems[0]?.path ?? "/dashboard/situation");
  }

  function handleOpenApps() {
    if (canViewMasterData) {
      handleNavigate("/admin/master-data");
      return;
    }
    if (canViewExports) {
      handleNavigate("/admin/export-handoff");
      return;
    }
    handleNavigate(navItems[0]?.path ?? "/dashboard/situation");
  }

  async function handleGenerateExport(command: {
    exportType: ExportType;
    exportFormat: ExportFormat;
  }) {
    if (!canGenerateExports) {
      return;
    }

    await runWorkspaceAction("Export", async () => {
      setIsExportGenerating(true);
      setExportError(null);
      const csrfToken = await getCsrfToken();
      const activePlanVersionId = schedulingOverview?.activePlanVersion?.id;
      const exportJob = await apiFetch<ExportJobRecord>("/exports/generate/", {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          export_type: command.exportType,
          export_format: command.exportFormat,
          ...(command.exportType === "audit" || !activePlanVersionId
            ? {}
            : { plan_version: activePlanVersionId }),
        }),
      });
      const refreshed = await apiFetch<ExportOverview>("/exports/overview/");
      setExportOverview(refreshed);
      setIsExportGenerating(false);
      return `Export generated: ${exportJob.file_name}`;
    }).finally(() => setIsExportGenerating(false));
  }

  async function handleImportDemand() {
    await runWorkspaceAction("Import demand", async () => {
      const csrfToken = await getCsrfToken();
      const stamp = Date.now();
      const dates = operatorPlanningDates();
      const job = await apiFetch<ImportJobRecord>("/planning/import-jobs/validate-ogv-demand/", {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          commit: true,
          filename: `operator-ui-demand-${stamp}.xlsx`,
          source: "operator-ui-action",
          rows: [
            {
              voyage_id: `VOY-UI-${String(stamp).slice(-6)}`,
              vessel_name: "MV Operator UI Import",
              customer_name: "Pilot Customer",
              laycan_start: dates.laycanStart,
              laycan_end: dates.laycanEnd,
              eta: dates.eta,
              required_mt: 64000,
            },
          ],
        }),
      });
      return `Import committed: ${job.filename} (${job.valid_rows}/${job.total_rows} rows)`;
    });
  }

  async function handleEnterOperatingWindows() {
    await runWorkspaceAction("Enter operating windows", async () => {
      const csrfToken = await getCsrfToken();
      const result = await apiFetch<{
        assetWindows: number;
        jettyWindows: number;
        tideWindow: string;
        bridgeWindow: string;
        tideWindows?: string[];
        bridgeWindows?: string[];
        constraintChecks: number;
      }>("/planning/overview/enter-operating-windows/", {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
      });
      const tideLabels = result.tideWindows?.join(", ") ?? result.tideWindow;
      const bridgeLabels = result.bridgeWindows?.join(", ") ?? result.bridgeWindow;
      return `Operating windows entered: ${tideLabels}; ${bridgeLabels}; ${result.constraintChecks} checks`;
    });
  }

  async function handleMasterDataExport(catalogKey: MasterDataCatalogKey) {
    await runWorkspaceAction("Master data export", async () => {
      const endpoint = MASTER_DATA_ENDPOINTS[catalogKey];
      const exported = await apiFetch<{ catalog: string; recordCount: number }>(
        `/master-data/${endpoint}/export/`,
      );
      return `Master data export ready: ${exported.catalog} (${exported.recordCount} records)`;
    });
  }

  async function handleMasterDataImport(
    catalogKey: MasterDataCatalogKey,
    selectedRecord: MasterDataRecord | null,
  ) {
    await runWorkspaceAction("Master data import", async () => {
      if (!selectedRecord) {
        throw new Error("No selected master data record");
      }
      const endpoint = MASTER_DATA_ENDPOINTS[catalogKey];
      const csrfToken = await getCsrfToken();
      const result = await apiFetch<{ created: number; updated: number; count: number }>(
        `/master-data/${endpoint}/import/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            records: [masterDataImportRecord(selectedRecord)],
          }),
        },
      );
      return `Master data import processed: ${result.updated} updated / ${result.created} created`;
    });
  }

  async function handleMasterDataValidate(catalogKey: MasterDataCatalogKey) {
    await runWorkspaceAction("Master data validate", async () => {
      const records = masterDataOverview?.catalogs[catalogKey] ?? [];
      const inactive = records.filter((record) => !record.is_active).length;
      return `Master data validation complete: ${records.length} ${catalogKey} records, ${inactive} inactive`;
    });
  }

  async function createInitialOperatorPlanVersion() {
    const csrfToken = await getCsrfToken();
    const defaultMembership = currentUser?.memberships.find((membership) => membership.is_default)
      ?? currentUser?.memberships[0];
    const stamp = Date.now();
    const dates = operatorPlanningDates();
    const plan = await apiFetch<PlanRecord>("/scheduling/plans/", {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({
        code: `PLAN-UI-${String(stamp).slice(-8)}`,
        name: "Operator UI Planning Run",
        organization_id: defaultMembership?.organization.id ?? null,
        horizon_start: dates.horizonStart,
        horizon_end: dates.horizonEnd,
        status: "active",
      }),
    });
    return apiFetch<PlanVersionRecord>(`/scheduling/plans/${plan.id}/create-version/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
      },
    });
  }

  async function handleCreateDraft() {
    await runWorkspaceAction("Create draft", async () => {
      const activeVersion = schedulingOverview?.activePlanVersion;
      if (!activeVersion) {
        const draft = await createInitialOperatorPlanVersion();
        return `Initial draft created: ${draft.plan_code} V${draft.version_no}`;
      }
      if (["draft", "proposed"].includes(activeVersion.status)) {
        return `Draft already active: ${activeVersion.plan_code} V${activeVersion.version_no}`;
      }
      if (activeVersion.status === "validated") {
        return `Editable plan already active: ${activeVersion.plan_code} V${activeVersion.version_no}`;
      }
      const csrfToken = await getCsrfToken();
      const draft = await apiFetch<PlanVersionRecord>(
        `/scheduling/plan-versions/${activeVersion.id}/clone/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
        },
      );
      return `Draft created: ${draft.plan_code} V${draft.version_no}`;
    });
  }

  async function handleRegeneratePlan() {
    await runWorkspaceAction("Generate schedule", async () => {
      const activeVersion = schedulingOverview?.activePlanVersion
        ?? await createInitialOperatorPlanVersion();
      if (["published", "superseded"].includes(activeVersion.status)) {
        throw new Error("No editable active plan version");
      }
      const csrfToken = await getCsrfToken();
      const version = await apiFetch<PlanVersionRecord>(
        `/scheduling/plan-versions/${activeVersion.id}/generate/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
        },
      );
      return `Schedule generated: ${version.plan_code} V${version.version_no}`;
    });
  }

  async function handleForceStartJetty(assignmentId: number, actualStartAt: string) {
    await runWorkspaceAction("Force start jetty", async () => {
      const assignment = schedulingOverview?.assignments.find((item) => item.id === assignmentId)
        ?? schedulingOverview?.assignments.find((item) => item.jetty)
        ?? schedulingOverview?.assignments[0];
      if (!assignment) {
        throw new Error("No assignment available for jetty override");
      }
      if (!actualStartAt) {
        throw new Error("Effective start time is required for impact calculation");
      }
      const csrfToken = await getCsrfToken();
      const override = await apiFetch<OverrideRequestRecord>(
        `/scheduling/assignments/${assignment.id}/apply-override/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            reason_code: "jetty_delay",
            description: `Force-started ${assignment.jetty?.code ?? "jetty queue"} from operator cockpit.`,
            changes: {
              status: "loading",
              next_action: "Force-started from operator cockpit; monitor downstream tide/bridge gates.",
            },
            impact_context: {
              actual_start_at: actualStartAt,
            },
          }),
        },
      );
      const delay = override.impact_assessment?.delay_minutes;
      return `Governed jetty override applied: ${override.reason_code.replaceAll("_", " ")}${
        typeof delay === "number" ? ` (${delay}m impact)` : ""
      }`;
    });
  }

  async function handleCreateScenario(source: ScenarioSourceInput) {
    await runWorkspaceAction("Create scenario", async () => {
      const csrfToken = await getCsrfToken();
      if (source.kind === "tracking_alert" && source.id) {
        const scenario = await apiFetch<SimulationScenarioRecord>(
          `/telemetry/alerts/${source.id}/convert-to-scenario/`,
          {
            method: "POST",
            headers: {
              "X-CSRFToken": csrfToken,
            },
          },
        );
        handleNavigate("/simulation/workspace");
        return `Scenario created from observed delay: ${scenario.scenario_id}`;
      }

      const activeVersion = schedulingOverview?.activePlanVersion;
      if (!activeVersion) {
        throw new Error("No active plan version");
      }
      const scenario = await apiFetch<SimulationScenarioRecord>(
        `/scheduling/plan-versions/${activeVersion.id}/create-scenario/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            ...(source.kind === "conflict" && source.id ? { conflict: source.id } : {}),
            ...(source.kind === "override" && source.id ? { override: source.id } : {}),
            name: source.name
              ?? `Operator recovery ${activeVersion.plan_code} V${activeVersion.version_no}`,
          }),
        },
      );
      handleNavigate("/simulation/workspace");
      return `Scenario created: ${scenario.scenario_id}`;
    });
  }

  async function handleStartTelemetryReplay(replayId: string) {
    await runWorkspaceAction("Start synthetic replay", async () => {
      const csrfToken = await getCsrfToken();
      const replay = await apiFetch<TelemetryReplayRunRecord>(
        `/telemetry/replay-runs/${replayId}/start/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
        },
      );
      return `Synthetic replay completed: ${replay.scenario_code.replaceAll("_", " ")}`;
    });
  }

  async function handleCreateAssumption(
    scenarioId: number,
    assumption: ScenarioAssumptionDraft,
  ) {
    await runWorkspaceAction("Add assumption", async () => {
      const csrfToken = await getCsrfToken();
      await apiFetch(`/scheduling/scenarios/${scenarioId}/assumptions/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(assumption),
      });
      return `Scenario assumption added: ${assumption.kind.replaceAll("_", " ")}`;
    });
  }

  function currentScenario(scenarioId?: number) {
    return schedulingOverview?.simulationScenarios.find((scenario) => scenario.id === scenarioId)
      ?? schedulingOverview?.simulationScenarios[0]
      ?? null;
  }

  async function handleRunSimulation(scenarioId?: number) {
    await runWorkspaceAction("Run simulation", async () => {
      const scenario = currentScenario(scenarioId);
      if (!scenario) {
        throw new Error("No simulation scenario");
      }
      const csrfToken = await getCsrfToken();
      const simulated = await apiFetch<SimulationScenarioRecord>(
        `/scheduling/scenarios/${scenario.id}/simulate/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
        },
      );
      return `Simulation complete: ${simulated.scenario_id}`;
    });
  }

  async function handlePromoteScenario(scenarioId?: number, runId?: number) {
    await runWorkspaceAction("Promote scenario", async () => {
      const scenario = currentScenario(scenarioId);
      if (!scenario) {
        throw new Error("No simulation scenario");
      }
      const csrfToken = await getCsrfToken();
      const promoted = await apiFetch<SimulationScenarioRecord>(
        `/scheduling/scenarios/${scenario.id}/promote/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify(runId ? { run_id: runId } : {}),
        },
      );
      return `Scenario promoted: ${promoted.scenario_version_ref ?? promoted.scenario_id}`;
    });
  }

  async function handleSubmitApproval() {
    await runWorkspaceAction("Submit approval", async () => {
      const activeVersion = schedulingOverview?.activePlanVersion;
      if (!activeVersion || ["published", "superseded"].includes(activeVersion.status)) {
        throw new Error("No submittable active plan version");
      }
      const csrfToken = await getCsrfToken();
      const approval = await apiFetch<ApprovalRequestRecord>(
        `/scheduling/plan-versions/${activeVersion.id}/request-approval/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            reason: `Submitted from operator cockpit for ${activeVersion.plan_code} V${activeVersion.version_no}.`,
          }),
        },
      );
      handleNavigate("/approvals/publishing");
      return `Approval submitted: ${approval.request_id}`;
    });
  }

  function authorityForCurrentUser(requestAuthorities: string[], decidedAuthorities: string[]) {
    const roleCodes = currentUser?.assignments.map((assignment) => assignment.role.code) ?? [];
    const preferredAuthority = roleCodes.includes("berau-scheduler")
      ? "berau_scheduler"
      : roleCodes.includes("abl-dispatcher")
        ? "abl_dispatcher"
        : null;
    if (
      preferredAuthority
      && requestAuthorities.includes(preferredAuthority)
      && !decidedAuthorities.includes(preferredAuthority)
    ) {
      return preferredAuthority;
    }
    return requestAuthorities.find((authority) => !decidedAuthorities.includes(authority));
  }

  async function handleApprovePlan() {
    await runWorkspaceAction("Approve plan", async () => {
      const request = schedulingOverview?.approvalRequests.find((item) => item.status === "pending")
        ?? schedulingOverview?.approvalRequests[0];
      if (!request) {
        throw new Error("No approval request");
      }
      const decidedAuthorities = request.decisions
        .filter((decision) => decision.decision === "approve")
        .map((decision) => decision.authority_role);
      const authorityRole = authorityForCurrentUser(request.required_authorities, decidedAuthorities);
      if (!authorityRole) {
        throw new Error("No remaining approval authority");
      }
      const csrfToken = await getCsrfToken();
      await apiFetch(`/scheduling/approval-requests/${request.id}/decide/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          authority_role: authorityRole,
          decision: "approve",
          comments: `Approved from ${currentUser?.email ?? "operator"} via cockpit action.`,
        }),
      });
      return `Approved ${request.request_id} as ${authorityRole.replaceAll("_", " ")}`;
    });
  }

  async function handleRejectPlan() {
    await runWorkspaceAction("Reject plan", async () => {
      const request = schedulingOverview?.approvalRequests.find((item) => item.status === "pending")
        ?? schedulingOverview?.approvalRequests[0];
      if (!request) {
        throw new Error("No approval request");
      }
      const decidedAuthorities = request.decisions.map((decision) => decision.authority_role);
      const authorityRole = authorityForCurrentUser(request.required_authorities, decidedAuthorities)
        ?? request.required_authorities[0];
      if (!authorityRole) {
        throw new Error("No approval authority");
      }
      const csrfToken = await getCsrfToken();
      await apiFetch(`/scheduling/approval-requests/${request.id}/decide/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          authority_role: authorityRole,
          decision: "reject",
          comments: `Rejected from ${currentUser?.email ?? "operator"} via cockpit action.`,
        }),
      });
      return `Rejected ${request.request_id} as ${authorityRole.replaceAll("_", " ")}`;
    });
  }

  async function handlePublishPlan() {
    await runWorkspaceAction("Publish plan", async () => {
      const activeVersion = schedulingOverview?.activePlanVersion;
      if (!activeVersion) {
        throw new Error("No active plan version");
      }
      const csrfToken = await getCsrfToken();
      await apiFetch(`/scheduling/plan-versions/${activeVersion.id}/publish/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
      });
      return `Published ${activeVersion.plan_code} V${activeVersion.version_no}`;
    });
  }

  function handleNavigate(path: string) {
    window.location.hash = path;
    setActivePath(path);
  }

  if (isBooting) {
    return <main className="boot-screen">Loading workspace...</main>;
  }

  if (!currentUser) {
    return <LoginPage onSubmit={handleLogin} />;
  }

  const firstAccessiblePath = navItems[0]?.path ?? "/dashboard/situation";
  const routeIsAllowed = navItems.some((item) => item.path === activePath);
  const route = routeIsAllowed ? activePath : firstAccessiblePath;
  const activePlanStatus = schedulingOverview?.activePlanVersion?.status;
  const activePlanIsEditable = Boolean(
    activePlanStatus && !["published", "superseded"].includes(activePlanStatus),
  );
  const isWorkspaceActionRunning = Boolean(actionInFlight);

  return (
    <main className={sidebarCollapsed ? "operations-shell sidebar-is-collapsed" : "operations-shell"}>
      <Topbar
        currentUser={currentUser}
        onLogout={handleLogout}
        onOpenApps={handleOpenApps}
        onOpenNotifications={handleOpenNotifications}
        onSyncWorkspace={handleSyncWorkspace}
      />
      <Sidebar
        activePath={route}
        canOpenSystemAudit={canViewAudit}
        canOpenTerminalSupport={canViewExports}
        collapsed={sidebarCollapsed}
        modules={navModules}
        onNavigate={handleNavigate}
        onOpenSystemAudit={() => handleNavigate("/admin/audit-logs")}
        onOpenTerminalSupport={() => handleNavigate("/admin/export-handoff")}
        onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
      />
      <section className="operations-main">
        {actionMessage ? <div className="workspace-action-banner">{actionMessage}</div> : null}
        {actionError ? <div className="workspace-action-banner critical">{actionError}</div> : null}
        {route === "/admin/master-data" && masterDataOverview ? (
          <MasterDataPage
            canManage={canManageMasterData}
            isActionRunning={isWorkspaceActionRunning}
            onExportCatalog={handleMasterDataExport}
            onImportCatalog={handleMasterDataImport}
            onValidateCatalog={handleMasterDataValidate}
            overview={masterDataOverview}
          />
        ) : null}
        {route === "/admin/users-rbac" && overview ? <RbacPage overview={overview} /> : null}
        {route === "/admin/audit-logs" && canViewAudit ? <AuditPage events={auditEvents} /> : null}
        {route === "/admin/export-handoff" && canViewExports ? (
          <ExportHandoffPage
            canGenerate={canGenerateExports}
            error={exportError}
            isGenerating={isExportGenerating}
            isLoading={isExportLoading}
            onGenerate={handleGenerateExport}
            overview={exportOverview}
          />
        ) : null}
        {route === "/schedule/ogv-demand" && canViewSchedule ? (
          <OgvDemandPage
            canEdit={canEditSchedule}
            canExport={canGenerateExports}
            isActionRunning={isWorkspaceActionRunning}
            onExportBoard={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            onImportDemand={handleImportDemand}
            overview={planningOverview}
          />
        ) : null}
        {route === "/schedule/coal-grade-sequence" && canViewSchedule ? (
          <CoalGradeSequencePage
            canEdit={canEditSchedule}
            canExport={canGenerateExports}
            isActionRunning={isWorkspaceActionRunning}
            onExport={() => handleGenerateExport({ exportType: "conflict", exportFormat: "json" })}
            overview={planningOverview}
          />
        ) : null}
        {route === "/constraints/tide-bridge" && canViewSchedule ? (
          <TideBridgePage
            canEdit={canEditSchedule}
            isActionRunning={isWorkspaceActionRunning}
            onEnterOperatingWindows={handleEnterOperatingWindows}
            overview={planningOverview}
          />
        ) : null}
        {route === "/operations/tug-barge-assignment" && canViewSchedule ? (
          <TugBargeAssignmentPage
            canEdit={canEditSchedule}
            canExport={canGenerateExports}
            isActionRunning={isWorkspaceActionRunning}
            onExport={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            onRegenerate={handleRegeneratePlan}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/operations/jetty-loading" && canViewSchedule ? (
          <JettyLoadingPage
            canEdit={canEditSchedule && activePlanIsEditable}
            canExport={canGenerateExports}
            isActionRunning={isWorkspaceActionRunning}
            onExport={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            onForceStartJetty={handleForceStartJetty}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/operations/cts-floating-crane" && canViewSchedule ? (
          <CtsOperationsPage
            canExport={canGenerateExports}
            isActionRunning={isWorkspaceActionRunning}
            onExport={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/schedule/published-plan" && canViewSchedule ? (
          <PublishedPlanPage
            canCreateDraft={canEditSchedule}
            isActionRunning={isWorkspaceActionRunning}
            onCreateDraft={handleCreateDraft}
            onSubmitApproval={activePlanIsEditable ? handleSubmitApproval : undefined}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/exceptions/center" && canViewSchedule ? (
          <ExceptionCenterPage
            canEdit={canEditSchedule && activePlanIsEditable}
            isActionRunning={isWorkspaceActionRunning}
            onCreateScenario={handleCreateScenario}
            onPublishTriage={canGenerateExports
              ? () => handleGenerateExport({ exportType: "conflict", exportFormat: "json" })
              : undefined}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/simulation/workspace" && canEditSchedule ? (
          <SimulationWorkspacePage
            canEdit={canEditSchedule && activePlanIsEditable}
            isActionRunning={isWorkspaceActionRunning}
            onCreateAssumption={handleCreateAssumption}
            onCreateScenario={handleCreateScenario}
            onPromoteScenario={handlePromoteScenario}
            onRunSimulation={handleRunSimulation}
            onSubmitApproval={activePlanIsEditable ? handleSubmitApproval : undefined}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/approvals/publishing" && canApproveSchedule ? (
          <ApprovalsPublishingPage
            canEdit={canApproveSchedule}
            canPublish={canPublishSchedule}
            isActionRunning={isWorkspaceActionRunning}
            onApprove={handleApprovePlan}
            onPublish={handlePublishPlan}
            onReject={handleRejectPlan}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/map/live" && canViewFleet ? (
          <LiveResourceMapPage
            canRunReplay={canRunTelemetryReplay}
            canRunSimulation={canRunSimulation}
            etaProjections={etaProjections}
            geofenceZones={geofenceZones}
            isActionRunning={isWorkspaceActionRunning}
            latestAssetStates={latestAssetStates}
            movementEvents={movementEvents}
            onNavigate={handleNavigate}
            onStartReplay={handleStartTelemetryReplay}
            overview={schedulingOverview}
            replayRuns={telemetryReplayRuns}
            trackingAlerts={trackingAlerts}
          />
        ) : null}
        {route === "/dashboard/situation" ? (
          <DashboardPage
            auditEvents={auditEvents}
            currentUser={currentUser}
            dashboard={dashboardReadModel}
            etaProjections={etaProjections}
            onNavigate={handleNavigate}
            operationsHealth={schedulingOverview?.operationsHealthSummary ?? null}
            replayRuns={telemetryReplayRuns}
            trackingAlerts={trackingAlerts}
          />
        ) : null}
      </section>
      <AuditStrip canViewAudit={canViewAudit} events={auditEvents} />
    </main>
  );
}

export default App;
