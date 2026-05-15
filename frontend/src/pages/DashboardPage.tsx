import type { AuditEvent, CurrentUser, RbacOverview } from "../types";

type DashboardPageProps = {
  currentUser: CurrentUser;
  overview: RbacOverview | null;
  auditEvents: AuditEvent[];
};

export function DashboardPage({ currentUser, overview, auditEvents }: DashboardPageProps) {
  const permissionCount = currentUser.permissions.includes("*")
    ? "ALL"
    : currentUser.permissions.length.toString().padStart(2, "0");
  const defaultMembership = currentUser.memberships.find((membership) => membership.is_default);

  return (
    <section className="workspace-page dashboard-cockpit">
      <header className="page-heading">
        <div>
          <p>Control Tower</p>
          <h1>Network Situation</h1>
        </div>
        <span className="phase-chip">Chunk 1 · Governance spine</span>
      </header>

      <div className="metric-strip six-up">
        <div>
          <span>Organizations</span>
          <strong>{overview?.organizations.length ?? "—"}</strong>
        </div>
        <div>
          <span>Active users</span>
          <strong>{overview?.users.length ?? "—"}</strong>
        </div>
        <div>
          <span>Role templates</span>
          <strong>{overview?.roles.length ?? "—"}</strong>
        </div>
        <div>
          <span>Assignments</span>
          <strong>{overview?.assignmentCount ?? "—"}</strong>
        </div>
        <div>
          <span>Audit events</span>
          <strong>{overview?.auditEventCount ?? auditEvents.length}</strong>
        </div>
        <div>
          <span>Authority</span>
          <strong>{permissionCount}</strong>
        </div>
      </div>

      <div className="cockpit-grid">
        <section className="plain-section board-surface">
          <h2>Governance readiness board</h2>
          <table>
            <thead>
              <tr>
                <th>Layer</th>
                <th>Status</th>
                <th>Current evidence</th>
                <th>Next build dependency</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Organizations</td>
                <td>
                  <span className="status-chip ok">Ready</span>
                </td>
                <td>
                  {overview ? `${overview.organizations.length} seeded tenants` : "restricted view"}
                </td>
                <td>Object ownership in Chunk 2</td>
              </tr>
              <tr>
                <td>RBAC</td>
                <td>
                  <span className="status-chip ok">Ready</span>
                </td>
                <td>{overview ? `${overview.roles.length} role templates` : "restricted view"}</td>
                <td>Workflow authority in scheduling</td>
              </tr>
              <tr>
                <td>Audit</td>
                <td>
                  <span className="status-chip ok">Writing</span>
                </td>
                <td>{auditEvents.length} recent events visible</td>
                <td>Domain event correlation</td>
              </tr>
              <tr>
                <td>Scheduling data</td>
                <td>
                  <span className="status-chip pending">Pending</span>
                </td>
                <td>No fake schedule data shown</td>
                <td>Master data catalog in Chunk 2</td>
              </tr>
            </tbody>
          </table>
        </section>

        <aside className="detail-drawer">
          <div>
            <span>Selected authority</span>
            <strong>{defaultMembership?.organization.name ?? "Unscoped"}</strong>
          </div>
          <dl>
            <div>
              <dt>User</dt>
              <dd>{currentUser.email}</dd>
            </div>
            <div>
              <dt>Primary role</dt>
              <dd>{currentUser.assignments[0]?.role.name ?? "No role assigned"}</dd>
            </div>
            <div>
              <dt>Data scope</dt>
              <dd>{currentUser.assignments[0]?.data_scope.name ?? "No scope assigned"}</dd>
            </div>
          </dl>
          <section>
            <h2>Event audit trail</h2>
            <ol className="trace-list">
              {auditEvents.slice(0, 4).map((event) => (
                <li key={event.id}>
                  <span>{new Date(event.created_at).toLocaleTimeString()}</span>
                  <strong>{event.action}</strong>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </section>
  );
}
