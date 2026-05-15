import { useEffect, useMemo, useState } from "react";

import { AuditStrip } from "./components/AuditStrip";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { apiFetch, login, logout } from "./lib/api";
import { canAccess, visibleNavItems, visibleNavModules } from "./lib/navigation";
import { AuditPage } from "./pages/AuditPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { MasterDataPage } from "./pages/MasterDataPage";
import { RbacPage } from "./pages/RbacPage";
import type { AuditEvent, CurrentUser, MasterDataOverview, RbacOverview } from "./types";

function currentHashPath() {
  return window.location.hash.replace("#", "") || "/dashboard/situation";
}

function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [activePath, setActivePath] = useState(currentHashPath());
  const [overview, setOverview] = useState<RbacOverview | null>(null);
  const [masterDataOverview, setMasterDataOverview] = useState<MasterDataOverview | null>(null);
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
  const canViewAdmin = currentUser ? canAccess(currentUser.permissions, "admin.view") : false;
  const canViewMasterData = currentUser
    ? canAccess(currentUser.permissions, "masterdata.view")
    : false;
  const canManageMasterData = currentUser
    ? canAccess(currentUser.permissions, "masterdata.manage")
    : false;

  useEffect(() => {
    if (!currentUser) {
      return;
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
  }, [canViewAdmin, canViewAudit, canViewMasterData, currentUser]);

  async function handleLogin(username: string, password: string) {
    const user = await login(username, password);
    setCurrentUser(user);
  }

  async function handleLogout() {
    await logout();
    setCurrentUser(null);
    setOverview(null);
    setMasterDataOverview(null);
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
        {route === "/dashboard/situation" ? (
          <DashboardPage
            auditEvents={auditEvents}
            currentUser={currentUser}
            overview={overview}
          />
        ) : null}
      </section>
      <AuditStrip canViewAudit={canViewAudit} events={auditEvents} />
    </main>
  );
}

export default App;
