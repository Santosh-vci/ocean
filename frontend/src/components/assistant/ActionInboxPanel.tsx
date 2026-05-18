import type { ActionRecommendation } from "../../types/assistant";

type ActionInboxPanelProps = {
  globalAction: ActionRecommendation | null;
  pageActions?: ActionRecommendation[];
  blockedActions?: ActionRecommendation[];
  onNavigate: (path: string) => void;
};

export function ActionInboxPanel({
  blockedActions = [],
  globalAction,
  onNavigate,
  pageActions = [],
}: ActionInboxPanelProps) {
  const actions = uniqueActions([
    ...(globalAction ? [globalAction] : []),
    ...pageActions,
  ]).slice(0, 6);
  const blocked = uniqueActions(blockedActions).slice(0, 3);

  if (!actions.length && !blocked.length) return null;

  return (
    <section className="assistant-action-inbox">
      <div className="grid-header">
        <div>
          <strong>Assistant action inbox</strong>
        </div>
        <span>{actions.length} active</span>
      </div>
      <div className="assistant-inbox-list">
        {actions.map((action) => (
          <button
            className={action.priority}
            disabled={!action.enabled}
            key={actionKey(action)}
            onClick={() => {
              if (action.enabled) onNavigate(action.route);
            }}
            title={action.enabled ? action.reason : action.blockedReason || action.reason}
            type="button"
          >
            <span>{action.priority}</span>
            <strong>{action.label}</strong>
            <em>{action.source}</em>
          </button>
        ))}
        {blocked.map((action) => (
          <span className="assistant-inbox-blocked" key={actionKey(action)}>
            <strong>{action.label}</strong>
            <em>{action.blockedReason || action.reason}</em>
          </span>
        ))}
      </div>
    </section>
  );
}

function uniqueActions(actions: ActionRecommendation[]) {
  const seen = new Set<string>();
  return actions.filter((action) => {
    const key = actionKey(action);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function actionKey(action: ActionRecommendation) {
  return [
    action.actionId,
    action.targetObjectType ?? "",
    action.targetObjectId ?? "",
  ].join(":");
}
