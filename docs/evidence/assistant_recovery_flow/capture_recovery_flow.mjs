import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";

const ROOT = "F:/ocean";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const PORT = 9338;
const PROFILE = `${ROOT}/.tmp/chrome-assist-recovery-flow`;
const BASE_URL = "http://localhost:8080";
const START_URL = `${BASE_URL}/#/dashboard/situation`;
const EVIDENCE_DIR = `${ROOT}/docs/evidence/assistant_recovery_flow`;
const SCREENSHOT_DIR = `${EVIDENCE_DIR}/screenshots`;

const flowLog = [];

async function main() {
await mkdir(SCREENSHOT_DIR, { recursive: true });
await seedPracticeCase();
await rm(PROFILE, { recursive: true, force: true });

const chrome = spawn(
  CHROME,
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    "--window-size=1440,1000",
    START_URL,
  ],
  { stdio: "ignore" },
);

try {
  const wsUrl = await waitForDebuggerUrl();
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
  await waitForText(cdp, "COALFLOW TOWER", 15000);
  await waitForText(cdp, "Super", 15000);
  await clickButton(cdp, "Super", { purpose: "Set Assist to Super mode", exact: true });
  await waitForText(cdp, "Open Exception Center", 15000);

  await captureStep(cdp, {
    step: "01",
    route: "/dashboard/situation",
    title: "Recovery practice dashboard",
    expectedNext: "OPEN_EXCEPTION_CENTER",
    note: "The practice case starts with multiple OGV demands, a generated blocked plan, and open tide/bridge conflicts.",
  });

  await clickButton(cdp, "OGV Demand & Laycan", {
    purpose: "Operator opens the demand board to inspect multiple OGVs",
    exact: true,
  });
  await waitForHash(cdp, "/schedule/ogv-demand");
  await captureStep(cdp, {
    step: "02",
    route: "/schedule/ogv-demand",
    title: "Multiple OGV demand board",
    expectedNext: "OPEN_EXCEPTION_CENTER",
    note: "The operator confirms the training case has three OGV demands and six cargo layers before recovery work.",
  });

  await clickButton(cdp, "Tide & Bridge Window", {
    purpose: "Operator opens the constraint board to inspect missed gate evidence",
    exact: true,
  });
  await waitForHash(cdp, "/constraints/tide-bridge");
  await waitForText(cdp, "Missed gates", 15000);
  await captureStep(cdp, {
    step: "03",
    route: "/constraints/tide-bridge",
    title: "Tide and bridge missed events",
    expectedNext: "OPEN_EXCEPTION_CENTER",
    note: "The operator sees missed tide/bridge checks before entering the recovery loop.",
  });

  await clickButton(cdp, "Open Exception Center", {
    purpose: "Assistant global CTA navigates operator to exception triage",
  });
  await waitForHash(cdp, "/exceptions/center");
  await waitForText(cdp, "Generate recovery options", 15000);
  await captureStep(cdp, {
    step: "04",
    route: "/exceptions/center",
    title: "Exception Center triage",
    expectedNext: "OPEN_EXCEPTION_CENTER",
    note: "The first blocking conflict is selected and can be used as recovery input.",
  });

  await clickButton(cdp, "Generate recovery options", {
    purpose: "Page CTA builds the recovery input snapshot and optimizer run",
    exact: true,
  });
  await waitForHash(cdp, "/recovery/recommendations");
  await waitForText(cdp, "Ranked recovery options", 20000);
  await captureStep(cdp, {
    step: "05",
    route: "/recovery/recommendations",
    title: "Recommendation Console ranked options",
    expectedNext: "MATERIALIZE_RECOVERY_RECOMMENDATION",
    note: "The recovery loop ranks candidate actions and explains score, risk, delay, missed windows, and hard constraints.",
  });

  await clickButton(cdp, "Test as scenario", {
    purpose: "Recommendation CTA creates a governed scenario for the selected option",
    exact: true,
  });
  await waitForHash(cdp, "/simulation/workspace");
  await waitForText(cdp, "Simulation Workspace", 20000);
  await captureStep(cdp, {
    step: "06",
    route: "/simulation/workspace",
    title: "Simulation workspace handoff",
    expectedNext: "PROMOTE_SCENARIO",
    note: "The tested recommendation opens in Simulation Workspace with a completed scenario run.",
  });

  await clickButton(cdp, "Run simulation", {
    purpose: "Page CTA reruns the scenario so the operator can practice simulation execution",
    exact: true,
  });
  await waitForText(cdp, "Simulation complete", 20000);
  await captureStep(cdp, {
    step: "07",
    route: "/simulation/workspace",
    title: "Simulation rerun completed",
    expectedNext: "PROMOTE_SCENARIO",
    note: "The operator can compare baseline versus projected timings, resource changes, and risk flags.",
  });

  await clickButton(cdp, "Promote to proposed", {
    purpose: "Page CTA promotes the scenario output to a proposed plan candidate",
    exact: true,
  });
  await waitForText(cdp, "Scenario promoted", 20000);
  await captureStep(cdp, {
    step: "08",
    route: "/simulation/workspace",
    title: "Scenario promoted with remaining blockers",
    expectedNext: "OPEN_EXCEPTION_CENTER",
    note: "The candidate is promoted for governance, but remaining critical constraints keep publication blocked.",
  });

  await clickButton(cdp, "Open Exception Center", {
    purpose: "Assistant routes the operator back to unresolved blockers",
  });
  await waitForHash(cdp, "/exceptions/center");
  await captureStep(cdp, {
    step: "09",
    route: "/exceptions/center",
    title: "Recovery loop returns to unresolved constraints",
    expectedNext: "OPEN_EXCEPTION_CENTER",
    note: "The operator learns that a promoted scenario is not automatically publishable when hard constraints remain.",
  });

  await clickButton(cdp, "Tide & Bridge Window", {
    purpose: "Operator returns to the constraint board to implement corrected recovery windows",
    exact: true,
  });
  await waitForHash(cdp, "/constraints/tide-bridge");
  await clickButton(cdp, "Enter operating windows", {
    purpose: "Page CTA applies corrected tide and bridge operating windows",
    exact: true,
  });
  await waitForPlanningState(cdp, (planning) => planning.validation?.missedWindows === 0, 20000);
  await captureStep(cdp, {
    step: "10",
    route: "/constraints/tide-bridge",
    title: "Recovery windows implemented",
    expectedNext: "REGENERATE_PLAN",
    note: "The corrected operating windows replace the missed gate checks and clear the missed-window count.",
  });

  await clickButton(cdp, "Tug/Barge Assignment", {
    purpose: "Operator moves to the assignment board to regenerate the recovery candidate",
    exact: true,
  });
  await waitForHash(cdp, "/operations/tug-barge-assignment");
  await clickButton(cdp, "Regenerate plan", {
    purpose: "Page CTA regenerates the proposed recovery plan against corrected constraints",
    exact: true,
  });
  await waitForSchedulingState(
    cdp,
    (scheduling) => (
      scheduling.activePlanVersion?.status === "validated"
      && scheduling.activePlanVersion?.validation_status === "feasible"
      && scheduling.validation?.blockingConflictCount === 0
    ),
    30000,
  );
  await captureStep(cdp, {
    step: "11",
    route: "/operations/tug-barge-assignment",
    title: "Recovery plan regenerated feasible",
    expectedNext: "SUBMIT_APPROVAL",
    note: "The recovery candidate has been regenerated and now has no blocking conflicts.",
  });

  await clickButton(cdp, "Published Plan & Schedule", {
    purpose: "Operator reviews the feasible recovery candidate before approval",
    exact: true,
  });
  await waitForHash(cdp, "/schedule/published-plan");
  await captureStep(cdp, {
    step: "12",
    route: "/schedule/published-plan",
    title: "Feasible recovery candidate ready for approval",
    expectedNext: "SUBMIT_APPROVAL",
    note: "The active recovery plan is feasible, so Assist can move the operator into approval governance.",
  });

  await clickButton(cdp, "Submit approval", {
    purpose: "Page CTA submits the feasible recovery plan for dual-party approval",
    exact: true,
  });
  await waitForHash(cdp, "/approvals/publishing");
  await waitForSchedulingState(
    cdp,
    (scheduling) => scheduling.approvalRequests?.some((item) => item.status === "pending"),
    20000,
  );
  await captureStep(cdp, {
    step: "13",
    route: "/approvals/publishing",
    title: "Approval request submitted",
    expectedNext: "APPROVE_PLAN",
    note: "A governed approval request is open and awaiting the first authority decision.",
  });

  await clickButton(cdp, "Approve", {
    purpose: "First authority approves the recovery plan",
    exact: true,
  });
  await waitForSchedulingState(
    cdp,
    (scheduling) => {
      const request = scheduling.approvalRequests?.[0];
      return request?.decisions?.length === 1 && request.status === "pending";
    },
    20000,
  );
  await captureStep(cdp, {
    step: "14",
    route: "/approvals/publishing",
    title: "First approval recorded",
    expectedNext: "APPROVE_PLAN",
    note: "One approval is recorded; the second authority must still approve before publishing.",
  });

  await clickButton(cdp, "Approve", {
    purpose: "Second authority approves the recovery plan",
    exact: true,
  });
  await waitForSchedulingState(
    cdp,
    (scheduling) => scheduling.approvalRequests?.[0]?.status === "approved",
    20000,
  );
  await captureStep(cdp, {
    step: "15",
    route: "/approvals/publishing",
    title: "Dual approval complete",
    expectedNext: "PUBLISH_PLAN",
    note: "Both required authorities have approved the feasible recovery candidate.",
  });

  await clickButton(cdp, "Publish plan", {
    purpose: "Header CTA publishes the approved recovery plan",
    exact: true,
  });
  await waitForSchedulingState(
    cdp,
    (scheduling) => (
      scheduling.activePlanVersion?.status === "published"
      && (scheduling.publishedSnapshots?.length ?? 0) >= 1
    ),
    30000,
  );
  await captureStep(cdp, {
    step: "16",
    route: "/approvals/publishing",
    title: "Recovery plan published",
    expectedNext: "GENERATE_EXPORT",
    note: "The approved recovery plan is now the live published plan.",
  });

  await clickButton(cdp, "Exports & Handoff", {
    purpose: "Operator opens export handoff for the published recovery plan",
    exact: true,
  });
  await waitForHash(cdp, "/admin/export-handoff", 5000).catch(async () => {
    flowLog.push({
      step: "navigation",
      title: "Fallback route to export handoff",
      target: "/admin/export-handoff",
      result: "navigated",
      note: "The sidebar item was off-screen in headless capture, so the route was opened directly after the click attempt.",
    });
    await navigate(cdp, `${BASE_URL}/#/admin/export-handoff`);
    await waitForHash(cdp, "/admin/export-handoff");
  });
  await captureStep(cdp, {
    step: "17",
    route: "/admin/export-handoff",
    title: "Published recovery plan ready for handoff",
    expectedNext: "GENERATE_EXPORT",
    note: "The published plan is ready for a governed handoff artifact.",
  });

  await domClickButton(cdp, "Printable schedule", {
    exact: false,
  });
  flowLog.push({
    step: "click",
    title: "Visible export command generates the operator handoff schedule",
    target: "Printable schedule",
    result: "clicked",
  });
  await delay(4000);
  await waitForExportState(cdp, (exports) => (exports.summary?.total ?? 0) >= 1, 30000);
  await captureStep(cdp, {
    step: "18",
    route: "/admin/export-handoff",
    title: "Successful recovery handoff export generated",
    expectedNext: "REVIEW_RECOMMENDATION_PROOF_PACK",
    note: "The flow ends with a published recovery plan and a generated handoff artifact.",
  });

  await writeFinalState(cdp);
  await writeFile(`${EVIDENCE_DIR}/assist_recovery_flow_capture.json`, JSON.stringify(flowLog, null, 2));
  console.log(JSON.stringify({ ok: true, steps: flowLog.length, evidenceDir: EVIDENCE_DIR }, null, 2));
} finally {
  chrome.kill();
}
}

async function seedPracticeCase() {
  await runCommand("docker", [
    "compose",
    "exec",
    "-T",
    "api",
    "python",
    "manage.py",
    "seed_phase0",
    "--master-data-only",
  ]);
  const seedJson = await runCommand("docker", [
    "compose",
    "exec",
    "-T",
    "api",
    "python",
    "manage.py",
    "seed_assistant_recovery_practice",
    "--skip-reset",
    "--json",
  ]);
  await writeFile(`${EVIDENCE_DIR}/recovery_practice_seed_summary.json`, seedJson);
}

async function captureStep(cdp, { step, route, title, expectedNext, note }) {
  await waitForApp(cdp);
  const screen = await screenState(cdp);
  const assistant = await pageFetchJson(
    cdp,
    `/api/assistant/next-actions/?route=${encodeURIComponent(route)}&mode=supervisor`,
  );
  const dashboard = await pageFetchJson(cdp, "/api/dashboard/situation/").catch(() => null);
  const planning = await pageFetchJson(cdp, "/api/planning/overview/").catch(() => null);
  const scheduling = await pageFetchJson(cdp, "/api/scheduling/overview/").catch(() => null);
  const exports = await pageFetchJson(cdp, "/api/exports/overview/").catch(() => null);
  const png = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });
  const screenshot = `${SCREENSHOT_DIR}/${step}_${slug(title)}.png`;
  await writeFile(screenshot, Buffer.from(png.data, "base64"));
  flowLog.push({
    step,
    title,
    route,
    screenshot,
    expectedNext,
    actualGlobalNext: assistant.global_next_action?.action_id ?? null,
    actualGlobalLabel: assistant.global_next_action?.label ?? null,
    pageActions: assistant.page_actions?.map((action) => action.action_id) ?? [],
    blockedActions: assistant.blocked_actions?.map((action) => ({
      actionId: action.action_id,
      reason: action.blocked_reason || action.reason,
    })) ?? [],
    checklist: assistant.checklist ?? [],
    visibleHighlights: screen.highlights,
    url: screen.url,
    note,
    dashboardCounts: dashboard
      ? {
          activePlanVersion: dashboard.activePlanVersion?.plan_code ?? null,
          conflictSummary: dashboard.conflictSummary ?? null,
          approvalQueue: dashboard.approvalQueue ?? null,
          publishedSnapshot: dashboard.publishedSnapshot ?? null,
        }
      : null,
    planningCounts: planning
      ? {
          voyages: planning.voyages?.length ?? 0,
          cargoLayers: planning.cargoLayerSteps?.length ?? 0,
          tideWindows: planning.tideWindows?.length ?? 0,
          bridgeWindows: planning.bridgeWindows?.length ?? 0,
          constraintChecks: planning.constraintChecks?.length ?? 0,
          missedWindows: planning.validation?.missedWindows ?? 0,
          highRiskVoyages: planning.validation?.highRiskVoyages ?? 0,
        }
      : null,
    schedulingCounts: scheduling
      ? {
          activePlanVersion: scheduling.activePlanVersion
            ? `${scheduling.activePlanVersion.plan_code} V${scheduling.activePlanVersion.version_no}`
            : null,
          activePlanStatus: scheduling.activePlanVersion?.status ?? null,
          activePlanValidation: scheduling.activePlanVersion?.validation_status ?? null,
          trips: scheduling.validation?.tripCount ?? 0,
          conflicts: scheduling.validation?.conflictCount ?? 0,
          blockingConflicts: scheduling.validation?.blockingConflictCount ?? 0,
          optimizerRuns: scheduling.validation?.optimizerRunCount ?? 0,
          recommendations: scheduling.validation?.recoveryRecommendationCount ?? 0,
          scenarios: scheduling.validation?.scenarioCount ?? 0,
          approvalsPending: scheduling.validation?.approvalPendingCount ?? 0,
          recoverySnapshots: scheduling.recoveryInputSnapshots?.length ?? 0,
          publishedSnapshots: scheduling.publishedSnapshots?.length ?? 0,
        }
      : null,
    exportCounts: exports
      ? {
          total: exports.summary?.total ?? 0,
          plan: exports.summary?.plan ?? 0,
          conflict: exports.summary?.conflict ?? 0,
          scenarioDiff: exports.summary?.scenario_diff ?? 0,
          visibleExports: exports.exports?.length ?? 0,
          latestPlanExport: exports.exports?.find((item) => item.export_type === "plan")?.file_name ?? null,
        }
      : null,
  });
}

async function writeFinalState(cdp) {
  const scheduling = await pageFetchJson(cdp, "/api/scheduling/overview/");
  const planning = await pageFetchJson(cdp, "/api/planning/overview/");
  const exports = await pageFetchJson(cdp, "/api/exports/overview/");
  const audit = await pageFetchJson(cdp, "/api/audit-events/").catch(() => []);
  const scenarioRuns = (scheduling.simulationScenarios ?? []).reduce(
    (count, scenario) => count + (scenario.runs?.length ?? 0),
    0,
  );
  const finalState = {
    revalidatedAt: new Date().toISOString(),
    activePlan: scheduling.activePlanVersion
      ? {
          planCode: scheduling.activePlanVersion.plan_code,
          versionNo: scheduling.activePlanVersion.version_no,
          status: scheduling.activePlanVersion.status,
          validationStatus: scheduling.activePlanVersion.validation_status,
          openBlockingConflicts: scheduling.validation?.blockingConflictCount ?? 0,
        }
      : null,
    endStateChecks: {
      published: scheduling.activePlanVersion?.status === "published",
      feasible: scheduling.activePlanVersion?.validation_status === "feasible",
      noOpenBlockers: (scheduling.validation?.blockingConflictCount ?? 0) === 0,
      noMissedWindows: (planning.validation?.missedWindows ?? 0) === 0,
      printableExportGenerated: (exports.summary?.plan ?? 0) >= 1,
    },
    planVersions: (scheduling.planVersions ?? []).map((version) => ({
      planCode: version.plan_code,
      versionNo: version.version_no,
      status: version.status,
      validationStatus: version.validation_status,
    })),
    approvals: (scheduling.approvalRequests ?? []).map((request) => ({
      request_id: request.request_id,
      status: request.status,
      decisions: request.decisions?.length ?? 0,
    })),
    publishedSnapshots: (scheduling.publishedSnapshots ?? []).map((snapshot) => ({
      snapshot_id: snapshot.snapshot_id,
      status: snapshot.status,
    })),
    exports: (exports.exports ?? []).map((item) => ({
      export_type: item.export_type,
      export_format: item.export_format,
      file_name: item.file_name,
      status: item.status,
    })),
    voyages: planning.voyages?.length ?? 0,
    cargoLayers: planning.cargoLayerSteps?.length ?? 0,
    navigationChecks: planning.constraintChecks?.length ?? 0,
    missedChecks: planning.validation?.missedWindows ?? 0,
    optimizerRuns: scheduling.optimizerRuns?.length ?? 0,
    recommendations: scheduling.recoveryRecommendations?.length ?? 0,
    simulationScenarios: scheduling.simulationScenarios?.length ?? 0,
    scenarioRuns,
    auditActions: (audit ?? []).map((item) => item.action),
  };
  await writeFile(
    `${EVIDENCE_DIR}/recovery_practice_final_state.json`,
    JSON.stringify(finalState, null, 2),
  );
}

async function loginIfNeeded(cdp) {
  const text = await waitForLoginOrWorkspace(cdp);
  if (!text.includes("Access the operations workspace")) {
    return;
  }
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
            username: 'admin@coalflow.local',
            password: 'admin12345'
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
  if ((await bodyText(cdp)).includes("Access the operations workspace")) {
    await clickLoginSubmit(cdp);
    await waitForApp(cdp);
  }
}

async function waitForLoginOrWorkspace(cdp, timeoutMs = 15000) {
  const start = Date.now();
  let lastBody = "";
  while (Date.now() - start < timeoutMs) {
    const text = await bodyText(cdp).catch(() => "");
    lastBody = text;
    if (
      text.includes("Access the operations workspace")
      || text.includes("Super")
      || text.includes("Open Exception Center")
    ) {
      return text;
    }
    await delay(500);
  }
  return lastBody;
}

async function clickLoginSubmit(cdp) {
  const match = await findButton(cdp, "Sign in", { exact: true });
  if (!match) {
    throw new Error("Login submit button not found.");
  }
  const x = match.rect.x + match.rect.width / 2;
  const y = match.rect.y + match.rect.height / 2;
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  await delay(2500);
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
    if (!match) {
      throw new Error(`Button not found after scroll: ${text}`);
    }
    if (match.rect.y < 0 || match.rect.y + match.rect.height > 1000) {
      await domClickButton(cdp, text, options);
      flowLog.push({
        step: "click",
        title: options.purpose || `Click ${text}`,
        target: text,
        matchedText: match.text,
        matchCount: match.matchCount,
        result: "clicked",
      });
      await delay(options.afterMs ?? 2500);
      return;
    }
  }
  if (match.disabled) {
    flowLog.push({
      step: "disabled",
      title: options.purpose || `Attempted ${text}`,
      target: text,
      result: "disabled",
      visibleText: match.text,
    });
    throw new Error(`Button disabled: ${text}`);
  }
  const x = match.rect.x + match.rect.width / 2;
  const y = match.rect.y + match.rect.height / 2;
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  flowLog.push({
    step: "click",
    title: options.purpose || `Click ${text}`,
    target: text,
    matchedText: match.text,
    matchCount: match.matchCount,
    result: "clicked",
  });
  await delay(options.afterMs ?? 2500);
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

async function domClickButton(cdp, text, { exact = false } = {}) {
  const clicked = await evalAsync(
    cdp,
    `
      (() => {
        const needle = ${JSON.stringify(text)}.toLowerCase();
        const exact = ${JSON.stringify(exact)};
        const buttons = Array.from(document.querySelectorAll('button'));
        const button = buttons.find((item) => {
          const label = item.innerText.trim().replace(/\\s+/g, ' ').toLowerCase();
          return exact ? label === needle : label.includes(needle);
        });
        if (!button) return false;
        button.scrollIntoView({ block: 'center', inline: 'nearest' });
        button.click();
        return true;
      })()
    `,
  );
  if (!clicked) {
    throw new Error(`DOM button click failed: ${text}`);
  }
}

async function pageFetchJson(cdp, path) {
  return evalAsync(
    cdp,
    `
      await fetch(${JSON.stringify(path)}, { credentials: 'include', cache: 'no-store' })
        .then(async (response) => {
          if (!response.ok) throw new Error(String(response.status));
          return response.json();
        });
    `,
  );
}

async function screenState(cdp) {
  return evalAsync(
    cdp,
    `
      (() => {
        const text = document.body.innerText;
        const interesting = [
          'Open Exception Center',
          'OGV Demand',
          'Tide & Bridge Window',
          'Missed gates',
          'TIDE_WINDOW_MISSED',
          'BRIDGE_WINDOW_MISSED',
          'Generate recovery options',
          'Recommendation Console',
          'Ranked recovery options',
          'Test as scenario',
          'Simulation Workspace',
          'Run simulation',
          'Promote to proposed',
          'Scenario promoted',
          'Enter operating windows',
          'Regenerate plan',
          'Published Plan & Schedule',
          'Submit approval',
          'Approvals & Publishing',
          'Approve',
          'Ready to publish',
          'Publish plan',
          'Published version',
          'Exports & Operational Handoff',
          'Generate schedule',
          'Download artifact',
          'LIVE-',
          'Generated',
          'Blocked',
          'Feasible',
          'Published',
          'Recovery Loop',
          'Constraint evaluations',
          'Risk flags',
        ];
        return {
          url: location.href,
          highlights: interesting.filter((item) => text.includes(item)),
          title: document.title,
        };
      })()
    `,
  );
}

function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: ROOT, shell: false });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve(stdout);
        return;
      }
      reject(new Error(`${command} ${args.join(" ")} failed with ${code}: ${stderr || stdout}`));
    });
  });
}

async function bodyText(cdp) {
  return evalAsync(cdp, "document.body.innerText");
}

async function waitForText(cdp, text, timeoutMs = 10000) {
  const start = Date.now();
  let lastBody = "";
  while (Date.now() - start < timeoutMs) {
    const body = await bodyText(cdp).catch(() => "");
    lastBody = body;
    if (body.toLowerCase().includes(text.toLowerCase())) return;
    await delay(500);
  }
  throw new Error(`Timed out waiting for text: ${text}. Body sample: ${lastBody.slice(0, 500)}`);
}

async function waitForHash(cdp, hashPath, timeoutMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const url = await evalAsync(cdp, "location.href").catch(() => "");
    if (url.includes(`#${hashPath}`)) return;
    await delay(500);
  }
  throw new Error(`Timed out waiting for route: ${hashPath}`);
}

async function waitForPlanningState(cdp, predicate, timeoutMs = 10000) {
  const start = Date.now();
  let last = null;
  while (Date.now() - start < timeoutMs) {
    last = await pageFetchJson(cdp, "/api/planning/overview/").catch(() => null);
    if (last && predicate(last)) return last;
    await delay(500);
  }
  throw new Error(`Timed out waiting for planning state. Last state: ${JSON.stringify(last)?.slice(0, 500)}`);
}

async function waitForSchedulingState(cdp, predicate, timeoutMs = 10000) {
  const start = Date.now();
  let last = null;
  while (Date.now() - start < timeoutMs) {
    last = await pageFetchJson(cdp, "/api/scheduling/overview/").catch(() => null);
    if (last && predicate(last)) return last;
    await delay(500);
  }
  throw new Error(`Timed out waiting for scheduling state. Last state: ${JSON.stringify(last)?.slice(0, 500)}`);
}

async function waitForExportState(cdp, predicate, timeoutMs = 10000) {
  const start = Date.now();
  let last = null;
  while (Date.now() - start < timeoutMs) {
    last = await pageFetchJson(cdp, "/api/exports/overview/").catch(() => null);
    if (last && predicate(last)) return last;
    await delay(500);
  }
  throw new Error(`Timed out waiting for export state. Last state: ${JSON.stringify(last)?.slice(0, 500)}`);
}

async function waitForApp(cdp) {
  await waitForExpression(cdp, "document.readyState === 'complete' || document.readyState === 'interactive'", 15000);
  await delay(750);
}

async function waitForExpression(cdp, expression, timeoutMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const value = await evalValue(cdp, expression).catch(() => false);
    if (value) return;
    await delay(250);
  }
  throw new Error(`Timed out waiting for expression: ${expression}`);
}

async function navigate(cdp, url) {
  await cdp.send("Page.navigate", { url });
  await waitForApp(cdp);
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

async function waitForDebuggerUrl() {
  const listUrl = `http://127.0.0.1:${PORT}/json/list`;
  const versionUrl = `http://127.0.0.1:${PORT}/json/version`;
  const start = Date.now();
  while (Date.now() - start < 15000) {
    try {
      const response = await fetch(listUrl);
      if (response.ok) {
        const targets = await response.json();
        const page = targets.find((target) => target.type === "page");
        if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
      }
    } catch {
      // Chrome is still starting.
    }
    try {
      const response = await fetch(versionUrl);
      if (response.ok) {
        await response.json();
      }
    } catch {
      // Chrome is still starting.
    }
    await delay(250);
  }
  throw new Error("Chrome debugger did not start.");
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
      }, 30000);
    });
  }
}

await main();
