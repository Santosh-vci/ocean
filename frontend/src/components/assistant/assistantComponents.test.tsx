import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { DashboardPage } from "../../pages/DashboardPage";
import type { CurrentUser } from "../../types";
import type { ActionRecommendation } from "../../types/assistant";
import { ActionInboxPanel } from "./ActionInboxPanel";
import { NextActionPill } from "./NextActionPill";
import { RecommendationCard } from "./RecommendationCard";

function action(overrides: Partial<ActionRecommendation> = {}): ActionRecommendation {
  return {
    actionId: "OPEN_RECOMMENDATION_CONSOLE",
    label: "Open Recommendation Console",
    priority: "warning",
    rankScore: 830,
    enabled: true,
    route: "/recovery/recommendations",
    ctaLabel: "Open recommendations",
    reason: "A successful recovery optimizer run has ranked candidate options.",
    hoverHint: "",
    detailText: "",
    impactIfIgnored: "",
    ownerRole: "berau-scheduler",
    requiredPermission: "schedule.view",
    auditRequired: false,
    targetObjectType: "optimizer_run",
    targetObjectId: "701",
    blockedReason: "",
    source: "recovery.optimizer_run_succeeded",
    expiresAt: null,
    metadata: {},
    ...overrides,
  };
}

const currentUser: CurrentUser = {
  id: 1,
  username: "operator",
  email: "operator@coalflow.local",
  is_active: true,
  memberships: [],
  assignments: [],
  permissions: ["dashboard.view"],
};

test("next action pill is hidden when no action exists", () => {
  const { container } = render(<NextActionPill action={null} onNavigate={vi.fn()} />);

  expect(container).toBeEmptyDOMElement();
});

test("next action pill renders priority tone and navigates when enabled", () => {
  const onNavigate = vi.fn();

  render(<NextActionPill action={action({ priority: "critical" })} onNavigate={onNavigate} />);

  const button = screen.getByRole("button", { name: /Open Recommendation Console/ });
  expect(button).toHaveClass("critical");
  fireEvent.click(button);
  expect(onNavigate).toHaveBeenCalledWith("/recovery/recommendations");
});

test("next action pill does not navigate when disabled", () => {
  const onNavigate = vi.fn();

  render(
    <NextActionPill
      action={action({
        blockedReason: "Schedule view permission is required.",
        enabled: false,
      })}
      onNavigate={onNavigate}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: /Open Recommendation Console/ }));
  expect(onNavigate).not.toHaveBeenCalled();
});

test("dashboard inbox renders Phase 5 assistant actions", () => {
  render(
    <ActionInboxPanel
      blockedActions={[]}
      globalAction={action()}
      onNavigate={vi.fn()}
      pageActions={[
        action({
          actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
          ctaLabel: "Create scenario",
          label: "Create scenario from recommendation",
          source: "recovery.recommendation_ready_to_materialize",
          targetObjectType: "recovery_recommendation",
          targetObjectId: "801",
        }),
      ]}
    />,
  );

  expect(screen.getByText("Assistant action inbox")).toBeInTheDocument();
  expect(screen.getByText("Open Recommendation Console")).toBeInTheDocument();
  expect(screen.getByText("Create scenario from recommendation")).toBeInTheDocument();
});

test("recommendation card CTA navigates with the action route", () => {
  const onNavigate = vi.fn();

  render(
    <RecommendationCard
      assistantPageActions={[action({ ctaLabel: "Open recommendations" })]}
      onAssistantNavigate={onNavigate}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Open recommendations" }));
  expect(onNavigate).toHaveBeenCalledWith("/recovery/recommendations");
});

test("dashboard assistant UI follows assisted and off modes", () => {
  const { rerender } = render(
    <DashboardPage
      assistantGlobalAction={action()}
      assistantMode="assisted"
      auditEvents={[]}
      currentUser={currentUser}
      dashboard={null}
      etaProjections={[]}
      onNavigate={vi.fn()}
      operationsHealth={null}
      replayRuns={[]}
      trackingAlerts={[]}
    />,
  );

  expect(screen.getByText("Assistant action inbox")).toBeInTheDocument();

  rerender(
    <DashboardPage
      assistantGlobalAction={action()}
      assistantMode="off"
      auditEvents={[]}
      currentUser={currentUser}
      dashboard={null}
      etaProjections={[]}
      onNavigate={vi.fn()}
      operationsHealth={null}
      replayRuns={[]}
      trackingAlerts={[]}
    />,
  );

  expect(screen.queryByText("Assistant action inbox")).not.toBeInTheDocument();
});
