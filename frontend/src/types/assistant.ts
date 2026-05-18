export type AssistantMode = "off" | "assisted" | "guided" | "supervisor";
export type AssistantPriority = "critical" | "warning" | "normal" | "info";

export type ActionRecommendation = {
  actionId: string;
  label: string;
  priority: AssistantPriority;
  rankScore: number;
  enabled: boolean;
  route: string;
  ctaLabel: string;
  reason: string;
  hoverHint: string;
  detailText: string;
  impactIfIgnored: string;
  ownerRole: string;
  requiredPermission: string | null;
  auditRequired: boolean;
  targetObjectType: string | null;
  targetObjectId: string | null;
  blockedReason: string;
  source: string;
  expiresAt: string | null;
  metadata: Record<string, unknown>;
};

export type AssistantChecklistItem = {
  key: string;
  label: string;
  status: "complete" | "current" | "blocked" | "pending";
  actionId?: string;
  route?: string;
  reason?: string;
};

export type NextActionResponse = {
  generatedAt: string;
  mode: AssistantMode;
  context: Record<string, unknown>;
  globalNextAction: ActionRecommendation | null;
  pageActions: ActionRecommendation[];
  rowActions: ActionRecommendation[];
  blockedActions: ActionRecommendation[];
  checklist: AssistantChecklistItem[];
};

const ASSISTANT_MODES = new Set<AssistantMode>([
  "off",
  "assisted",
  "guided",
  "supervisor",
]);

export function normalizeNextActionResponse(raw: unknown): NextActionResponse {
  const value = asRecord(raw);
  return {
    generatedAt: stringValue(value.generated_at),
    mode: assistantModeValue(value.mode),
    context: asRecord(value.context),
    globalNextAction: value.global_next_action
      ? normalizeActionRecommendation(value.global_next_action)
      : null,
    pageActions: arrayValue(value.page_actions).map(normalizeActionRecommendation),
    rowActions: arrayValue(value.row_actions).map(normalizeActionRecommendation),
    blockedActions: arrayValue(value.blocked_actions).map(normalizeActionRecommendation),
    checklist: arrayValue(value.checklist).map(normalizeChecklistItem),
  };
}

export function normalizeActionRecommendation(raw: unknown): ActionRecommendation {
  const value = asRecord(raw);
  return {
    actionId: stringValue(value.action_id),
    label: stringValue(value.label),
    priority: priorityValue(value.priority),
    rankScore: numberValue(value.rank_score),
    enabled: booleanValue(value.enabled),
    route: stringValue(value.route),
    ctaLabel: stringValue(value.cta_label),
    reason: stringValue(value.reason),
    hoverHint: stringValue(value.hover_hint),
    detailText: stringValue(value.detail_text),
    impactIfIgnored: stringValue(value.impact_if_ignored),
    ownerRole: stringValue(value.owner_role),
    requiredPermission: nullableStringValue(value.required_permission),
    auditRequired: booleanValue(value.audit_required),
    targetObjectType: nullableStringValue(value.target_object_type),
    targetObjectId: nullableStringValue(value.target_object_id),
    blockedReason: stringValue(value.blocked_reason),
    source: stringValue(value.source),
    expiresAt: nullableStringValue(value.expires_at),
    metadata: asRecord(value.metadata),
  };
}

function normalizeChecklistItem(raw: unknown): AssistantChecklistItem {
  const value = asRecord(raw);
  const item: AssistantChecklistItem = {
    key: stringValue(value.key),
    label: stringValue(value.label),
    status: checklistStatusValue(value.status),
  };
  const actionId = nullableStringValue(value.action_id);
  const route = nullableStringValue(value.route);
  const reason = nullableStringValue(value.reason);
  if (actionId) item.actionId = actionId;
  if (route) item.route = route;
  if (reason) item.reason = reason;
  return item;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function nullableStringValue(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return typeof value === "string" ? value : String(value);
}

function numberValue(value: unknown): number {
  const resolved = typeof value === "number" ? value : Number(value);
  return Number.isFinite(resolved) ? resolved : 0;
}

function booleanValue(value: unknown): boolean {
  return typeof value === "boolean" ? value : false;
}

function assistantModeValue(value: unknown): AssistantMode {
  return typeof value === "string" && ASSISTANT_MODES.has(value as AssistantMode)
    ? value as AssistantMode
    : "assisted";
}

function priorityValue(value: unknown): AssistantPriority {
  return (
    value === "critical"
    || value === "warning"
    || value === "normal"
    || value === "info"
  ) ? value : "info";
}

function checklistStatusValue(value: unknown): AssistantChecklistItem["status"] {
  return (
    value === "complete"
    || value === "current"
    || value === "blocked"
    || value === "pending"
  ) ? value : "pending";
}
