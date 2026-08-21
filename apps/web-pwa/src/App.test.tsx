import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { ApiRequestError } from "./api/client";
import type {
  CaptureDraftCreateInput,
  CaptureDraftSummary,
  CaptureDraftUpdateInput,
  DashboardSnapshot,
  ScreenshotOcrResult
} from "./api/types";

const financeSnapshot: DashboardSnapshot = {
  session: {
    viewerName: "Мария",
    householdName: "Дом",
    accessLabel: "Вход выполнен",
    householdId: "household-1"
  },
  accounts: [
    {
      id: "account-1",
      name: "Карта Мир",
      ownerName: "Личное",
      kind: "card",
      isPaymentAccount: true,
      ownershipType: "personal",
      householdId: null,
      status: "active",
      version: 1,
      balance: { value: 925.5, currency: "USD" }
    },
    {
      id: "account-2",
      name: "Вклад",
      ownerName: "Личное",
      kind: "deposit",
      isPaymentAccount: true,
      ownershipType: "personal",
      householdId: null,
      status: "active",
      version: 1,
      balance: { value: 125, currency: "USD" }
    },
    {
      id: "account-3",
      name: "Семейный счет",
      ownerName: "Общее",
      kind: "bank",
      isPaymentAccount: true,
      ownershipType: "shared",
      householdId: "household-1",
      status: "active",
      version: 1,
      balance: { value: 300, currency: "USD" }
    }
  ],
  categories: [
    {
      id: "category-1",
      name: "Продукты",
      direction: "expense",
      iconKey: "shopping",
      color: "#0f766e",
      scope: "personal",
      householdId: null,
      status: "active",
      version: 1,
      planned: { value: 0, currency: "USD" },
      actual: { value: 0, currency: "USD" }
    },
    {
      id: "category-2",
      name: "Зарплата",
      direction: "income",
      iconKey: "income",
      color: "#2563eb",
      scope: "personal",
      householdId: null,
      status: "active",
      version: 1,
      planned: { value: 0, currency: "USD" },
      actual: { value: 0, currency: "USD" }
    },
    {
      id: "category-3",
      name: "Дом",
      direction: "expense",
      iconKey: "home",
      color: "#c2410c",
      scope: "household",
      householdId: "household-1",
      status: "active",
      version: 1,
      planned: { value: 0, currency: "USD" },
      actual: { value: 0, currency: "USD" }
    }
  ],
  operations: [
    {
      id: "operation-1",
      date: "2026-06-17",
      title: "Покупка продуктов",
      accountId: "account-1",
      categoryId: "category-1",
      version: 1,
      categoryName: "Продукты",
      accountName: "Карта Мир",
      amount: { value: -69.75, currency: "USD" }
    },
    {
      id: "operation-2",
      date: "2026-06-16",
      title: "Домашняя покупка",
      accountId: "account-3",
      categoryId: "category-3",
      version: 1,
      categoryName: "Дом",
      accountName: "Семейный счет",
      amount: { value: -30, currency: "USD" }
    }
  ],
  transfers: [
    {
      id: "transfer-1",
      date: "2026-06-17",
      accountId: "account-1",
      counterpartyAccountId: "account-2",
      version: 1,
      transferScope: "personal_same_owner",
      transferStatus: "posted",
      fromAccountName: "Карта Мир",
      toAccountName: "Вклад",
      amount: { value: 25, currency: "USD" }
    }
  ],
  reports: [
    {
      mode: "personal",
      title: "Личное",
      periodLabel: "Текущий месяц",
      income: { value: 250, currency: "USD" },
      expense: { value: 69.75, currency: "USD" },
      balanceDelta: { value: 180.25, currency: "USD" },
      investmentsTotal: { value: 0, currency: "USD" }
    },
    {
      mode: "shared_family_report",
      title: "Общее",
      periodLabel: "Текущий месяц",
      income: { value: 0, currency: "USD" },
      expense: { value: 30, currency: "USD" },
      balanceDelta: { value: -30, currency: "USD" }
    },
    {
      mode: "combined_viewer_overview",
      title: "Обзор",
      periodLabel: "Текущий месяц",
      income: { value: 250, currency: "USD" },
      expense: { value: 99.75, currency: "USD" },
      balanceDelta: { value: 150.25, currency: "USD" }
    }
  ],
  assetCategories: [],
  assetCategoryGroups: [],
  investmentsByCurrency: [],
  investmentsTotal: null
};

afterEach(() => {
  vi.useRealTimers();
});

function makeClient(snapshot: DashboardSnapshot = financeSnapshot) {
  return {
    archiveAccount: vi.fn(async () => snapshot.accounts[0]),
    archiveCategory: vi.fn(async () => snapshot.categories[0]),
    archiveOperation: vi.fn(async () => undefined),
    archiveTransfer: vi.fn(async () => undefined),
    createDemoAccount: vi.fn(async () => snapshot.accounts[0]),
    createDemoCategory: vi.fn(async () => snapshot.categories[0]),
    createDemoOperation: vi.fn(async (_input: unknown) => snapshot.operations[0]),
    createDemoTransfer: vi.fn(async (_input: unknown) => snapshot.transfers[0]),
    createCaptureDraft: vi.fn(async (_input: CaptureDraftCreateInput) => ({
      id: "draft-1",
      status: "pending" as const,
      idempotencyKey: "ocr-1",
      captureSource: "screenshot" as const,
      capturedAt: "2026-05-31T10:00:00.000Z",
      occurredDate: null,
      occurredAt: null,
      amount: { value: 123.45, currency: "USD" as const },
      description: "РџСЂРѕРґСѓРєС‚С‹ В· 3 РѕРїРµСЂР°С†РёРё",
      accountId: "account-1",
      categoryId: "category-1",
      confidence: 0.9
    })),
    deleteAccount: vi.fn(async () => undefined),
    deleteOperation: vi.fn(async () => undefined),
    deleteCategory: vi.fn(async () => undefined),
    getDashboardSnapshot: vi.fn(async () => snapshot),
    listAssetCategories: vi.fn(async () => []),
    createAssetCategory: vi.fn(async () => ({} as any)),
    updateAssetCategory: vi.fn(async () => ({} as any)),
    archiveAssetCategory: vi.fn(async () => ({} as any)),
    restoreAssetCategory: vi.fn(async () => ({} as any)),
    listPlanningPlans: vi.fn(async () => null),
    listPlanningPlanHistory: vi.fn(async () => []),
    createPlanningPlan: vi.fn(async () => ({} as any)),
    getPlanningPlan: vi.fn(async () => ({} as any)),
    createPlanningIncomeSource: vi.fn(async () => ({} as any)),
    updatePlanningIncomeSource: vi.fn(async () => ({} as any)),
    confirmPlanningIncomeSource: vi.fn(async () => ({} as any)),
    deletePlanningIncomeSource: vi.fn(async () => undefined),
    createPlanningAllocation: vi.fn(async () => ({} as any)),
    updatePlanningAllocation: vi.fn(async () => ({} as any)),
    deletePlanningAllocation: vi.fn(async () => undefined),
    copyPlanningPlan: vi.fn(async () => ({} as any)),
    getAccountBalancesReport: vi.fn(async () => ({
      assetCategoryGroups: [],
      investmentsByCurrency: [],
      investmentsTotal: null
    })),
    getCategoryBreakdown: vi.fn(async () => [
      {
        categoryId: "category-1",
        categoryName: "Продукты",
        categoryType: "expense" as const,
        categoryScope: "personal" as const,
        amount: { value: 69.75, currency: "USD" as const },
        transactionCount: 1,
        shareOfVisibleTotal: 1
      }
    ]),
    loginWithPassword: vi.fn(async () => undefined),
    registerUser: vi.fn(
      async (): Promise<{ status: "authenticated" } | { status: "accepted" }> => ({
        status: "authenticated"
      })
    ),
    listCaptureDrafts: vi.fn(async () => [] as CaptureDraftSummary[]),
    logout: vi.fn(async () => undefined),
    restoreAccount: vi.fn(async () => snapshot.accounts[0]),
    restoreCategory: vi.fn(async () => snapshot.categories[0]),
    restoreOperation: vi.fn(async () => snapshot.operations[0]),
    restoreTransfer: vi.fn(async () => snapshot.transfers[0]),
    saveCategoryMapping: vi.fn(async (_externalLabel: string, _categoryId: string, _householdId?: string | null) => undefined),
    updateCaptureDraft: vi.fn(async (input: CaptureDraftUpdateInput): Promise<CaptureDraftSummary> => ({
      id: input.draftId,
      status: "pending" as const,
      idempotencyKey: "ocr-1",
      captureSource: "screenshot" as const,
      capturedAt: "2026-05-31T10:00:00.000Z",
      occurredDate: input.occurredDate ?? null,
      occurredAt: input.occurredAt ?? null,
      amount: { value: input.amount ?? 123.45, currency: "USD" as const },
      description: input.description ?? "Продукты · 3 операции",
      accountId: input.accountId ?? "account-1",
      categoryId: input.categoryId ?? "category-1",
      confidence: 0.9
    })),
    confirmCaptureDraft: vi.fn(async (draftId: string): Promise<CaptureDraftSummary> => ({
      id: draftId,
      status: "confirmed" as const,
      idempotencyKey: "ocr-1",
      captureSource: "screenshot" as const,
      capturedAt: "2026-05-31T10:00:00.000Z",
      occurredDate: "2026-05-31",
      occurredAt: "2026-05-31T12:00:00.000Z",
      amount: { value: 123.45, currency: "USD" as const },
      description: "Продукты · 3 операции",
      accountId: "account-1",
      categoryId: "category-1",
      confidence: 0.9
    })),
    discardCaptureDraft: vi.fn(async (draftId: string): Promise<CaptureDraftSummary> => ({
      id: draftId,
      status: "discarded" as const,
      idempotencyKey: "ocr-1",
      captureSource: "screenshot" as const,
      capturedAt: "2026-05-31T10:00:00.000Z",
      occurredDate: null,
      occurredAt: null,
      amount: { value: 123.45, currency: "USD" as const },
      description: "Продукты · 3 операции",
      accountId: "account-1",
      categoryId: "category-1",
      confidence: 0.9
    })),
    updateAccount: vi.fn(async () => snapshot.accounts[0]),
    updateCategory: vi.fn(async () => snapshot.categories[0]),
    updateOperation: vi.fn(async () => snapshot.operations[0]),
    updateTransfer: vi.fn(async () => snapshot.transfers[0]),
    uploadScreenshotOcr: vi.fn(async (): Promise<ScreenshotOcrResult> => ({
      captureSource: "screenshot" as const,
      parseVersion: "category-aggregate-v1" as const,
      recognizedAt: "2026-05-31T10:00:01.000Z",
      items: [],
      warnings: []
    }))
  };
}

function pendingDraft(input: Partial<CaptureDraftSummary> & { id: string }): CaptureDraftSummary {
  return {
    id: input.id,
    status: input.status ?? "pending",
    idempotencyKey: `ocr-${input.id}`,
    captureSource: "screenshot",
    capturedAt: input.capturedAt ?? "2026-05-31T10:00:00.000Z",
    occurredDate: input.occurredDate ?? null,
    occurredAt: input.occurredAt ?? null,
    amount: input.amount ?? { value: 123.45, currency: "USD" },
    description: input.description ?? "Market OCR",
    accountId: input.accountId ?? null,
    categoryId: input.categoryId ?? null,
    confidence: input.confidence ?? 0.88
  };
}

async function chooseCategory(
  user: ReturnType<typeof userEvent.setup>,
  root: HTMLElement,
  label: string,
  optionName: string,
  query = optionName
) {
  await user.click(within(root).getByLabelText(label));
  const dialog = await screen.findByRole("dialog", { name: label });
  await user.clear(within(dialog).getByLabelText("Поиск категории"));
  await user.type(within(dialog).getByLabelText("Поиск категории"), query);
  await user.click(within(dialog).getByRole("button", { name: new RegExp(optionName, "i") }));
  await waitFor(() => {
    expect(screen.queryByRole("dialog", { name: label })).not.toBeInTheDocument();
  });
}

describe("PWA finance experience", () => {
  it("shows an interactive masked login form and refreshes session state after login", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    client.getDashboardSnapshot = vi
      .fn()
      .mockRejectedValueOnce(new ApiRequestError("auth required", 401, "GET", "/api/v1/sessions/current"))
      .mockResolvedValueOnce(financeSnapshot);

    render(<App client={client} />);

    const form = await screen.findByRole("form", { name: "Вход в финансы" });
    const passwordInput = within(form).getByLabelText("Пароль");
    expect(passwordInput).toHaveAttribute("type", "password");

    await user.type(within(form).getByLabelText("Email"), "demo.owner@example.test");
    await user.type(passwordInput, "not-for-logs");
    expect(document.body).not.toHaveTextContent("not-for-logs");
    await user.click(within(form).getByRole("button", { name: "Войти" }));

    await waitFor(() => {
      expect(client.loginWithPassword).toHaveBeenCalledWith({
        email: "demo.owner@example.test",
        password: "not-for-logs"
      });
    });
    expect(await screen.findByRole("heading", { name: "Деньги" })).toBeInTheDocument();
  });

  it("validates self-service registration before calling the API", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    client.getDashboardSnapshot = vi.fn().mockRejectedValue(
      new ApiRequestError("auth required", 401, "GET", "/api/v1/sessions/current")
    );

    render(<App client={client} />);

    const form = await screen.findByRole("form", { name: "Вход в финансы" });
    await user.click(within(form).getByRole("button", { name: "Регистрация" }));
    await user.click(within(form).getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Укажите email.")).toBeInTheDocument();
    expect(client.registerUser).not.toHaveBeenCalled();

    await user.type(within(form).getByLabelText("Email"), "not-email");
    await user.click(within(form).getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Укажите корректный email.")).toBeInTheDocument();

    const passwordInputs = within(form)
      .getAllByDisplayValue("")
      .filter((input) => input.getAttribute("type") === "password");
    await user.clear(within(form).getByLabelText("Email"));
    await user.type(within(form).getByLabelText("Email"), "new.owner@example.test");
    await user.type(passwordInputs[0], "short");
    await user.type(within(form).getByLabelText("Подтвердите пароль"), "short");
    await user.click(within(form).getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Пароль должен быть не короче 12 символов.")).toBeInTheDocument();
    expect(client.registerUser).not.toHaveBeenCalled();

    await user.clear(passwordInputs[0]);
    await user.clear(within(form).getByLabelText("Подтвердите пароль"));
    await user.type(passwordInputs[0], "dummy-password-12");
    await user.type(within(form).getByLabelText("Подтвердите пароль"), "different-pass-12");
    await user.click(within(form).getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Пароли не совпадают.")).toBeInTheDocument();
    expect(client.registerUser).not.toHaveBeenCalled();
  });

  it("registers a new PWA user and opens the finance dashboard", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    client.getDashboardSnapshot = vi
      .fn()
      .mockRejectedValueOnce(new ApiRequestError("auth required", 401, "GET", "/api/v1/sessions/current"))
      .mockResolvedValueOnce(financeSnapshot);

    render(<App client={client} />);

    const form = await screen.findByRole("form", { name: "Вход в финансы" });
    await user.click(within(form).getByRole("button", { name: "Регистрация" }));
    await user.type(within(form).getByLabelText("Email"), "new.owner@example.test");
    await user.type(within(form).getByLabelText("Имя"), "New Owner");
    const passwordInputs = within(form)
      .getAllByDisplayValue("")
      .filter((input) => input.getAttribute("type") === "password");
    await user.type(passwordInputs[0], "dummy-password-12");
    await user.type(within(form).getByLabelText("Подтвердите пароль"), "dummy-password-12");
    expect(document.body).not.toHaveTextContent("dummy-password-12");
    await user.click(within(form).getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(client.registerUser).toHaveBeenCalledWith({
        email: "new.owner@example.test",
        password: "dummy-password-12",
        displayName: "New Owner"
      });
    });
    expect(await screen.findByRole("heading", { name: "Деньги" })).toBeInTheDocument();
  });

  it("handles accepted duplicate-style registration neutrally and offers sign in", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    client.getDashboardSnapshot = vi.fn().mockRejectedValue(
      new ApiRequestError("auth required", 401, "GET", "/api/v1/sessions/current")
    );
    client.registerUser = vi.fn(async () => ({ status: "accepted" as const }));

    render(<App client={client} />);

    const form = await screen.findByRole("form", { name: "Вход в финансы" });
    await user.click(within(form).getByRole("button", { name: "Регистрация" }));
    await user.type(within(form).getByLabelText("Email"), "known@example.test");
    const passwordInputs = within(form)
      .getAllByDisplayValue("")
      .filter((input) => input.getAttribute("type") === "password");
    await user.type(passwordInputs[0], "dummy-password-12");
    await user.type(within(form).getByLabelText("Подтвердите пароль"), "dummy-password-12");
    await user.click(within(form).getByRole("button", { name: "Create account" }));

    expect(
      await screen.findByText(
        "Запрос принят. Если аккаунт с этим email уже есть, войдите с ним."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Вход в финансы" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Деньги" })).not.toBeInTheDocument();
    expect(client.loginWithPassword).not.toHaveBeenCalled();
  });

  it("logs out from the UI and clears the rendered finance session", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getByRole("button", { name: /Выйти/i }));

    await waitFor(() => expect(client.logout).toHaveBeenCalled());
    expect(await screen.findByRole("form", { name: "Вход в финансы" })).toBeInTheDocument();
    expect(screen.queryByText("Капитал")).not.toBeInTheDocument();
  });

  it("does not claim logout when server-side cookie revocation fails", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    client.logout = vi.fn(async () => {
      throw new Error("revocation unavailable");
    });
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getByRole("button", { name: /Выйти/i }));

    expect(await screen.findByRole("heading", { name: "Не удалось завершить выход" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Сессия может оставаться активной");
    expect(screen.queryByRole("form", { name: "Вход в финансы" })).not.toBeInTheDocument();
    expect(screen.queryByText("Капитал")).not.toBeInTheDocument();
  });

  it("renders the financial dashboard and hides technical wording", async () => {
    render(<App client={makeClient()} />);

    expect(await screen.findByRole("heading", { name: "Деньги" })).toBeInTheDocument();
    expect(screen.getByText("Капитал")).toBeInTheDocument();
    expect(screen.getByText("Расходы месяца")).toBeInTheDocument();
    expect(screen.getByText("Доходы")).toBeInTheDocument();
    expect(screen.getByText("Чистый поток")).toBeInTheDocument();
    expect(screen.getByText("Группы активов")).toBeInTheDocument();
    expect(screen.getByText("Топ категорий")).toBeInTheDocument();
    expect(screen.getByText("Последние операции")).toBeInTheDocument();

    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    expect(within(nav).getByRole("button", { name: /Деньги/i })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Операции/i })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Счета и активы/i })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Категории/i })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Аналитика/i })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Настройки/i })).toBeInTheDocument();

    expect(document.body).not.toHaveTextContent(
      /MVP|CRUD|PATCH|Live API|session id|demo|E2E/i
    );
    expect(document.querySelector('input[type="file"]')).toBeNull();
    expect(screen.queryByLabelText(/Файл отч[её]та/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Импорт отчета" })).not.toBeInTheDocument();
  });

  it("opens all top spending categories from the server breakdown", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-06-12T10:00:00.000Z"));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const client = makeClient();
    client.getCategoryBreakdown = vi.fn(async () => [
      {
        categoryId: "category-transport",
        categoryName: "Транспорт",
        categoryType: "expense" as const,
        categoryScope: "personal" as const,
        amount: { value: 15, currency: "USD" as const },
        transactionCount: 1,
        shareOfVisibleTotal: 0.176
      },
      {
        categoryId: "category-1",
        categoryName: "Продукты",
        categoryType: "expense" as const,
        categoryScope: "personal" as const,
        amount: { value: 70, currency: "USD" as const },
        transactionCount: 2,
        shareOfVisibleTotal: 0.824
      }
    ]);
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getByRole("button", { name: "Все" }));

    const dialog = await screen.findByRole("dialog", { name: "Все категории трат" });
    const dialogLayer = dialog.closest(".modalLayer");
    expect(dialogLayer?.parentElement).toBe(document.body);
    expect(dialog.closest(".appShell")).toBeNull();
    expect(client.getCategoryBreakdown).toHaveBeenCalledWith(
      expect.objectContaining({
        reportMode: "personal",
        householdId: null,
        startDate: "2026-06-01",
        endDate: "2026-06-30"
      })
    );
    expect(within(dialog).getByText("Продукты").compareDocumentPosition(within(dialog).getByText("Транспорт"))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING
    );
  });

  it("shows newer posted operations before older ones in overview and operations", async () => {
    const user = userEvent.setup();
    render(
      <App
        client={makeClient({
          ...financeSnapshot,
          operations: [
            {
              id: "operation-old",
              date: "2026-06-10",
              title: "Old grocery run",
              accountId: "account-1",
              categoryId: "category-1",
              version: 1,
              categoryName: "Products",
              accountName: "Card",
              amount: { value: -10, currency: "USD" }
            },
            {
              id: "operation-new",
              date: "2026-06-18",
              title: "New cafe visit",
              accountId: "account-1",
              categoryId: "category-1",
              version: 1,
              categoryName: "Products",
              accountName: "Card",
              amount: { value: -20, currency: "USD" }
            }
          ],
          transfers: []
        })}
      />
    );

    await screen.findByText("New cafe visit");
    expect(screen.getByText("New cafe visit").compareDocumentPosition(screen.getByText("Old grocery run"))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING
    );

    await user.click(screen.getByTestId("mobile-nav-operations"));
    expect(screen.getByText("New cafe visit").compareDocumentPosition(screen.getByText("Old grocery run"))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING
    );
  });

  it("adds an expense from quick add", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });

    expect(within(sheet).getByLabelText("Сумма")).toHaveValue(null);
    await user.clear(within(sheet).getByLabelText("Сумма"));
    await user.type(within(sheet).getByLabelText("Сумма"), "345");
    await user.selectOptions(within(sheet).getByLabelText("Счет"), "account-1");
    await chooseCategory(user, sheet, "Категория", "Продукты", "дук");
    await user.click(within(sheet).getByText("Еще"));
    fireEvent.change(within(sheet).getByLabelText("Дата"), {
      target: { value: "2026-06-05" }
    });
    await user.click(within(sheet).getByRole("button", { name: /Готово/i }));

    await waitFor(() => {
      expect(client.createDemoOperation).toHaveBeenCalledWith(
        expect.objectContaining({
          accountId: "account-1",
          amount: 345,
          categoryId: "category-1",
          transactionDate: "2026-06-05",
          transactionType: "expense"
        })
      );
    });
    expect(client.createDemoOperation.mock.calls[0][0]).not.toHaveProperty("occurredAt");
    expect(client.getDashboardSnapshot).toHaveBeenCalledTimes(2);
  });

  it("filters quick add categories in a searchable overlay", async () => {
    const user = userEvent.setup();
    const client = makeClient({
      ...financeSnapshot,
      categories: [
        ...financeSnapshot.categories,
        {
          id: "category-transport",
          name: "Транспорт",
          direction: "expense",
          iconKey: "car",
          color: "#7c3aed",
          scope: "personal",
          householdId: null,
          status: "active",
          version: 1,
          planned: { value: 0, currency: "USD" },
          actual: { value: 0, currency: "USD" }
        }
      ]
    });
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });

    await user.click(within(sheet).getByLabelText("Категория"));
    const dialog = await screen.findByRole("dialog", { name: "Категория" });
    await user.type(within(dialog).getByLabelText("Поиск категории"), "дук");

    expect(within(dialog).getByRole("button", { name: /Продукты/i })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /Транспорт/i })).not.toBeInTheDocument();
  });

  it("limits expense account choices to active payment accounts without blocking income", async () => {
    const user = userEvent.setup();
    const client = makeClient({
      ...financeSnapshot,
      accounts: financeSnapshot.accounts.map((account) =>
        account.id === "account-1"
          ? { ...account, isPaymentAccount: false }
          : { ...account, isPaymentAccount: true }
      )
    });
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });

    const expenseAccountSelect = within(sheet).getByLabelText("Счет");
    expect(within(expenseAccountSelect).queryByRole("option", { name: "Карта Мир" })).not.toBeInTheDocument();
    expect(within(expenseAccountSelect).getByRole("option", { name: "Вклад" })).toBeInTheDocument();

    await user.click(within(sheet).getByRole("button", { name: /Доход/i }));
    expect(within(sheet).getByRole("option", { name: "Карта Мир" })).toBeInTheDocument();
  });

  it("clears stale quick add category after switching expense to income", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });

    await user.clear(within(sheet).getByLabelText("Сумма"));
    await user.type(within(sheet).getByLabelText("Сумма"), "345");
    await user.selectOptions(within(sheet).getByLabelText("Счет"), "account-1");
    await chooseCategory(user, sheet, "Категория", "Продукты");
    await user.click(within(sheet).getByRole("button", { name: /Доход/i }));

    await waitFor(() => {
      expect(within(sheet).getByLabelText("Категория")).toHaveTextContent("Выберите категорию");
    });

    expect(within(sheet).getByTestId("quick-add-submit")).toBeDisabled();
    await user.click(within(sheet).getByTestId("quick-add-submit"));
    expect(client.createDemoOperation).not.toHaveBeenCalled();

    await chooseCategory(user, sheet, "Категория", "Зарплата");
    await user.click(within(sheet).getByRole("button", { name: /Готово/i }));

    await waitFor(() => {
      expect(client.createDemoOperation).toHaveBeenCalledWith(
        expect.objectContaining({
          accountId: "account-1",
          amount: 345,
          categoryId: "category-2",
          transactionType: "income"
        })
      );
    });
    expect(client.createDemoOperation).not.toHaveBeenCalledWith(
      expect.objectContaining({
        categoryId: "category-1",
        transactionType: "income"
      })
    );
  });

  it("adds a transfer from quick add without routing it through expense creation", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });

    await user.click(within(sheet).getByRole("button", { name: /Перевод/i }));
    await user.clear(within(sheet).getByLabelText("Сумма"));
    await user.type(within(sheet).getByLabelText("Сумма"), "125");
    await user.selectOptions(within(sheet).getByLabelText("Откуда"), "account-1");
    await user.selectOptions(within(sheet).getByLabelText("Куда"), "account-2");
    await user.click(within(sheet).getByText("Еще"));
    fireEvent.change(within(sheet).getByLabelText("Дата"), {
      target: { value: "2026-06-05" }
    });
    await user.click(within(sheet).getByRole("button", { name: /Готово/i }));

    await waitFor(() => {
      expect(client.createDemoTransfer).toHaveBeenCalledWith(
        expect.objectContaining({
          fromAccountId: "account-1",
          toAccountId: "account-2",
          amount: 125,
          transactionDate: "2026-06-05"
        })
      );
    });
    expect(client.createDemoTransfer.mock.calls[0][0]).not.toHaveProperty("occurredAt");
    expect(client.createDemoOperation).not.toHaveBeenCalled();
  });

  it("adds an investment transfer into an investment account from quick add", async () => {
    const user = userEvent.setup();
    const investmentSnapshot: DashboardSnapshot = {
      ...financeSnapshot,
      accounts: [
        ...financeSnapshot.accounts,
        {
          id: "account-invest",
          name: "Брокер",
          ownerName: "Личное",
          kind: "brokerage",
          isPaymentAccount: false,
          ownershipType: "personal",
          householdId: null,
          status: "active",
          version: 1,
          balance: { value: 0, currency: "USD" },
          assetCategoryId: "asset-cat-invest"
        }
      ],
      assetCategories: [
        {
          id: "asset-cat-invest",
          name: "Инвестиции",
          scopeType: "personal",
          householdId: null,
          ownerUserId: "user-1",
          currency: "USD",
          manualAmount: { value: 0, currency: "USD" },
          isInvestment: true,
          assetType: "brokerage",
          iconKey: "chart",
          recordStatus: "active",
          version: 1
        }
      ]
    };
    const client = makeClient(investmentSnapshot);
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });

    await user.click(within(sheet).getByRole("button", { name: /Инвестиция/i }));
    await user.clear(within(sheet).getByLabelText("Сумма"));
    await user.type(within(sheet).getByLabelText("Сумма"), "250");
    await user.selectOptions(within(sheet).getByLabelText("Откуда"), "account-1");
    await user.selectOptions(within(sheet).getByLabelText("Инвестсчет"), "account-invest");
    await user.click(within(sheet).getByText("Еще"));
    fireEvent.change(within(sheet).getByLabelText("Дата"), {
      target: { value: "2026-06-09" }
    });
    await user.click(within(sheet).getByRole("button", { name: /Готово/i }));

    await waitFor(() => {
      expect(client.createDemoTransfer).toHaveBeenCalledWith(
        expect.objectContaining({
          fromAccountId: "account-1",
          toAccountId: "account-invest",
          amount: 250,
          transactionDate: "2026-06-09",
          description: "Инвестиция"
        })
      );
    });
    expect(client.createDemoOperation).not.toHaveBeenCalled();
  });

  it("creates quick-add assets in personal scope without a scope selector", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });

    await user.click(within(sheet).getByRole("button", { name: /Актив/i }));
    await user.clear(within(sheet).getByLabelText("Сумма"));
    await user.type(within(sheet).getByLabelText("Сумма"), "222");
    await user.selectOptions(within(sheet).getByLabelText("Тип"), "deposit");
    await user.click(within(sheet).getByText("Еще"));
    expect(within(sheet).queryByRole("group", { name: "Куда сохранить" })).not.toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: /Готово/i }));

    await waitFor(() => {
      expect(client.createDemoAccount).toHaveBeenCalledWith(
        expect.objectContaining({
          kind: "deposit",
          initialBalance: 222,
          ownershipType: "personal",
          householdId: null
        })
      );
    });
    expect(client.createDemoOperation).not.toHaveBeenCalled();
  });

  it("does not expose shared asset creation when the session has no household", async () => {
    const user = userEvent.setup();
    const client = makeClient({
      ...financeSnapshot,
      session: { ...financeSnapshot.session, householdId: null },
      accounts: financeSnapshot.accounts.filter((account) => account.ownershipType !== "shared"),
      categories: financeSnapshot.categories.filter((category) => category.scope !== "household")
    });
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });

    await user.click(within(sheet).getByRole("button", { name: /Актив/i }));
    await user.click(within(sheet).getByText("Еще"));

    expect(within(sheet).queryByText("Общее")).not.toBeInTheDocument();
    expect(within(sheet).queryByText("Личное")).not.toBeInTheDocument();
  });

  it("creates and edits categories from the categories UI", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    await user.click(within(nav).getByRole("button", { name: /Категории/i }));

    const form = screen.getByRole("form", { name: "Управление категорией" });
    expect(screen.getByRole("heading", { level: 2, name: "Категории расходов" })).toBeInTheDocument();
    expect(within(form).queryByLabelText("Тип")).not.toBeInTheDocument();
    expect(within(form).queryByLabelText("Доступ")).not.toBeInTheDocument();
    await user.type(within(form).getByLabelText("Название"), "Дом");
    await user.selectOptions(within(form).getByLabelText("Иконка"), "home");
    fireEvent.change(within(form).getByLabelText("Цвет"), { target: { value: "#087F5B" } });
    await user.click(within(form).getByRole("button", { name: "Создать" }));

    await waitFor(() => {
      expect(client.createDemoCategory).toHaveBeenCalledWith({
        name: "Дом",
        direction: "expense",
        scope: "personal",
        householdId: null,
        iconKey: "home",
        color: "#087f5b"
      });
    });

    await user.click(screen.getAllByRole("button", { name: "Изменить" })[0]);
    const editForm = screen.getByRole("form", { name: "Управление категорией" });
    await user.clear(within(editForm).getByLabelText("Название"));
    await user.type(within(editForm).getByLabelText("Название"), "Еда и дом");
    fireEvent.change(within(editForm).getByLabelText("Цвет"), { target: { value: "#0F766E" } });
    await user.click(within(editForm).getByRole("button", { name: "Сохранить" }));

    await waitFor(() => {
      expect(client.updateCategory).toHaveBeenCalledWith({
        categoryId: "category-1",
        name: "Еда и дом",
        iconKey: "shopping",
        color: "#0f766e",
        version: 1
      });
    });
  });

  it("keeps transfers out of monthly spending", async () => {
    render(<App client={makeClient()} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const spendingMetric = screen.getByText("Расходы месяца").closest("article");

    expect(spendingMetric).toHaveTextContent("70");
    expect(spendingMetric).not.toHaveTextContent("95");
    expect(screen.getByText("Перевод между счетами")).toBeInTheDocument();
    expect(screen.getByText(/Карта Мир → Вклад/)).toBeInTheDocument();
  });

  it("does not fall back to a shared report when the personal report is absent", async () => {
    render(
      <App
        client={makeClient({
          ...financeSnapshot,
          reports: financeSnapshot.reports.filter(
            (report) => report.mode === "shared_family_report"
          )
        })}
      />
    );

    await screen.findByRole("heading", { name: "Деньги" });
    const spendingMetric = screen.getByText("Расходы месяца").closest("article");
    expect(spendingMetric).toHaveTextContent("0 $");
    expect(spendingMetric).not.toHaveTextContent("30");
    expect(screen.queryByRole("group", { name: "Режим просмотра" })).not.toBeInTheDocument();
  });

  it("hides transfers when only one side is visible in the current scope", async () => {
    render(
      <App
        client={makeClient({
          ...financeSnapshot,
          transfers: [
            {
              id: "transfer-hidden-side",
              date: "2026-05-18T12:45:00Z",
              accountId: "account-1",
              counterpartyAccountId: "account-3",
              version: 1,
              transferScope: "cross_scope",
              transferStatus: "posted",
              fromAccountName: "Карта Мир",
              toAccountName: "Семейный счет",
              amount: { value: 50, currency: "USD" }
            }
          ]
        })}
      />
    );

    await screen.findByRole("heading", { name: "Деньги" });
    expect(screen.queryByText("Перевод между счетами")).not.toBeInTheDocument();
    expect(screen.queryByText(/Семейный счет/)).not.toBeInTheDocument();
  });

  it("navigates to assets, categories and analytics", async () => {
    const user = userEvent.setup();
    render(<App client={makeClient()} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    await user.click(within(nav).getByRole("button", { name: /Счета и активы/i }));
    expect(screen.getByRole("heading", { level: 2, name: "Счета и активы" })).toBeInTheDocument();
    expect(screen.getByText("Карта Мир")).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: /Категории/i }));
    expect(screen.getByRole("heading", { level: 2, name: "Категории расходов" })).toBeInTheDocument();
    expect(screen.getByText("Продукты")).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: /Аналитика/i }));
    expect(screen.getByRole("heading", { level: 2, name: "Аналитика" })).toBeInTheDocument();
    expect(screen.getByText("Итог")).toBeInTheDocument();
    expect(document.querySelector('input[type="file"]')).toBeNull();
    expect(screen.queryByLabelText(/Файл отч[её]та/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Импорт отчета" })).not.toBeInTheDocument();
  });

  it("shows monthly investments from summary report instead of account balances", async () => {
    const user = userEvent.setup();
    render(
      <App
        client={makeClient({
          ...financeSnapshot,
          reports: financeSnapshot.reports.map((report) =>
            report.mode === "personal"
              ? { ...report, investmentsTotal: { value: 40, currency: "USD" } }
              : report
          ),
          investmentsTotal: { value: 999, currency: "USD" }
        })}
      />
    );

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    await user.click(within(nav).getByRole("button", { name: /Аналитика/i }));

    const investmentsMetric = screen.getByText("Инвестиции").closest("article");
    expect(investmentsMetric).toHaveTextContent("40");
    expect(investmentsMetric).not.toHaveTextContent("999");
  });

  it("switches analytics month and reloads reports with selected date boundaries", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-06-12T10:00:00.000Z"));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    await user.click(within(nav).getByRole("button", { name: /Аналитика/i }));

    expect(screen.getByRole("group", { name: "Месяц аналитики" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Предыдущий месяц" }));

    await waitFor(() => {
      expect(client.getDashboardSnapshot).toHaveBeenLastCalledWith({
        startDate: "2026-05-01",
        endDate: "2026-05-31"
      });
    });

    await user.click(screen.getByRole("button", { name: "Текущий" }));
    await waitFor(() => {
      expect(client.getDashboardSnapshot).toHaveBeenLastCalledWith({
        startDate: "2026-06-01",
        endDate: "2026-06-30"
      });
    });
  });

  it("opens operations, assets and categories from the mobile bottom navigation", async () => {
    const user = userEvent.setup();
    render(<App client={makeClient()} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Нижняя навигация" });
    expect(within(nav).getByRole("button", { name: "Операции" })).toHaveAttribute("title", "Операции");
    expect(within(nav).getByText("Операции")).toHaveClass("visuallyHidden");

    await user.click(screen.getByTestId("mobile-nav-operations"));
    expect(screen.getByRole("heading", { level: 2, name: "Операции" })).toBeInTheDocument();

    await user.click(screen.getByTestId("mobile-nav-assets"));
    expect(screen.getByRole("heading", { level: 2, name: "Счета и активы" })).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: /Категории/i }));

    expect(screen.getByRole("heading", { level: 2, name: "Категории расходов" })).toBeInTheDocument();
    expect(screen.getByText("Продукты")).toBeInTheDocument();
  });

  it("uploads a screenshot, reviews OCR category candidates, saves mapping and creates drafts after confirmation", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-06-12T10:00:00.000Z"));

    const user = userEvent.setup();
    const client = makeClient();
    client.uploadScreenshotOcr = vi.fn(async () => ({
      captureSource: "screenshot" as const,
      parseVersion: "category-aggregate-v1" as const,
      recognizedAt: "2026-05-31T10:00:01.000Z",
      items: [
        {
          candidateType: "categoryAggregate" as const,
          externalLabel: "Products",
          amount: { value: 123.45, currency: "USD" as const },
          operationCount: 3,
          description: "Products · 3 operations",
          confidence: 0.9,
          idempotencyKey: "ocr-products",
          evidenceHash: "hash-products",
          suggestedCategoryId: "category-1"
        }
      ],
      warnings: []
    }));
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    await user.click(within(nav).getByRole("button", { name: /Операции/i }));

    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).toHaveAttribute("accept", "image/png,image/jpeg,image/webp");
    const screenshot = new File(["image"], "expenses.png", { type: "image/png" });
    await user.upload(fileInput!, screenshot);

    expect(await screen.findByText("Products")).toBeInTheDocument();
    expect(screen.getByText("Products · 3 operations")).toBeInTheDocument();
    expect(screen.getByText("3 операций")).toBeInTheDocument();
    expect(screen.getByLabelText("Категория для Products")).toHaveTextContent("Продукты");
    expect(client.createCaptureDraft).not.toHaveBeenCalled();

    await user.selectOptions(screen.getByLabelText("Счет для черновиков"), "account-1");
    await user.click(screen.getByRole("button", { name: /Создать черновики/i }));

    await waitFor(() => {
      expect(client.saveCategoryMapping).toHaveBeenCalledWith("Products", "category-1", null);
      expect(client.createCaptureDraft).toHaveBeenCalledWith(
        expect.objectContaining({
          idempotencyKey: "ocr-products",
          captureSource: "screenshot",
          amount: 123.45,
          currency: "USD",
          description: "Скрин: агрегированные расходы, 3 операций",
          occurredDate: "2026-06-12",
          accountId: "account-1",
          categoryId: "category-1",
          confidence: 0.9,
          evidenceHash: "hash-products"
        })
      );
    });
    const payload = client.createCaptureDraft.mock.calls[0][0];
    expect(payload.description).not.toContain("Products");
    expect(JSON.stringify(payload)).not.toMatch(/ocrText|rawOcrText|body|text|image/i);
    expect(client.getDashboardSnapshot).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("Черновики готовы к подтверждению")).toBeInTheDocument();
  });

  it("edits, confirms and discards pending OCR capture drafts from operations", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    let pendingDrafts: CaptureDraftSummary[] = [
      pendingDraft({
        id: "draft-1",
        amount: { value: 123.45, currency: "USD" },
        description: "Market OCR",
        accountId: null,
        categoryId: null
      }),
      pendingDraft({
        id: "draft-2",
        amount: { value: 25, currency: "USD" },
        description: "Duplicate OCR",
        accountId: "account-1",
        categoryId: "category-1"
      })
    ];
    client.listCaptureDrafts = vi.fn(async () =>
      pendingDrafts.filter((draft) => draft.status === "pending")
    );
    client.updateCaptureDraft = vi.fn(async (input) => {
      const current = pendingDrafts.find((draft) => draft.id === input.draftId);
      const updated: CaptureDraftSummary = {
        ...(current ?? pendingDraft({ id: input.draftId })),
        amount: {
          value: input.amount ?? current?.amount.value ?? 0,
          currency: input.currency ?? current?.amount.currency ?? "USD"
        },
        description: input.description ?? current?.description ?? "",
        occurredDate: input.occurredDate ?? current?.occurredDate ?? null,
        occurredAt: input.occurredAt ?? current?.occurredAt ?? null,
        accountId: input.accountId ?? current?.accountId ?? null,
        categoryId: input.categoryId ?? current?.categoryId ?? null,
        confidence: input.confidence ?? current?.confidence ?? null
      };
      pendingDrafts = pendingDrafts.map((draft) =>
        draft.id === input.draftId ? updated : draft
      );
      return updated;
    });
    client.confirmCaptureDraft = vi.fn(async (draftId) => {
      const current = pendingDrafts.find((draft) => draft.id === draftId) ?? pendingDraft({ id: draftId });
      const confirmed = { ...current, status: "confirmed" as const };
      pendingDrafts = pendingDrafts.map((draft) =>
        draft.id === draftId ? confirmed : draft
      );
      return confirmed;
    });
    client.discardCaptureDraft = vi.fn(async (draftId) => {
      const current = pendingDrafts.find((draft) => draft.id === draftId) ?? pendingDraft({ id: draftId });
      const discarded = { ...current, status: "discarded" as const };
      pendingDrafts = pendingDrafts.map((draft) =>
        draft.id === draftId ? discarded : draft
      );
      return discarded;
    });

    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    await user.click(within(nav).getByRole("button", { name: /Операции/i }));

    const firstDraft = await screen.findByTestId("pending-draft-draft-1");
    await user.clear(within(firstDraft).getByLabelText("Сумма draft-1"));
    await user.type(within(firstDraft).getByLabelText("Сумма draft-1"), "140");
    fireEvent.change(within(firstDraft).getByLabelText("Дата draft-1"), {
      target: { value: "2026-06-01" }
    });
    await user.clear(within(firstDraft).getByLabelText("Описание draft-1"));
    await user.type(within(firstDraft).getByLabelText("Описание draft-1"), "Market reviewed");
    await user.selectOptions(within(firstDraft).getByLabelText("Счет draft-1"), "account-1");
    await chooseCategory(user, firstDraft, "Категория draft-1", "Продукты");
    await user.click(within(firstDraft).getByRole("button", { name: /Подтвердить/i }));

    await waitFor(() => {
      expect(client.updateCaptureDraft).toHaveBeenCalledWith(
        expect.objectContaining({
          draftId: "draft-1",
          amount: 140,
          currency: "USD",
          description: "Market reviewed",
          occurredDate: "2026-06-01",
          accountId: "account-1",
          categoryId: "category-1",
          confidence: 0.88
        })
      );
      expect(client.confirmCaptureDraft).toHaveBeenCalledWith("draft-1");
    });
    expect(client.updateCaptureDraft.mock.calls[0][0].occurredDate).toBe("2026-06-01");
    expect(client.updateCaptureDraft.mock.calls[0][0].occurredAt).toBeUndefined();

    await waitFor(() => {
      expect(screen.queryByTestId("pending-draft-draft-1")).not.toBeInTheDocument();
    });

    const secondDraft = await screen.findByTestId("pending-draft-draft-2");
    await user.click(within(secondDraft).getByRole("button", { name: /Отклонить/i }));

    await waitFor(() => {
      expect(client.discardCaptureDraft).toHaveBeenCalledWith("draft-2");
      expect(screen.queryByTestId("pending-draft-draft-2")).not.toBeInTheDocument();
    });
    expect(client.getDashboardSnapshot).toHaveBeenCalledTimes(3);
  });

  it("shows warnings-only OCR results without rendering create candidates", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    client.uploadScreenshotOcr = vi.fn(async () => ({
      captureSource: "screenshot" as const,
      parseVersion: "category-aggregate-v1" as const,
      recognizedAt: "2026-05-31T10:00:01.000Z",
      items: [],
      warnings: [
        {
          code: "NO_CATEGORY_AGGREGATES_FOUND" as const,
          message: "Итоговые строки не превращены в категории."
        }
      ]
    }));
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    await user.click(within(nav).getByRole("button", { name: /Операции/i }));

    const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
    await user.upload(fileInput!, new File(["image"], "summary.webp", { type: "image/webp" }));

    expect(await screen.findByText("Итоговые строки не превращены в категории.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Проверка распознанных расходов")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Создать черновики/i })).not.toBeInTheDocument();
    expect(client.createCaptureDraft).not.toHaveBeenCalled();
    expect(document.body).not.toHaveTextContent(/Импорт отчета|Файл отчета|report-preview/i);
  });

  it("keeps mobile quick add controls clickable", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    await user.click(screen.getByTestId("mobile-quick-add"));
    const sheet = screen.getByRole("form", { name: "Быстро добавить" });
    await user.click(screen.getByTestId("quick-add-more"));
    expect(within(sheet).getByLabelText("Дата")).toBeInTheDocument();
    await user.clear(within(sheet).getByLabelText("Сумма"));
    await user.type(within(sheet).getByLabelText("Сумма"), "456");
    await user.selectOptions(within(sheet).getByLabelText("Счет"), "account-1");
    await chooseCategory(user, sheet, "Категория", "Продукты");
    await user.click(screen.getByTestId("quick-add-submit"));

    await waitFor(() => {
      expect(client.createDemoOperation).toHaveBeenCalledWith(
        expect.objectContaining({
          amount: 456,
          transactionType: "expense"
        })
      );
    });
  });
  it("shows only personal finance data without scope modes", async () => {
    render(<App client={makeClient()} />);

    await screen.findByRole("heading", { name: "Деньги" });
    expect(screen.queryByRole("group", { name: "Режим просмотра" })).not.toBeInTheDocument();
    expect(screen.getByText("Покупка продуктов")).toBeInTheDocument();
    expect(screen.queryByText("Домашняя покупка")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/Общее|Мой обзор|combined_viewer_overview|shared_family_report/i);
  });
});
