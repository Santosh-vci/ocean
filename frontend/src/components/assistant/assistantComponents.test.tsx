import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { DashboardPage } from "../../pages/DashboardPage";
import type { CurrentUser } from "../../types";
import type { ActionRecommendation } from "../../types/assistant";
import { ActionInboxPanel } from "./ActionInboxPanel";
import { DisabledReasonTooltip } from "./DisabledReasonTooltip";
import { NextActionPill } from "./NextActionPill";
import { RecommendationCard } from "./RecommendationCard";
import { RowActionHint } from "./RowActionHint";

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

test("disabled reason tooltip finds and shows the matching blocked action reason", () => {
  render(
    <DisabledReasonTooltip
      actionId="PUBLISH_PLAN"
      actions={[
        action({
          actionId: "PUBLISH_PLAN",
          blockedReason: "Publishing requires completed approvals.",
          enabled: false,
        }),
      ]}
    >
      <button disabled type="button">Publish plan</button>
    </DisabledReasonTooltip>,
  );

  expect(
    screen.getByLabelText("Blocked reason: Publishing requires completed approvals."),
  ).toHaveTextContent("Blocked");
});

test("disabled reason tooltip does not change child button handler", () => {
  const onClick = vi.fn();

  render(
    <DisabledReasonTooltip
      actionId="PUBLISH_PLAN"
      actions={[
        action({
          actionId: "PUBLISH_PLAN",
          blockedReason: "Publishing requires completed approvals.",
          enabled: false,
        }),
      ]}
    >
      <button onClick={onClick} type="button">Publish plan</button>
    </DisabledReasonTooltip>,
  );

  fireEvent.click(screen.getByRole("button", { name: "Publish plan" }));
  expect(onClick).toHaveBeenCalledOnce();
});

test("row action hint filters by object type and object id", () => {
  const onNavigate = vi.fn();

  render(
    <RowActionHint
      actions={[
        action({
          actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
          ctaLabel: "Create scenario",
          label: "Create scenario from recommendation",
          targetObjectType: "recovery_recommendation",
          targetObjectId: "801",
        }),
        action({
          ctaLabel: "Open run",
          targetObjectType: "optimizer_run",
          targetObjectId: "701",
        }),
      ]}
      objectId={801}
      objectType="recovery_recommendation"
      onNavigate={onNavigate}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: /Create scenario/ }));
  expect(screen.queryByText("Open run")).not.toBeInTheDocument();
  expect(onNavigate).toHaveBeenCalledWith("/recovery/recommendations");
});

test("row action hint renders nothing when no matching action exists", () => {
  const { container } = render(
    <RowActionHint
      actions={[action({ targetObjectType: "optimizer_run", targetObjectId: "701" })]}
      objectId={801}
      objectType="recovery_recommendation"
    />,
  );

  expect(container).toBeEmptyDOMElement();
});

test("row action hint targets one recovery recommendation without affecting siblings", () => {
  render(
    <RowActionHint
      actions={[
        action({
          actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
          ctaLabel: "Create scenario",
          label: "Create scenario from REC-801",
          targetObjectType: "recovery_recommendation",
          targetObjectId: "801",
        }),
        action({
          actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
          ctaLabel: "Create scenario",
          label: "Create scenario from REC-802",
          targetObjectType: "recovery_recommendation",
          targetObjectId: "802",
        }),
      ]}
      objectId={802}
      objectType="recovery_recommendation"
    />,
  );

  expect(screen.getByText("Create scenario from REC-802")).toBeInTheDocument();
  expect(screen.queryByText("Create scenario from REC-801")).not.toBeInTheDocument();
});

test("row action hint shows distinct dismissed and materialized blocked reasons", () => {
  const dismissed = action({
    actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
    blockedReason: "Dismissed recommendations cannot be materialized.",
    enabled: false,
    targetObjectType: "recovery_recommendation",
    targetObjectId: "901",
  });
  const materialized = action({
    actionId: "DISMISS_RECOVERY_RECOMMENDATION",
    blockedReason: "Materialized recommendations cannot be dismissed.",
    enabled: false,
    targetObjectType: "recovery_recommendation",
    targetObjectId: "902",
  });
  const { rerender } = render(
    <RowActionHint
      actions={[dismissed, materialized]}
      objectId={901}
      objectType="recovery_recommendation"
    />,
  );

  expect(screen.getByText("Dismissed recommendations cannot be materialized."))
    .toBeInTheDocument();

  rerender(
    <RowActionHint
      actions={[dismissed, materialized]}
      objectId={902}
      objectType="recovery_recommendation"
    />,
  );

  expect(screen.getByText("Materialized recommendations cannot be dismissed."))
    .toBeInTheDocument();
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
