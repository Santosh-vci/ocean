import { useEffect, useMemo, useState } from "react";

import { AuditStrip } from "./components/AuditStrip";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { apiFetch, login, logout } from "./lib/api";
import { canAccess, visibleNavItems, visibleNavModules } from "./lib/navigation";
import { AuditPage } from "./pages/AuditPage";
import { CoalGradeSequencePage } from "./pages/CoalGradeSequencePage";
import { DashboardPage } from "./pages/DashboardPage";
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
  MasterDataOverview,
  PlanningOverview,
  RbacOverview,
  SchedulingOverview,
} from "./types";

function currentHashPath() {
  return window.location.hash.replace("#", "") || "/dashboard/situation";
}

function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [activePath, setActivePath] = useState(currentHashPath());
  const [overview, setOverview] = useState<RbacOverview | null>(null);
  const [masterDataOverview, setMasterDataOverview] = useState<MasterDataOverview | null>(null);
  const [planningOverview, setPlanningOverview] = useState<PlanningOverview | null>(null);
  const [schedulingOverview, setSchedulingOverview] = useState<SchedulingOverview | null>(null);
  const [dashboardReadModel, setDashboardReadModel] = useState<DashboardReadModel | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
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

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    if (canViewDashboard) {
      apiFetch<DashboardReadModel>("/dashboard/situation/")
        .then(setDashboardReadModel)
        .catch(() => setDashboardReadModel(null));
    }

    if (canViewAdmin) {
      apiFetch<RbacOverview>("/rbac/overview/").then(setOverview).catch(() => setOverview(null));
    }

    if (canViewMasterData) {
      apiFetch<MasterDataOverview>("/master-data/overview/")
        .then(setMasterDataOverview)
        .catch(() => setMasterDataOverview(null));
    }

    if (canViewAudit) {
      apiFetch<AuditEvent[]>("/audit-events/").then(setAuditEvents).catch(() => setAuditEvents([]));
    }

    if (canViewSchedule) {
      apiFetch<PlanningOverview>("/planning/overview/")
        .then(setPlanningOverview)
        .catch(() => setPlanningOverview(null));
    }

    if (canViewSchedule) {
      apiFetch<SchedulingOverview>("/scheduling/overview/")
        .then(setSchedulingOverview)
        .catch(() => setSchedulingOverview(null));
    }
  }, [
    canViewAdmin,
    canViewAudit,
    canViewDashboard,
    canViewMasterData,
    canViewSchedule,
    currentUser,
  ]);

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
    setAuditEvents([]);
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
        {route === "/admin/master-data" && masterDataOverview ? (
          <MasterDataPage canManage={canManageMasterData} overview={masterDataOverview} />
        ) : null}
        {route === "/admin/users-rbac" && overview ? <RbacPage overview={overview} /> : null}
        {route === "/admin/audit-logs" && canViewAudit ? <AuditPage events={auditEvents} /> : null}
        {route === "/schedule/ogv-demand" && canViewSchedule ? (
          <OgvDemandPage canEdit={canEditSchedule} overview={planningOverview} />
        ) : null}
        {route === "/schedule/coal-grade-sequence" && canViewSchedule ? (
          <CoalGradeSequencePage canEdit={canEditSchedule} overview={planningOverview} />
        ) : null}
        {route === "/constraints/tide-bridge" && canViewSchedule ? (
          <TideBridgePage overview={planningOverview} />
        ) : null}
        {route === "/operations/tug-barge-assignment" && canViewSchedule ? (
          <TugBargeAssignmentPage canEdit={canEditSchedule} overview={schedulingOverview} />
        ) : null}
        {route === "/operations/jetty-loading" && canViewSchedule ? (
          <JettyLoadingPage canEdit={canEditSchedule} overview={schedulingOverview} />
        ) : null}
        {route === "/operations/cts-floating-crane" && canViewSchedule ? (
          <CtsOperationsPage overview={schedulingOverview} />
        ) : null}
        {route === "/schedule/published-plan" && canViewSchedule ? (
          <PublishedPlanPage overview={schedulingOverview} />
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
