import type { ActionRecommendation, AssistantFlow } from "../../types/assistant";
import { AbbrText } from "../Abbreviation";

type ActionInboxPanelProps = {
  assistantFlow?: AssistantFlow | null;
  globalAction: ActionRecommendation | null;
  pageActions?: ActionRecommendation[];
  blockedActions?: ActionRecommendation[];
  onNavigate: (path: string) => void;
};

export function ActionInboxPanel({
  assistantFlow = null,
  blockedActions = [],
  globalAction,
  onNavigate,
  pageActions = [],
}: ActionInboxPanelProps) {
  const actions = uniqueActions([
    ...(globalAction ? [globalAction] : []),
    ...pageActions,
  ]);
  const prioritizedActions = prioritizeExpectedAction(
    actions,
    assistantFlow?.expectedActionId,
  ).slice(0, 6);
  const blocked = uniqueActions(blockedActions).slice(0, 3);

  if (!prioritizedActions.length && !blocked.length) return null;

  return (
    <section className="assistant-action-inbox">
      <div className="grid-header">
        <div>
          <strong>Assistant action inbox</strong>
        </div>
        <span>{prioritizedActions.length} active</span>
      </div>
      <div className="assistant-inbox-list">
        {prioritizedActions.map((action) => (
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
            <strong><AbbrText text={action.label} /></strong>
            <em>{action.source}</em>
          </button>
        ))}
        {blocked.map((action) => (
          <span className="assistant-inbox-blocked" key={actionKey(action)}>
            <strong><AbbrText text={action.label} /></strong>
            <em><AbbrText text={action.blockedReason || action.reason} /></em>
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

function prioritizeExpectedAction(
  actions: ActionRecommendation[],
  expectedActionId?: string,
) {
  if (!expectedActionId) return actions;
  const preferred = actions.find((action) => action.actionId === expectedActionId);
  if (!preferred) return actions;
  return [
    preferred,
    ...actions.filter((action) => actionKey(action) !== actionKey(preferred)),
  ];
}

function actionKey(action: ActionRecommendation) {
  return [
    action.actionId,
    action.targetObjectType ?? "",
    action.targetObjectId ?? "",
  ].join(":");
}
