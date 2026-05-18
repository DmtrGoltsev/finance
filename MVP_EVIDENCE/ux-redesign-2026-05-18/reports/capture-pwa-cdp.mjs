import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { inflateSync } from "node:zlib";

const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const evidenceRoot = resolve("MVP_EVIDENCE/ux-redesign-2026-05-18");
const screenshotDir = join(evidenceRoot, "screenshots");
const reportsDir = join(evidenceRoot, "reports");
const url = process.argv[2] ?? "http://127.0.0.1:5178/";
const cdpPort = Number(process.argv[3] ?? 9227);
const userDataDir = join(reportsDir, "chrome-cdp-profile");

if (!existsSync(chromePath)) {
  throw new Error(`Chrome not found at ${chromePath}`);
}

await mkdir(screenshotDir, { recursive: true });
await mkdir(reportsDir, { recursive: true });
await rm(userDataDir, { recursive: true, force: true });

const chrome = spawn(chromePath, [
  "--headless=new",
  `--remote-debugging-port=${cdpPort}`,
  `--user-data-dir=${userDataDir}`,
  "--disable-gpu",
  "--disable-dev-shm-usage",
  "--no-first-run",
  "--no-default-browser-check",
  "about:blank"
], { stdio: "ignore" });

const validations = [];

try {
  await waitForHttp(`http://127.0.0.1:${cdpPort}/json/version`);
  const target = await createTarget(cdpPort);
  const cdp = await connectCdp(target.webSocketDebuggerUrl);

  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Network.enable");

  await setViewport(cdp, { width: 1440, height: 1000, mobile: false, scale: 1 });
  await navigate(cdp, url);
  await waitForApp(cdp);
  await capture(cdp, "pwa-desktop-01-main-money-overview.png", "Desktop main: Деньги/Обзор");

  await clickByText(cdp, "Добавить");
  await wait(500);
  await capture(cdp, "pwa-desktop-02-quick-add.png", "Desktop quick add");
  await clickByLabel(cdp, "Закрыть");
  await wait(300);

  await clickByText(cdp, "Операции");
  await wait(600);
  await capture(cdp, "pwa-desktop-03-operations-transfer-proof.png", "Desktop operations with transfer as separate row");

  await clickByText(cdp, "Счета и активы");
  await wait(600);
  await capture(cdp, "pwa-desktop-04-assets-card-deposit-brokerage-metal.png", "Desktop assets: card/deposit/brokerage/metal");

  await clickByText(cdp, "Категории");
  await wait(600);
  await capture(cdp, "pwa-desktop-05-categories-income-expense.png", "Desktop categories");

  await clickByText(cdp, "Аналитика");
  await wait(600);
  await capture(cdp, "pwa-desktop-06-analytics-personal.png", "Desktop analytics personal");

  await clickByText(cdp, "Общее");
  await wait(800);
  await capture(cdp, "pwa-desktop-07-report-switcher-shared.png", "Desktop report switcher: Общее");

  await clickByText(cdp, "Обзор");
  await wait(800);
  await capture(cdp, "pwa-desktop-08-report-switcher-overview.png", "Desktop report switcher: Обзор");

  await setViewport(cdp, { width: 390, height: 844, mobile: true, scale: 2 });
  await navigate(cdp, url);
  await waitForApp(cdp);
  await capture(cdp, "pwa-mobile-09-overview-iphone.png", "Mobile iPhone overview");

  await clickByText(cdp, "Аналитика");
  await wait(600);
  await clickByText(cdp, "Обзор");
  await wait(600);
  await capture(cdp, "pwa-mobile-10-analytics-report-switcher-iphone.png", "Mobile iPhone analytics/report switcher");

  const forbiddenCheck = await evaluate(cdp, `(() => {
    const text = document.body.innerText || "";
    const forbidden = ["CRUD", "debug", "Debug", "PATCH", "Live API", "session id", "E2E", "MVP"];
    return {
      checkedAt: new Date().toISOString(),
      url: location.href,
      forbiddenMatches: forbidden.filter((item) => text.includes(item)),
      requiredMatches: ["Деньги", "Операции", "Активы", "Категории", "Аналитика", "Личное", "Общее", "Обзор"]
        .filter((item) => text.includes(item))
    };
  })()`);
  await writeFile(
    join(reportsDir, "pwa-rendered-forbidden-strings.json"),
    `${JSON.stringify(forbiddenCheck, null, 2)}\n`,
    "utf8"
  );

  await writeFile(
    join(reportsDir, "pwa-screenshot-validation.json"),
    `${JSON.stringify(validations, null, 2)}\n`,
    "utf8"
  );

  await cdp.send("Browser.close").catch(() => {});
} finally {
  if (!chrome.killed) {
    chrome.kill();
  }
}

async function setViewport(cdp, { width, height, mobile, scale }) {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: scale,
    mobile
  });
  await cdp.send("Emulation.setUserAgentOverride", {
    userAgent: mobile
      ? "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
      : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
  });
}

async function navigate(cdp, targetUrl) {
  const loaded = waitForEvent(cdp, "Page.loadEventFired", 15000);
  await cdp.send("Page.navigate", { url: targetUrl });
  await loaded.catch(() => {});
  await wait(1000);
}

async function waitForApp(cdp) {
  await waitForCondition(async () => {
    const result = await evaluate(cdp, `(() => {
      const text = document.body.innerText || "";
      return text.includes("Деньги") && text.includes("Операции") && !text.includes("Загружаем");
    })()`);
    return result === true;
  }, 15000, "PWA did not render expected UX labels");
}

async function clickByText(cdp, label) {
  const result = await evaluate(cdp, `(() => {
    const label = ${JSON.stringify(label)};
    const wanted = label.toLocaleLowerCase("ru-RU");
    const candidates = Array.from(document.querySelectorAll("button, [role=button]"));
    const element = candidates.find((node) => {
      const text = ((node.innerText || node.textContent || node.getAttribute("aria-label") || "")).trim();
      return text.toLocaleLowerCase("ru-RU").includes(wanted);
    });
    if (!element) {
      return { ok: false, label, sample: (document.body.innerText || "").slice(0, 1000) };
    }
    element.click();
    return { ok: true, label, clicked: element.innerText || element.getAttribute("aria-label") };
  })()`);
  if (!result.ok) {
    throw new Error(`Button not found for text "${label}". Sample: ${result.sample}`);
  }
}

async function clickByLabel(cdp, label) {
  const result = await evaluate(cdp, `(() => {
    const label = ${JSON.stringify(label)};
    const element = document.querySelector(\`button[aria-label="\${label}"]\`);
    if (!element) return { ok: false };
    element.click();
    return { ok: true };
  })()`);
  if (!result.ok) {
    throw new Error(`Button not found for aria-label "${label}"`);
  }
}

async function capture(cdp, filename, label) {
  const screenshot = await cdp.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false
  });
  const filePath = join(screenshotDir, filename);
  const buffer = Buffer.from(screenshot.data, "base64");
  await writeFile(filePath, buffer);
  validations.push({ filename, label, ...validatePng(filePath) });
}

function validatePng(filePath) {
  const buffer = readFileSync(filePath);
  if (buffer.length < 1024) {
    throw new Error(`PNG too small: ${filePath}`);
  }
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  const pixels = decodePng(buffer);
  const stride = pixels.channels;
  let min = 255;
  let max = 0;
  let colored = 0;
  const step = Math.max(stride, Math.floor(pixels.data.length / 5000 / stride) * stride);
  for (let i = 0; i < pixels.data.length; i += step) {
    const r = pixels.data[i];
    const g = pixels.data[i + 1] ?? r;
    const b = pixels.data[i + 2] ?? r;
    const luma = Math.round((r + g + b) / 3);
    min = Math.min(min, luma);
    max = Math.max(max, luma);
    if (Math.max(r, g, b) - Math.min(r, g, b) > 8) {
      colored += 1;
    }
  }
  const lumaRange = max - min;
  if (width < 300 || height < 500 || lumaRange < 10 || colored < 10) {
    throw new Error(`PNG appears blank or invalid: ${filePath}`);
  }
  return { width, height, bytes: buffer.length, lumaRange, sampledColoredPixels: colored };
}

function decodePng(buffer) {
  const pngSignature = "89504e470d0a1a0a";
  if (buffer.subarray(0, 8).toString("hex") !== pngSignature) {
    throw new Error("Invalid PNG signature");
  }
  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idat = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.subarray(offset + 4, offset + 8).toString("ascii");
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === "IHDR") {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === "IDAT") {
      idat.push(data);
    } else if (type === "IEND") {
      break;
    }
    offset += 12 + length;
  }
  if (bitDepth !== 8 || ![2, 6].includes(colorType)) {
    throw new Error(`Unsupported PNG format: bitDepth=${bitDepth}, colorType=${colorType}`);
  }
  const channels = colorType === 6 ? 4 : 3;
  const inflated = inflateSync(Buffer.concat(idat));
  const rowBytes = width * channels;
  const raw = Buffer.alloc(rowBytes * height);
  let source = 0;
  for (let y = 0; y < height; y += 1) {
    const filter = inflated[source++];
    const rowStart = y * rowBytes;
    for (let x = 0; x < rowBytes; x += 1) {
      const byte = inflated[source++];
      const left = x >= channels ? raw[rowStart + x - channels] : 0;
      const up = y > 0 ? raw[rowStart + x - rowBytes] : 0;
      const upLeft = y > 0 && x >= channels ? raw[rowStart + x - rowBytes - channels] : 0;
      raw[rowStart + x] = unfilter(byte, filter, left, up, upLeft);
    }
  }
  return { width, height, channels, data: raw };
}

function unfilter(byte, filter, left, up, upLeft) {
  if (filter === 0) return byte;
  if (filter === 1) return (byte + left) & 255;
  if (filter === 2) return (byte + up) & 255;
  if (filter === 3) return (byte + Math.floor((left + up) / 2)) & 255;
  if (filter === 4) return (byte + paeth(left, up, upLeft)) & 255;
  throw new Error(`Unsupported PNG filter: ${filter}`);
}

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  if (pb <= pc) return b;
  return c;
}

async function createTarget(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" });
  if (!response.ok) {
    throw new Error(`Could not create Chrome target: ${response.status}`);
  }
  return response.json();
}

async function connectCdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  const handlers = new Map();
  let id = 0;
  await new Promise((resolveOpen, rejectOpen) => {
    ws.addEventListener("open", resolveOpen, { once: true });
    ws.addEventListener("error", rejectOpen, { once: true });
  });
  ws.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.id && pending.has(payload.id)) {
      const { resolve: ok, reject } = pending.get(payload.id);
      pending.delete(payload.id);
      if (payload.error) reject(new Error(JSON.stringify(payload.error)));
      else ok(payload.result);
      return;
    }
    if (payload.method && handlers.has(payload.method)) {
      for (const handler of handlers.get(payload.method)) {
        handler(payload.params);
      }
    }
  });
  return {
    on(method, handler) {
      const list = handlers.get(method) ?? [];
      list.push(handler);
      handlers.set(method, list);
      return () => handlers.set(method, (handlers.get(method) ?? []).filter((item) => item !== handler));
    },
    send(method, params = {}) {
      const messageId = ++id;
      ws.send(JSON.stringify({ id: messageId, method, params }));
      return new Promise((resolve, reject) => {
        pending.set(messageId, { resolve, reject });
        setTimeout(() => {
          if (pending.has(messageId)) {
            pending.delete(messageId);
            reject(new Error(`CDP timeout: ${method}`));
          }
        }, 20000);
      });
    }
  };
}

function waitForEvent(cdp, method, timeoutMs) {
  return new Promise((resolveEvent, rejectEvent) => {
    const timeout = setTimeout(() => {
      unsubscribe();
      rejectEvent(new Error(`Timed out waiting for ${method}`));
    }, timeoutMs);
    const unsubscribe = cdp.on(method, (params) => {
      clearTimeout(timeout);
      unsubscribe();
      resolveEvent(params);
    });
  });
}

async function evaluate(cdp, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true
  });
  if (result.exceptionDetails) {
    throw new Error(JSON.stringify(result.exceptionDetails));
  }
  return result.result.value;
}

async function waitForHttp(targetUrl) {
  await waitForCondition(async () => {
    try {
      const response = await fetch(targetUrl);
      return response.ok;
    } catch {
      return false;
    }
  }, 10000, `HTTP endpoint did not become ready: ${targetUrl}`);
}

async function waitForCondition(check, timeoutMs, message) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await check()) {
      return;
    }
    await wait(250);
  }
  throw new Error(message);
}

function wait(ms) {
  return new Promise((resolveWait) => setTimeout(resolveWait, ms));
}
