import { useEffect, useMemo, useState } from "react";

import { AuditStrip } from "./components/AuditStrip";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { apiFetch, login, logout } from "./lib/api";
import { canAccess, visibleNavItems } from "./lib/navigation";
import { AuditPage } from "./pages/AuditPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { RbacPage } from "./pages/RbacPage";
import type { AuditEvent, CurrentUser, RbacOverview } from "./types";

function currentHashPath() {
  return window.location.hash.replace("#", "") || "/dashboard/situation";
}

function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [activePath, setActivePath] = useState(currentHashPath());
  const [overview, setOverview] = useState<RbacOverview | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [isBooting, setIsBooting] = useState(true);

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
  const canViewAudit = currentUser ? canAccess(currentUser.permissions, "audit.view") : false;
  const canViewAdmin = currentUser ? canAccess(currentUser.permissions, "admin.view") : false;

  useEffect(() => {
    if (!currentUser) {
      return;
    }

    if (canViewAdmin) {
      apiFetch<RbacOverview>("/rbac/overview/").then(setOverview).catch(() => setOverview(null));
    }

    if (canViewAudit) {
      apiFetch<AuditEvent[]>("/audit-events/").then(setAuditEvents).catch(() => setAuditEvents([]));
    }
  }, [canViewAdmin, canViewAudit, currentUser]);

  async function handleLogin(username: string, password: string) {
    const user = await login(username, password);
    setCurrentUser(user);
  }

  async function handleLogout() {
    await logout();
    setCurrentUser(null);
    setOverview(null);
    setAuditEvents([]);
  }

  function handleNavigate(path: string) {
    window.location.hash = path;
    setActivePath(path);
  }

  if (isBooting) {
    return <main className="boot-screen">Loading workspace…</main>;
  }

  if (!currentUser) {
    return <LoginPage onSubmit={handleLogin} />;
  }

  const firstAccessiblePath = navItems[0]?.path ?? "/dashboard/situation";
  const routeIsAllowed = navItems.some((item) => item.path === activePath);
  const route = routeIsAllowed ? activePath : firstAccessiblePath;

  return (
    <main className="operations-shell">
      <Sidebar activePath={route} items={navItems} onNavigate={handleNavigate} />
      <section className="operations-main">
        <Topbar currentUser={currentUser} onLogout={handleLogout} />
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
