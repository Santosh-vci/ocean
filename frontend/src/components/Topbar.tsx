import type { CurrentUser } from "../types";

type TopbarProps = {
  currentUser: CurrentUser;
  onLogout: () => void;
};

export function Topbar({ currentUser, onLogout }: TopbarProps) {
  const defaultMembership = currentUser.memberships.find((membership) => membership.is_default);
  const currentRole = currentUser.assignments[0]?.role.name ?? "No role assigned";

  return (
    <header className="topbar">
      <div>
        <span>Current scope</span>
        <strong>{defaultMembership?.organization.name ?? "Unscoped"}</strong>
      </div>
      <div>
        <span>Authority</span>
        <strong>{currentRole}</strong>
      </div>
      <div>
        <span>Session</span>
        <strong>{currentUser.email}</strong>
      </div>
      <button onClick={onLogout} type="button">
        Sign out
      </button>
    </header>
  );
}

