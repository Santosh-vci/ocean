import { beforeEach, expect, test, vi } from "vitest";

import { fetchNextActions } from "../lib/api";
import { normalizeNextActionResponse } from "./assistant";

function rawResponse() {
  return {
    generated_at: "2026-05-18T08:00:00.000Z",
    mode: "guided",
    context: {
      route: "/recovery/recommendations",
      object_type: "recovery_recommendation",
      object_id: "801",
    },
    global_next_action: rawAction(),
    page_actions: [rawAction({ action_id: "OPEN_RECOMMENDATION_CONSOLE" })],
    row_actions: [rawAction({ action_id: "MATERIALIZE_RECOVERY_RECOMMENDATION" })],
    blocked_actions: [rawAction({ action_id: "PUBLISH_PLAN", enabled: false })],
    checklist: [{
      key: "review",
      label: "Review recommendation",
      status: "current",
      action_id: "OPEN_RECOMMENDATION_CONSOLE",
      route: "/recovery/recommendations",
      reason: "Recommendation review is ready.",
    }],
  };
}

function rawAction(overrides: Record<string, unknown> = {}) {
  return {
    action_id: "MATERIALIZE_RECOVERY_RECOMMENDATION",
    label: "Create scenario from recommendation",
    priority: "warning",
    rank_score: 810,
    enabled: true,
    route: "/recovery/recommendations",
    cta_label: "Create scenario",
    reason: "The top recovery recommendation is ready.",
    hover_hint: "Ready for scenario handoff.",
    detail_text: "Persisted Phase 5 guidance.",
    impact_if_ignored: "The optimizer output remains advisory only.",
    owner_role: "berau-scheduler",
    required_permission: "schedule.edit",
    audit_required: true,
    target_object_type: "recovery_recommendation",
    target_object_id: "801",
    blocked_reason: "",
    source: "recovery.recommendation_ready_to_materialize",
    expires_at: null,
    metadata: { recommendationRef: "REC-801" },
    ...overrides,
  };
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

test("normalizer maps assistant response fields to frontend shape", () => {
  const normalized = normalizeNextActionResponse(rawResponse());

  expect(normalized.generatedAt).toBe("2026-05-18T08:00:00.000Z");
  expect(normalized.mode).toBe("guided");
  expect(normalized.context.object_id).toBe("801");
  expect(normalized.globalNextAction?.actionId).toBe(
    "MATERIALIZE_RECOVERY_RECOMMENDATION",
  );
  expect(normalized.globalNextAction?.rankScore).toBe(810);
  expect(normalized.globalNextAction?.targetObjectType).toBe("recovery_recommendation");
  expect(normalized.globalNextAction?.metadata.recommendationRef).toBe("REC-801");
  expect(normalized.pageActions[0].actionId).toBe("OPEN_RECOMMENDATION_CONSOLE");
  expect(normalized.rowActions[0].actionId).toBe("MATERIALIZE_RECOVERY_RECOMMENDATION");
  expect(normalized.blockedActions[0].enabled).toBe(false);
  expect(normalized.checklist[0]).toMatchObject({
    key: "review",
    actionId: "OPEN_RECOMMENDATION_CONSOLE",
    status: "current",
  });
});

test("normalizer defaults missing optional arrays and unknown mode safely", () => {
  const normalized = normalizeNextActionResponse({
    generated_at: "2026-05-18T08:00:00.000Z",
    mode: "unknown",
    context: null,
  });

  expect(normalized.mode).toBe("assisted");
  expect(normalized.context).toEqual({});
  expect(normalized.globalNextAction).toBeNull();
  expect(normalized.pageActions).toEqual([]);
  expect(normalized.rowActions).toEqual([]);
  expect(normalized.blockedActions).toEqual([]);
  expect(normalized.checklist).toEqual([]);
});

test("fetchNextActions sends route, mode, limit, and Phase 5 object params", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => rawResponse(),
  });
  vi.stubGlobal("fetch", fetchMock);

  const response = await fetchNextActions({
    route: "/recovery/recommendations",
    objectType: "recovery_recommendation",
    objectId: 801,
    mode: "guided",
    limit: 5,
  });

  expect(response.globalNextAction?.targetObjectId).toBe("801");
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/assistant/next-actions/?route=%2Frecovery%2Frecommendations&object_type=recovery_recommendation&object_id=801&mode=guided&limit=5",
    expect.objectContaining({
      credentials: "include",
      headers: expect.objectContaining({ "Content-Type": "application/json" }),
    }),
  );
});
