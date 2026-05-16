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
  ImportJobRecord,
  MasterDataCatalogs,
  MasterDataRecord,
  MasterDataOverview,
  PlanVersionRecord,
  PlanningOverview,
  RbacOverview,
  SchedulingOverview,
} from "./types";

function currentHashPath() {
  return window.location.hash.replace("#", "") || "/dashboard/situation";
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

    await Promise.all(refreshes);
  }, [
    canViewAdmin,
    canViewAudit,
    canViewDashboard,
    canViewExports,
    canViewMasterData,
    canViewSchedule,
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
    setDashboardReadModel(null);
    setExportOverview(null);
    setAuditEvents([]);
    setExportError(null);
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
      const job = await apiFetch<ImportJobRecord>("/planning/import-jobs/validate-ogv-demand/", {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          filename: `operator-ui-demand-${stamp}.xlsx`,
          source: "operator-ui-action",
          rows: [
            {
              voyage_id: `VOY-UI-${String(stamp).slice(-6)}`,
              vessel_name: "MV Operator UI Import",
              customer_name: "Pilot Customer",
              laycan_start: "2026-11-05T00:00:00Z",
              laycan_end: "2026-11-08T00:00:00Z",
              eta: "2026-11-05T06:00:00Z",
              required_mt: 64000,
            },
          ],
        }),
      });
      return `Import validated: ${job.filename} (${job.valid_rows}/${job.total_rows} rows)`;
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

  async function handleCreateDraft() {
    await runWorkspaceAction("Create draft", async () => {
      const activeVersion = schedulingOverview?.activePlanVersion;
      if (!activeVersion) {
        throw new Error("No active plan version");
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
      const activeVersion = schedulingOverview?.activePlanVersion;
      if (!activeVersion || ["published", "superseded"].includes(activeVersion.status)) {
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

  return (
    <main className={sidebarCollapsed ? "operations-shell sidebar-is-collapsed" : "operations-shell"}>
      <Topbar currentUser={currentUser} onLogout={handleLogout} />
      <Sidebar
        activePath={route}
        collapsed={sidebarCollapsed}
        modules={navModules}
        onNavigate={handleNavigate}
        onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
      />
      <section className="operations-main">
        {actionMessage ? <div className="workspace-action-banner">{actionMessage}</div> : null}
        {actionError ? <div className="workspace-action-banner critical">{actionError}</div> : null}
        {route === "/admin/master-data" && masterDataOverview ? (
          <MasterDataPage
            canManage={canManageMasterData}
            isActionRunning={actionInFlight === "Master data import" || actionInFlight === "Master data export"}
            onExportCatalog={handleMasterDataExport}
            onImportCatalog={handleMasterDataImport}
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
            isActionRunning={actionInFlight === "Import demand" || actionInFlight === "Export"}
            onExportBoard={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            onImportDemand={handleImportDemand}
            overview={planningOverview}
          />
        ) : null}
        {route === "/schedule/coal-grade-sequence" && canViewSchedule ? (
          <CoalGradeSequencePage
            canEdit={canEditSchedule}
            canExport={canGenerateExports}
            isActionRunning={actionInFlight === "Export"}
            onExport={() => handleGenerateExport({ exportType: "conflict", exportFormat: "json" })}
            overview={planningOverview}
          />
        ) : null}
        {route === "/constraints/tide-bridge" && canViewSchedule ? (
          <TideBridgePage overview={planningOverview} />
        ) : null}
        {route === "/operations/tug-barge-assignment" && canViewSchedule ? (
          <TugBargeAssignmentPage
            canEdit={canEditSchedule}
            canExport={canGenerateExports}
            isActionRunning={actionInFlight === "Generate schedule" || actionInFlight === "Export"}
            onExport={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            onRegenerate={handleRegeneratePlan}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/operations/jetty-loading" && canViewSchedule ? (
          <JettyLoadingPage
            canEdit={canEditSchedule}
            canExport={canGenerateExports}
            isActionRunning={actionInFlight === "Export"}
            onExport={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/operations/cts-floating-crane" && canViewSchedule ? (
          <CtsOperationsPage
            canExport={canGenerateExports}
            isActionRunning={actionInFlight === "Export"}
            onExport={() => handleGenerateExport({ exportType: "plan", exportFormat: "csv" })}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/schedule/published-plan" && canViewSchedule ? (
          <PublishedPlanPage
            canCreateDraft={canEditSchedule}
            isActionRunning={actionInFlight === "Create draft"}
            onCreateDraft={handleCreateDraft}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/exceptions/center" && canViewSchedule ? (
          <ExceptionCenterPage canEdit={canEditSchedule} overview={schedulingOverview} />
        ) : null}
        {route === "/simulation/workspace" && canEditSchedule ? (
          <SimulationWorkspacePage canEdit={canEditSchedule} overview={schedulingOverview} />
        ) : null}
        {route === "/approvals/publishing" && canApproveSchedule ? (
          <ApprovalsPublishingPage
            canEdit={canApproveSchedule}
            canPublish={canPublishSchedule}
            isActionRunning={actionInFlight === "Approve plan" || actionInFlight === "Publish plan"}
            onApprove={handleApprovePlan}
            onPublish={handlePublishPlan}
            onReject={handleRejectPlan}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/map/live" && canViewFleet ? (
          <LiveResourceMapPage
            dashboard={dashboardReadModel}
            onNavigate={handleNavigate}
            overview={schedulingOverview}
          />
        ) : null}
        {route === "/dashboard/situation" ? (
          <DashboardPage
            auditEvents={auditEvents}
            currentUser={currentUser}
            dashboard={dashboardReadModel}
            onNavigate={handleNavigate}
          />
        ) : null}
      </section>
      <AuditStrip canViewAudit={canViewAudit} events={auditEvents} />
    </main>
  );
}

export default App;
