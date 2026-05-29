import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { DashboardPage } from "../../pages/DashboardPage";
import type { CurrentUser } from "../../types";
import type {
  ActionRecommendation,
  AssistantChecklistItem,
  AssistantFlow,
} from "../../types/assistant";
import { ActionInboxPanel } from "./ActionInboxPanel";
import { DisabledReasonTooltip } from "./DisabledReasonTooltip";
import { GuidedChecklist } from "./GuidedChecklist";
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

const checklist: AssistantChecklistItem[] = [
  {
    key: "demand_imported",
    label: "Demand imported",
    status: "complete",
    reason: "Demand exists.",
  },
  {
    key: "recovery_recommendation_reviewed",
    label: "Recovery recommendation reviewed",
    status: "current",
    actionId: "OPEN_RECOMMENDATION_CONSOLE",
    route: "/recovery/recommendations",
    reason: "Ranked recovery recommendations are ready.",
  },
];

const assistantFlow: AssistantFlow = {
  activeFlow: "phase5_plus_recovery_v1",
  flowRunId: "FLOW-123",
  flowName: "Phase 5+ recovery path",
  flowStatus: "active",
  currentStep: "materialize_recommendation",
  currentStepLabel: "Materialize recommendation",
  stepStatus: "active",
  expectedRoute: "/recovery/recommendations",
  expectedActionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
  blockedReason: "",
  trialPack: "operator_trial_phase5",
  evidenceRunId: "operator-trial-recovery",
  expectedActionIds: ["MATERIALIZE_RECOVERY_RECOMMENDATION"],
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
          ctaLabel: "Test as scenario",
          label: "Test recommendation as scenario",
          source: "recovery.recommendation_ready_to_materialize",
          targetObjectType: "recovery_recommendation",
          targetObjectId: "801",
        }),
      ]}
    />,
  );

  expect(screen.getByText("Assistant action inbox")).toBeInTheDocument();
  expect(screen.getByText("Open Recommendation Console")).toBeInTheDocument();
  expect(screen.getByText("Test recommendation as scenario")).toBeInTheDocument();
});

test("dashboard inbox prioritizes the flow expected action", () => {
  render(
    <ActionInboxPanel
      assistantFlow={assistantFlow}
      blockedActions={[]}
      globalAction={action()}
      onNavigate={vi.fn()}
      pageActions={[
        action({
          actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
          ctaLabel: "Test as scenario",
          label: "Test recommendation as scenario",
          source: "flow.current_step",
          targetObjectType: "recovery_recommendation",
          targetObjectId: "801",
        }),
      ]}
    />,
  );

  expect(screen.getAllByRole("button")[0]).toHaveTextContent("Test recommendation as scenario");
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

test("recommendation card prefers the flow expected action", () => {
  const onNavigate = vi.fn();

  render(
    <RecommendationCard
      assistantFlow={assistantFlow}
      assistantPageActions={[
        action({ ctaLabel: "Open recommendations" }),
        action({
          actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
          ctaLabel: "Test as scenario",
          label: "Test recommendation as scenario",
          source: "flow.current_step",
        }),
      ]}
      onAssistantNavigate={onNavigate}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Test as scenario" }));
  expect(onNavigate).toHaveBeenCalledWith("/recovery/recommendations");
});

test("guided checklist uses flow name as title when flow metadata is present", () => {
  render(
    <GuidedChecklist
      assistantFlow={assistantFlow}
      items={checklist}
      mode="guided"
    />,
  );

  expect(screen.getByText("Phase 5+ recovery path")).toBeInTheDocument();
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
          ctaLabel: "Test as scenario",
          label: "Test recommendation as scenario",
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

  fireEvent.click(screen.getByRole("button", { name: /Test as scenario/ }));
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
          ctaLabel: "Test as scenario",
          label: "Test REC-801 as scenario",
          targetObjectType: "recovery_recommendation",
          targetObjectId: "801",
        }),
        action({
          actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
          ctaLabel: "Test as scenario",
          label: "Test REC-802 as scenario",
          targetObjectType: "recovery_recommendation",
          targetObjectId: "802",
        }),
      ]}
      objectId={802}
      objectType="recovery_recommendation"
    />,
  );

  expect(screen.getByText("Test REC-802 as scenario")).toBeInTheDocument();
  expect(screen.queryByText("Test REC-801 as scenario")).not.toBeInTheDocument();
});

test("row action hint shows distinct dismissed and materialized blocked reasons", () => {
  const dismissed = action({
    actionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
    blockedReason: "Dismissed recommendations cannot be tested as scenarios.",
    enabled: false,
    targetObjectType: "recovery_recommendation",
    targetObjectId: "901",
  });
  const materialized = action({
    actionId: "DISMISS_RECOVERY_RECOMMENDATION",
    blockedReason: "Recommendations already created as scenarios cannot be dismissed.",
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

  expect(screen.getByText("Dismissed recommendations cannot be tested as scenarios."))
    .toBeInTheDocument();

  rerender(
    <RowActionHint
      actions={[dismissed, materialized]}
      objectId={902}
      objectType="recovery_recommendation"
    />,
  );

  expect(screen.getByText("Recommendations already created as scenarios cannot be dismissed."))
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

test("dashboard guided mode renders preview lifecycle checklist", () => {
  render(
    <DashboardPage
      assistantChecklist={checklist}
      assistantGlobalAction={action()}
      assistantMode="guided"
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

  expect(screen.getByText("Guided checklist preview")).toBeInTheDocument();
  expect(screen.getAllByText("Recovery recommendation reviewed").length).toBeGreaterThan(0);
  expect(screen.getByText("Now")).toBeInTheDocument();
});
