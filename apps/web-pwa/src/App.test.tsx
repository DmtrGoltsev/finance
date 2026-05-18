import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { DashboardSnapshot } from "./api/types";

const liveSnapshot: DashboardSnapshot = {
  session: {
    viewerName: "Demo owner",
    householdName: "Демо-семья",
    accessLabel: "Live API: session"
  },
  accounts: [
    {
      id: "account-1",
      name: "Dev Personal Cash",
      ownerName: "Личный",
      kind: "cash",
      ownershipType: "personal",
      householdId: null,
      status: "active",
      version: 1,
      balance: { value: 925.5, currency: "USD" }
    },
    {
      id: "account-2",
      name: "Dev Personal Savings",
      ownerName: "Личный",
      kind: "savings",
      ownershipType: "personal",
      householdId: null,
      status: "active",
      version: 1,
      balance: { value: 125, currency: "USD" }
    }
  ],
  categories: [
    {
      id: "category-1",
      name: "Dev Groceries",
      direction: "expense",
      scope: "personal",
      householdId: null,
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
      title: "Dev household supplies",
      accountId: "account-1",
      categoryId: "category-1",
      version: 1,
      categoryName: "Dev Groceries",
      accountName: "Dev Personal Cash",
      amount: { value: -69.75, currency: "USD" }
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
      fromAccountName: "Dev Personal Cash",
      toAccountName: "Dev Personal Savings",
      amount: { value: 25, currency: "USD" }
    }
  ],
  reports: [
    {
      mode: "shared_family_report",
      title: "Общий семейный отчет",
      periodLabel: "Текущий период",
      income: { value: 250, currency: "USD" },
      expense: { value: 69.75, currency: "USD" },
      balanceDelta: { value: 180.25, currency: "USD" }
    },
    {
      mode: "combined_viewer_overview",
      title: "Сводный обзор участника",
      periodLabel: "Текущий период",
      income: { value: 250, currency: "USD" },
      expense: { value: 0, currency: "USD" },
      balanceDelta: { value: 250, currency: "USD" }
    }
  ]
};

function makeClient() {
  return {
    archiveAccount: vi.fn(async () => liveSnapshot.accounts[0]),
    archiveCategory: vi.fn(async () => liveSnapshot.categories[0]),
    archiveOperation: vi.fn(async () => undefined),
    archiveTransfer: vi.fn(async () => undefined),
    createDemoAccount: vi.fn(async () => liveSnapshot.accounts[0]),
    createDemoCategory: vi.fn(async () => liveSnapshot.categories[0]),
    createDemoOperation: vi.fn(async () => liveSnapshot.operations[0]),
    createDemoTransfer: vi.fn(async () => liveSnapshot.transfers[0]),
    deleteAccount: vi.fn(async () => undefined),
    deleteCategory: vi.fn(async () => undefined),
    getDashboardSnapshot: vi.fn(async () => liveSnapshot),
    restoreAccount: vi.fn(async () => liveSnapshot.accounts[0]),
    restoreCategory: vi.fn(async () => liveSnapshot.categories[0]),
    restoreOperation: vi.fn(async () => liveSnapshot.operations[0]),
    restoreTransfer: vi.fn(async () => liveSnapshot.transfers[0]),
    updateAccount: vi.fn(async () => liveSnapshot.accounts[0]),
    updateCategory: vi.fn(async () => liveSnapshot.categories[0]),
    updateOperation: vi.fn(async () => liveSnapshot.operations[0]),
    updateTransfer: vi.fn(async () => liveSnapshot.transfers[0])
  };
}

describe("PWA live shell", () => {
  it("renders Russian finance shell with live API data", async () => {
    render(<App client={makeClient()} />);

    expect(
      await screen.findByRole("heading", { name: "Финансовая панель" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Обзор/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Счета/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Категории/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Операции/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Переводы/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Отчеты/i })).toBeInTheDocument();
    expect(screen.getByText("Dev Personal Cash")).toBeInTheDocument();
    expect(screen.getByText("Dev household supplies")).toBeInTheDocument();
  });

  it("shows explicit Russian report mode vocabulary", async () => {
    const user = userEvent.setup();
    render(<App client={makeClient()} />);

    await screen.findByRole("heading", { name: "Финансовая панель" });
    await user.click(screen.getByRole("button", { name: /Отчеты/i }));

    expect(
      screen.getByRole("button", { name: "Общий семейный отчет" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Сводный обзор участника" })
    ).toBeInTheDocument();
  });

  it("exposes account, category, operation and transfer lifecycle controls", async () => {
    const user = userEvent.setup();
    render(<App client={makeClient()} />);

    await screen.findByRole("heading", { name: "Финансовая панель" });

    await user.click(screen.getByRole("button", { name: /Счета/i }));
    expect(screen.getByText("CRUD / архив / восстановление счета")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Создать/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Обновить/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Архив/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Удалить/i })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /Категории/i }));
    expect(screen.getByText("CRUD / архив / восстановление категории")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Операции/i }));
    expect(screen.getByText("CRUD / архив / восстановление операции")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Переводы/i }));
    expect(
      screen.getByText("Ручной перевод: создать / обновить / удалить / восстановить")
    ).toBeInTheDocument();
    expect(screen.getByTestId("transfer-count")).toHaveTextContent("1 между счетами");
    expect(screen.getByTestId("transfer-row")).toHaveTextContent("Dev Personal Cash");
  });
});
