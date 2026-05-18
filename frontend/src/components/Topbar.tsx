import type { CurrentUser } from "../types";
import type { ActionRecommendation, AssistantMode } from "../types/assistant";
import { AssistantModeToggle, NextActionPill } from "./assistant";
import { SvgIcon } from "./SvgIcon";

type TopbarProps = {
  assistantAction: ActionRecommendation | null;
  assistantMode: AssistantMode;
  currentUser: CurrentUser;
  onAssistantModeChange: (mode: AssistantMode) => void;
  onAssistantNavigate: (path: string) => void;
  onOpenApps: () => void;
  onOpenNotifications: () => void;
  onLogout: () => void;
  onSyncWorkspace: () => void;
};

export function Topbar({
  assistantAction,
  assistantMode,
  currentUser,
  onAssistantModeChange,
  onAssistantNavigate,
  onOpenApps,
  onOpenNotifications,
  onLogout,
  onSyncWorkspace,
}: TopbarProps) {
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

      <div className="topbar-assistant">
        <NextActionPill action={assistantAction} onNavigate={onAssistantNavigate} />
        <AssistantModeToggle mode={assistantMode} onChange={onAssistantModeChange} />
      </div>

      <div className="topbar-actions">
        <button aria-label="Sync workspace" onClick={onSyncWorkspace} type="button">
          <SvgIcon name="sync" />
        </button>
        <button aria-label="Notifications" onClick={onOpenNotifications} type="button">
          <SvgIcon name="bell" />
        </button>
        <button aria-label="Apps" onClick={onOpenApps} type="button">
          <SvgIcon name="apps" />
        </button>
        <button className="user-pill" onClick={onLogout} title="Sign out" type="button">
          {initials || "AD"}
        </button>
      </div>
    </header>
  );
}
