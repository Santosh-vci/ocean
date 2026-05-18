import type { ActionRecommendation } from "../../types/assistant";

export function blockedReasonFor(actions: ActionRecommendation[], actionId: string) {
  const action = actions.find((item) => item.actionId === actionId && !item.enabled);
  return action?.blockedReason || action?.reason || "";
}

export function actionsForObject(
  actions: ActionRecommendation[],
  objectType: string,
  objectId: number | string | null | undefined,
) {
  if (objectId === null || objectId === undefined) return [];
  const id = String(objectId);
  return actions.filter(
    (action) => action.targetObjectType === objectType && action.targetObjectId === id,
  );
}
