import { beforeEach, expect, test, vi } from "vitest";

import {
  fetchActiveTrialFlow,
  fetchActiveFlowForAction,
  recordFlowCtaEvidence,
  shouldRecordFlowCta,
  trialDemandPackForImport,
} from "./flowEvidence";
import type { AssistantFlow } from "../types/assistant";

const flow: AssistantFlow = {
  activeFlow: "operator_happy_path_v1",
  flowRunId: "FLOW-123",
  flowName: "Operator happy path",
  flowStatus: "active",
  currentStep: "import_ogv_demand",
  currentStepLabel: "Import OGV demand",
  stepStatus: "active",
  expectedRoute: "/schedule/ogv-demand",
  expectedActionId: "IMPORT_OGV_DEMAND",
  blockedReason: "",
  trialPack: "operator_happy_path_v1",
  evidenceRunId: "operator-trial-happy-path",
  expectedActionIds: ["IMPORT_OGV_DEMAND"],
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

test("shouldRecordFlowCta only matches the active expected flow action", () => {
  expect(shouldRecordFlowCta(flow, "IMPORT_OGV_DEMAND")).toBe(true);
  expect(shouldRecordFlowCta(flow, "GENERATE_PLAN")).toBe(false);
  expect(shouldRecordFlowCta(null, "IMPORT_OGV_DEMAND")).toBe(false);
});

test("trialDemandPackForImport selects flow pack or clean operator happy-path default", () => {
  expect(trialDemandPackForImport(flow)).toBe("operator_happy_path_v1");
  expect(trialDemandPackForImport({
    ...flow,
    trialPack: "operator_trial_phase5",
  })).toBe("operator_trial_phase5");
  expect(trialDemandPackForImport({
    ...flow,
    activeFlow: "phase5_plus_recovery_v1",
    expectedActionId: "OPEN_EXCEPTION_CENTER",
    trialPack: "operator_trial_phase5",
  })).toBe("operator_trial_phase5");
  expect(trialDemandPackForImport(null)).toBe("operator_happy_path_v1");
});

test("recordFlowCtaEvidence posts flow event after a matching CTA", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ csrfToken: "csrf-token" }),
    })
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ run_id: "FLOW-123" }),
    });
  vi.stubGlobal("fetch", fetchMock);

  await recordFlowCtaEvidence(flow, "IMPORT_OGV_DEMAND", "/schedule/ogv-demand", {
    importJobId: 7,
  });

  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(fetchMock).toHaveBeenLastCalledWith(
    "/api/flows/FLOW-123/events/",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        step_key: "import_ogv_demand",
        action_id: "IMPORT_OGV_DEMAND",
        route: "/schedule/ogv-demand",
        object_type: "import_job",
        object_id: "7",
        metadata: {
          source: "operator_ui_cta",
          importJobId: 7,
        },
      }),
    }),
  );
});

test("fetchActiveFlowForAction maps runtime flow truth for a matching CTA", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        flow: {
          run_id: "FLOW-456",
          flow_definition: {
            flow_key: "operator_happy_path_v1",
            name: "Operator happy path",
          },
          status: "active",
          current_step_key: "import_ogv_demand",
          metadata: {
            trial_pack: "operator_happy_path_v1",
            evidence_run_id: "operator-trial-happy-path",
            expected_action_ids: ["IMPORT_OGV_DEMAND", "ENTER_OPERATING_WINDOWS"],
          },
          step_runs: [
            {
              step_key: "import_ogv_demand",
              status: "active",
              expected_route: "/schedule/ogv-demand",
              expected_action_id: "IMPORT_OGV_DEMAND",
              blocked_reason: "",
            },
          ],
        },
      }),
    });
  vi.stubGlobal("fetch", fetchMock);

  const activeFlow = await fetchActiveFlowForAction("IMPORT_OGV_DEMAND");

  expect(activeFlow).toMatchObject({
    flowRunId: "FLOW-456",
    expectedActionId: "IMPORT_OGV_DEMAND",
    trialPack: "operator_happy_path_v1",
    evidenceRunId: "operator-trial-happy-path",
    expectedActionIds: ["IMPORT_OGV_DEMAND", "ENTER_OPERATING_WINDOWS"],
  });
});

test("fetchActiveTrialFlow maps trial metadata even when the current step is not import", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        flow: {
          run_id: "FLOW-789",
          flow_definition: {
            flow_key: "phase5_recovery_from_demand_v1",
            name: "Phase 5 recovery from demand import",
          },
          status: "active",
          current_step_key: "open_exception_center",
          metadata: {
            trial_pack: "operator_trial_phase5",
            evidence_run_id: "operator-trial-recovery-from-demand",
            expected_action_ids: ["IMPORT_OGV_DEMAND", "ENTER_OPERATING_WINDOWS"],
          },
          step_runs: [
            {
              step_key: "open_exception_center",
              status: "active",
              expected_route: "/exceptions/center",
              expected_action_id: "OPEN_EXCEPTION_CENTER",
              blocked_reason: "",
            },
          ],
        },
      }),
    });
  vi.stubGlobal("fetch", fetchMock);

  const activeFlow = await fetchActiveTrialFlow();

  expect(activeFlow).toMatchObject({
    activeFlow: "phase5_recovery_from_demand_v1",
    expectedActionId: "OPEN_EXCEPTION_CENTER",
    trialPack: "operator_trial_phase5",
    evidenceRunId: "operator-trial-recovery-from-demand",
  });
});

test("recordFlowCtaEvidence no-ops for non-matching actions", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  await recordFlowCtaEvidence(flow, "GENERATE_PLAN", "/operations/tug-barge-assignment");

  expect(fetchMock).not.toHaveBeenCalled();
});

test("recordFlowCtaEvidence surfaces flow event failures", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ csrfToken: "csrf-token" }),
    })
    .mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
  vi.stubGlobal("fetch", fetchMock);

  await expect(
    recordFlowCtaEvidence(flow, "IMPORT_OGV_DEMAND", "/schedule/ogv-demand"),
  ).rejects.toThrow("500");
});
