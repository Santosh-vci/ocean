import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { ASSISTANT_MODE_KEY, useAssistantMode } from "./useAssistantMode";
import { useNextActions } from "./useNextActions";

function ModeProbe() {
  const { mode, setMode } = useAssistantMode();
  return <button onClick={() => setMode("off")}>{mode}</button>;
}

function NextActionsProbe({
  objectId,
  objectType,
  route,
}: {
  objectId?: number;
  objectType?: string;
  route: string;
}) {
  const { data, error, loading, mode } = useNextActions(route, { objectId, objectType });
  return (
    <>
      <span data-testid="mode">{mode}</span>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="label">{data?.globalNextAction?.label ?? "none"}</span>
      <span data-testid="error">{error?.message ?? "none"}</span>
    </>
  );
}

function rawResponse() {
  return {
    generated_at: "2026-05-18T08:00:00.000Z",
    mode: "assisted",
    context: { route: "/recovery/recommendations" },
    global_next_action: {
      action_id: "MATERIALIZE_RECOVERY_RECOMMENDATION",
      label: "Create scenario from recommendation",
      priority: "warning",
      rank_score: 810,
      enabled: true,
      route: "/recovery/recommendations",
      cta_label: "Create scenario",
      reason: "The top recovery recommendation is ready.",
      hover_hint: "",
      detail_text: "",
      impact_if_ignored: "",
      owner_role: "berau-scheduler",
      required_permission: "schedule.edit",
      audit_required: true,
      target_object_type: "recovery_recommendation",
      target_object_id: "801",
      blocked_reason: "",
      source: "recovery.recommendation_ready_to_materialize",
      expires_at: null,
      metadata: {},
    },
    page_actions: [],
    row_actions: [],
    blocked_actions: [],
    checklist: [],
  };
}

beforeEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

test("assistant mode defaults to assisted and can persist off", () => {
  render(<ModeProbe />);

  const button = screen.getByRole("button", { name: "assisted" });
  expect(button).toHaveTextContent("assisted");

  fireEvent.click(button);

  expect(button).toHaveTextContent("off");
  expect(window.localStorage.getItem(ASSISTANT_MODE_KEY)).toBe("off");
});

test("useNextActions does not call the API when assistant mode is off", () => {
  window.localStorage.setItem(ASSISTANT_MODE_KEY, "off");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(<NextActionsProbe route="/recovery/recommendations" />);

  expect(screen.getByTestId("mode")).toHaveTextContent("off");
  expect(screen.getByTestId("label")).toHaveTextContent("none");
  expect(fetchMock).not.toHaveBeenCalled();
});

test("useNextActions handles API rejection without throwing into render", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    }),
  );

  render(<NextActionsProbe route="/dashboard/situation" />);

  await waitFor(() => {
    expect(screen.getByTestId("error")).toHaveTextContent("500");
  });
  expect(screen.getByTestId("label")).toHaveTextContent("none");
});

test("useNextActions requests object-scoped Phase 5 guidance", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => rawResponse(),
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <NextActionsProbe
      objectId={801}
      objectType="recovery_recommendation"
      route="/recovery/recommendations"
    />,
  );

  await waitFor(() => {
    expect(screen.getByTestId("label")).toHaveTextContent(
      "Create scenario from recommendation",
    );
  });
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("object_type=recovery_recommendation"),
    expect.any(Object),
  );
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("object_id=801"),
    expect.any(Object),
  );
});
