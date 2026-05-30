import { apiFetch, getCsrfToken } from "./api";
import type { AssistantFlow } from "../types/assistant";

type FlowRuntimeStep = {
  step_key?: string;
  status?: string;
  expected_route?: string;
  expected_action_id?: string;
  blocked_reason?: string;
};

type FlowRuntimeRun = {
  run_id?: string;
  flow_definition?: {
    flow_key?: string;
    name?: string;
  };
  status?: string;
  current_step_key?: string;
  metadata?: Record<string, unknown>;
  step_runs?: FlowRuntimeStep[];
};

export function shouldRecordFlowCta(
  flow: AssistantFlow | null | undefined,
  actionId: string,
) {
  return Boolean(
    flow?.flowRunId
    && flow.currentStep
    && flow.expectedActionId === actionId,
  );
}

export function trialDemandPackForImport(flow: AssistantFlow | null | undefined) {
  if (
    flow?.expectedActionId === "IMPORT_OGV_DEMAND"
    && (
      flow.trialPack === "operator_happy_path_v1"
      || flow.trialPack === "operator_trial_phase5"
    )
  ) {
    return flow.trialPack;
  }
  return "operator_happy_path_v1";
}

export async function fetchActiveFlowForAction(actionId: string) {
  const response = await apiFetch<{ flow?: FlowRuntimeRun | null }>("/flows/active/");
  const flow = runtimeFlowToAssistantFlow(response.flow ?? null);
  return shouldRecordFlowCta(flow, actionId) ? flow : null;
}

export async function recordFlowCtaEvidence(
  flow: AssistantFlow | null | undefined,
  actionId: string,
  route: string,
  metadata: Record<string, unknown> = {},
) {
  if (!shouldRecordFlowCta(flow, actionId)) {
    return null;
  }
  const activeFlow = flow as AssistantFlow;

  const csrfToken = await getCsrfToken();
  const objectRef = objectRefForAction(actionId, metadata);
  return apiFetch<unknown>(`/flows/${activeFlow.flowRunId}/events/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify({
      step_key: activeFlow.currentStep,
      action_id: actionId,
      route: route || activeFlow.expectedRoute,
      ...(objectRef ? { object_type: objectRef.objectType, object_id: objectRef.objectId } : {}),
      metadata: {
        source: "operator_ui_cta",
        ...metadata,
      },
    }),
  });
}

function objectRefForAction(actionId: string, metadata: Record<string, unknown>) {
  const ref = (objectType: string, value: unknown) => {
    if (value === null || value === undefined || value === "") return null;
    return { objectType, objectId: String(value) };
  };
  if (actionId === "IMPORT_OGV_DEMAND") return ref("import_job", metadata.importJobId);
  if (actionId === "GENERATE_PLAN" || actionId === "REPAIR_PLAN_CONFLICTS") {
    return ref("plan_version", metadata.planVersionId);
  }
  if (actionId === "GENERATE_RECOVERY_OPTIONS") return ref("optimizer_run", metadata.optimizerRunId);
  if (actionId === "VALIDATE_ROOT_CAUSE_REPAIR" || actionId === "MATERIALIZE_RECOVERY_RECOMMENDATION") {
    return ref("recovery_recommendation", metadata.recommendationId);
  }
  if (actionId === "RUN_SIMULATION" || actionId === "PROMOTE_SCENARIO") {
    return ref("simulation_scenario", metadata.scenarioId);
  }
  if (actionId === "SUBMIT_APPROVAL" || actionId === "APPROVE_PLAN") {
    return ref("approval_request", metadata.approvalRequestId);
  }
  if (actionId === "RUN_PUBLISHABILITY_CHECK") {
    return ref("publishability_assessment", metadata.assessmentId);
  }
  if (actionId === "PUBLISH_PLAN") return ref("published_plan_snapshot", metadata.publishedSnapshotId);
  if (actionId === "GENERATE_EXPORT") return ref("export_job", metadata.exportJobId);
  return null;
}

function runtimeFlowToAssistantFlow(flow: FlowRuntimeRun | null): AssistantFlow | null {
  if (!flow?.run_id) return null;
  const steps = Array.isArray(flow.step_runs) ? flow.step_runs : [];
  const currentStepKey = typeof flow.current_step_key === "string" ? flow.current_step_key : "";
  const currentStep = steps.find((step) => step.step_key === currentStepKey) ?? null;
  const metadata = flow.metadata && typeof flow.metadata === "object" ? flow.metadata : {};
  return {
    activeFlow: stringValue(flow.flow_definition?.flow_key),
    flowRunId: flow.run_id,
    flowName: stringValue(flow.flow_definition?.name),
    flowStatus: stringValue(flow.status),
    currentStep: currentStepKey,
    currentStepLabel: labelFromStepKey(currentStepKey),
    stepStatus: stringValue(currentStep?.status),
    expectedRoute: stringValue(currentStep?.expected_route),
    expectedActionId: stringValue(currentStep?.expected_action_id),
    blockedReason: stringValue(currentStep?.blocked_reason),
    trialPack: nullableStringValue(metadata.trial_pack),
    evidenceRunId: nullableStringValue(metadata.evidence_run_id),
    expectedActionIds: Array.isArray(metadata.expected_action_ids)
      ? metadata.expected_action_ids.map(stringValue).filter(Boolean)
      : [],
  };
}

function labelFromStepKey(stepKey: string) {
  return stepKey
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}

function nullableStringValue(value: unknown) {
  if (value === null || value === undefined) return null;
  return typeof value === "string" ? value : "";
}
