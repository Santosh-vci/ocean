import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, rm, writeFile } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APP_URL = process.env.OPERATOR_TRIAL_APP_URL ?? "http://localhost:8080";
const USERNAME = process.env.OPERATOR_TRIAL_USER ?? "admin@coalflow.local";
const PASSWORD = process.env.OPERATOR_TRIAL_PASSWORD ?? "admin12345";
const EVIDENCE_DIR = path.join(ROOT, "docs/evidence/operator_trial_flow");
const SCREENSHOT_DIR = path.join(EVIDENCE_DIR, "screenshots");
const EVIDENCE_JSON = path.join(EVIDENCE_DIR, "operator_trial_flow_capture.json");

const evidence = {
  preparedAt: new Date().toISOString(),
  appUrl: APP_URL,
  preparedFlow: null,
  steps: [],
  clicks: [],
  finalAssertions: {},
};

async function main() {
  await rm(SCREENSHOT_DIR, { recursive: true, force: true });
  await mkdir(SCREENSHOT_DIR, { recursive: true });
  await waitForHttpOk(APP_URL);

  evidence.preparedFlow = prepareDbTruth();
  await rm(path.join(ROOT, ".tmp/chrome-operator-trial-flow"), { recursive: true, force: true });

  const browserPath = findBrowser();
  const port = await getFreePort();
  const profile = path.join(os.tmpdir(), `coalflow-operator-trial-${Date.now()}`);
  const chrome = spawn(
    browserPath,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--window-size=1440,1000",
      `${APP_URL}/#/dashboard/situation`,
    ],
    { stdio: "ignore" },
  );

  try {
    const wsUrl = await waitForDebuggerUrl(port);
    const cdp = await CdpClient.connect(wsUrl);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Network.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });

    await waitForApp(cdp);
    await loginIfNeeded(cdp);
    await waitForText(cdp, "COALFLOW TOWER", 15_000);
    await waitForText(cdp, "Super", 15_000);
    await clickButton(cdp, "Super", { purpose: "Set Assist to Super mode", exact: true });
    await waitForAssistantNext(cdp, "IMPORT_OGV_DEMAND", "/dashboard/situation");

    await captureStep(cdp, {
      step: "01",
      title: "Prepared operator trial flow",
      route: "/dashboard/situation",
      expectedActionId: "IMPORT_OGV_DEMAND",
      expectedCurrentStep: "import_ogv_demand",
      expectedFlowStatus: "active",
      clickedCtaLabel: null,
      expectations: {
        voyages: 0,
        plans: 0,
        publishedSnapshots: 0,
        exports: 0,
      },
    });

    let clicked = await clickButton(cdp, "Import OGV demand", {
      purpose: "Global Next Action opens demand import page",
    });
    await waitForHash(cdp, "/schedule/ogv-demand");
    await captureStep(cdp, {
      step: "02",
      title: "Demand page opened",
      route: "/schedule/ogv-demand",
      expectedActionId: "IMPORT_OGV_DEMAND",
      expectedCurrentStep: "import_ogv_demand",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
    });

    clicked = await clickButton(cdp, "Import demand", {
      purpose: "Visible page CTA imports clean happy-path OGV demand",
      exact: true,
    });
    await waitForText(cdp, "Import committed", 20_000);
    await waitForFlowState(cdp, { currentStep: "enter_operating_windows", status: "active" });
    await waitForAssistantNext(cdp, "ENTER_OPERATING_WINDOWS", "/schedule/ogv-demand");
    await captureStep(cdp, {
      step: "03",
      title: "Clean OGV demand imported",
      route: "/schedule/ogv-demand",
      expectedActionId: "ENTER_OPERATING_WINDOWS",
      expectedCurrentStep: "enter_operating_windows",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        voyages: 2,
        cargoLayerSteps: 6,
        plans: 0,
        trips: 0,
        sequenceViolations: 0,
        minFlowEvents: 2,
      },
    });

    clicked = await clickButton(cdp, "Coal Grade Sequence", {
      purpose: "Operator reviews the clean cargo sequence before entering windows",
      exact: true,
    });
    await waitForHash(cdp, "/schedule/coal-grade-sequence");
    await waitForText(cdp, "Coal Grade Sequence", 20_000);
    await captureStep(cdp, {
      step: "04",
      title: "Clean coal sequence reviewed",
      route: "/schedule/coal-grade-sequence",
      expectedActionId: "ENTER_OPERATING_WINDOWS",
      expectedCurrentStep: "enter_operating_windows",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        cargoLayerSteps: 6,
        sequenceViolations: 0,
      },
    });

    clicked = await clickButton(cdp, "Enter tide/bridge windows", {
      purpose: "Global Next Action opens operating-window page",
    });
    await waitForHash(cdp, "/constraints/tide-bridge");
    await captureStep(cdp, {
      step: "05",
      title: "Operating-window page opened",
      route: "/constraints/tide-bridge",
      expectedActionId: "ENTER_OPERATING_WINDOWS",
      expectedCurrentStep: "enter_operating_windows",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
    });

    clicked = await clickButton(cdp, "Enter operating windows", {
      purpose: "Visible page CTA creates tide, bridge, asset, and jetty windows",
      exact: true,
    });
    await waitForText(cdp, "Operating windows entered", 20_000);
    await waitForFlowState(cdp, { currentStep: "generate_plan", status: "active" });
    await waitForAssistantNext(cdp, "GENERATE_PLAN", "/constraints/tide-bridge");
    await captureStep(cdp, {
      step: "06",
      title: "Operating windows entered",
      route: "/constraints/tide-bridge",
      expectedActionId: "GENERATE_PLAN",
      expectedCurrentStep: "generate_plan",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        tideWindows: 2,
        bridgeWindows: 2,
        constraintChecks: 6,
        trips: 0,
      },
    });

    clicked = await clickButton(cdp, "Generate plan", {
      purpose: "Global Next Action opens tug-barge assignment page",
    });
    await waitForHash(cdp, "/operations/tug-barge-assignment");
    await captureStep(cdp, {
      step: "07",
      title: "Assignment page opened",
      route: "/operations/tug-barge-assignment",
      expectedActionId: "GENERATE_PLAN",
      expectedCurrentStep: "generate_plan",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        movementCandidateRuns: 0,
        trips: 0,
      },
    });

    clicked = await clickButton(cdp, "Generate candidates", {
      purpose: "Visible page CTA derives feasible tug-barge-jetty-CTS candidates",
      exact: true,
    });
    await waitForText(cdp, "Assignment candidates generated: 6 movements", 30_000);
    await waitForAssistantNext(cdp, "GENERATE_PLAN", "/operations/tug-barge-assignment");
    await captureStep(cdp, {
      step: "08",
      title: "Assignment candidates generated",
      route: "/operations/tug-barge-assignment",
      expectedActionId: "GENERATE_PLAN",
      expectedCurrentStep: "generate_plan",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        minPlanVersions: 1,
        movementCandidateRuns: 1,
        movementCandidateCovered: 6,
        movementCandidateMovements: 6,
        trips: 0,
      },
    });

    clicked = await clickButton(cdp, "Regenerate plan", {
      purpose: "Visible page CTA generates the operator plan",
      exact: true,
    });
    await waitForText(cdp, "Schedule generated", 25_000);
    await waitForFlowState(cdp, { currentStep: "submit_approval", status: "active" });
    await waitForAssistantNext(cdp, "SUBMIT_APPROVAL", "/operations/tug-barge-assignment");
    await captureStep(cdp, {
      step: "09",
      title: "Plan generated from clean demand",
      route: "/operations/tug-barge-assignment",
      expectedActionId: "SUBMIT_APPROVAL",
      expectedCurrentStep: "submit_approval",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        minPlanVersions: 1,
        trips: 6,
        movementCandidateRuns: 1,
        movementCandidateCovered: 6,
        tripsWithCandidateProvenance: 6,
        generatedFromMovementCandidates: true,
        blockingConflicts: 0,
      },
    });

    clicked = await clickButton(cdp, "Submit approval", {
      purpose: "Global Next Action opens approval-submission page",
    });
    await waitForHash(cdp, "/schedule/published-plan");
    await captureStep(cdp, {
      step: "10",
      title: "Published-plan page opened",
      route: "/schedule/published-plan",
      expectedActionId: "SUBMIT_APPROVAL",
      expectedCurrentStep: "submit_approval",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
    });

    clicked = await clickButton(cdp, "Submit approval", {
      purpose: "Visible page CTA creates the approval request",
      exact: true,
    });
    await waitForFlowState(cdp, { currentStep: "approve_plan", status: "blocked" });
    let approvalRouteOpened = await hashIncludes(cdp, "/approvals/publishing");
    if (!approvalRouteOpened) {
      await waitForAssistantNext(cdp, "APPROVE_PLAN", "/schedule/published-plan");
      await navigateHash(cdp, "/approvals/publishing");
      clicked = { ...clicked, text: `${clicked.text}; route /approvals/publishing` };
    }
    await waitForHash(cdp, "/approvals/publishing");
    await waitForText(cdp, "Approve", 20_000);
    await waitForAssistantNext(cdp, "APPROVE_PLAN", "/approvals/publishing");
    await captureStep(cdp, {
      step: "11",
      title: "Approval request submitted",
      route: "/approvals/publishing",
      expectedActionId: "APPROVE_PLAN",
      expectedCurrentStep: "approve_plan",
      expectedFlowStatus: "blocked",
      clickedCtaLabel: clicked.text,
      expectations: {
        minApprovalRequests: 1,
        minPendingApprovals: 1,
      },
    });

    clicked = await clickButton(cdp, "Approve", {
      purpose: "Visible page CTA records first authority approval",
      exact: true,
    });
    await waitForText(cdp, "Approved", 20_000);
    await waitForFlowState(cdp, { currentStep: "approve_plan", status: "blocked" });
    await waitForAssistantNext(cdp, "APPROVE_PLAN", "/approvals/publishing");
    await captureStep(cdp, {
      step: "12",
      title: "First authority approved",
      route: "/approvals/publishing",
      expectedActionId: "APPROVE_PLAN",
      expectedCurrentStep: "approve_plan",
      expectedFlowStatus: "blocked",
      clickedCtaLabel: clicked.text,
      expectations: {
        minApprovalDecisions: 1,
      },
    });

    clicked = await clickButton(cdp, "Approve", {
      purpose: "Visible page CTA records second authority approval",
      exact: true,
    });
    await waitForText(cdp, "Publish plan", 20_000);
    await waitForFlowState(cdp, { currentStep: "run_publishability_check", status: "active" });
    await waitForAssistantNext(cdp, "RUN_PUBLISHABILITY_CHECK", "/approvals/publishing");
    await captureStep(cdp, {
      step: "13",
      title: "All approvals complete",
      route: "/approvals/publishing",
      expectedActionId: "RUN_PUBLISHABILITY_CHECK",
      expectedCurrentStep: "run_publishability_check",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        minApprovalDecisions: 2,
        approvalsComplete: true,
      },
    });

    clicked = await clickButton(cdp, "Check publishability", {
      purpose: "Visible page CTA computes the publishability gate before manual publish",
      domClick: true,
      exact: true,
    });
    await waitForText(cdp, "Publishability checked", 25_000);
    await waitForFlowState(cdp, { currentStep: "publish_plan", status: "active" });
    await waitForAssistantNext(cdp, "PUBLISH_PLAN", "/approvals/publishing");
    await captureStep(cdp, {
      step: "14",
      title: "Publishability gate cleared",
      route: "/approvals/publishing",
      expectedActionId: "PUBLISH_PLAN",
      expectedCurrentStep: "publish_plan",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        approvalsComplete: true,
        minPublishabilityAssessments: 1,
        publishabilityAllowsPublish: true,
      },
    });

    clicked = await clickButton(cdp, "Publish plan", {
      purpose: "Visible page CTA manually publishes the plan",
      exact: true,
    });
    await waitForText(cdp, "Published", 25_000);
    await waitForFlowState(cdp, { currentStep: "generate_export", status: "active" });
    await waitForAssistantNext(cdp, "GENERATE_EXPORT", "/approvals/publishing");
    await captureStep(cdp, {
      step: "15",
      title: "Plan manually published",
      route: "/approvals/publishing",
      expectedActionId: "GENERATE_EXPORT",
      expectedCurrentStep: "generate_export",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        minPublishedSnapshots: 1,
      },
    });

    clicked = await clickButton(cdp, "Generate governed export", {
      purpose: "Global Next Action opens governed export page",
    });
    await waitForHash(cdp, "/admin/export-handoff");
    await captureStep(cdp, {
      step: "16",
      title: "Export handoff page opened",
      route: "/admin/export-handoff",
      expectedActionId: "GENERATE_EXPORT",
      expectedCurrentStep: "generate_export",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
    });

    clicked = await clickButton(cdp, "Printable schedule", {
      purpose: "Visible page CTA generates the governed export",
      domClick: true,
    });
    await waitForText(cdp, "Export generated", 25_000);
    await waitForFlowState(cdp, { currentStep: "", status: "completed" });
    await captureStep(cdp, {
      step: "17",
      title: "Governed export generated",
      route: "/admin/export-handoff",
      expectedActionId: null,
      expectedCurrentStep: "",
      expectedFlowStatus: "completed",
      clickedCtaLabel: clicked.text,
      expectations: {
        minExports: 1,
        minPublishedSnapshots: 1,
        approvalsComplete: true,
        trips: 6,
        tripsWithCandidateProvenance: 6,
        generatedFromMovementCandidates: true,
      },
    });

    const finalFlow = await getFlow(cdp);
    const finalDomain = await domainState(cdp);
    evidence.finalAssertions = {
      flowRunId: evidence.preparedFlow.flowRunId,
      flowKey: evidence.preparedFlow.flowKey,
      flowCompleted: finalFlow.status === "completed",
      activePublishedSnapshotExists: finalDomain.publishedSnapshots >= 1,
      approvalsComplete: finalDomain.approvalsComplete,
      publishabilityAllowsPublish: finalDomain.publishabilityAllowsPublish,
      generatedExportExists: finalDomain.exports >= 1,
      movementCandidateCovered: finalDomain.movementCandidateCovered,
      generatedTrips: finalDomain.trips,
      tripsWithCandidateProvenance: finalDomain.tripsWithCandidateProvenance,
    };
    assertCondition(evidence.finalAssertions.flowCompleted, "Final flow is not completed.");
    assertCondition(
      evidence.finalAssertions.activePublishedSnapshotExists,
      "No published snapshot exists after publish CTA.",
    );
    assertCondition(
      evidence.finalAssertions.approvalsComplete,
      "Approvals are not complete after approval CTAs.",
    );
    assertCondition(
      evidence.finalAssertions.publishabilityAllowsPublish,
      "Publishability was not clear before publish CTA.",
    );
    assertCondition(
      evidence.finalAssertions.generatedExportExists,
      "No export exists after export CTA.",
    );
    assertCondition(
      evidence.finalAssertions.movementCandidateCovered === 6,
      `Expected 6 candidate-covered movements, got ${evidence.finalAssertions.movementCandidateCovered}.`,
    );
    assertCondition(
      evidence.finalAssertions.generatedTrips === 6,
      `Expected 6 generated trips, got ${evidence.finalAssertions.generatedTrips}.`,
    );
    assertCondition(
      evidence.finalAssertions.tripsWithCandidateProvenance === 6,
      `Expected 6 trips with movement candidate provenance, got ${evidence.finalAssertions.tripsWithCandidateProvenance}.`,
    );

    await writeFile(EVIDENCE_JSON, JSON.stringify(evidence, null, 2));
    console.log(JSON.stringify({
      ok: true,
      flowRunId: evidence.preparedFlow.flowRunId,
      steps: evidence.steps.length,
      evidenceJson: EVIDENCE_JSON,
      screenshots: SCREENSHOT_DIR,
    }, null, 2));
  } finally {
    chrome.kill();
    await rm(profile, { recursive: true, force: true }).catch(() => undefined);
  }
}

function prepareDbTruth() {
  const output = runDockerManage([
    "operator_trial_practice",
    "prepare-db-truth",
    "--flow",
    "happy-path",
    "--json",
  ]);
  return parseJsonPayload(output);
}

function runDockerManage(args) {
  const result = spawnSync(
    "docker",
    ["compose", "exec", "-T", "api", "python", "manage.py", ...args],
    {
      cwd: ROOT,
      encoding: "utf8",
      maxBuffer: 1024 * 1024 * 8,
    },
  );
  if (result.status !== 0) {
    throw new Error(
      `manage.py ${args.join(" ")} failed\nSTDOUT:\n${result.stdout}\nSTDERR:\n${result.stderr}`,
    );
  }
  return result.stdout;
}

function parseJsonPayload(output) {
  const firstBrace = output.indexOf("{");
  const lastBrace = output.lastIndexOf("}");
  if (firstBrace === -1 || lastBrace === -1 || lastBrace < firstBrace) {
    throw new Error(`Could not find JSON payload in command output:\n${output}`);
  }
  return JSON.parse(output.slice(firstBrace, lastBrace + 1));
}

async function captureStep(
  cdp,
  {
    step,
    title,
    route,
    expectedActionId,
    expectedCurrentStep,
    expectedFlowStatus,
    clickedCtaLabel,
    expectations = {},
  },
) {
  await waitForApp(cdp);
  const assistant = await assistantState(cdp, route);
  const flow = await getFlow(cdp);
  const currentStep = flow.current_step_key
    ? flow.step_runs.find((item) => item.step_key === flow.current_step_key)
    : null;
  const domain = await domainState(cdp);
  assertFlowAndAssistant({
    assistant,
    flow,
    expectedActionId,
    expectedCurrentStep,
    expectedFlowStatus,
  });
  assertDomainState(domain, expectations);

  const screenshotName = `${step}_${slug(title)}.png`;
  const screenshot = path.join(SCREENSHOT_DIR, screenshotName);
  const png = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });
  await writeFile(screenshot, Buffer.from(png.data, "base64"));

  evidence.steps.push({
    step,
    title,
    route,
    screenshot,
    flowRunId: flow.run_id,
    flowKey: flow.flow_definition?.flow_key ?? null,
    flowStatus: flow.status,
    currentStep: flow.current_step_key,
    flowStepStatus: currentStep?.status ?? (flow.status === "completed" ? "completed" : null),
    expectedActionId,
    actualGlobalActionId: assistant.global_next_action?.action_id ?? null,
    actualGlobalLabel: assistant.global_next_action?.label ?? null,
    clickedCtaLabel,
    assistantFlow: assistant.flow ?? null,
    domainState: domain,
    recentFlowEvents: flow.recent_events?.slice(0, 5).map((event) => ({
      eventType: event.event_type,
      stepKey: event.step_key,
      actionId: event.action_id,
      route: event.route,
      metadata: event.metadata,
    })) ?? [],
  });
}

function assertFlowAndAssistant({
  assistant,
  flow,
  expectedActionId,
  expectedCurrentStep,
  expectedFlowStatus,
}) {
  assertCondition(
    flow.run_id === evidence.preparedFlow.flowRunId,
    `Expected flow ${evidence.preparedFlow.flowRunId}, got ${flow.run_id}.`,
  );
  assertCondition(
    flow.flow_definition?.flow_key === "operator_happy_path_v1",
    `Expected operator_happy_path_v1, got ${flow.flow_definition?.flow_key}.`,
  );
  assertCondition(
    flow.status === expectedFlowStatus,
    `Expected flow status ${expectedFlowStatus}, got ${flow.status}.`,
  );
  assertCondition(
    flow.current_step_key === expectedCurrentStep,
    `Expected current step ${expectedCurrentStep}, got ${flow.current_step_key}.`,
  );
  assertCondition(
    assistant.flow === null || assistant.flow?.flow_run_id === flow.run_id,
    `Assistant flow run mismatch: ${assistant.flow?.flow_run_id}.`,
  );
  if (expectedActionId) {
    assertCondition(
      assistant.global_next_action?.action_id === expectedActionId,
      `Expected assistant action ${expectedActionId}, got ${assistant.global_next_action?.action_id}.`,
    );
  }
}

function assertDomainState(domain, expectations) {
  const checks = [
    ["voyages", domain.voyages],
    ["plans", domain.plans],
    ["publishedSnapshots", domain.publishedSnapshots],
    ["exports", domain.exports],
    ["cargoLayerSteps", domain.cargoLayerSteps],
    ["sequenceViolations", domain.sequenceViolations],
    ["tideWindows", domain.tideWindows],
    ["bridgeWindows", domain.bridgeWindows],
    ["constraintChecks", domain.constraintChecks],
    ["trips", domain.trips],
    ["blockingConflicts", domain.blockingConflicts],
    ["movementCandidateRuns", domain.movementCandidateRuns],
    ["movementCandidateCovered", domain.movementCandidateCovered],
    ["movementCandidateMovements", domain.movementCandidateMovements],
    ["tripsWithCandidateProvenance", domain.tripsWithCandidateProvenance],
  ];
  for (const [key, actual] of checks) {
    if (expectations[key] !== undefined) {
      assertCondition(actual === expectations[key], `Expected ${key}=${expectations[key]}, got ${actual}.`);
    }
  }
  const minimums = [
    ["minVoyages", "voyages"],
    ["minCargoLayerSteps", "cargoLayerSteps"],
    ["minFlowEvents", "flowEvents"],
    ["minTideWindows", "tideWindows"],
    ["minBridgeWindows", "bridgeWindows"],
    ["minConstraintChecks", "constraintChecks"],
    ["minPlanVersions", "planVersions"],
    ["minTrips", "trips"],
    ["minApprovalRequests", "approvalRequests"],
    ["minPendingApprovals", "pendingApprovals"],
    ["minApprovalDecisions", "approvalDecisions"],
    ["minPublishabilityAssessments", "publishabilityAssessments"],
    ["minPublishedSnapshots", "publishedSnapshots"],
    ["minExports", "exports"],
  ];
  for (const [expectationKey, domainKey] of minimums) {
    if (expectations[expectationKey] !== undefined) {
      assertCondition(
        domain[domainKey] >= expectations[expectationKey],
        `Expected ${domainKey}>=${expectations[expectationKey]}, got ${domain[domainKey]}.`,
      );
    }
  }
  if (expectations.approvalsComplete !== undefined) {
    assertCondition(
      domain.approvalsComplete === expectations.approvalsComplete,
      `Expected approvalsComplete=${expectations.approvalsComplete}, got ${domain.approvalsComplete}.`,
    );
  }
  if (expectations.publishabilityAllowsPublish !== undefined) {
    assertCondition(
      domain.publishabilityAllowsPublish === expectations.publishabilityAllowsPublish,
      `Expected publishabilityAllowsPublish=${expectations.publishabilityAllowsPublish}, got ${domain.publishabilityAllowsPublish}.`,
    );
  }
  if (expectations.generatedFromMovementCandidates !== undefined) {
    assertCondition(
      domain.generatedFromMovementCandidates === expectations.generatedFromMovementCandidates,
      `Expected generatedFromMovementCandidates=${expectations.generatedFromMovementCandidates}, got ${domain.generatedFromMovementCandidates}.`,
    );
  }
}

async function assistantState(cdp, route) {
  return pageFetchJson(
    cdp,
    `/api/assistant/next-actions/?route=${encodeURIComponent(route)}&mode=supervisor`,
  );
}

async function getFlow(cdp) {
  return pageFetchJson(cdp, `/api/flows/${evidence.preparedFlow.flowRunId}/`);
}

async function domainState(cdp) {
  const [planning, scheduling, exportsOverview, dashboard] = await Promise.all([
    pageFetchJson(cdp, "/api/planning/overview/").catch(() => null),
    pageFetchJson(cdp, "/api/scheduling/overview/").catch(() => null),
    pageFetchJson(cdp, "/api/exports/overview/").catch(() => null),
    pageFetchJson(cdp, "/api/dashboard/situation/").catch(() => null),
  ]);
  const approvalRequests = scheduling?.approvalRequests ?? [];
  const candidateRun = scheduling?.movementAssignmentCandidateRun ?? null;
  const trips = scheduling?.trips ?? [];
  const approvalDecisions = approvalRequests.reduce(
    (total, request) => total + (request.decisions?.length ?? 0),
    0,
  );
  return {
    importJobs: planning?.importJobs?.length ?? 0,
    voyages: planning?.voyages?.length ?? 0,
    cargoLayerSteps: planning?.cargoLayerSteps?.length ?? 0,
    sequenceViolations: planning?.validation?.sequenceViolations ?? 0,
    tideWindows: planning?.tideWindows?.length ?? 0,
    bridgeWindows: planning?.bridgeWindows?.length ?? 0,
    constraintChecks: planning?.constraintChecks?.length ?? 0,
    plans: scheduling?.plans?.length ?? 0,
    planVersions: scheduling?.planVersions?.length ?? 0,
    activePlanVersionStatus: scheduling?.activePlanVersion?.status ?? null,
    activePlanVersionValidation: scheduling?.activePlanVersion?.validation_status ?? null,
    trips: trips.length,
    movementCandidateRuns: candidateRun ? 1 : 0,
    movementCandidateMovements: Number(candidateRun?.metadata?.movementCount ?? 0),
    movementCandidateCovered: Number(candidateRun?.metadata?.coveredMovementCount ?? 0),
    movementCandidateCount: scheduling?.movementAssignmentCandidates?.length ?? 0,
    tripsWithCandidateProvenance: trips.filter((trip) => (
      trip.selection_reason?.reason_code === "MOVEMENT_ASSIGNMENT_CANDIDATE"
      || trip.selection_reason?.reasonCode === "MOVEMENT_ASSIGNMENT_CANDIDATE"
    )).length,
    generatedFromMovementCandidates: Boolean(
      scheduling?.activePlanVersion?.summary?.generatedFromMovementCandidates,
    ),
    assignmentCandidateRunId: scheduling?.activePlanVersion?.summary?.assignmentCandidateRunId ?? null,
    blockingConflicts: scheduling?.validation?.blockingConflictCount ?? 0,
    approvalRequests: approvalRequests.length,
    pendingApprovals: scheduling?.validation?.approvalPendingCount ?? 0,
    approvalDecisions,
    publishabilityStatus: scheduling?.publishabilityAssessment?.status ?? null,
    publishabilityBlockers: scheduling?.publishabilityAssessment?.blocking_reason_count ?? 0,
    publishabilityWarnings: scheduling?.publishabilityAssessment?.warning_count ?? 0,
    publishabilityAssessments: scheduling?.publishabilityAssessment ? 1 : 0,
    publishabilityAllowsPublish: ["publishable", "warning"].includes(
      scheduling?.publishabilityAssessment?.status ?? "",
    ),
    approvalsComplete: approvalRequests.some((request) => request.status === "approved")
      || approvalRequests.some((request) => request.status === "published"),
    publishedSnapshots: scheduling?.publishedSnapshots?.length ?? 0,
    exports: exportsOverview?.exports?.length ?? 0,
    flowEvents: (await getFlow(cdp)).recent_events?.length ?? 0,
    dashboardPublishState: dashboard?.planRisk?.publishState ?? null,
  };
}

async function waitForFlowState(cdp, { currentStep, status }, timeoutMs = 20_000) {
  const started = Date.now();
  let lastFlow = null;
  while (Date.now() - started < timeoutMs) {
    lastFlow = await getFlow(cdp).catch(() => null);
    if (lastFlow?.status === status && lastFlow.current_step_key === currentStep) {
      return lastFlow;
    }
    await delay(500);
  }
  throw new Error(
    `Timed out waiting for flow state ${status}/${currentStep}. Last flow: ${JSON.stringify(lastFlow)}`,
  );
}

async function waitForAssistantNext(cdp, expectedActionId, route, timeoutMs = 20_000) {
  const started = Date.now();
  let lastAssistant = null;
  while (Date.now() - started < timeoutMs) {
    lastAssistant = await assistantState(cdp, route).catch(() => null);
    if (lastAssistant?.global_next_action?.action_id === expectedActionId) {
      return lastAssistant;
    }
    await delay(500);
  }
  throw new Error(
    `Timed out waiting for assistant action ${expectedActionId}. Last assistant: ${JSON.stringify(lastAssistant)}`,
  );
}

async function loginIfNeeded(cdp) {
  const meStatus = await evalAsync(
    cdp,
    "fetch('/api/me/', { credentials: 'include' }).then((response) => response.status).catch(() => 0)",
  );
  if (meStatus === 200) {
    return;
  }
  await waitForText(cdp, "Access the operations workspace", 15_000);
  const result = await evalAsync(
    cdp,
    `
      (async () => {
        const csrf = await fetch('/api/auth/csrf/', { credentials: 'include' })
          .then((response) => response.json())
          .then((body) => body.csrfToken);
        const response = await fetch('/api/auth/login/', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: JSON.stringify({
            username: ${JSON.stringify(USERNAME)},
            password: ${JSON.stringify(PASSWORD)}
          })
        });
        const me = await fetch('/api/me/', { credentials: 'include' });
        return { status: response.status, meStatus: me.status };
      })()
    `,
  );
  if (result.status !== 200) {
    throw new Error(`Login failed with status ${result.status}`);
  }
  if (result.meStatus !== 200) {
    throw new Error(`Login did not create an authenticated session; /me returned ${result.meStatus}`);
  }
  await cdp.send("Page.reload", { ignoreCache: true });
  await waitForApp(cdp);
}

async function clickButton(cdp, text, options = {}) {
  await waitForApp(cdp);
  let match = await findButton(cdp, text, options);
  if (!match) {
    throw new Error(`Button not found: ${text}`);
  }
  if (match.rect.y < 0 || match.rect.y + match.rect.height > 1000) {
    await scrollButtonIntoView(cdp, match.index);
    await delay(500);
    match = await findButton(cdp, text, options);
    if (!match) throw new Error(`Button not found after scroll: ${text}`);
  }
  if (match.disabled) {
    throw new Error(`Button disabled: ${text}`);
  }
  if (options.domClick) {
    await clickButtonByIndex(cdp, match.index);
  } else {
    const x = match.rect.x + match.rect.width / 2;
    const y = match.rect.y + match.rect.height / 2;
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x,
      y,
      button: "left",
      clickCount: 1,
    });
    await cdp.send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x,
      y,
      button: "left",
      clickCount: 1,
    });
  }
  const click = {
    purpose: options.purpose ?? `Click ${text}`,
    target: text,
    text: match.text,
    matchCount: match.matchCount,
    route: await evalAsync(cdp, "location.hash"),
    clickedAt: new Date().toISOString(),
  };
  evidence.clicks.push(click);
  await delay(options.afterMs ?? 1800);
  return click;
}

async function findButton(cdp, text, { exact = false } = {}) {
  const matches = await evalAsync(
    cdp,
    `
      (() => {
        const needle = ${JSON.stringify(text)};
        const normalizedNeedle = needle.toLowerCase();
        const exact = ${JSON.stringify(exact)};
        const buttons = Array.from(document.querySelectorAll('button'));
        const matches = buttons
          .map((button, index) => {
            const rect = button.getBoundingClientRect();
            return {
              index,
              text: button.innerText.trim().replace(/\\s+/g, ' '),
              disabled: button.disabled,
              rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
              visible: rect.width > 0 && rect.height > 0,
            };
          })
          .filter((button) => button.visible)
          .filter((button) => {
            const normalizedText = button.text.toLowerCase();
            return exact
              ? normalizedText === normalizedNeedle
              : normalizedText.includes(normalizedNeedle);
          });
        return matches.map((button) => ({ ...button, matchCount: matches.length }));
      })()
    `,
  );
  return matches[0] ?? null;
}

async function scrollButtonIntoView(cdp, index) {
  await evalAsync(
    cdp,
    `
      (() => {
        const button = Array.from(document.querySelectorAll('button'))[${JSON.stringify(index)}];
        if (!button) return false;
        button.scrollIntoView({ block: 'center', inline: 'nearest' });
        return true;
      })()
    `,
  );
}

async function clickButtonByIndex(cdp, index) {
  await evalAsync(
    cdp,
    `
      (() => {
        const button = Array.from(document.querySelectorAll('button'))[${JSON.stringify(index)}];
        if (!button) return false;
        button.click();
        return true;
      })()
    `,
  );
}

async function pageFetchJson(cdp, apiPath) {
  return evalAsync(
    cdp,
    `
      await fetch(${JSON.stringify(apiPath)}, { credentials: 'include' })
        .then(async (response) => {
          if (!response.ok) throw new Error(String(response.status));
          return response.json();
        })
    `,
  );
}

async function bodyText(cdp) {
  return evalAsync(cdp, "document.body.innerText");
}

async function waitForText(cdp, text, timeoutMs = 10_000) {
  const start = Date.now();
  let lastBody = "";
  while (Date.now() - start < timeoutMs) {
    const body = await bodyText(cdp).catch(() => "");
    lastBody = body;
    if (body.toLowerCase().includes(text.toLowerCase())) return;
    await delay(500);
  }
  throw new Error(`Timed out waiting for text: ${text}. Body sample: ${lastBody.slice(0, 700)}`);
}

async function waitForHash(cdp, hashPath, timeoutMs = 10_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const url = await evalAsync(cdp, "location.href").catch(() => "");
    if (url.includes(`#${hashPath}`)) return;
    await delay(400);
  }
  throw new Error(`Timed out waiting for route: ${hashPath}`);
}

async function hashIncludes(cdp, hashPath) {
  const url = await evalAsync(cdp, "location.href").catch(() => "");
  return url.includes(`#${hashPath}`);
}

async function navigateHash(cdp, hashPath) {
  await evalAsync(cdp, `location.hash = ${JSON.stringify(hashPath)}`);
  await delay(500);
}

async function waitForApp(cdp) {
  await waitForExpression(
    cdp,
    "document.readyState === 'complete' || document.readyState === 'interactive'",
    15_000,
  );
  await delay(500);
}

async function waitForExpression(cdp, expression, timeoutMs = 10_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const value = await evalValue(cdp, expression).catch(() => false);
    if (value) return;
    await delay(250);
  }
  throw new Error(`Timed out waiting for expression: ${expression}`);
}

async function evalAsync(cdp, expression) {
  const trimmedExpression = expression.trim().replace(/;+\s*$/, "");
  const response = await cdp.send("Runtime.evaluate", {
    expression: `(async () => { return (${trimmedExpression}); })()`,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    const detail = response.exceptionDetails.exception?.description || response.exceptionDetails.text;
    throw new Error(detail);
  }
  return response.result.value;
}

async function evalValue(cdp, expression) {
  const response = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    return false;
  }
  return response.result.value;
}

async function waitForHttpOk(url, timeoutMs = 45_000) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (response.ok) return;
      lastError = new Error(`${response.status} ${response.statusText}`);
    } catch (error) {
      lastError = error;
    }
    await delay(500);
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
}

async function waitForDebuggerUrl(port) {
  const listUrl = `http://127.0.0.1:${port}/json/list`;
  const start = Date.now();
  while (Date.now() - start < 15_000) {
    try {
      const response = await fetch(listUrl);
      if (response.ok) {
        const targets = await response.json();
        const page = targets.find((target) => target.type === "page");
        if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
      }
    } catch {
      // Browser debugger is still starting.
    }
    await delay(250);
  }
  throw new Error("Chrome debugger did not start.");
}

function chromeCandidates() {
  if (process.env.CHROME_PATH) return [process.env.CHROME_PATH];
  if (process.platform === "win32") {
    return [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    ];
  }
  return [
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ];
}

function findBrowser() {
  const browserPath = chromeCandidates().find((candidate) => existsSync(candidate));
  if (!browserPath) {
    throw new Error("Chrome/Edge was not found. Set CHROME_PATH to a Chromium-compatible browser.");
  }
  return browserPath;
}

async function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
  });
}

function assertCondition(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function slug(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

class CdpClient {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (!message.id) return;
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) {
        pending.reject(new Error(message.error.message));
      } else {
        pending.resolve(message.result ?? {});
      }
    };
  }

  static async connect(wsUrl) {
    const ws = new WebSocket(wsUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });
    return new CdpClient(ws);
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const payload = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(payload);
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP timeout: ${method}`));
        }
      }, 30_000);
    });
  }
}

await main();
