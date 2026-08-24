import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium, devices } = require(
  path.resolve("MVP_EVIDENCE/test-runs/iphone-rerun-runner/node_modules/playwright")
);

const pwaUrl = process.env.PWA_URL || "http://127.0.0.1:5173/";
const evidenceDir = path.resolve("MVP_EVIDENCE/pwa-iphone-parity-postfix-qa-20260727-005600");
const screenshotDir = path.join(evidenceDir, "screenshots");
const resultPath = path.join(evidenceDir, "iphone-parity-smoke.json");

const actor = {
  userId: "qa-user-1",
  sessionId: "qa-session-1",
  memberships: [{ householdId: "qa-household-1", status: "active" }]
};

const accounts = [
  {
    id: "account-card",
    name: "QA Personal Card",
    accountType: "card",
    isPaymentAccount: true,
    ownershipType: "personal",
    ownerUserId: "qa-user-1",
    householdId: null,
    currency: "RUB",
    currentBalance: "125000",
    status: "active",
    version: 1
  },
  {
    id: "account-family",
    name: "QA Family Account",
    accountType: "bank",
    isPaymentAccount: true,
    ownershipType: "shared",
    ownerUserId: null,
    householdId: "qa-household-1",
    currency: "RUB",
    currentBalance: "74000",
    status: "active",
    version: 1
  },
  {
    id: "account-invest",
    name: "QA Broker",
    accountType: "brokerage",
    isPaymentAccount: false,
    ownershipType: "personal",
    ownerUserId: "qa-user-1",
    householdId: null,
    currency: "RUB",
    currentBalance: "310000",
    status: "active",
    version: 1,
    assetCategoryId: "asset-cat-invest"
  }
];

const categories = [
  {
    id: "category-food",
    name: "Продукты",
    type: "expense",
    iconKey: "shopping",
    color: "#0f766e",
    scope: "personal",
    householdId: null,
    status: "active",
    version: 1
  },
  {
    id: "category-home",
    name: "Дом",
    type: "expense",
    iconKey: "home",
    color: "#c2410c",
    scope: "household",
    householdId: "qa-household-1",
    status: "active",
    version: 1
  },
  {
    id: "category-transport",
    name: "Транспорт",
    type: "expense",
    iconKey: "transport",
    color: "#7c3aed",
    scope: "personal",
    householdId: null,
    status: "active",
    version: 1
  },
  {
    id: "category-health",
    name: "Здоровье",
    type: "expense",
    iconKey: "health",
    color: "#db2777",
    scope: "personal",
    householdId: null,
    status: "active",
    version: 1
  },
  {
    id: "category-salary",
    name: "Зарплата",
    type: "income",
    iconKey: "income",
    color: "#2563eb",
    scope: "personal",
    householdId: null,
    status: "active",
    version: 1
  }
];

let transactionCounter = 8;
const transactions = [
  tx("tx-food-1", "expense", "account-card", "category-food", "12800", "2026-07-03T12:00:00.000Z", "QA weekly groceries"),
  tx("tx-food-2", "expense", "account-card", "category-food", "6400", "2026-07-08T12:00:00.000Z", "QA market"),
  tx("tx-home", "expense", "account-family", "category-home", "9100", "2026-07-09T12:00:00.000Z", "QA shared home"),
  tx("tx-transport", "expense", "account-card", "category-transport", "4200", "2026-07-11T12:00:00.000Z", "QA metro"),
  tx("tx-health", "expense", "account-card", "category-health", "3100", "2026-07-12T12:00:00.000Z", "QA pharmacy"),
  tx("tx-salary", "income", "account-card", "category-salary", "185000", "2026-07-01T12:00:00.000Z", "QA salary"),
  {
    id: "tx-invest-transfer",
    transactionType: "transfer",
    accountId: "account-card",
    counterpartyAccountId: "account-invest",
    categoryId: null,
    amount: "22000",
    currency: "RUB",
    occurredAt: "2026-07-14T12:00:00.000Z",
    description: "QA investment transfer",
    sourceType: "manual",
    transferScope: "personal_same_owner",
    transferStatus: "posted",
    version: 1
  }
];

const assetCategories = [
  {
    id: "asset-cat-invest",
    name: "Инвестиции",
    scopeType: "personal",
    ownerUserId: "qa-user-1",
    householdId: null,
    currency: "RUB",
    manualAmount: "0",
    isInvestment: true,
    assetType: "brokerage",
    iconKey: "brokerage",
    recordStatus: "active",
    version: 1
  }
];

const checks = [];
const errors = [];
let authenticated = false;

function tx(id, transactionType, accountId, categoryId, amount, occurredAt, description) {
  return {
    id,
    transactionType,
    accountId,
    counterpartyAccountId: null,
    categoryId,
    amount,
    currency: "RUB",
    occurredAt,
    description,
    sourceType: "manual",
    version: 1
  };
}

function record(name, ok, details = "") {
  checks.push({ name, ok, details });
}

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(body)
  });
}

function report(mode) {
  const personalExpense = 12800 + 6400 + 4200 + 3100;
  const sharedExpense = 9100;
  const income = mode === "shared_family_report" ? 0 : 185000;
  const expense =
    mode === "shared_family_report"
      ? sharedExpense
      : mode === "personal"
        ? personalExpense
        : personalExpense + sharedExpense;
  return {
    data: {
      reportMode: mode,
      currency: "RUB",
      incomeTotal: String(income),
      expenseTotal: String(expense),
      netTotal: String(income - expense),
      investmentsTotal: mode === "personal" ? "22000" : "0"
    }
  };
}

function accountBalances() {
  return {
    data: {
      assetCategoryGroups: [
        {
          assetCategoryId: "asset-cat-invest",
          name: "Инвестиции",
          scopeType: "personal",
          currency: "RUB",
          manualAmount: "0",
          accountsTotal: "310000",
          totalAmount: "310000",
          isInvestment: true,
          assetType: "brokerage",
          iconKey: "brokerage",
          accountCount: 1
        }
      ],
      investmentsByCurrency: [{ currency: "RUB", investmentsTotal: "310000" }],
      totalsByCurrency: [{ currency: "RUB", netWorthTotal: "509000" }]
    }
  };
}

function categoryBreakdown() {
  return {
    items: [
      ["category-food", "Продукты", "personal", 19200, 2, 0.497],
      ["category-home", "Дом", "household", 9100, 1, 0.236],
      ["category-transport", "Транспорт", "personal", 4200, 1, 0.109],
      ["category-health", "Здоровье", "personal", 3100, 1, 0.08],
      ["category-education", "Education", "personal", 2900, 1, 0.075],
      ["category-cafe", "Cafe", "personal", 2700, 1, 0.07],
      ["category-kids", "Kids", "household", 2500, 1, 0.065],
      ["category-pets", "Pets", "personal", 2300, 1, 0.06],
      ["category-gifts", "Gifts", "household", 2100, 1, 0.054],
      ["category-services", "Services", "personal", 1900, 1, 0.049],
      ["category-travel", "Travel", "personal", 1700, 1, 0.044],
      ["category-sport", "Sport", "personal", 1500, 1, 0.039],
      ["category-books", "Books", "personal", 1300, 1, 0.034],
      ["category-other", "Other", "household", 1100, 1, 0.028],
      ...Array.from({ length: 24 }, (_, index) => [
        `category-scroll-${index + 1}`,
        `Scroll QA ${String(index + 1).padStart(2, "0")}`,
        index % 3 === 0 ? "household" : "personal",
        1000 - index * 10,
        1,
        0.01
      ]),
      [null, "Без категории", null, 3000, 1, 0.078]
    ].map(([categoryId, categoryName, categoryScope, amount, transactionCount, shareOfVisibleTotal]) => ({
      categoryId,
      categoryName,
      categoryType: "expense",
      categoryScope,
      currency: "RUB",
      amount: String(amount),
      transactionCount,
      shareOfVisibleTotal: String(shareOfVisibleTotal)
    }))
  };
}

async function installApiMock(page) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (url.pathname === "/api/v1/sessions/current" && method === "GET") {
      return authenticated
        ? json(route, { actor })
        : json(route, { error: { code: "auth_required" } }, 401);
    }
    if (url.pathname === "/api/v1/sessions" && method === "POST") {
      authenticated = true;
      return json(route, {
        transport: "pwa_cookie",
        csrfToken: "qa-csrf-token",
        expiresAt: "2026-07-28T00:00:00.000Z",
        actor
      });
    }
    if (url.pathname === "/api/v1/accounts" && method === "GET") {
      return json(route, { items: accounts });
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
        id: `tx-created-${++transactionCounter}`,
        transactionType: input.transactionType || "expense",
        accountId: input.accountId || "account-card",
        counterpartyAccountId: input.counterpartyAccountId || null,
        categoryId: input.categoryId || null,
        amount: String(input.amount || "1"),
        currency: input.currency || "RUB",
        occurredAt: input.occurredAt || `${input.transactionDate || "2026-07-20"}T12:00:00.000Z`,
        description: input.description || "QA quick add",
        sourceType: "manual",
        version: 1
      };
      transactions.push(next);
      return json(route, { data: next }, 201);
    }
    if (url.pathname === "/api/v1/asset-categories" && method === "GET") {
      return json(route, { items: assetCategories });
    }
    if (url.pathname === "/api/v1/reports/summary" && method === "GET") {
      return json(route, report(url.searchParams.get("reportMode") || "personal"));
    }
    if (url.pathname === "/api/v1/reports/account-balances" && method === "GET") {
      return json(route, accountBalances());
    }
    if (url.pathname === "/api/v1/reports/category-breakdown" && method === "GET") {
      return json(route, { data: categoryBreakdown() });
    }
    if (url.pathname === "/api/v1/planning/plans" && method === "GET") {
      return json(route, { error: { code: "not_found" } }, 404);
    }

    return json(route, { error: { code: "not_found", path: url.pathname, method } }, 404);
  });
}

async function screenshot(page, name) {
  const filePath = path.join(screenshotDir, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: false });
  record(`screenshot ${name}`, true, path.relative(evidenceDir, filePath));
}

async function assertVisible(page, name, locator) {
  await locator.waitFor({ state: "visible", timeout: 10000 });
  record(`${name} visible`, true);
}

async function checkNoHorizontalOverflow(page, label) {
  const data = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth
  }));
  const maxScrollWidth = Math.max(data.scrollWidth, data.bodyScrollWidth);
  record(
    `${label} no horizontal overflow`,
    maxScrollWidth <= data.innerWidth + 1,
    JSON.stringify(data)
  );
}

async function probeLocator(label, locator) {
  const data = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const hit = document.elementFromPoint(x, y);
    const containsHit = Boolean(hit && (element === hit || element.contains(hit)));
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      rect: {
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height
      },
      containsHit,
      hit: hit
        ? {
            tag: hit.tagName,
            testId: hit.getAttribute("data-testid"),
            className: String(hit.getAttribute("class") || ""),
            text: hit.textContent?.trim().slice(0, 80) || ""
          }
        : null
    };
  });
  const withinViewport =
    data.rect.left >= -1 &&
    data.rect.top >= -1 &&
    data.rect.right <= data.viewport.width + 1 &&
    data.rect.bottom <= data.viewport.height + 1;
  record(`${label} inside viewport`, withinViewport, JSON.stringify(data));
  record(`${label} center hit-test`, data.containsHit, JSON.stringify(data.hit));
}

async function probe(page, label, selector) {
  await probeLocator(label, page.locator(selector));
}

async function run() {
  await fs.mkdir(screenshotDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    ...devices["iPhone 14"],
    locale: "ru-RU"
  });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.on("console", (message) => {
    const text = message.text();
    const expectedApiMiss =
      text.includes("401 (Unauthorized)") || text.includes("404 (Not Found)");
    if (message.type() === "error" && !expectedApiMiss) {
      errors.push({ type: "console", message: message.text() });
    }
  });
  page.on("pageerror", (error) => {
    errors.push({ type: "pageerror", message: error.message });
  });

  try {
    await installApiMock(page);
    await page.goto(pwaUrl, { waitUntil: "networkidle", timeout: 30000 });
    await assertVisible(page, "login form", page.getByRole("form", { name: "Вход в финансы" }));
    await checkNoHorizontalOverflow(page, "login");
    await screenshot(page, "01-login");

    const form = page.getByRole("form", { name: "Вход в финансы" });
    await form.getByLabel("Email").fill("qa.iphone.parity@example.test");
    await form.getByLabel("Пароль").fill("dummy-password-12");
    await form.getByRole("button", { name: "Войти" }).click();
    await assertVisible(page, "home heading", page.getByRole("heading", { name: "Деньги" }));
    await checkNoHorizontalOverflow(page, "home");
    await probe(page, "mobile bottom nav", ".mobileNav");
    await probe(page, "mobile quick add FAB", "[data-testid='mobile-quick-add']");
    await screenshot(page, "02-home");

    await page.getByTestId("mobile-quick-add").tap();
    await assertVisible(page, "quick add sheet", page.getByRole("form", { name: "Быстро добавить" }));
    await checkNoHorizontalOverflow(page, "quick add");
    await probe(page, "quick add sheet", ".quickSheet");
    await probe(page, "quick add more", "[data-testid='quick-add-more']");
    await page.getByTestId("quick-add-submit").scrollIntoViewIfNeeded();
    await probe(page, "quick add submit after sheet scroll", "[data-testid='quick-add-submit']");
    await screenshot(page, "03-quick-add");

    await page.getByRole("form", { name: "Быстро добавить" }).getByRole("button", { name: "Категория" }).click();
    await assertVisible(page, "category picker dialog", page.getByRole("dialog", { name: "Категория" }));
    await checkNoHorizontalOverflow(page, "category overlay");
    await probe(page, "category picker sheet", ".categoryPickerSheet");
    await probe(page, "category search", ".searchInputWrap");
    await probeLocator("category option Продукты", page.getByRole("button", { name: "Продукты" }));
    await screenshot(page, "04-category-overlay");

    await page.getByRole("dialog", { name: "Категория" }).getByLabel("Закрыть").click();
    await page.getByRole("form", { name: "Быстро добавить" }).getByLabel("Закрыть").click();
    await page.getByTestId("mobile-nav-analytics").tap();
    await assertVisible(page, "analytics heading", page.locator("#analytics-title"));
    await checkNoHorizontalOverflow(page, "analytics");
    const analyticsCards = page.locator(".metricCard");
    const analyticsCardCount = await analyticsCards.count();
    record("analytics card count", analyticsCardCount >= 4, `count=${analyticsCardCount}`);
    await probeLocator("first analytics card", analyticsCards.first());
    await analyticsCards.nth(analyticsCardCount - 1).scrollIntoViewIfNeeded();
    await probeLocator("last analytics card after scroll", analyticsCards.nth(analyticsCardCount - 1));
    await probe(page, "mobile bottom nav on analytics", ".mobileNav");
    await screenshot(page, "05-analytics");

    await page.getByTestId("mobile-nav-money").tap();
    await assertVisible(page, "home heading after analytics", page.getByRole("heading", { name: "Деньги" }));
    await page.getByRole("button", { name: "Все" }).click();
    await assertVisible(page, "top categories all dialog", page.getByRole("dialog", { name: "Все категории трат" }));
    const fallbackWarningCount = await page.getByText("Серверная разбивка недоступна.").count();
    record("top categories all uses server breakdown", fallbackWarningCount === 0, `fallbackWarnings=${fallbackWarningCount}`);
    await checkNoHorizontalOverflow(page, "top categories all");
    await probe(page, "top categories all sheet", ".quickSheet");
    await screenshot(page, "06-top-categories-all");
    const topCategoriesScroll = await page.getByRole("dialog", { name: "Все категории трат" }).evaluate((dialog) => {
      const scroller = dialog.querySelector(".listStack") || dialog;
      const before = scroller.scrollTop;
      scroller.scrollTop = scroller.scrollHeight;
      const after = scroller.scrollTop;
      return {
        clientHeight: scroller.clientHeight,
        scrollHeight: scroller.scrollHeight,
        before,
        after,
        canScroll: after > before
      };
    });
    record(
      "top categories all dialog content scrolls",
      topCategoriesScroll.scrollHeight > topCategoriesScroll.clientHeight && topCategoriesScroll.canScroll,
      JSON.stringify(topCategoriesScroll)
    );
    const topCategoriesOverlayStack = await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"][aria-label="Все категории трат"]');
      const modal = dialog?.closest(".modalLayer");
      const fab = document.querySelector('[data-testid="mobile-quick-add"]');
      const nav = document.querySelector(".mobileNav");
      function hitAtCenter(element) {
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
        return hit
          ? {
              tag: hit.tagName,
              className: String(hit.getAttribute("class") || ""),
              testId: hit.getAttribute("data-testid"),
              text: hit.textContent?.trim().slice(0, 80) || "",
              insideDialog: Boolean(dialog && (dialog === hit || dialog.contains(hit))),
              insideModal: Boolean(modal && (modal === hit || modal.contains(hit)))
            }
          : null;
      }
      return {
        fabCenter: hitAtCenter(fab),
        navCenter: hitAtCenter(nav)
      };
    });
    record(
      "top categories all modal overlays FAB",
      Boolean(topCategoriesOverlayStack.fabCenter?.insideModal),
      JSON.stringify(topCategoriesOverlayStack.fabCenter)
    );
    record(
      "top categories all modal overlays bottom nav",
      Boolean(topCategoriesOverlayStack.navCenter?.insideModal),
      JSON.stringify(topCategoriesOverlayStack.navCenter)
    );
    await screenshot(page, "07-top-categories-all-scrolled");
  } catch (error) {
    record("flow exception", false, error instanceof Error ? error.stack || error.message : String(error));
  } finally {
    await context.close();
    await browser.close();
  }

  const result = {
    ok: checks.every((check) => check.ok) && errors.length === 0,
    pwaUrl,
    device: "Playwright Chromium iPhone 14",
    mockData: true,
    screenshots: [
      "01-login.png",
      "02-home.png",
      "03-quick-add.png",
      "04-category-overlay.png",
      "05-analytics.png",
      "06-top-categories-all.png",
      "07-top-categories-all-scrolled.png"
    ],
    checks,
    errors
  };
  await fs.writeFile(resultPath, JSON.stringify(result, null, 2), "utf8");
  console.log(JSON.stringify({ ok: result.ok, resultPath, checks, errors }, null, 2));
  if (!result.ok) {
    process.exitCode = 1;
  }
}

await run();
