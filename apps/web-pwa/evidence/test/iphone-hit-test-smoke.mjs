import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium, devices } = require(
  "../../../../MVP_EVIDENCE/test-runs/iphone-rerun-runner/node_modules/playwright"
);

const pwaUrl = process.env.PWA_URL || "http://127.0.0.1:63519/";
const useMockApi = process.env.MOCK_API !== "0";
const outputDir = path.resolve("evidence/test-runs");
const outputPath = path.join(outputDir, "iphone-hit-test-smoke.json");

const actor = {
  userId: "user-1",
  sessionId: "session-1",
  memberships: [{ householdId: "household-1", status: "active" }]
};

let transactionCounter = 2;
let accountCounter = 3;

const accounts = [
  {
    id: "account-1",
    name: "Personal Card",
    accountType: "card",
    ownershipType: "personal",
    ownerUserId: "user-1",
    householdId: null,
    currency: "RUB",
    currentBalance: "100000",
    status: "active",
    version: 1
  },
  {
    id: "account-2",
    name: "Family Bank",
    accountType: "bank",
    ownershipType: "shared",
    ownerUserId: null,
    householdId: "household-1",
    currency: "RUB",
    currentBalance: "50000",
    status: "active",
    version: 1
  }
];

const categories = [
  {
    id: "category-1",
    name: "Groceries",
    type: "expense",
    iconKey: "shopping",
    color: "#0f766e",
    scope: "personal",
    householdId: null,
    status: "active",
    version: 1
  },
  {
    id: "category-2",
    name: "Salary",
    type: "income",
    iconKey: "income",
    color: "#2563eb",
    scope: "personal",
    householdId: null,
    status: "active",
    version: 1
  },
  {
    id: "category-3",
    name: "Home",
    type: "expense",
    iconKey: "home",
    color: "#c2410c",
    scope: "household",
    householdId: "household-1",
    status: "active",
    version: 1
  }
];

const transactions = [
  {
    id: "transaction-1",
    transactionType: "expense",
    accountId: "account-1",
    counterpartyAccountId: null,
    categoryId: "category-1",
    amount: "1000",
    currency: "RUB",
    occurredAt: "2026-05-18T12:00:00.000Z",
    description: "Groceries",
    sourceType: "manual",
    version: 1
  }
];

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(body)
  });
}

function report(mode) {
  return {
    data: {
      reportMode: mode,
      currency: "RUB",
      incomeTotal: "25000",
      expenseTotal: "1000",
      netTotal: "24000"
    }
  };
}

async function installApiMock(page) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (url.pathname === "/api/v1/sessions" && method === "POST") {
      return json(route, {
        transport: "pwa_cookie",
        csrfToken: "csrf-token",
        expiresAt: "2026-05-19T23:59:59.000Z",
        actor
      });
    }
    if (url.pathname === "/api/v1/sessions/current" && method === "GET") {
      return json(route, { actor });
    }
    if (url.pathname === "/api/v1/accounts" && method === "GET") {
      return json(route, { items: accounts });
    }
    if (url.pathname === "/api/v1/accounts" && method === "POST") {
      const input = JSON.parse(request.postData() || "{}");
      const next = {
        id: `account-${++accountCounter}`,
        name: input.name || "New Asset",
        accountType: input.accountType || "card",
        ownershipType: input.ownershipType || "personal",
        ownerUserId: input.ownershipType === "shared" ? null : "user-1",
        householdId: input.ownershipType === "shared" ? "household-1" : null,
        currency: input.currency || "RUB",
        currentBalance: input.initialBalance || "0",
        status: "active",
        version: 1
      };
      accounts.push(next);
      return json(route, { data: next }, 201);
    }
    if (url.pathname === "/api/v1/categories" && method === "GET") {
      return json(route, { items: categories });
    }
    if (url.pathname === "/api/v1/transactions" && method === "GET") {
      return json(route, { items: transactions });
    }
    if (url.pathname === "/api/v1/transactions" && method === "POST") {
      const input = JSON.parse(request.postData() || "{}");
      const next = {
        id: `transaction-${++transactionCounter}`,
        transactionType: input.transactionType || "expense",
        accountId: input.accountId,
        counterpartyAccountId: input.counterpartyAccountId || null,
        categoryId: input.categoryId || null,
        amount: input.amount || "1",
        currency: input.currency || "RUB",
        occurredAt: input.occurredAt || new Date().toISOString(),
        description: input.description || input.transactionType || "Manual",
        sourceType: "manual",
        transferScope: input.transactionType === "transfer" ? "personal_same_owner" : null,
        transferStatus: input.transactionType === "transfer" ? "posted" : null,
        version: 1
      };
      transactions.push(next);
      return json(route, { data: next }, 201);
    }
    if (url.pathname === "/api/v1/reports/summary" && method === "GET") {
      return json(route, report(url.searchParams.get("reportMode") || "combined_viewer_overview"));
    }
    return json(route, { error: { code: "not_found" } }, 404);
  });
}

async function probeLocator(page, name, locator) {
  await locator.waitFor({ state: "visible", timeout: 15000 });
  const box = await locator.boundingBox();
  const data = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const hit = document.elementFromPoint(x, y);
    const hitStyle = hit ? window.getComputedStyle(hit) : null;
    const elementStyle = window.getComputedStyle(element);
    return {
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        visualWidth: window.visualViewport?.width ?? null,
        visualHeight: window.visualViewport?.height ?? null,
        scale: window.visualViewport?.scale ?? null
      },
      rect: {
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height
      },
      element: {
        tag: element.tagName,
        className: element.className,
        testId: element.getAttribute("data-testid"),
        zIndex: elementStyle.zIndex,
        pointerEvents: elementStyle.pointerEvents,
        position: elementStyle.position,
        display: elementStyle.display,
        visibility: elementStyle.visibility
      },
      hit: hit
        ? {
            tag: hit.tagName,
            className: hit.className,
            testId: hit.getAttribute("data-testid"),
            text: hit.textContent?.trim().slice(0, 80) ?? "",
            zIndex: hitStyle?.zIndex ?? "",
            pointerEvents: hitStyle?.pointerEvents ?? "",
            position: hitStyle?.position ?? ""
          }
        : null,
      containsHit: hit ? element === hit || element.contains(hit) : false
    };
  });

  return { name, box, ...data };
}

async function tryClick(name, locator) {
  try {
    await locator.click({ timeout: 4000 });
    return { name, ok: true };
  } catch (error) {
    return { name, ok: false, error: error.message.split("\n")[0] };
  }
}

async function tryTap(name, locator) {
  try {
    await locator.tap({ timeout: 4000 });
    return { name, ok: true };
  } catch (error) {
    return { name, ok: false, error: error.message.split("\n")[0] };
  }
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  ...devices["iPhone 14"],
  locale: "ru-RU"
});
const page = await context.newPage();
page.setDefaultTimeout(10000);

const result = {
  pwaUrl,
  environment: {
    device: "Playwright Chromium iPhone 14",
    userAgent: await page.evaluate(() => navigator.userAgent).catch(() => null),
    mockApi: useMockApi
  },
  probes: [],
  clicks: []
};

try {
  if (useMockApi) {
    await installApiMock(page);
  }

  await page.goto(pwaUrl, { waitUntil: "networkidle", timeout: 30000 });
  await page.getByTestId("mobile-quick-add").waitFor({ state: "visible", timeout: 15000 });

  for (const [name, locator] of [
    ["FAB", page.getByTestId("mobile-quick-add")],
    ["nav-money", page.getByTestId("mobile-nav-money")],
    ["nav-operations", page.getByTestId("mobile-nav-operations")],
    ["nav-assets", page.getByTestId("mobile-nav-assets")],
    ["nav-categories", page.getByTestId("mobile-nav-categories")],
    ["nav-analytics", page.getByTestId("mobile-nav-analytics")]
  ]) {
    result.probes.push(await probeLocator(page, name, locator));
  }

  result.clicks.push(await tryTap("tap FAB", page.getByTestId("mobile-quick-add")));
  if (!result.clicks.at(-1)?.ok) {
    result.clicks.push(await tryClick("click FAB", page.getByTestId("mobile-quick-add")));
  }
  if (result.clicks.at(-1)?.ok) {
    const form = page.getByRole("form").first();
    await form.waitFor({ state: "visible", timeout: 10000 });
    result.probes.push(await probeLocator(page, "quick-add-more", page.getByTestId("quick-add-more")));
    result.probes.push(await probeLocator(page, "quick-add-submit", page.getByTestId("quick-add-submit")));
    result.clicks.push(await tryTap("tap Quick Add More", page.getByTestId("quick-add-more")));
    result.clicks.push(await tryTap("tap Quick Add Submit", page.getByTestId("quick-add-submit")));
  }

  for (const [name, id] of [
    ["nav-operations", "mobile-nav-operations"],
    ["nav-assets", "mobile-nav-assets"],
    ["nav-categories", "mobile-nav-categories"],
    ["nav-analytics", "mobile-nav-analytics"]
  ]) {
    result.clicks.push(await tryTap(`tap ${name}`, page.getByTestId(id)));
  }
} finally {
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(outputPath, JSON.stringify(result, null, 2), "utf8");
  await context.close();
  await browser.close();
}

console.log(JSON.stringify({ outputPath, clicks: result.clicks, probes: result.probes }, null, 2));
