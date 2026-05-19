import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { setTimeout as delay } from "node:timers/promises";

const ROOT = "F:/ocean";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const PORT = 9337;
const PROFILE = `${ROOT}/.tmp/chrome-assist-super-flow`;
const BASE_URL = "http://localhost:8080";
const START_URL = `${BASE_URL}/#/dashboard/situation`;
const EVIDENCE_DIR = `${ROOT}/docs/evidence/assistant_super_flow`;
const SCREENSHOT_DIR = `${EVIDENCE_DIR}/screenshots`;

const flowLog = [];

async function main() {
await mkdir(SCREENSHOT_DIR, { recursive: true });
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
  await waitForText(cdp, "Import OGV demand", 15000);

  await captureStep(cdp, {
    step: "01",
    route: "/dashboard/situation",
    title: "Blank dashboard after master-only reseed",
    expectedNext: "IMPORT_OGV_DEMAND",
    note: "No OGV demand, plan, conflicts, approvals, published snapshot, or export exists yet.",
  });

  await clickButton(cdp, "Import OGV demand", {
    purpose: "Assistant global CTA navigates operator to the demand board",
  });
  await waitForHash(cdp, "/schedule/ogv-demand");
  await captureStep(cdp, {
    step: "02",
    route: "/schedule/ogv-demand",
    title: "Demand board reached from Assist",
    expectedNext: "IMPORT_OGV_DEMAND",
    note: "Assist has navigated to the right page; the page CTA performs the import.",
  });

  await clickButton(cdp, "Import demand", {
    purpose: "Page CTA imports one operator demand row and default cargo layers",
    exact: true,
  });
  await waitForText(cdp, "Import committed", 15000);
  await waitForText(cdp, "Enter tide/bridge windows", 15000);
  await captureStep(cdp, {
    step: "03",
    route: "/schedule/ogv-demand",
    title: "Demand imported",
    expectedNext: "ENTER_OPERATING_WINDOWS",
    note: "The transaction now has OGV demand and cargo layers but no navigation windows.",
  });

  await clickButton(cdp, "Enter tide/bridge windows", {
    purpose: "Assistant global CTA navigates operator to constraints",
  });
  await waitForHash(cdp, "/constraints/tide-bridge");
  await captureStep(cdp, {
    step: "04",
    route: "/constraints/tide-bridge",
    title: "Tide and bridge page reached from Assist",
    expectedNext: "ENTER_OPERATING_WINDOWS",
    note: "Assist has navigated to the constraint entry page.",
  });

  await clickButton(cdp, "Enter operating windows", {
    purpose: "Page CTA creates tide, bridge, asset, jetty, and navigation checks",
    exact: true,
  });
  await waitForText(cdp, "Operating windows entered", 15000);
  await waitForText(cdp, "Generate plan", 15000);
  await captureStep(cdp, {
    step: "05",
    route: "/constraints/tide-bridge",
    title: "Operating windows entered",
    expectedNext: "GENERATE_PLAN",
    note: "The transaction now has constraint windows and feasibility checks.",
  });

  await clickButton(cdp, "Generate plan", {
    purpose: "Assistant global CTA navigates operator to assignment board",
  });
  await waitForHash(cdp, "/operations/tug-barge-assignment");
  await captureStep(cdp, {
    step: "06",
    route: "/operations/tug-barge-assignment",
    title: "Assignment page reached from Assist",
    expectedNext: "GENERATE_PLAN",
    note: "Assist has navigated to the page where schedule generation is available.",
  });

  await clickButton(cdp, "Regenerate plan", {
    purpose: "Page CTA creates the initial operator plan and generated assignments",
    exact: true,
  });
  await waitForText(cdp, "Schedule generated", 20000);
  await waitForText(cdp, "Submit approval", 15000);
  await captureStep(cdp, {
    step: "07",
    route: "/operations/tug-barge-assignment",
    title: "Plan generated",
    expectedNext: "SUBMIT_APPROVAL",
    note: "The generated plan is feasible, so Assist moves the operator to approval submission.",
  });

  await clickButton(cdp, "Submit approval", {
    purpose: "Assistant global CTA navigates operator to the publishing plan page",
  });
  await waitForHash(cdp, "/schedule/published-plan");
  await captureStep(cdp, {
    step: "08",
    route: "/schedule/published-plan",
    title: "Published-plan page reached from Assist",
    expectedNext: "SUBMIT_APPROVAL",
    note: "Assist has navigated to the plan governance page; the page CTA submits the request.",
  });

  await clickButton(cdp, "Submit approval", {
    purpose: "Page CTA creates the dual-authority approval request",
    exact: true,
  });
  await waitForHash(cdp, "/approvals/publishing");
  await waitForText(cdp, "Approve", 15000);
  await captureStep(cdp, {
    step: "09",
    route: "/approvals/publishing",
    title: "Approval request submitted",
    expectedNext: "APPROVE_PLAN",
    note: "The plan is now waiting for required authority decisions.",
  });

  await clickButton(cdp, "Approve", {
    purpose: "First authority approval",
    exact: true,
  });
  await waitForText(cdp, "Approved", 15000);
  await delay(2500);
  await captureStep(cdp, {
    step: "10",
    route: "/approvals/publishing",
    title: "First approval recorded",
    expectedNext: "APPROVE_PLAN",
    note: "One required approval is complete; Assist still asks for the remaining decision.",
  });

  await clickButton(cdp, "Approve", {
    purpose: "Second authority approval",
    exact: true,
  });
  await waitForText(cdp, "Approved", 15000);
  await waitForText(cdp, "Publish plan", 15000);
  await captureStep(cdp, {
    step: "11",
    route: "/approvals/publishing",
    title: "All approvals recorded",
    expectedNext: "PUBLISH_PLAN",
    note: "Both required approvals are complete, so Assist moves the operator to publication.",
  });

  await clickButton(cdp, "Publish plan", {
    purpose: "Page CTA publishes immutable snapshot",
    exact: true,
  });
  await waitForText(cdp, "Published", 20000);
  await waitForText(cdp, "Generate governed export", 15000);
  await captureStep(cdp, {
    step: "12",
    route: "/approvals/publishing",
    title: "Plan published",
    expectedNext: "GENERATE_EXPORT",
    note: "The plan is published and still needs a governed handoff export.",
  });

  await clickButton(cdp, "Generate governed export", {
    purpose: "Assistant global CTA navigates operator to export handoff",
  });
  await waitForHash(cdp, "/admin/export-handoff");
  await captureStep(cdp, {
    step: "13",
    route: "/admin/export-handoff",
    title: "Export page reached from Assist",
    expectedNext: "GENERATE_EXPORT",
    note: "Assist has navigated to the export handoff page.",
  });

  await clickButton(cdp, "Printable schedule", {
    purpose: "Page CTA creates governed plan export",
  });
  await waitForText(cdp, "Export generated", 20000);
  await captureStep(cdp, {
    step: "14",
    route: "/admin/export-handoff",
    title: "Governed export generated",
    expectedNext: null,
    note: "The transaction has reached the export handoff endpoint.",
  });

  await writeFile(`${EVIDENCE_DIR}/assist_super_flow_capture.json`, JSON.stringify(flowLog, null, 2));
  console.log(JSON.stringify({ ok: true, steps: flowLog.length, evidenceDir: EVIDENCE_DIR }, null, 2));
} finally {
  chrome.kill();
}
}

async function captureStep(cdp, { step, route, title, expectedNext, note }) {
  await waitForApp(cdp);
  const screen = await screenState(cdp);
  const assistant = await pageFetchJson(
    cdp,
    `/api/assistant/next-actions/?route=${encodeURIComponent(route)}&mode=supervisor`,
  );
  const counts = await pageFetchJson(cdp, "/api/dashboard/situation/").catch(() => null);
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
    dashboardCounts: counts
      ? {
          activePlanVersion: counts.activePlanVersion?.plan_code ?? null,
          conflictSummary: counts.conflictSummary ?? null,
          approvalQueue: counts.approvalQueue ?? null,
          publishedSnapshot: counts.publishedSnapshot ?? null,
        }
      : null,
  });
}

async function loginIfNeeded(cdp) {
  const text = await bodyText(cdp);
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
}

async function clickButton(cdp, text, options = {}) {
  await waitForApp(cdp);
  const match = await findButton(cdp, text, options);
  if (!match) {
    throw new Error(`Button not found: ${text}`);
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

async function pageFetchJson(cdp, path) {
  return evalAsync(
    cdp,
    `
      await fetch(${JSON.stringify(path)}, { credentials: 'include' })
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
          'Import OGV demand',
          'Assistant action inbox',
          'Enter operating windows',
          'Generate plan',
          'Regenerate plan',
          'Submit approval',
          'Approve',
          'Publish plan',
          'Generate export',
          'Generate schedule',
          'No active plan version',
          'No active conflicts',
          'Export generated',
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
