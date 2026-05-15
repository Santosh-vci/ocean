import type { CurrentUser } from "../types";
import { SvgIcon } from "./SvgIcon";

type TopbarProps = {
  currentUser: CurrentUser;
  onLogout: () => void;
};

export function Topbar({ currentUser, onLogout }: TopbarProps) {
  const defaultMembership = currentUser.memberships.find((membership) => membership.is_default);
  const currentRole = currentUser.assignments[0]?.role.name ?? "No role assigned";
  const initials = currentUser.email
    .split("@", 1)[0]
    .split(/[._-]/)
    .map((part) => part[0]?.toUpperCase())
    .join("")
    .slice(0, 2);

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <strong>COALFLOW TOWER</strong>
        <span>Berau-ABL scheduling workspace</span>
      </div>

      <label className="global-search">
        <SvgIcon name="search" />
        <input placeholder="Search Master Data, route, asset..." type="search" />
      </label>

      <div className="topbar-scope">
        <span>Current scope</span>
        <strong>{defaultMembership?.organization.name ?? "Unscoped"}</strong>
      </div>
      <div className="topbar-scope">
        <span>Authority</span>
        <strong>{currentRole}</strong>
      </div>

      <div className="topbar-actions">
        <button aria-label="Sync workspace" type="button">
          <SvgIcon name="sync" />
        </button>
        <button aria-label="Notifications" type="button">
          <SvgIcon name="bell" />
        </button>
        <button aria-label="Apps" type="button">
          <SvgIcon name="apps" />
        </button>
        <button className="user-pill" onClick={onLogout} title="Sign out" type="button">
          {initials || "AD"}
        </button>
      </div>
    </header>
  );
}
