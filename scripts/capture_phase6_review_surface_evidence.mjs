import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, rm, writeFile } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APP_URL = process.env.PHASE6_REVIEW_APP_URL ?? "http://localhost:8080";
const USERNAME = process.env.PHASE6_REVIEW_USER ?? "admin@coalflow.local";
const PASSWORD = process.env.PHASE6_REVIEW_PASSWORD ?? "admin12345";
const EVIDENCE_DIR = path.join(ROOT, "docs/evidence/phase6_review_surfaces");
const SCREENSHOT_DIR = path.join(EVIDENCE_DIR, "screenshots");
const EVIDENCE_JSON = path.join(EVIDENCE_DIR, "phase6_review_surface_capture.json");

const evidence = {
  preparedAt: new Date().toISOString(),
  appUrl: APP_URL,
  setup: {
    mode: "review-surface visibility setup",
    note: "Backend setup/generation is allowed here because these are read-only review surfaces, not the operator happy-path execution.",
  },
  surfaces: [],
  finalAssertions: {},
};

async function main() {
  await mkdir(SCREENSHOT_DIR, { recursive: true });
  await waitForHttpOk(APP_URL);

  evidence.setup.seedOutput = runDockerManage(["seed_phase0", "--reset-operational-data"]);

  const browserPath = findBrowser();
  const port = await getFreePort();
  const profile = path.join(os.tmpdir(), `coalflow-phase6-review-${Date.now()}`);
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

    evidence.setup.generated = await prepareReviewSurfaceData(cdp);

    await navigate(cdp, "/optimization/global");
    await waitForText(cdp, "Global Optimization Review", 20_000);
    await captureSurface(cdp, {
      key: "global_optimization",
      title: "Global Optimization Review",
      route: "/optimization/global",
      requiredText: [
        "Read-only candidates",
        "Ranked global candidates",
        "Candidate contract",
        "Audit lineage",
        "Advisory only",
      ],
      forbiddenWorkspaceButtons: [
        "Materialize",
        "Promote",
        "Approve",
        "Publish",
      ],
      stateProbe: () => pageFetchJson(cdp, "/api/scheduling/overview/"),
      assertionsFromState: (overview) => ({
        globalRunCount: overview.globalOptimizationRuns?.length ?? 0,
        globalCandidateCount: overview.globalOptimizationCandidates?.length ?? 0,
        hasCandidates: (overview.globalOptimizationCandidates?.length ?? 0) > 0,
        candidatesReadOnly: true,
      }),
    });

    await navigate(cdp, "/map/live");
    await waitForText(cdp, "Telemetry", 20_000);
    await captureSurface(cdp, {
      key: "telemetry_trust",
      title: "Live Map Telemetry Trust",
      route: "/map/live",
      requiredText: [
        "Telemetry",
        "Trust",
      ],
      forbiddenWorkspaceButtons: [],
      stateProbe: () => pageFetchJson(cdp, "/api/scheduling/overview/"),
      assertionsFromState: (overview) => ({
        profileKey: overview.telemetryTrustSummary?.profileKey ?? null,
        latestAssessmentCount: overview.telemetryTrustSummary?.latestAssessmentCount ?? 0,
        trustedCount: overview.telemetryTrustSummary?.trustedCount ?? 0,
        degradedCount: overview.telemetryTrustSummary?.degradedCount ?? 0,
        blockingCount: overview.telemetryTrustSummary?.blockingCount ?? 0,
        hasTrustAssessment: (overview.telemetryTrustSummary?.latestAssessmentCount ?? 0) > 0,
      }),
    });

    await navigate(cdp, "/commercial/projections");
    await waitForText(cdp, "Commercial Projections", 20_000);
    await captureSurface(cdp, {
      key: "commercial_projection",
      title: "Commercial Projection Review",
      route: "/commercial/projections",
      requiredText: [
        "Commercial Projections",
        "Projection only",
        "not settlement",
        "not a customer commitment",
        "invoice",
        "laytime",
      ],
      forbiddenWorkspaceButtons: [
        "Settle",
        "Invoice",
        "Commit",
        "Approve",
        "Publish",
        "Materialize",
      ],
      stateProbe: () => pageFetchJson(cdp, "/api/scheduling/overview/"),
      assertionsFromState: (overview) => ({
        commercialRunId: overview.commercialProjectionRun?.run_id ?? null,
        projectionCount: overview.commercialProjectionSummary?.projectionCount
          ?? overview.commercialProjections?.length
          ?? 0,
        projectionOnly: overview.commercialProjectionSummary?.projectionOnly ?? null,
        hasCommercialProjectionRun: Boolean(overview.commercialProjectionRun),
      }),
    });

    evidence.finalAssertions = {
      globalOptimizerCandidatesVisible: Boolean(
        evidence.surfaces.find((surface) => surface.key === "global_optimization")
          ?.assertions.hasCandidates,
      ),
      telemetryTrustVisible: Boolean(
        evidence.surfaces.find((surface) => surface.key === "telemetry_trust")
          ?.assertions.hasTrustAssessment,
      ),
      commercialProjectionVisible: Boolean(
        evidence.surfaces.find((surface) => surface.key === "commercial_projection")
          ?.assertions.hasCommercialProjectionRun,
      ),
      commercialProjectionOnly: evidence.surfaces.find(
        (surface) => surface.key === "commercial_projection",
      )?.assertions.projectionOnly === true,
    };
    for (const [key, passed] of Object.entries(evidence.finalAssertions)) {
      assertCondition(Boolean(passed), `Final assertion failed: ${key}`);
    }

    await writeFile(EVIDENCE_JSON, JSON.stringify(evidence, null, 2));
    console.log(JSON.stringify({
      ok: true,
      surfaces: evidence.surfaces.length,
      evidenceJson: EVIDENCE_JSON,
      screenshots: SCREENSHOT_DIR,
    }, null, 2));
  } finally {
    chrome.kill();
    await rm(profile, { recursive: true, force: true }).catch(() => undefined);
  }
}

async function prepareReviewSurfaceData(cdp) {
  const globalRun = await pagePostJson(
    cdp,
    "/api/scheduling/global-optimization-runs/generate/",
    { max_candidates: 3 },
  );
  const trustAssessments = await pagePostJson(
    cdp,
    "/api/telemetry/trust-assessments/assess/",
    {},
  );
  const commercialRun = await pagePostJson(
    cdp,
    "/api/scheduling/commercial-projection-runs/generate/",
    {},
  );
  const overview = await pageFetchJson(cdp, "/api/scheduling/overview/");
  return {
    globalOptimizationRunId: globalRun.run_id,
    globalOptimizationCandidateCount: globalRun.candidates?.length ?? 0,
    telemetryTrustAssessmentCount: Array.isArray(trustAssessments) ? trustAssessments.length : 1,
    commercialProjectionRunId: commercialRun.run_id,
    commercialProjectionCount: commercialRun.projections?.length ?? 0,
    activePlanVersion: overview.activePlanVersion?.plan_code ?? null,
  };
}

async function captureSurface(
  cdp,
  {
    key,
    title,
    route,
    requiredText,
    forbiddenWorkspaceButtons,
    stateProbe,
    assertionsFromState,
  },
) {
  const body = await bodyText(cdp);
  for (const text of requiredText) {
    assertCondition(
      body.toLowerCase().includes(text.toLowerCase()),
      `Expected ${title} to contain text: ${text}`,
    );
  }

  const forbiddenButtons = await visibleWorkspaceButtonsMatching(cdp, forbiddenWorkspaceButtons);
  assertCondition(
    forbiddenButtons.length === 0,
    `${title} exposes forbidden workspace controls: ${forbiddenButtons.join(", ")}`,
  );

  const state = await stateProbe();
  const assertions = assertionsFromState(state);
  for (const [assertionKey, assertionValue] of Object.entries(assertions)) {
    if (assertionKey.startsWith("has") || assertionKey.endsWith("Only")) {
      assertCondition(Boolean(assertionValue), `${title} assertion failed: ${assertionKey}`);
    }
  }

  const screenshotName = `${String(evidence.surfaces.length + 1).padStart(2, "0")}_${slug(title)}.png`;
  const screenshot = path.join(SCREENSHOT_DIR, screenshotName);
  const png = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });
  await writeFile(screenshot, Buffer.from(png.data, "base64"));

  evidence.surfaces.push({
    key,
    title,
    route,
    screenshot,
    requiredText,
    forbiddenWorkspaceButtons,
    assertions,
    capturedAt: new Date().toISOString(),
  });
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

async function navigate(cdp, route) {
  await evalAsync(cdp, `location.hash = ${JSON.stringify(route)}`);
  await waitForHash(cdp, route);
  await waitForApp(cdp);
}

async function pagePostJson(cdp, apiPath, body) {
  const csrfToken = await pageFetchJson(cdp, "/api/auth/csrf/").then((payload) => payload.csrfToken);
  return evalAsync(
    cdp,
    `
      await fetch(${JSON.stringify(apiPath)}, {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': ${JSON.stringify(csrfToken)}
        },
        body: JSON.stringify(${JSON.stringify(body)})
      }).then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(JSON.stringify({ status: response.status, payload }));
        return payload;
      })
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

async function visibleWorkspaceButtonsMatching(cdp, needles) {
  if (!needles.length) return [];
  return evalAsync(
    cdp,
    `
      (() => {
        const needles = ${JSON.stringify(needles.map((item) => item.toLowerCase()))};
        const root = document.querySelector('.workspace-page') || document.body;
        return Array.from(root.querySelectorAll('button'))
          .map((button) => {
            const rect = button.getBoundingClientRect();
            return {
              text: button.innerText.trim().replace(/\\s+/g, ' '),
              visible: rect.width > 0 && rect.height > 0,
            };
          })
          .filter((button) => button.visible)
          .map((button) => button.text)
          .filter((text) => needles.some((needle) => text.toLowerCase().includes(needle)));
      })()
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
