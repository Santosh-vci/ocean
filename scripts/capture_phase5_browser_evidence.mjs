import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import fs from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const APP_URL = process.env.PHASE5_APP_URL ?? "http://localhost:8080";
const USERNAME = process.env.PHASE5_EVIDENCE_USER ?? "admin@coalflow.local";
const PASSWORD = process.env.PHASE5_EVIDENCE_PASSWORD ?? "admin12345";
const OUTPUT_DIR = path.resolve(
  process.env.PHASE5_EVIDENCE_DIR ?? "docs/evidence/phase5/screenshots",
);
const EVIDENCE_JSON = path.resolve(
  process.env.PHASE5_EVIDENCE_JSON ?? "docs/evidence/phase5/browser_visibility_evidence.json",
);

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

async function waitForJson(url, timeoutMs = 15_000) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
      lastError = new Error(`${response.status} ${response.statusText}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
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
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
}

class CdpClient {
  constructor(webSocketUrl) {
    this.nextId = 1;
    this.pending = new Map();
    this.waiters = new Map();
    this.ws = new WebSocket(webSocketUrl);
    this.ready = new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => this.handleMessage(event));
  }

  handleMessage(event) {
    const message = JSON.parse(event.data);
    if (message.id) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) {
        pending.reject(new Error(`${message.error.message}: ${message.error.data ?? ""}`));
      } else {
        pending.resolve(message.result ?? {});
      }
      return;
    }
    const waiters = this.waiters.get(message.method) ?? [];
    this.waiters.set(
      message.method,
      waiters.filter((waiter) => {
        waiter.resolve(message.params ?? {});
        clearTimeout(waiter.timer);
        return false;
      }),
    );
  }

  async send(method, params = {}) {
    await this.ready;
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }

  async waitEvent(method, timeoutMs = 10_000) {
    await this.ready;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.waiters.set(
          method,
          (this.waiters.get(method) ?? []).filter((waiter) => waiter.timer !== timer),
        );
        reject(new Error(`Timed out waiting for ${method}`));
      }, timeoutMs);
      this.waiters.set(method, [...(this.waiters.get(method) ?? []), { resolve, timer }]);
    });
  }

  close() {
    this.ws.close();
  }
}

async function createTarget(port, url) {
  const targetUrl = `http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`;
  let response = await fetch(targetUrl, { method: "PUT" });
  if (!response.ok) response = await fetch(targetUrl);
  if (!response.ok) {
    throw new Error(`Could not create browser target: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function evaluate(cdp, expression) {
  const response = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.text ?? "Runtime evaluation failed.");
  }
  return response.result?.value;
}

async function waitUntil(cdp, expression, timeoutMs = 15_000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(cdp, expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  const visibleText = await evaluate(
    cdp,
    "document.body.innerText.slice(0, 1500)",
  ).catch(() => "");
  throw new Error(`Timed out waiting for expression: ${expression}\nVisible text:\n${visibleText}`);
}

async function capture(cdp, fileName) {
  const result = await cdp.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
  });
  const filePath = path.join(OUTPUT_DIR, fileName);
  await fs.writeFile(filePath, Buffer.from(result.data, "base64"));
  return filePath;
}

async function pageText(cdp) {
  return evaluate(cdp, "document.querySelector('.operations-main')?.innerText || document.body.innerText");
}

async function navigateHash(cdp, hash) {
  const baseUrl = APP_URL.replace(/\/$/, "");
  await cdp.send("Page.navigate", { url: `${baseUrl}/#${hash}` });
  await cdp.waitEvent("Page.loadEventFired", 700).catch(() => undefined);
  await new Promise((resolve) => setTimeout(resolve, 700));
}

async function captureTarget(cdp, evidence, key, hash, waitExpression, fileName) {
  const started = Date.now();
  await navigateHash(cdp, hash);
  await waitUntil(cdp, waitExpression);
  evidence.routeTimingsMs[key] = Date.now() - started;
  evidence.screenshots[key] = await capture(cdp, fileName);
  evidence.observations[key] = (await pageText(cdp)).slice(0, 2600);
}

const browserPath = findBrowser();
const port = await getFreePort();
const userDataDir = await fs.mkdtemp(path.join(os.tmpdir(), "coalflow-phase5-evidence-"));
await fs.mkdir(OUTPUT_DIR, { recursive: true });
await fs.mkdir(path.dirname(EVIDENCE_JSON), { recursive: true });

const browserProcess = spawn(browserPath, [
  "--headless=new",
  "--disable-gpu",
  "--disable-dev-shm-usage",
  "--no-first-run",
  "--no-default-browser-check",
  "--window-size=1600,950",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${userDataDir}`,
  "about:blank",
], { stdio: "ignore" });

const evidence = {
  generatedAt: new Date().toISOString(),
  appUrl: APP_URL,
  user: USERNAME,
  mode: "Recommendation proof flow",
  screenshots: {},
  observations: {},
  routeTimingsMs: {},
};

let cdp;
try {
  await waitForJson(`http://127.0.0.1:${port}/json/version`);
  await waitForHttpOk(APP_URL);
  const target = await createTarget(port, `${APP_URL}/#/recovery/recommendations`);
  cdp = new CdpClient(target.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1600,
    height: 950,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp.waitEvent("Page.loadEventFired", 15_000).catch(() => undefined);
  await waitUntil(
    cdp,
    "document.body.innerText.includes('Access the operations workspace') || document.body.innerText.includes('Recommendation Console')",
  );

  const needsLogin = await evaluate(cdp, "document.body.innerText.includes('Access the operations workspace')");
  if (needsLogin) {
    await evaluate(cdp, `
      (() => {
        const inputs = [...document.querySelectorAll('input')];
        const username = inputs.find((input) => input.type !== 'password');
        const password = inputs.find((input) => input.type === 'password');
        username.value = ${JSON.stringify(USERNAME)};
        password.value = ${JSON.stringify(PASSWORD)};
        username.dispatchEvent(new Event('input', { bubbles: true }));
        password.dispatchEvent(new Event('input', { bubbles: true }));
        [...document.querySelectorAll('button')]
          .find((button) => button.textContent.trim() === 'Sign in')
          .click();
        return true;
      })()
    `);
  }

  await captureTarget(
    cdp,
    evidence,
    "exceptionCenter",
    "/exceptions/center",
    "/Exception Center/i.test(document.body.innerText) && /Generate recovery options/i.test(document.body.innerText)",
    "phase5-exception-center.png",
  );
  await captureTarget(
    cdp,
    evidence,
    "recommendationConsole",
    "/recovery/recommendations",
    "/Recommendation Console/i.test(document.body.innerText) && /Ranked recovery options/i.test(document.body.innerText) && /Before \\/ after actions/i.test(document.body.innerText)",
    "phase5-recommendation-console.png",
  );
  await captureTarget(
    cdp,
    evidence,
    "simulationWorkspace",
    "/simulation/workspace",
    "/Simulation Workspace/i.test(document.body.innerText) && /recovery recommendation/i.test(document.body.innerText)",
    "phase5-simulation-workspace.png",
  );
  await captureTarget(
    cdp,
    evidence,
    "approvalsPublishing",
    "/approvals/publishing",
    "/Plan Approvals & Publishing/i.test(document.body.innerText) && /APPROVAL CHAIN/i.test(document.body.innerText)",
    "phase5-approvals-publishing.png",
  );
  await captureTarget(
    cdp,
    evidence,
    "auditLogs",
    "/admin/audit-logs",
    "/Audit & Logs/i.test(document.body.innerText) && /phase5\\.proof/i.test(document.body.innerText)",
    "phase5-audit-logs.png",
  );

  evidence.performance = {
    routeMaxMs: Math.max(...Object.values(evidence.routeTimingsMs), 0),
  };

  await fs.writeFile(EVIDENCE_JSON, `${JSON.stringify(evidence, null, 2)}\n`);
  console.log(JSON.stringify(evidence, null, 2));
} finally {
  if (cdp) cdp.close();
  browserProcess.kill();
  await Promise.race([
    new Promise((resolve) => browserProcess.once("exit", resolve)),
    new Promise((resolve) => setTimeout(resolve, 1500)),
  ]);
  await fs.rm(userDataDir, { recursive: true, force: true }).catch(() => undefined);
}
