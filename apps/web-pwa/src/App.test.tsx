import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
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
  ]
};

function makeClient(snapshot: DashboardSnapshot = financeSnapshot) {
  return {
    archiveAccount: vi.fn(async () => snapshot.accounts[0]),
    archiveCategory: vi.fn(async () => snapshot.categories[0]),
    archiveOperation: vi.fn(async () => undefined),
    archiveTransfer: vi.fn(async () => undefined),
    createDemoAccount: vi.fn(async () => snapshot.accounts[0]),
    createDemoCategory: vi.fn(async () => snapshot.categories[0]),
    createDemoOperation: vi.fn(async (_input: unknown) => snapshot.operations[0]),
    createDemoTransfer: vi.fn(async () => snapshot.transfers[0]),
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
    deleteCategory: vi.fn(async () => undefined),
    getDashboardSnapshot: vi.fn(async () => snapshot),
    loginWithPassword: vi.fn(async () => undefined),
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
    await user.selectOptions(within(sheet).getByLabelText("Категория"), "category-1");
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
    await user.selectOptions(within(sheet).getByLabelText("Категория"), "category-1");
    await user.click(within(sheet).getByRole("button", { name: /Доход/i }));

    await waitFor(() => {
      expect(within(sheet).getByLabelText("Категория")).toHaveValue("");
    });

    expect(within(sheet).getByTestId("quick-add-submit")).toBeDisabled();
    await user.click(within(sheet).getByTestId("quick-add-submit"));
    expect(client.createDemoOperation).not.toHaveBeenCalled();

    await user.selectOptions(within(sheet).getByLabelText("Категория"), "category-2");
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
    await user.click(within(sheet).getByRole("button", { name: /Готово/i }));

    await waitFor(() => {
      expect(client.createDemoTransfer).toHaveBeenCalledWith(
        expect.objectContaining({
          fromAccountId: "account-1",
          toAccountId: "account-2",
          amount: 125
        })
      );
    });
    expect(client.createDemoOperation).not.toHaveBeenCalled();
  });

  it("preserves shared visibility when adding an asset from quick add", async () => {
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
    await user.click(within(sheet).getByLabelText("Общее"));
    await user.click(within(sheet).getByRole("button", { name: /Готово/i }));

    await waitFor(() => {
      expect(client.createDemoAccount).toHaveBeenCalledWith(
        expect.objectContaining({
          kind: "deposit",
          initialBalance: 222,
          ownershipType: "shared",
          householdId: "household-1"
        })
      );
    });
    expect(client.createDemoOperation).not.toHaveBeenCalled();
  });

  it("disables shared asset creation when the current session has no household", async () => {
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

    expect(within(sheet).getByLabelText("Общее")).toBeDisabled();
  });

  it("creates and edits categories from the categories UI", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    render(<App client={client} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const nav = screen.getByRole("navigation", { name: "Основная навигация" });
    await user.click(within(nav).getByRole("button", { name: /Категории/i }));

    const form = screen.getByRole("form", { name: "Управление категорией" });
    await user.type(within(form).getByLabelText("Название"), "Подработка");
    await user.selectOptions(within(form).getByLabelText("Тип"), "income");
    await user.selectOptions(within(form).getByLabelText("Доступ"), "household");
    await user.selectOptions(within(form).getByLabelText("Иконка"), "income");
    fireEvent.change(within(form).getByLabelText("Цвет"), { target: { value: "#087F5B" } });
    await user.click(within(form).getByRole("button", { name: "Создать" }));

    await waitFor(() => {
      expect(client.createDemoCategory).toHaveBeenCalledWith({
        name: "Подработка",
        direction: "income",
        scope: "household",
        householdId: "household-1",
        iconKey: "income",
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

  it("does not fall back to another report mode when overview report is absent", async () => {
    const user = userEvent.setup();
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
    await user.click(screen.getByRole("button", { name: /Обзор/i }));

    const spendingMetric = screen.getByText("Расходы месяца").closest("article");
    expect(spendingMetric).toHaveTextContent("0 $");
    expect(spendingMetric).not.toHaveTextContent("30");
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
    expect(screen.getByRole("heading", { level: 2, name: "Категории" })).toBeInTheDocument();
    expect(screen.getByText("Продукты")).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: /Аналитика/i }));
    expect(screen.getByRole("heading", { level: 2, name: "Аналитика" })).toBeInTheDocument();
    expect(screen.getByText("Итог")).toBeInTheDocument();
    expect(document.querySelector('input[type="file"]')).toBeNull();
    expect(screen.queryByLabelText(/Файл отч[её]та/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Импорт отчета" })).not.toBeInTheDocument();
  });

  it("switches analytics month and reloads reports with selected date boundaries", async () => {
    const user = userEvent.setup();
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
    await user.click(screen.getByTestId("mobile-nav-operations"));
    expect(screen.getByRole("heading", { level: 2, name: "Операции" })).toBeInTheDocument();

    await user.click(screen.getByTestId("mobile-nav-assets"));
    expect(screen.getByRole("heading", { level: 2, name: "Счета и активы" })).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: /Категории/i }));

    expect(screen.getByRole("heading", { level: 2, name: "Категории" })).toBeInTheDocument();
    expect(screen.getByText("Продукты")).toBeInTheDocument();
  });

  it("uploads a screenshot, reviews OCR category candidates, saves mapping and creates drafts after confirmation", async () => {
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
    expect(screen.getByLabelText("Категория для Products")).toHaveValue("category-1");
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
    await user.selectOptions(within(firstDraft).getByLabelText("Категория draft-1"), "category-1");
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
    await user.selectOptions(within(sheet).getByLabelText("Категория"), "category-1");
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
  it("shows explicit personal, shared and overview modes without technical wording", async () => {
    const user = userEvent.setup();
    render(<App client={makeClient()} />);

    await screen.findByRole("heading", { name: "Деньги" });
    const modeSwitch = screen.getByRole("group", { name: "Режим просмотра" });
    expect(within(modeSwitch).getByRole("button", { name: /Личное/i })).toBeInTheDocument();
    expect(within(modeSwitch).getByRole("button", { name: /Общее/i })).toBeInTheDocument();
    expect(within(modeSwitch).getByRole("button", { name: /Обзор/i })).toBeInTheDocument();
    expect(screen.getByText("Личное видно только вам")).toBeInTheDocument();
    expect(screen.getByText("Покупка продуктов")).toBeInTheDocument();
    expect(screen.queryByText("Домашняя покупка")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Общее/i }));
    expect(screen.getByText("Общее для семьи")).toBeInTheDocument();
    expect(screen.getByText("Домашняя покупка")).toBeInTheDocument();
    expect(screen.queryByText("Покупка продуктов")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Обзор/i }));
    expect(screen.getByText("Мой обзор: личное + общее, без личных данных других участников")).toBeInTheDocument();
    expect(screen.getByText("Покупка продуктов")).toBeInTheDocument();
    expect(screen.getByText("Домашняя покупка")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/combined_viewer_overview|shared_family_report/i);
  });
});
