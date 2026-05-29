import type {
  ActionRecommendation,
  AssistantChecklistItem,
  AssistantFlow,
  AssistantMode,
} from "../../types/assistant";
import { AbbrText } from "../Abbreviation";

export type AssistantRecommendationSurfaceProps = {
  assistantFlow?: AssistantFlow | null;
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
  assistantFlow = null,
  assistantPageActions = [],
  assistantRowActions = [],
  onAssistantNavigate,
  title = "Assistant guidance",
}: RecommendationCardProps) {
  const enabledActions = uniqueActions([...assistantRowActions, ...assistantPageActions])
    .filter((action) => action.enabled);
  const blockedActions = uniqueActions(assistantBlockedActions).filter((action) => !action.enabled);
  const primaryAction = preferredAction(enabledActions, assistantFlow?.expectedActionId)
    ?? blockedActions[0]
    ?? null;

  if (!primaryAction) return null;

  const secondaryActions = enabledActions
    .filter((action) => actionKey(action) !== actionKey(primaryAction))
    .slice(0, 3);
  const checklistItems = assistantChecklist.slice(0, 4);

  return (
    <section className={`assistant-recommendation-card ${primaryAction.priority}`}>
      <div className="assistant-card-primary">
        <div>
          <span>{title}</span>
          <h2><AbbrText text={primaryAction.label} /></h2>
          <p><AbbrText text={primaryAction.reason} /></p>
        </div>
        <button
          disabled={!primaryAction.enabled || !onAssistantNavigate}
          onClick={() => onAssistantNavigate?.(primaryAction.route)}
          title={primaryAction.enabled
            ? primaryAction.reason
            : primaryAction.blockedReason || primaryAction.reason}
          type="button"
        >
          {primaryAction.enabled ? <AbbrText text={primaryAction.ctaLabel} /> : "Blocked"}
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
              <strong><AbbrText text={action.ctaLabel} /></strong>
              <span><AbbrText text={action.label} /></span>
            </button>
          ))}
          {blockedActions.slice(0, 2).map((action) => (
            <span className="assistant-blocked-action" key={actionKey(action)}>
              <strong><AbbrText text={action.label} /></strong>
              <em><AbbrText text={action.blockedReason || action.reason} /></em>
            </span>
          ))}
          {checklistItems.map((item) => (
            <span className={`assistant-checklist-item ${item.status}`} key={item.key}>
              <strong><AbbrText text={item.label} /></strong>
              {item.reason ? <em><AbbrText text={item.reason} /></em> : null}
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

function preferredAction(
  actions: ActionRecommendation[],
  expectedActionId?: string,
) {
  if (!expectedActionId) return actions[0] ?? null;
  return actions.find((action) => action.actionId === expectedActionId) ?? actions[0] ?? null;
}

function actionKey(action: ActionRecommendation) {
  return [
    action.actionId,
    action.targetObjectType ?? "",
    action.targetObjectId ?? "",
  ].join(":");
}
