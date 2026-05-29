import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AuditStrip } from "./components/AuditStrip";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { useNextActions } from "./hooks/useNextActions";
import { apiFetch, getCsrfToken, login, logout } from "./lib/api";
import {
  fetchActiveFlowForAction,
  recordFlowCtaEvidence,
  shouldUseHappyPathTrialImport,
} from "./lib/flowEvidence";
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
import { OperationsEventConsolePage } from "./pages/OperationsEventConsolePage";
import { RbacPage } from "./pages/RbacPage";
import {
  ApprovalsPublishingPage,
  ExceptionCenterPage,
  GlobalOptimizationReviewPage,
  RecommendationConsolePage,
  type RecommendationSourceInput,
  type ScenarioAssumptionDraft,
  type ScenarioSourceInput,
  SimulationWorkspacePage,
} from "./pages/RecoveryPages";
import { TideBridgePage } from "./pages/TideBridgePage";
import type {
  AuditEvent,
  CurrentUser,
  DashboardReadModel,
  DeviceEndpointRecord,
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
  OperationalEventCandidateRecord,
  ConfirmedOperationalEventRecord,
  OperationsOverviewRecord,
  ApprovalRequestRecord,
  OverrideRequestRecord,
  PlanRecord,
  PlanVersionRecord,
  PlanningOverview,
  PublishabilityAssessmentRecord,
  RbacOverview,
  RecoveryInputSnapshotRecord,
  RecoveryRecommendationRecord,
  RootCauseRepairAssessmentRecord,
  OptimizerRunRecord,
  SchedulingOverview,
  SimulationScenarioRecord,
  TelemetryReplayRunRecord,
  TrackingAlertRecord,
} from "./types";

function currentHashPath() {
  return window.location.hash.replace("#", "") || "/dashboard/situation";
}

const LIVE_REFRESH_INTERVAL_MS = 15000;
const INTERACTION_REFRESH_THROTTLE_MS = 1000;
const ACTION_FEEDBACK_TIMEOUT_MS = 4000;

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
  const [operationsOverview, setOperationsOverview] = useState<OperationsOverviewRecord | null>(null);
  const [operationCandidates, setOperationCandidates] = useState<OperationalEventCandidateRecord[]>([]);
  const [confirmedOperationalEvents, setConfirmedOperationalEvents] = useState<ConfirmedOperationalEventRecord[]>([]);
  const [operationDevices, setOperationDevices] = useState<DeviceEndpointRecord[]>([]);
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
  const masterDataOverviewRef = useRef<MasterDataOverview | null>(null);
  const schedulingOverviewRef = useRef<SchedulingOverview | null>(null);
  const workspaceRefreshPromiseRef = useRef<Promise<void> | null>(null);
  const workspaceLastRefreshAtRef = useRef(0);
  const actionFeedbackTimerRef = useRef<number | null>(null);

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
  const canViewOperations = currentUser
    ? canAccess(currentUser.permissions, "operations.view")
    : false;
  const canConfirmJetty = currentUser
    ? canAccess(currentUser.permissions, "operations.confirm_jetty")
    : false;
  const canConfirmCts = currentUser
    ? canAccess(currentUser.permissions, "operations.confirm_cts")
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
  const firstAccessiblePath = navItems[0]?.path ?? "/dashboard/situation";
  const routeIsAllowed = navItems.some((item) => item.path === activePath);
  const route = routeIsAllowed ? activePath : firstAccessiblePath;
  const assistant = useNextActions(route, { enabled: Boolean(currentUser) });
  const refreshAssistantActions = assistant.refresh;
  const assistantFlowRef = useRef(assistant.data?.flow ?? null);

  useEffect(() => {
    assistantFlowRef.current = assistant.data?.flow ?? null;
  }, [assistant.data?.flow]);

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
        .then((data) => {
          masterDataOverviewRef.current = data;
          setMasterDataOverview(data);
        })
        .catch(() => {
          masterDataOverviewRef.current = null;
          setMasterDataOverview(null);
        }));
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
        .then((data) => {
          schedulingOverviewRef.current = data;
          setSchedulingOverview(data);
        })
        .catch(() => {
          schedulingOverviewRef.current = null;
          setSchedulingOverview(null);
        }));
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

    if (canViewOperations) {
      refreshes.push(apiFetch<OperationsOverviewRecord>("/operations/overview/")
        .then(setOperationsOverview)
        .catch(() => setOperationsOverview(null)));
      refreshes.push(apiFetch<OperationalEventCandidateRecord[]>("/operations/event-candidates/?limit=160")
        .then(setOperationCandidates)
        .catch(() => setOperationCandidates([])));
      refreshes.push(apiFetch<ConfirmedOperationalEventRecord[]>("/operations/confirmed-events/?limit=160")
        .then(setConfirmedOperationalEvents)
        .catch(() => setConfirmedOperationalEvents([])));
      refreshes.push(apiFetch<DeviceEndpointRecord[]>("/operations/devices/?limit=80")
        .then(setOperationDevices)
        .catch(() => setOperationDevices([])));
    } else {
      setOperationsOverview(null);
      setOperationCandidates([]);
      setConfirmedOperationalEvents([]);
      setOperationDevices([]);
    }

    await Promise.all(refreshes);
  }, [
    canViewAdmin,
    canViewAudit,
    canViewDashboard,
    canViewExports,
    canViewMasterData,
    canViewSchedule,
    canViewOperations,
    canViewTelemetry,
    currentUser,
  ]);

  const requestWorkspaceRefresh = useCallback(async (options: { force?: boolean } = {}) => {
    if (!currentUser) {
      return;
    }

    const now = Date.now();
    if (
      !options.force
      && !workspaceRefreshPromiseRef.current
      && now - workspaceLastRefreshAtRef.current < INTERACTION_REFRESH_THROTTLE_MS
    ) {
      return;
    }

    if (workspaceRefreshPromiseRef.current) {
      await workspaceRefreshPromiseRef.current;
      return;
    }

    const refreshPromise = refreshWorkspaceData()
      .then(() => {
        workspaceLastRefreshAtRef.current = Date.now();
        refreshAssistantActions();
      })
      .finally(() => {
        workspaceRefreshPromiseRef.current = null;
      });
    workspaceRefreshPromiseRef.current = refreshPromise;
    await refreshPromise;
  }, [currentUser, refreshAssistantActions, refreshWorkspaceData]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    void requestWorkspaceRefresh({ force: true });
  }, [currentUser, requestWorkspaceRefresh, route]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    function refreshWhenVisible() {
      if (document.visibilityState !== "hidden") {
        void requestWorkspaceRefresh();
      }
    }

    const intervalId = window.setInterval(refreshWhenVisible, LIVE_REFRESH_INTERVAL_MS);
    window.addEventListener("focus", refreshWhenVisible);
    window.addEventListener("online", refreshWhenVisible);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", refreshWhenVisible);
      window.removeEventListener("online", refreshWhenVisible);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [currentUser, requestWorkspaceRefresh]);

  useEffect(() => {
    if (actionFeedbackTimerRef.current !== null) {
      window.clearTimeout(actionFeedbackTimerRef.current);
      actionFeedbackTimerRef.current = null;
    }

    if (!actionMessage && !actionError) {
      return undefined;
    }

    actionFeedbackTimerRef.current = window.setTimeout(() => {
      setActionMessage(null);
      setActionError(null);
      actionFeedbackTimerRef.current = null;
    }, ACTION_FEEDBACK_TIMEOUT_MS);

    return () => {
      if (actionFeedbackTimerRef.current !== null) {
        window.clearTimeout(actionFeedbackTimerRef.current);
        actionFeedbackTimerRef.current = null;
      }
    };
  }, [actionMessage, actionError]);

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    function refreshForOperatorInteraction(event: Event) {
      const target = event.target;
      if (!(target instanceof Element) || !target.closest(".operations-shell")) {
        return;
      }
      void requestWorkspaceRefresh();
    }

    document.addEventListener("pointerdown", refreshForOperatorInteraction, true);
    document.addEventListener("keydown", refreshForOperatorInteraction, true);
    return () => {
      document.removeEventListener("pointerdown", refreshForOperatorInteraction, true);
      document.removeEventListener("keydown", refreshForOperatorInteraction, true);
    };
  }, [currentUser, requestWorkspaceRefresh]);

  function liveSchedulingOverview() {
    return schedulingOverviewRef.current ?? schedulingOverview;
  }

  function liveMasterDataOverview() {
    return masterDataOverviewRef.current ?? masterDataOverview;
  }

  async function runWorkspaceAction(label: string, action: () => Promise<string>) {
    setActionInFlight(label);
    setActionError(null);
    setActionMessage(null);
    try {
      await requestWorkspaceRefresh({ force: true });
      const message = await action();
      setActionMessage(message);
      await requestWorkspaceRefresh({ force: true });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      setActionError(`${label} failed (${detail}). Check permissions, active plan state, and backend logs.`);
    } finally {
      setActionInFlight(null);
    }
  }

  async function recordActiveFlowCta(
    actionId: string,
    route: string,
    metadata: Record<string, unknown> = {},
  ) {
    const flow = await resolveActiveFlowForAction(actionId);
    await recordFlowCtaEvidence(flow, actionId, route, metadata);
  }

  function hasFlowRecommendationForAction(actionId: string) {
    const actions = [
      assistant.data?.globalNextAction,
      ...(assistant.data?.pageActions ?? []),
      ...(assistant.data?.rowActions ?? []),
    ].filter(Boolean);
    return actions.some((action) => (
      action?.actionId === actionId
      && action.source === "flow.current_step"
    ));
  }

  async function resolveActiveFlowForAction(actionId: string) {
    const currentFlow = assistant.data?.flow ?? assistantFlowRef.current;
    const currentFlowHasTrialMetadata = Boolean(
      currentFlow?.trialPack
      || currentFlow?.evidenceRunId,
    );
    if (
      currentFlow?.expectedActionId === actionId
      && (actionId !== "IMPORT_OGV_DEMAND" || currentFlowHasTrialMetadata)
    ) {
      assistantFlowRef.current = currentFlow;
      return currentFlow;
    }
    if (!currentFlow && !hasFlowRecommendationForAction(actionId)) {
      return null;
    }
    const refreshedFlow = await fetchActiveFlowForAction(actionId);
    if (refreshedFlow) {
      assistantFlowRef.current = refreshedFlow;
    }
    return refreshedFlow;
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
    masterDataOverviewRef.current = null;
    schedulingOverviewRef.current = null;
    workspaceRefreshPromiseRef.current = null;
    workspaceLastRefreshAtRef.current = 0;
    setLatestAssetStates([]);
    setGeofenceZones([]);
    setMovementEvents([]);
    setOperationsOverview(null);
    setOperationCandidates([]);
    setConfirmedOperationalEvents([]);
    setOperationDevices([]);
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
      const activePlanVersionId = liveSchedulingOverview()?.activePlanVersion?.id;
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
      await recordActiveFlowCta("GENERATE_EXPORT", "/admin/export-handoff", {
        exportJobId: exportJob.id,
        exportType: command.exportType,
        exportFormat: command.exportFormat,
      });
      return `Export generated: ${exportJob.file_name}`;
    }).finally(() => setIsExportGenerating(false));
  }

  async function handleImportDemand() {
    await runWorkspaceAction("Import demand", async () => {
      const csrfToken = await getCsrfToken();
      const activeFlow = await resolveActiveFlowForAction("IMPORT_OGV_DEMAND");
      const usesHappyPathTrialPack = shouldUseHappyPathTrialImport(activeFlow);
      const job = usesHappyPathTrialPack
        ? await apiFetch<ImportJobRecord>("/planning/import-jobs/import-trial-demand/", {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            pack: "operator_happy_path_v1",
            filename: "operator_happy_path_ogv_demand.xlsx",
            source: "operator-trial-flow-ui",
          }),
        })
        : await importSingleUiDemand(csrfToken);
      await recordActiveFlowCta("IMPORT_OGV_DEMAND", "/schedule/ogv-demand", {
        importJobId: job.id,
        filename: job.filename,
      });
      return `Import committed: ${job.filename} (${job.valid_rows}/${job.total_rows} rows)`;
    });
  }

  async function importSingleUiDemand(csrfToken: string) {
    const stamp = Date.now();
    const dates = operatorPlanningDates();
    return apiFetch<ImportJobRecord>("/planning/import-jobs/validate-ogv-demand/", {
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
      await recordActiveFlowCta("ENTER_OPERATING_WINDOWS", "/constraints/tide-bridge", {
        constraintChecks: result.constraintChecks,
        tideWindows: result.tideWindows ?? [result.tideWindow],
        bridgeWindows: result.bridgeWindows ?? [result.bridgeWindow],
      });
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
      const records = liveMasterDataOverview()?.catalogs[catalogKey] ?? [];
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
      const activeVersion = liveSchedulingOverview()?.activePlanVersion;
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
      const activeVersion = liveSchedulingOverview()?.activePlanVersion
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
      await recordActiveFlowCta("GENERATE_PLAN", "/operations/tug-barge-assignment", {
        planVersionId: version.id,
        planCode: version.plan_code,
        versionNo: version.version_no,
      });
      return `Schedule generated: ${version.plan_code} V${version.version_no}`;
    });
  }

  async function handleForceStartJetty(assignmentId: number, actualStartAt: string) {
    await runWorkspaceAction("Force start jetty", async () => {
      const liveOverview = liveSchedulingOverview();
      const assignment = liveOverview?.assignments.find((item) => item.id === assignmentId)
        ?? liveOverview?.assignments.find((item) => item.jetty)
        ?? liveOverview?.assignments[0];
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

  async function handleConfirmOperationalEvent(
    candidateId: number,
    actualAt: string,
    reasonCode: string,
  ) {
    await runWorkspaceAction("Confirm operational event", async () => {
      const csrfToken = await getCsrfToken();
      const event = await apiFetch<ConfirmedOperationalEventRecord>(
        `/operations/event-candidates/${candidateId}/confirm/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            actual_at: actualAt,
            reason_code: reasonCode,
          }),
        },
      );
      return `Operational event confirmed: ${event.event_id}`;
    });
  }

  async function handleRejectOperationalEvent(
    candidateId: number,
    reasonCode: string,
    notes: string,
  ) {
    await runWorkspaceAction("Reject operational event", async () => {
      const csrfToken = await getCsrfToken();
      const candidate = await apiFetch<OperationalEventCandidateRecord>(
        `/operations/event-candidates/${candidateId}/reject/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            reason_code: reasonCode,
            notes,
          }),
        },
      );
      return `Operational event rejected: ${candidate.candidate_id}`;
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

      const activeVersion = liveSchedulingOverview()?.activePlanVersion;
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

  async function handleGenerateRecoveryOptions(source: RecommendationSourceInput) {
    await runWorkspaceAction("Generate recovery options", async () => {
      const activeVersion = liveSchedulingOverview()?.activePlanVersion;
      if (!activeVersion) {
        throw new Error("No active plan version");
      }
      const csrfToken = await getCsrfToken();
      const snapshot = await apiFetch<RecoveryInputSnapshotRecord>(
        "/scheduling/recovery-input-snapshots/build/",
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            plan_version: activeVersion.id,
            source_kind: source.kind,
            ...(source.kind === "conflict" ? { source_conflict: source.id } : {}),
            ...(source.kind === "override" ? { source_override: source.id } : {}),
            ...(source.kind === "tracking_alert" ? { source_tracking_alert: source.id } : {}),
            ...(source.kind === "operational_event" ? { source_operational_event: source.id } : {}),
          }),
        },
      );
      const run = await apiFetch<OptimizerRunRecord>("/scheduling/recovery-runs/", {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          input_snapshot: snapshot.id,
        }),
      });
      await recordActiveFlowCta("GENERATE_RECOVERY_OPTIONS", "/exceptions/center", {
        snapshotId: snapshot.id,
        sourceRef: snapshot.source_ref,
        optimizerRunId: run.id,
        recommendationCount: run.recommendations.length,
      });
      handleNavigate("/recovery/recommendations");
      return `Recovery options generated: ${run.recommendations.length} candidates from ${snapshot.source_ref}`;
    });
  }

  async function handleMaterializeRecommendation(recommendationId: number) {
    await runWorkspaceAction("Create recovery scenario", async () => {
      const csrfToken = await getCsrfToken();
      const recommendation = await apiFetch<RecoveryRecommendationRecord>(
        `/scheduling/recovery-recommendations/${recommendationId}/materialize-scenario/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({
            run_simulation: true,
          }),
        },
      );
      await recordActiveFlowCta("MATERIALIZE_RECOVERY_RECOMMENDATION", "/recovery/recommendations", {
        recommendationId,
        scenarioRef: recommendation.scenario_ref,
      });
      handleNavigate("/simulation/workspace");
      return `Recovery scenario created: ${recommendation.scenario_ref ?? recommendation.recommendation_id}`;
    });
  }

  async function handleValidateRootCause(recommendationId: number) {
    await runWorkspaceAction("Validate root-cause repair", async () => {
      const csrfToken = await getCsrfToken();
      const assessment = await apiFetch<RootCauseRepairAssessmentRecord>(
        `/scheduling/recovery-recommendations/${recommendationId}/root-cause-assessment/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
        },
      );
      await recordActiveFlowCta("VALIDATE_ROOT_CAUSE_REPAIR", "/recovery/recommendations", {
        recommendationId,
        assessmentId: assessment.id,
        assessmentRef: assessment.assessment_id,
        status: assessment.status,
        sourceCauseType: assessment.source_cause_type,
      });
      return `Root-cause validation recorded: ${assessment.status.replaceAll("_", " ")}`;
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
    const liveOverview = liveSchedulingOverview();
    return liveOverview?.simulationScenarios.find((scenario) => scenario.id === scenarioId)
      ?? liveOverview?.simulationScenarios[0]
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
      await recordActiveFlowCta("RUN_SIMULATION", "/simulation/workspace", {
        scenarioId: simulated.id,
        scenarioRef: simulated.scenario_id,
      });
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
      await recordActiveFlowCta("PROMOTE_SCENARIO", "/simulation/workspace", {
        scenarioId: promoted.id,
        scenarioRef: promoted.scenario_id,
        scenarioVersionRef: promoted.scenario_version_ref,
      });
      return `Scenario promoted: ${promoted.scenario_version_ref ?? promoted.scenario_id}`;
    });
  }

  async function handleSubmitApproval() {
    await runWorkspaceAction("Submit approval", async () => {
      const activeVersion = liveSchedulingOverview()?.activePlanVersion;
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
      await recordActiveFlowCta("SUBMIT_APPROVAL", "/schedule/published-plan", {
        approvalRequestId: approval.id,
        requestId: approval.request_id,
        planVersionId: activeVersion.id,
      });
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
      const liveOverview = liveSchedulingOverview();
      const request = liveOverview?.approvalRequests.find((item) => item.status === "pending")
        ?? liveOverview?.approvalRequests[0];
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
      await recordActiveFlowCta("APPROVE_PLAN", "/approvals/publishing", {
        approvalRequestId: request.id,
        requestId: request.request_id,
        authorityRole,
      });
      return `Approved ${request.request_id} as ${authorityRole.replaceAll("_", " ")}`;
    });
  }

  async function handleRejectPlan() {
    await runWorkspaceAction("Reject plan", async () => {
      const liveOverview = liveSchedulingOverview();
      const request = liveOverview?.approvalRequests.find((item) => item.status === "pending")
        ?? liveOverview?.approvalRequests[0];
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

  async function handleCheckPublishability() {
    await runWorkspaceAction("Check publishability", async () => {
      const activeVersion = liveSchedulingOverview()?.activePlanVersion;
      if (!activeVersion) {
        throw new Error("No active plan version");
      }
      const csrfToken = await getCsrfToken();
      const assessment = await apiFetch<PublishabilityAssessmentRecord>(
        `/scheduling/plan-versions/${activeVersion.id}/publishability-assessment/`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
        },
      );
      await recordActiveFlowCta("RUN_PUBLISHABILITY_CHECK", "/approvals/publishing", {
        planVersionId: activeVersion.id,
        assessmentId: assessment.id,
        assessmentRef: assessment.assessment_id,
        status: assessment.status,
        blockingReasonCount: assessment.blocking_reason_count,
        warningCount: assessment.warning_count,
      });
      return `Publishability checked: ${assessment.status.replaceAll("_", " ")}`;
    });
  }

  async function handlePublishPlan() {
    await runWorkspaceAction("Publish plan", async () => {
      const activeVersion = liveSchedulingOverview()?.activePlanVersion;
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
      await recordActiveFlowCta("PUBLISH_PLAN", "/approvals/publishing", {
        planVersionId: activeVersion.id,
        planCode: activeVersion.plan_code,
        versionNo: activeVersion.version_no,
      });
      return `Published ${activeVersion.plan_code} V${activeVersion.version_no}`;
    });
  }

  function handleNavigate(path: string) {
    void requestWorkspaceRefresh({ force: true }).finally(() => {
      window.location.hash = path;
      setActivePath(path);
    });
  }

  if (isBooting) {
    return <main className="boot-screen">Loading workspace...</main>;
  }

  if (!currentUser) {
    return <LoginPage onSubmit={handleLogin} />;
  }

  const activePlanStatus = schedulingOverview?.activePlanVersion?.status;
  const activePlanIsEditable = Boolean(
    activePlanStatus && !["published", "superseded"].includes(activePlanStatus),
  );
  const isWorkspaceActionRunning = Boolean(actionInFlight);
  const assistantPageProps = {
    assistantBlockedActions: assistant.data?.blockedActions ?? [],
    assistantChecklist: assistant.data?.checklist ?? [],
    assistantFlow: assistant.data?.flow ?? null,
    assistantMode: assistant.mode,
    assistantPageActions: assistant.data?.pageActions ?? [],
    assistantRowActions: assistant.data?.rowActions ?? [],
    onAssistantNavigate: handleNavigate,
  };

  return (
    <main className={sidebarCollapsed ? "operations-shell sidebar-is-collapsed" : "operations-shell"}>
      <Topbar
        assistantAction={assistant.data?.globalNextAction ?? null}
        assistantFlow={assistant.data?.flow ?? null}
        assistantMode={assistant.mode}
        currentUser={currentUser}
        onAssistantModeChange={assistant.setMode}
        onAssistantNavigate={handleNavigate}
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
        {actionMessage ? (
          <div aria-live="polite" className="workspace-action-banner" role="status">
            {actionMessage}
          </div>
        ) : null}
        {actionError ? (
          <div aria-live="assertive" className="workspace-action-banner critical" role="alert">
            {actionError}
          </div>
        ) : null}
        {route === "/admin/master-data" && masterDataOverview ? (
          <MasterDataPage
            {...assistantPageProps}
            canManage={canManageMasterData}
            isActionRunning={isWorkspaceActionRunning}
            onExportCatalog={handleMasterDataExport}
            onImportCatalog={handleMasterDataImport}
            onValidateCatalog={handleMasterDataValidate}
            overview={masterDataOverview}
          />
        ) : null}
        {route === "/admin/users-rbac" && overview ? (
          <RbacPage {...assistantPageProps} overview={overview} />
        ) : null}
        {route === "/admin/audit-logs" && canViewAudit ? (
          <AuditPage {...assistantPageProps} events={auditEvents} />
        ) : null}
        {route === "/admin/export-handoff" && canViewExports ? (
          <ExportHandoffPage
            {...assistantPageProps}
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
            {...assistantPageProps}
            canEdit={canEditSchedule}
            canExport={canGenerateExports}
            isActionRunning={isWorkspaceActionRunning}
            onExportBoard={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            onImportDemand={handleImportDemand}
            overview={planningOverview}
            schedulingOverview={schedulingOverview}
          />
        ) : null}
        {route === "/schedule/coal-grade-sequence" && canViewSchedule ? (
          <CoalGradeSequencePage
            {...assistantPageProps}
            canEdit={canEditSchedule}
            canExport={canGenerateExports}
            isActionRunning={isWorkspaceActionRunning}
            onExport={() => handleGenerateExport({ exportType: "conflict", exportFormat: "json" })}
            overview={planningOverview}
            schedulingOverview={schedulingOverview}
          />
        ) : null}
        {route === "/constraints/tide-bridge" && canViewSchedule ? (
          <TideBridgePage
            {...assistantPageProps}
            canEdit={canEditSchedule}
            confirmedOperationalEvents={confirmedOperationalEvents}
            isActionRunning={isWorkspaceActionRunning}
            onEnterOperatingWindows={handleEnterOperatingWindows}
            operationCandidates={operationCandidates}
            operationDevices={operationDevices}
            overview={planningOverview}
          />
        ) : null}
        {route === "/operations/tug-barge-assignment" && canViewSchedule ? (
          <TugBargeAssignmentPage
            {...assistantPageProps}
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
            {...assistantPageProps}
            canEdit={canEditSchedule && activePlanIsEditable}
            canExport={canGenerateExports}
            canConfirmJetty={canConfirmJetty}
            confirmedOperationalEvents={confirmedOperationalEvents}
            isActionRunning={isWorkspaceActionRunning}
            onConfirmOperationalEvent={handleConfirmOperationalEvent}
            onExport={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            onForceStartJetty={handleForceStartJetty}
            onRejectOperationalEvent={handleRejectOperationalEvent}
            operationCandidates={operationCandidates}
            operationDevices={operationDevices}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/operations/cts-floating-crane" && canViewSchedule ? (
          <CtsOperationsPage
            {...assistantPageProps}
            canExport={canGenerateExports}
            canConfirmCts={canConfirmCts}
            confirmedOperationalEvents={confirmedOperationalEvents}
            isActionRunning={isWorkspaceActionRunning}
            onConfirmOperationalEvent={handleConfirmOperationalEvent}
            onExport={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            onRejectOperationalEvent={handleRejectOperationalEvent}
            operationCandidates={operationCandidates}
            operationDevices={operationDevices}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/schedule/published-plan" && canViewSchedule ? (
          <PublishedPlanPage
            {...assistantPageProps}
            canCreateDraft={canEditSchedule}
            isActionRunning={isWorkspaceActionRunning}
            onCreateDraft={handleCreateDraft}
            onSubmitApproval={activePlanIsEditable ? handleSubmitApproval : undefined}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/exceptions/center" && canViewSchedule ? (
          <ExceptionCenterPage
            {...assistantPageProps}
            canEdit={canEditSchedule && activePlanIsEditable}
            confirmedOperationalEvents={confirmedOperationalEvents}
            isActionRunning={isWorkspaceActionRunning}
            operationCandidates={operationCandidates}
            onCreateScenario={handleCreateScenario}
            onGenerateRecoveryOptions={handleGenerateRecoveryOptions}
            onPublishTriage={canGenerateExports
              ? () => handleGenerateExport({ exportType: "conflict", exportFormat: "json" })
              : undefined}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/recovery/recommendations" && canViewSchedule ? (
          <RecommendationConsolePage
            {...assistantPageProps}
            canEdit={canEditSchedule && activePlanIsEditable}
            isActionRunning={isWorkspaceActionRunning}
            onMaterializeRecommendation={handleMaterializeRecommendation}
            onNavigate={handleNavigate}
            onValidateRootCause={handleValidateRootCause}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/simulation/workspace" && canEditSchedule ? (
          <SimulationWorkspacePage
            {...assistantPageProps}
            canEdit={canEditSchedule && activePlanIsEditable}
            isActionRunning={isWorkspaceActionRunning}
            onCreateAssumption={handleCreateAssumption}
            onCreateScenario={handleCreateScenario}
            onPromoteScenario={handlePromoteScenario}
            onRunSimulation={handleRunSimulation}
            onSubmitApproval={activePlanIsEditable ? handleSubmitApproval : undefined}
            onNavigate={handleNavigate}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/approvals/publishing" && canApproveSchedule ? (
          <ApprovalsPublishingPage
            {...assistantPageProps}
            canEdit={canApproveSchedule}
            canPublish={canPublishSchedule}
            isActionRunning={isWorkspaceActionRunning}
            onApprove={handleApprovePlan}
            onCheckPublishability={handleCheckPublishability}
            onPublish={handlePublishPlan}
            onReject={handleRejectPlan}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/optimization/global" && canViewSchedule ? (
          <GlobalOptimizationReviewPage
            {...assistantPageProps}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/map/live" && canViewFleet ? (
          <LiveResourceMapPage
            {...assistantPageProps}
            canRunReplay={canRunTelemetryReplay}
            canRunSimulation={canRunSimulation}
            etaProjections={etaProjections}
            geofenceZones={geofenceZones}
            isActionRunning={isWorkspaceActionRunning}
            latestAssetStates={latestAssetStates}
            movementEvents={movementEvents}
            operationCandidates={operationCandidates}
            operationDevices={operationDevices}
            confirmedOperationalEvents={confirmedOperationalEvents}
            onNavigate={handleNavigate}
            onStartReplay={handleStartTelemetryReplay}
            overview={schedulingOverview}
            replayRuns={telemetryReplayRuns}
            trackingAlerts={trackingAlerts}
          />
        ) : null}
        {route === "/operations/event-confirmation" && canViewOperations ? (
          <OperationsEventConsolePage
            {...assistantPageProps}
            candidates={operationCandidates}
            confirmedEvents={confirmedOperationalEvents}
            devices={operationDevices}
            isActionRunning={isWorkspaceActionRunning}
            onConfirm={handleConfirmOperationalEvent}
            onReject={handleRejectOperationalEvent}
            overview={operationsOverview}
            permissions={currentUser.permissions}
          />
        ) : null}
        {route === "/dashboard/situation" ? (
          <DashboardPage
            assistantBlockedActions={assistant.data?.blockedActions ?? []}
            assistantChecklist={assistant.data?.checklist ?? []}
            assistantFlow={assistant.data?.flow ?? null}
            assistantGlobalAction={assistant.data?.globalNextAction ?? null}
            assistantMode={assistant.mode}
            assistantPageActions={assistant.data?.pageActions ?? []}
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
