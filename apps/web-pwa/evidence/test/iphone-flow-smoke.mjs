import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium, devices } = require(
  "../../../../MVP_EVIDENCE/test-runs/iphone-rerun-runner/node_modules/playwright"
);

const pwaUrl = process.env.PWA_URL || "http://127.0.0.1:63518/";
const outputDir = path.resolve("evidence/test-runs");
const outputPath = path.join(outputDir, "iphone-flow-smoke.json");

const checks = [];

function record(name, ok, details = "") {
  checks.push({ name, ok, details });
}

async function tap(name, locator) {
  try {
    await locator.tap({ timeout: 10000 });
    record(name, true);
    return true;
  } catch (error) {
    record(name, false, error.message.split("\n")[0]);
    return false;
  }
}

async function fill(name, locator, value) {
  try {
    await locator.fill(value, { timeout: 10000 });
    record(name, true);
    return true;
  } catch (error) {
    record(name, false, error.message.split("\n")[0]);
    return false;
  }
}

async function selectIndex(name, locator, index) {
  try {
    await locator.selectOption({ index }, { timeout: 10000 });
    record(name, true);
    return true;
  } catch (error) {
    record(name, false, error.message.split("\n")[0]);
    return false;
  }
}

async function selectLabel(name, locator, label) {
  try {
    await locator.selectOption({ label }, { timeout: 10000 });
    record(name, true);
    return true;
  } catch (error) {
    record(name, false, error.message.split("\n")[0]);
    return false;
  }
}

function field(form, label) {
  return form.locator("label.field", { hasText: label }).locator("input,select").first();
}

async function expenseMetric(page) {
  return page
    .locator("article.metricCard", { hasText: "Расходы месяца" })
    .locator("strong")
    .innerText({ timeout: 10000 });
}

async function openMoney(page) {
  await tap("tap nav Деньги", page.getByTestId("mobile-nav-money"));
  await page.getByRole("heading", { name: "Деньги" }).waitFor({ state: "visible" });
}

async function quickAdd(page, kind, amount, options = {}) {
  await tap(`tap FAB for ${kind}`, page.getByTestId("mobile-quick-add"));
  const form = page.getByRole("form", { name: "Быстро добавить" });
  await form.waitFor({ state: "visible", timeout: 10000 });
  await tap(`tap kind ${kind}`, form.getByRole("button", { name: kind, exact: true }));
  await fill(`fill amount ${kind}`, form.getByLabel("Сумма"), String(amount));

  if (kind === "Перевод") {
    await selectLabel("select transfer from", field(form, "Откуда"), "Семейная карта");
    await selectLabel("select transfer to", field(form, "Куда"), "Общий вклад");
  }
  if (kind === "Актив") {
    await selectIndex("select asset type", field(form, "Тип"), 1);
  }
  if (kind === "Расход" || kind === "Доход") {
    await selectIndex(`select category ${kind}`, form.getByLabel("Категория"), 1);
  }

  await tap(`tap Еще ${kind}`, page.getByTestId("quick-add-more"));
  await fill(`fill comment ${kind}`, form.getByLabel("Комментарий"), `iphone-flow-${kind}`);
  if (options.shared) {
    await tap("tap visibility Общее", form.getByLabel("Общее"));
  }

  await Promise.all([
    form.waitFor({ state: "hidden", timeout: 15000 }),
    tap(`tap submit ${kind}`, page.getByTestId("quick-add-submit"))
  ]);
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  ...devices["iPhone 14"],
  locale: "ru-RU"
});
const page = await context.newPage();
page.setDefaultTimeout(10000);

try {
  await fs.mkdir(outputDir, { recursive: true });

  await page.goto(pwaUrl, { waitUntil: "networkidle", timeout: 30000 });
  await page.getByRole("heading", { name: "Деньги" }).waitFor({ state: "visible" });
  record("PWA loaded", true, pwaUrl);

  await quickAdd(page, "Расход", 111);
  await quickAdd(page, "Доход", 222);

  const expenseBeforeTransfer = await expenseMetric(page);
  await quickAdd(page, "Перевод", 333);
  const expenseAfterTransfer = await expenseMetric(page);
  record(
    "transfer does not increase Расходы месяца",
    expenseBeforeTransfer === expenseAfterTransfer,
    `before=${expenseBeforeTransfer}; after=${expenseAfterTransfer}`
  );

  await quickAdd(page, "Актив", 444);

  for (const [name, testId, heading] of [
    ["Операции", "mobile-nav-operations", "Операции"],
    ["Активы", "mobile-nav-assets", "Счета и активы"],
    ["Категории", "mobile-nav-categories", "Категории"],
    ["Аналитика", "mobile-nav-analytics", "Аналитика"]
  ]) {
    await tap(`tap nav ${name}`, page.getByTestId(testId));
    await page.getByRole("heading", { level: 2, name: heading }).waitFor({ state: "visible" });
    record(`heading ${heading} visible`, true);
  }

  const fileInputCount = await page.locator('input[type="file"]').count();
  record(
    "removed file import preview UI is absent",
    fileInputCount === 0,
    `fileInputs=${fileInputCount}`
  );
} catch (error) {
  record("flow exception", false, error instanceof Error ? error.message : String(error));
} finally {
  const result = {
    ok: checks.every((check) => check.ok),
    pwaUrl,
    checks
  };
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(outputPath, JSON.stringify(result, null, 2), "utf8");
  await context.close();
  await browser.close();
  console.log(JSON.stringify({ outputPath, ok: result.ok, checks }, null, 2));
  if (!result.ok) {
    process.exitCode = 1;
  }
}
