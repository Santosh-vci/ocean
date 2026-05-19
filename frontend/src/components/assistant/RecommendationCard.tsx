import type {
  ActionRecommendation,
  AssistantChecklistItem,
  AssistantMode,
} from "../../types/assistant";

export type AssistantRecommendationSurfaceProps = {
  assistantMode?: AssistantMode;
  assistantPageActions?: ActionRecommendation[];
  assistantRowActions?: ActionRecommendation[];
  assistantBlockedActions?: ActionRecommendation[];
  assistantChecklist?: AssistantChecklistItem[];
  onAssistantNavigate?: (path: string) => void;
};

type RecommendationCardProps = AssistantRecommendationSurfaceProps & {
  title?: string;
};

export function RecommendationCard({
  assistantBlockedActions = [],
  assistantChecklist = [],
  assistantPageActions = [],
  assistantRowActions = [],
  onAssistantNavigate,
  title = "Assistant guidance",
}: RecommendationCardProps) {
  const enabledActions = uniqueActions([...assistantRowActions, ...assistantPageActions])
    .filter((action) => action.enabled);
  const blockedActions = uniqueActions(assistantBlockedActions).filter((action) => !action.enabled);
  const primaryAction = enabledActions[0] ?? blockedActions[0] ?? null;

  if (!primaryAction) return null;

  const secondaryActions = enabledActions
    .filter((action) => action !== primaryAction)
    .slice(0, 3);
  const checklistItems = assistantChecklist.slice(0, 4);

  return (
    <section className={`assistant-recommendation-card ${primaryAction.priority}`}>
      <div className="assistant-card-primary">
        <div>
          <span>{title}</span>
          <h2>{primaryAction.label}</h2>
          <p>{primaryAction.reason}</p>
        </div>
        <button
          disabled={!primaryAction.enabled || !onAssistantNavigate}
          onClick={() => onAssistantNavigate?.(primaryAction.route)}
          title={primaryAction.enabled
            ? primaryAction.reason
            : primaryAction.blockedReason || primaryAction.reason}
          type="button"
        >
          {primaryAction.enabled ? primaryAction.ctaLabel : "Blocked"}
        </button>
      </div>

      {secondaryActions.length || blockedActions.length || checklistItems.length ? (
        <div className="assistant-card-secondary">
          {secondaryActions.map((action) => (
            <button
              className={action.priority}
              key={actionKey(action)}
              onClick={() => onAssistantNavigate?.(action.route)}
              type="button"
            >
              <strong>{action.ctaLabel}</strong>
              <span>{action.label}</span>
            </button>
          ))}
          {blockedActions.slice(0, 2).map((action) => (
            <span className="assistant-blocked-action" key={actionKey(action)}>
              <strong>{action.label}</strong>
              <em>{action.blockedReason || action.reason}</em>
            </span>
          ))}
          {checklistItems.map((item) => (
            <span className={`assistant-checklist-item ${item.status}`} key={item.key}>
              <strong>{item.label}</strong>
              {item.reason ? <em>{item.reason}</em> : null}
            </span>
          ))}
        </div>
      ) : null}
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
