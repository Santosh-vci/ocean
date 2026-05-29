import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, rm, writeFile } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APP_URL = process.env.PHASE6_RECOVERY_APP_URL ?? "http://localhost:8080";
const USERNAME = process.env.PHASE6_RECOVERY_USER ?? "admin@coalflow.local";
const PASSWORD = process.env.PHASE6_RECOVERY_PASSWORD ?? "admin12345";
const EVIDENCE_DIR = path.join(ROOT, "docs/evidence/phase6_recovery_flow");
const SCREENSHOT_DIR = path.join(EVIDENCE_DIR, "screenshots");
const EVIDENCE_JSON = path.join(EVIDENCE_DIR, "phase6_recovery_flow_capture.json");
const FINAL_STATE_JSON = path.join(EVIDENCE_DIR, "phase6_recovery_final_state.json");

const evidence = {
  preparedAt: new Date().toISOString(),
  appUrl: APP_URL,
  preparedFlow: null,
  steps: [],
  clicks: [],
  finalAssertions: {},
};

async function main() {
  await mkdir(SCREENSHOT_DIR, { recursive: true });
  await waitForHttpOk(APP_URL);

  evidence.preparedFlow = prepareDbTruth();

  const browserPath = findBrowser();
  const port = await getFreePort();
  const profile = path.join(os.tmpdir(), `coalflow-phase6-recovery-${Date.now()}`);
  await rm(profile, { recursive: true, force: true });
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
    await waitForAssistantNext(cdp, "OPEN_EXCEPTION_CENTER", "/dashboard/situation");

    await captureStep(cdp, {
      step: "01",
      title: "Prepared Phase 5 plus recovery flow",
      route: "/dashboard/situation",
      expectedActionId: "GENERATE_RECOVERY_OPTIONS",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "generate_recovery_options",
      expectedFlowStatus: "active",
      clickedCtaLabel: null,
      expectations: {
        minVoyages: 3,
        minTrips: 6,
        minOpenConflicts: 2,
        recommendations: 0,
        rootCauseAssessments: 0,
        scenarios: 0,
      },
    });

    let clicked = await clickButton(cdp, "Open Exception Center", {
      purpose: "Global Next Action opens Exception Center for recovery option generation",
    });
    await waitForHash(cdp, "/exceptions/center");
    await captureStep(cdp, {
      step: "02",
      title: "Exception Center opened from Next Action",
      route: "/exceptions/center",
      expectedActionId: "GENERATE_RECOVERY_OPTIONS",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "generate_recovery_options",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: { minOpenConflicts: 2 },
    });

    clicked = await clickButton(cdp, "Generate recovery options", {
      purpose: "Visible page CTA creates recovery snapshot and optimizer run",
      exact: true,
    });
    await waitForHash(cdp, "/recovery/recommendations");
    await waitForText(cdp, "Ranked recovery options", 25_000);
    await waitForFlowState(cdp, { currentStep: "validate_root_cause", status: "active" });
    await captureStep(cdp, {
      step: "03",
      title: "Recovery recommendations generated",
      route: "/recovery/recommendations",
      expectedActionId: "VALIDATE_ROOT_CAUSE_REPAIR",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "validate_root_cause",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        minRecoverySnapshots: 1,
        minOptimizerRuns: 1,
        minRecommendations: 1,
      },
    });

    clicked = await clickButton(cdp, "Validate root cause", {
      purpose: "Visible page CTA records root-cause repair assessment",
      exact: true,
    });
    await waitForText(cdp, "Root-cause validation recorded", 25_000);
    await waitForFlowState(cdp, { currentStep: "materialize_recommendation", status: "active" });
    await captureStep(cdp, {
      step: "04",
      title: "Root-cause validation recorded",
      route: "/recovery/recommendations",
      expectedActionId: "MATERIALIZE_RECOVERY_RECOMMENDATION",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "materialize_recommendation",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: { minRootCauseAssessments: 1 },
    });

    clicked = await clickButton(cdp, "Test as scenario", {
      purpose: "Visible page CTA materializes recommendation into a governed scenario",
      exact: true,
    });
    await waitForHash(cdp, "/simulation/workspace");
    await waitForText(cdp, "Simulation Workspace", 25_000);
    await waitForFlowState(cdp, { currentStep: "promote_scenario", status: "active" });
    await captureStep(cdp, {
      step: "05",
      title: "Scenario materialized with simulation result",
      route: "/simulation/workspace",
      expectedActionId: "PROMOTE_SCENARIO",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "promote_scenario",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        minScenarios: 1,
        minScenarioRuns: 1,
      },
    });

    clicked = await clickButton(cdp, "Run simulation", {
      purpose: "Visible page CTA reruns the scenario before promotion",
      exact: true,
    });
    await waitForText(cdp, "Simulation complete", 25_000);
    await captureStep(cdp, {
      step: "06",
      title: "Scenario simulation rerun visible",
      route: "/simulation/workspace",
      expectedActionId: "PROMOTE_SCENARIO",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "promote_scenario",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: { minScenarioRuns: 1 },
    });

    clicked = await clickButton(cdp, "Promote to proposed", {
      purpose: "Visible page CTA promotes scenario into a proposed recovery plan",
      exact: true,
    });
    await waitForText(cdp, "Scenario promoted", 25_000);
    await waitForFlowState(cdp, { currentStep: "repair_remaining_conflicts", status: "blocked" });
    await waitForAssistantNext(cdp, "OPEN_EXCEPTION_CENTER", "/simulation/workspace");
    await captureStep(cdp, {
      step: "07",
      title: "Promoted scenario returns to remaining blockers",
      route: "/simulation/workspace",
      expectedActionId: "REPAIR_PLAN_CONFLICTS",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "repair_remaining_conflicts",
      expectedFlowStatus: "blocked",
      clickedCtaLabel: clicked.text,
      expectations: {
        minScenarios: 1,
        minOpenConflicts: 1,
      },
    });

    clicked = await clickButton(cdp, "Open Exception Center", {
      purpose: "Next Action routes operator back to blockers for repair",
    });
    await waitForHash(cdp, "/exceptions/center");
    await captureStep(cdp, {
      step: "08",
      title: "Exception Center shows remaining repair work",
      route: "/exceptions/center",
      expectedActionId: "REPAIR_PLAN_CONFLICTS",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "repair_remaining_conflicts",
      expectedFlowStatus: "blocked",
      clickedCtaLabel: clicked.text,
      expectations: { minOpenConflicts: 1 },
    });

    clicked = await clickButton(cdp, "Tide & Bridge Window", {
      purpose: "Operator opens operating windows to repair remaining navigation blockers",
      exact: true,
    });
    await waitForHash(cdp, "/constraints/tide-bridge");
    await waitForText(cdp, "Tide", 15_000);
    await captureStep(cdp, {
      step: "09",
      title: "Operating windows opened for conflict repair",
      route: "/constraints/tide-bridge",
      expectedActionId: "REPAIR_PLAN_CONFLICTS",
      expectedGlobalActionId: "OPEN_EXCEPTION_CENTER",
      expectedCurrentStep: "repair_remaining_conflicts",
      expectedFlowStatus: "blocked",
      clickedCtaLabel: clicked.text,
    });

    clicked = await clickButton(cdp, "Enter operating windows", {
      purpose: "Visible page CTA applies corrected operating windows",
      exact: true,
    });
    await waitForText(cdp, "Operating windows entered", 25_000);
    await captureStep(cdp, {
      step: "10",
      title: "Corrected operating windows entered",
      route: "/constraints/tide-bridge",
      expectedActionId: "REPAIR_PLAN_CONFLICTS",
      expectedGlobalActionId: "REGENERATE_PLAN",
      expectedCurrentStep: "repair_remaining_conflicts",
      expectedFlowStatus: "blocked",
      clickedCtaLabel: clicked.text,
      expectations: {
        minTideWindows: 1,
        minBridgeWindows: 1,
      },
    });

    clicked = await clickButton(cdp, "Tug/Barge Assignment", {
      purpose: "Operator opens assignment board to regenerate against repaired constraints",
      exact: true,
    });
    await waitForHash(cdp, "/operations/tug-barge-assignment");
    clicked = await clickButton(cdp, "Regenerate plan", {
      purpose: "Visible page CTA regenerates the recovery plan and clears blockers",
      exact: true,
    });
    await waitForFlowState(cdp, { currentStep: "submit_approval", status: "active" }, 30_000);
    await waitForAssistantNext(cdp, "SUBMIT_APPROVAL", "/operations/tug-barge-assignment");
    await captureStep(cdp, {
      step: "11",
      title: "Recovery plan regenerated feasible",
      route: "/operations/tug-barge-assignment",
      expectedActionId: "SUBMIT_APPROVAL",
      expectedCurrentStep: "submit_approval",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        blockingConflicts: 0,
        minPlanVersions: 1,
      },
    });

    clicked = await clickButton(cdp, "Submit approval", {
      purpose: "Next Action opens published-plan page for approval submission",
    });
    await waitForHash(cdp, "/schedule/published-plan");
    await captureStep(cdp, {
      step: "12",
      title: "Recovery candidate ready for approval submission",
      route: "/schedule/published-plan",
      expectedActionId: "SUBMIT_APPROVAL",
      expectedCurrentStep: "submit_approval",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: { blockingConflicts: 0 },
    });

    clicked = await clickButton(cdp, "Submit approval", {
      purpose: "Visible page CTA submits recovery plan for approval",
      exact: true,
    });
    await waitForHash(cdp, "/approvals/publishing");
    await waitForFlowState(cdp, { currentStep: "approve_plan", status: "blocked" });
    await waitForAssistantNext(cdp, "APPROVE_PLAN", "/approvals/publishing");
    await captureStep(cdp, {
      step: "13",
      title: "Recovery approval request submitted",
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
      purpose: "Visible page CTA records first approval authority",
      exact: true,
    });
    await waitForText(cdp, "Approved", 25_000);
    await waitForFlowState(cdp, { currentStep: "approve_plan", status: "blocked" });
    await waitForAssistantNext(cdp, "APPROVE_PLAN", "/approvals/publishing");
    await captureStep(cdp, {
      step: "14",
      title: "First recovery approval recorded",
      route: "/approvals/publishing",
      expectedActionId: "APPROVE_PLAN",
      expectedCurrentStep: "approve_plan",
      expectedFlowStatus: "blocked",
      clickedCtaLabel: clicked.text,
      expectations: { minApprovalDecisions: 1 },
    });

    clicked = await clickButton(cdp, "Approve", {
      purpose: "Visible page CTA records second approval authority",
      exact: true,
    });
    await waitForFlowState(cdp, { currentStep: "run_publishability_check", status: "active" });
    await waitForAssistantNext(cdp, "RUN_PUBLISHABILITY_CHECK", "/approvals/publishing");
    await captureStep(cdp, {
      step: "15",
      title: "Dual recovery approval complete",
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
      purpose: "Visible page CTA computes publishability gate for recovery plan",
      domClick: true,
      exact: true,
    });
    await waitForText(cdp, "Publishability checked", 25_000);
    await waitForFlowState(cdp, { currentStep: "publish_plan", status: "active" });
    await waitForAssistantNext(cdp, "PUBLISH_PLAN", "/approvals/publishing");
    await captureStep(cdp, {
      step: "16",
      title: "Recovery publishability gate cleared",
      route: "/approvals/publishing",
      expectedActionId: "PUBLISH_PLAN",
      expectedCurrentStep: "publish_plan",
      expectedFlowStatus: "active",
      clickedCtaLabel: clicked.text,
      expectations: {
        minPublishabilityAssessments: 1,
        publishabilityAllowsPublish: true,
      },
    });

    clicked = await clickButton(cdp, "Publish plan", {
      purpose: "Visible page CTA manually publishes approved recovery plan",
      exact: true,
    });
    await waitForText(cdp, "Published", 30_000);
    await waitForFlowState(cdp, { currentStep: "", status: "completed" });
    await captureStep(cdp, {
      step: "17",
      title: "Recovery plan manually published",
      route: "/approvals/publishing",
      expectedActionId: null,
      expectedCurrentStep: "",
      expectedFlowStatus: "completed",
      clickedCtaLabel: clicked.text,
      expectations: {
        minPublishedSnapshots: 1,
        approvalsComplete: true,
        publishabilityAllowsPublish: true,
      },
    });

    const finalFlow = await getFlow(cdp);
    const finalDomain = await domainState(cdp);
    evidence.finalAssertions = {
      flowRunId: evidence.preparedFlow.flowRunId,
      flowKey: evidence.preparedFlow.flowKey,
      flowCompleted: finalFlow.status === "completed",
      recommendationsCreatedByUi: finalDomain.recommendations >= 1,
      rootCauseAssessmentExists: finalDomain.rootCauseAssessments >= 1,
      scenarioMaterializedByUi: finalDomain.scenarios >= 1,
      publishabilityAssessmentExists: finalDomain.publishabilityAssessments >= 1,
      approvalsComplete: finalDomain.approvalsComplete,
      activePublishedSnapshotExists: finalDomain.publishedSnapshots >= 1,
    };
    for (const [key, passed] of Object.entries(evidence.finalAssertions)) {
      if (key.endsWith("Id") || key === "flowKey") continue;
      assertCondition(Boolean(passed), `Final assertion failed: ${key}`);
    }
    await writeFile(EVIDENCE_JSON, JSON.stringify(evidence, null, 2));
    await writeFile(FINAL_STATE_JSON, JSON.stringify(finalDomain, null, 2));
    console.log(JSON.stringify({
      ok: true,
      flowRunId: evidence.preparedFlow.flowRunId,
      steps: evidence.steps.length,
      evidenceJson: EVIDENCE_JSON,
      finalStateJson: FINAL_STATE_JSON,
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
    "recovery",
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
    expectedGlobalActionId,
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
    expectedGlobalActionId,
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
    expectedGlobalActionId: expectedGlobalActionId ?? expectedActionId,
    actualGlobalActionId: assistant.global_next_action?.action_id ?? null,
    actualGlobalLabel: assistant.global_next_action?.label ?? null,
    clickedCtaLabel,
    assistantFlow: assistant.flow ?? null,
    domainState: domain,
    recentFlowEvents: flow.recent_events?.slice(0, 8).map((event) => ({
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
  expectedGlobalActionId,
  expectedCurrentStep,
  expectedFlowStatus,
}) {
  assertCondition(
    flow.run_id === evidence.preparedFlow.flowRunId,
    `Expected flow ${evidence.preparedFlow.flowRunId}, got ${flow.run_id}.`,
  );
  assertCondition(
    flow.flow_definition?.flow_key === "phase5_plus_recovery_v1",
    `Expected phase5_plus_recovery_v1, got ${flow.flow_definition?.flow_key}.`,
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
  const expectedGlobal = expectedGlobalActionId ?? expectedActionId;
  if (expectedGlobal) {
    assertCondition(
      assistant.global_next_action?.action_id === expectedGlobal,
      `Expected assistant action ${expectedGlobal}, got ${assistant.global_next_action?.action_id}.`,
    );
  }
}

function assertDomainState(domain, expectations) {
  const exacts = [
    ["recommendations", domain.recommendations],
    ["rootCauseAssessments", domain.rootCauseAssessments],
    ["scenarios", domain.scenarios],
    ["blockingConflicts", domain.blockingConflicts],
  ];
  for (const [key, actual] of exacts) {
    if (expectations[key] !== undefined) {
      assertCondition(actual === expectations[key], `Expected ${key}=${expectations[key]}, got ${actual}.`);
    }
  }
  const minimums = [
    ["minVoyages", "voyages"],
    ["minTrips", "trips"],
    ["minOpenConflicts", "openConflicts"],
    ["minRecoverySnapshots", "recoverySnapshots"],
    ["minOptimizerRuns", "optimizerRuns"],
    ["minRecommendations", "recommendations"],
    ["minRootCauseAssessments", "rootCauseAssessments"],
    ["minScenarios", "scenarios"],
    ["minScenarioRuns", "scenarioRuns"],
    ["minTideWindows", "tideWindows"],
    ["minBridgeWindows", "bridgeWindows"],
    ["minPlanVersions", "planVersions"],
    ["minApprovalRequests", "approvalRequests"],
    ["minPendingApprovals", "pendingApprovals"],
    ["minApprovalDecisions", "approvalDecisions"],
    ["minPublishabilityAssessments", "publishabilityAssessments"],
    ["minPublishedSnapshots", "publishedSnapshots"],
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
  const [planning, scheduling, exportsOverview] = await Promise.all([
    pageFetchJson(cdp, "/api/planning/overview/").catch(() => null),
    pageFetchJson(cdp, "/api/scheduling/overview/").catch(() => null),
    pageFetchJson(cdp, "/api/exports/overview/").catch(() => null),
  ]);
  const approvalRequests = scheduling?.approvalRequests ?? [];
  const approvalDecisions = approvalRequests.reduce(
    (total, request) => total + (request.decisions?.length ?? 0),
    0,
  );
  const scenarioRuns = (scheduling?.simulationScenarios ?? []).reduce(
    (total, scenario) => total + (scenario.runs?.length ?? 0),
    0,
  );
  return {
    voyages: planning?.voyages?.length ?? 0,
    cargoLayerSteps: planning?.cargoLayerSteps?.length ?? 0,
    tideWindows: planning?.tideWindows?.length ?? 0,
    bridgeWindows: planning?.bridgeWindows?.length ?? 0,
    plans: scheduling?.plans?.length ?? 0,
    planVersions: scheduling?.planVersions?.length ?? 0,
    trips: scheduling?.trips?.length ?? 0,
    openConflicts: (scheduling?.conflicts ?? []).filter((conflict) => !conflict.resolved_at).length,
    blockingConflicts: scheduling?.validation?.blockingConflictCount ?? 0,
    recoverySnapshots: scheduling?.recoveryInputSnapshots?.length ?? 0,
    optimizerRuns: scheduling?.optimizerRuns?.length ?? 0,
    recommendations: scheduling?.recoveryRecommendations?.length ?? 0,
    rootCauseAssessments: (scheduling?.recoveryRecommendations ?? [])
      .filter((recommendation) => recommendation.root_cause_assessment).length,
    scenarios: scheduling?.simulationScenarios?.length ?? 0,
    scenarioRuns,
    approvalRequests: approvalRequests.length,
    pendingApprovals: scheduling?.validation?.approvalPendingCount ?? 0,
    approvalDecisions,
    approvalsComplete: approvalRequests.some((request) => request.status === "approved")
      || approvalRequests.some((request) => request.status === "published"),
    publishabilityStatus: scheduling?.publishabilityAssessment?.status ?? null,
    publishabilityBlockers: scheduling?.publishabilityAssessment?.blocking_reason_count ?? 0,
    publishabilityWarnings: scheduling?.publishabilityAssessment?.warning_count ?? 0,
    publishabilityAssessments: scheduling?.publishabilityAssessment ? 1 : 0,
    publishabilityAllowsPublish: ["publishable", "warning"].includes(
      scheduling?.publishabilityAssessment?.status ?? "",
    ),
    publishedSnapshots: scheduling?.publishedSnapshots?.length ?? 0,
    exports: exportsOverview?.exports?.length ?? 0,
    activePlanVersion: scheduling?.activePlanVersion
      ? {
        planCode: scheduling.activePlanVersion.plan_code,
        versionNo: scheduling.activePlanVersion.version_no,
        status: scheduling.activePlanVersion.status,
        validationStatus: scheduling.activePlanVersion.validation_status,
      }
      : null,
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
      await fetch(${JSON.stringify(apiPath)}, { credentials: 'include', cache: 'no-store' })
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
    ws.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data);
      if (!payload.id) return;
      const pending = this.pending.get(payload.id);
      if (!pending) return;
      this.pending.delete(payload.id);
      if (payload.error) {
        pending.reject(new Error(payload.error.message));
      } else {
        pending.resolve(payload.result);
      }
    });
  }

  static async connect(wsUrl) {
    const ws = new WebSocket(wsUrl);
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve, { once: true });
      ws.addEventListener("error", reject, { once: true });
    });
    return new CdpClient(ws);
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
