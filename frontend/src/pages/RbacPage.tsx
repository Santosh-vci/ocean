import { useState } from "react";

import {
  RecommendationCard,
  type AssistantRecommendationSurfaceProps,
} from "../components/assistant";
import { AbbrText } from "../components/Abbreviation";
import type { AccessPermission, RbacOverview, UserSummary } from "../types";

type RbacPageProps = AssistantRecommendationSurfaceProps & {
  overview: RbacOverview;
};

function hasPermission(user: UserSummary, permissionCode: string) {
  return user.assignments.some((assignment) =>
    assignment.role.permissions.some((permission) => permission.code === permissionCode),
  );
}

function selectedPermissions(user: UserSummary): AccessPermission[] {
  const seen = new Map<number, AccessPermission>();
  user.assignments.forEach((assignment) => {
    assignment.role.permissions.forEach((permission) => {
      seen.set(permission.id, permission);
    });
  });
  return [...seen.values()];
}

export function RbacPage({
  assistantBlockedActions,
  assistantChecklist,
  assistantPageActions,
  assistantRowActions,
  onAssistantNavigate,
  overview,
}: RbacPageProps) {
  const [selectedUserId, setSelectedUserId] = useState<number>(overview.users[0]?.id ?? 0);
  const selectedUser =
    overview.users.find((user) => user.id === selectedUserId) ?? overview.users[0];
  const accessRiskCount = overview.users.filter((user) =>
    hasPermission(user, "admin.manage_users"),
  ).length;
  const approvalAuthorityCount = overview.users.filter((user) =>
    hasPermission(user, "schedule.approve"),
  ).length;
  const permissions = selectedUser ? selectedPermissions(selectedUser) : [];
  const permissionModules = [...new Set(overview.permissions.map((permission) => permission.module))];

  return (
    <section className="workspace-page governance-cockpit">
      <header className="page-heading">
        <div>
          <p>Admin</p>
          <h1>Users & <AbbrText text="RBAC" /></h1>
        </div>
        <span className="phase-chip">Hardened governance cockpit</span>
      </header>
      <RecommendationCard
        assistantBlockedActions={assistantBlockedActions}
        assistantChecklist={assistantChecklist}
        assistantPageActions={assistantPageActions}
        assistantRowActions={assistantRowActions}
        onAssistantNavigate={onAssistantNavigate}
      />

      <div className="metric-strip four-up">
        <div>
          <span>Users</span>
          <strong>{overview.users.length}</strong>
        </div>
        <div>
          <span>Approval <AbbrText text="auth" /></span>
          <strong>{approvalAuthorityCount}</strong>
        </div>
        <div>
          <span>Module access</span>
          <strong>{permissionModules.length}</strong>
        </div>
        <div>
          <span>Access risk</span>
          <strong>{accessRiskCount}</strong>
        </div>
      </div>

      <div className="governance-layout">
        <section className="plain-section board-surface">
          <h2>User access roster</h2>
          <table>
            <thead>
              <tr>
                <th>User</th>
                <th>Organization</th>
                <th>Role assignment</th>
                <th>Data scope</th>
                <th>Approval</th>
              </tr>
            </thead>
            <tbody>
              {overview.users.map((user) => {
                const assignment = user.assignments[0];
                const isSelected = user.id === selectedUser?.id;
                return (
                  <tr
                    className={isSelected ? "selected-row" : ""}
                    key={user.id}
                    onClick={() => setSelectedUserId(user.id)}
                  >
                    <td>{user.email}</td>
                    <td>{assignment?.organization.name ?? "—"}</td>
                    <td>{assignment?.role.name ?? "—"}</td>
                    <td>{assignment?.data_scope.name ?? "—"}</td>
                    <td>{hasPermission(user, "schedule.approve") ? "Yes" : "No"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        {selectedUser ? (
          <aside className="detail-drawer rbac-drawer">
            <div>
              <span>Selected user</span>
              <strong>{selectedUser.email}</strong>
            </div>

            <section>
              <h2>Role assignment</h2>
              {selectedUser.assignments.map((assignment) => (
                <dl key={`${assignment.role.code}-${assignment.organization.slug}`}>
                  <div>
                    <dt>Role</dt>
                    <dd>{assignment.role.name}</dd>
                  </div>
                  <div>
                    <dt>Organization</dt>
                    <dd>{assignment.organization.name}</dd>
                  </div>
                  <div>
                    <dt>Data scope</dt>
                    <dd>{assignment.data_scope.name}</dd>
                  </div>
                </dl>
              ))}
            </section>

            <section>
              <h2>Module access matrix</h2>
              <div className="matrix-list">
                {permissionModules.map((module) => {
                  const enabled = permissions.some((permission) => permission.module === module);
                  return (
                    <span className={enabled ? "matrix-cell enabled" : "matrix-cell"} key={module}>
                      {module}
                    </span>
                  );
                })}
              </div>
            </section>

            <section>
              <h2>Validation checklist</h2>
              <ul className="validation-list">
                <li>{selectedUser.memberships.length > 0 ? "✓" : "!"} Organization assigned</li>
                <li>{selectedUser.assignments.length > 0 ? "✓" : "!"} Role assigned</li>
                <li>{permissions.length > 0 ? "✓" : "!"} Permissions resolved</li>
              </ul>
            </section>
          </aside>
        ) : null}
      </div>
    </section>
  );
}
