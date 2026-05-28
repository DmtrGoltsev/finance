import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { ApiRequestError } from "./api/client";
import type { DashboardSnapshot } from "./api/types";

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
      date: "2026-05-17T12:30:00Z",
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
      date: "2026-05-16T12:30:00Z",
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
      date: "2026-05-17T12:45:00Z",
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
    createDemoOperation: vi.fn(async () => snapshot.operations[0]),
    createDemoTransfer: vi.fn(async () => snapshot.transfers[0]),
    deleteAccount: vi.fn(async () => undefined),
    deleteCategory: vi.fn(async () => undefined),
    getDashboardSnapshot: vi.fn(async () => snapshot),
    loginWithPassword: vi.fn(async () => undefined),
    logout: vi.fn(async () => undefined),
    restoreAccount: vi.fn(async () => snapshot.accounts[0]),
    restoreCategory: vi.fn(async () => snapshot.categories[0]),
    restoreOperation: vi.fn(async () => snapshot.operations[0]),
    restoreTransfer: vi.fn(async () => snapshot.transfers[0]),
    updateAccount: vi.fn(async () => snapshot.accounts[0]),
    updateCategory: vi.fn(async () => snapshot.categories[0]),
    updateOperation: vi.fn(async () => snapshot.operations[0]),
    updateTransfer: vi.fn(async () => snapshot.transfers[0])
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

    await user.clear(within(sheet).getByLabelText("Сумма"));
    await user.type(within(sheet).getByLabelText("Сумма"), "345");
    await user.click(within(sheet).getByRole("button", { name: /Готово/i }));

    await waitFor(() => {
      expect(client.createDemoOperation).toHaveBeenCalledWith(
        expect.objectContaining({
          accountId: "account-1",
          amount: 345,
          categoryId: "category-1",
          transactionType: "expense"
        })
      );
    });
    expect(client.getDashboardSnapshot).toHaveBeenCalledTimes(2);
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
    expect(screen.getByText("Карта Мир → Вклад")).toBeInTheDocument();
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
    expect(screen.getByText("Сводный обзор")).toBeInTheDocument();
    expect(screen.getByText("Покупка продуктов")).toBeInTheDocument();
    expect(screen.getByText("Домашняя покупка")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/combined_viewer_overview|shared_family_report/i);
  });
});
