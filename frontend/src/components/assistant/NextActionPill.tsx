import type { ActionRecommendation } from "../../types/assistant";
import { AbbrText } from "../Abbreviation";

type NextActionPillProps = {
  action: ActionRecommendation | null;
  onNavigate: (path: string) => void;
};

export function NextActionPill({ action, onNavigate }: NextActionPillProps) {
  if (!action) return null;

  return (
    <button
      className={`next-action-pill ${action.priority}`}
      disabled={!action.enabled}
      onClick={() => {
        if (action.enabled) onNavigate(action.route);
      }}
      title={action.enabled ? action.reason : action.blockedReason || action.reason}
      type="button"
    >
      <span>Next Action</span>
      <strong><AbbrText text={action.label} /></strong>
    </button>
  );
}
