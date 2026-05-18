import type { ActionRecommendation } from "../../types/assistant";
import { actionsForObject } from "./actionMatching";

type RowActionHintProps = {
  actions?: ActionRecommendation[];
  objectType: string;
  objectId: number | string | null | undefined;
  onNavigate?: (path: string) => void;
};

export function RowActionHint({
  actions = [],
  objectType,
  objectId,
  onNavigate,
}: RowActionHintProps) {
  const action = actionForObject(actions, objectType, objectId);
  if (!action) return null;

  const reason = action.enabled ? action.reason : action.blockedReason || action.reason;
  const label = action.enabled ? action.ctaLabel : "Blocked";

  if (action.enabled && onNavigate) {
    return (
      <button
        className={`row-action-hint ${action.priority}`}
        onClick={(event) => {
          event.stopPropagation();
          onNavigate(action.route);
        }}
        title={reason}
        type="button"
      >
        <strong>{label}</strong>
        <em>{action.label}</em>
      </button>
    );
  }

  return (
    <span
      className={`row-action-hint ${action.priority}${action.enabled ? "" : " blocked"}`}
      title={reason}
    >
      <strong>{label}</strong>
      <em>{action.enabled ? action.label : reason}</em>
    </span>
  );
}

function actionForObject(
  actions: ActionRecommendation[],
  objectType: string,
  objectId: number | string | null | undefined,
) {
  const matches = actionsForObject(actions, objectType, objectId);
  return matches.find((action) => action.enabled) ?? matches[0] ?? null;
}
