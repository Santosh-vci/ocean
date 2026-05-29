import type { ActionRecommendation, AssistantFlow } from "../../types/assistant";
import { AbbrText } from "../Abbreviation";

type NextActionPillProps = {
  action: ActionRecommendation | null;
  assistantFlow?: AssistantFlow | null;
  onNavigate: (path: string) => void;
};

export function NextActionPill({
  action,
  assistantFlow = null,
  onNavigate,
}: NextActionPillProps) {
  if (!action) return null;
  const flowTitle = assistantFlow && action.actionId === assistantFlow.expectedActionId
    ? `${assistantFlow.flowName}: ${assistantFlow.currentStepLabel}`
    : "";
  const title = flowTitle
    ? `${flowTitle}. ${action.enabled ? action.reason : action.blockedReason || action.reason}`
    : action.enabled ? action.reason : action.blockedReason || action.reason;

  return (
    <button
      className={`next-action-pill ${action.priority}`}
      disabled={!action.enabled}
      onClick={() => {
        if (action.enabled) onNavigate(action.route);
      }}
      title={title}
      type="button"
    >
      <span>Next Action</span>
      <strong><AbbrText text={action.label} /></strong>
    </button>
  );
}
