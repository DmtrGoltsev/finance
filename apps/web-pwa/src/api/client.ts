import type {
  AccountKind,
  AccountSummary,
  CategorySummary,
  CurrencyCode,
  DashboardSnapshot,
  MoneyAmount,
  OperationSummary,
  ReportMode,
  ReportSummary,
  TransferSummary
} from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_EMAIL = "demo.owner@example.test";
const DEFAULT_PASSWORD = "demo-password-only";
const CSRF_COOKIE_NAME = "finance_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";

type Fetcher = typeof fetch;

type MembershipDto = {
  householdId: string;
  status: string;
};

type ActorDto = {
  userId: string;
  sessionId: string;
  memberships: MembershipDto[];
};

type LoginResponseDto = {
  transport: "pwa_cookie";
  csrfToken: string;
  expiresAt: string;
  actor: ActorDto;
};

type SessionResponseDto = {
  actor: ActorDto;
};

type AccountDto = {
  id: string;
  name: string;
  accountType: string;
  ownershipType: "personal" | "shared";
  ownerUserId: string | null;
  householdId: string | null;
  currency: string;
  currentBalance: string | number;
  status?: "active" | "archived" | "deleted";
  version?: number;
};

type CategoryDto = {
  id: string;
  name: string;
  type: "income" | "expense";
  scope?: "personal" | "household";
  householdId?: string | null;
  status?: "active" | "archived" | "deleted";
  version?: number;
};

type TransactionDto = {
  id: string;
  transactionType: "income" | "expense" | "transfer";
  accountId: string;
  counterpartyAccountId: string | null;
  categoryId: string | null;
  amount: string | number;
  currency: string;
  occurredAt: string;
  description: string | null;
  sourceType?: "manual";
  transferScope?: string | null;
  transferStatus?: string | null;
  version?: number;
};

type ReportSummaryDto = {
  reportMode?: ReportMode;
  currency?: string;
  incomeTotal?: string | number;
  expenseTotal?: string | number;
  netTotal?: string | number;
  totalIncome?: string | number;
  totalExpense?: string | number;
  balanceDelta?: string | number;
  netAmount?: string | number;
  scope?: {
    reportMode?: ReportMode;
  };
  totalsByCurrency?: Array<{
    currency: string;
    incomeTotal?: string | number;
    expenseTotal?: string | number;
    netTotal?: string | number;
  }>;
};

type PageEnvelope<T> = {
  items: T[];
};

type DataEnvelope<T> = {
  data: T;
};

export interface FinanceApiClient {
  getDashboardSnapshot(): Promise<DashboardSnapshot>;
  createDemoAccount(): Promise<AccountSummary>;
  updateAccount(input: {
    accountId: string;
    version?: number;
  }): Promise<AccountSummary>;
  archiveAccount(accountId: string): Promise<AccountSummary>;
  restoreAccount(accountId: string): Promise<AccountSummary>;
  deleteAccount(accountId: string): Promise<void>;
  createDemoCategory(input: { householdId: string | null }): Promise<CategorySummary>;
  updateCategory(input: {
    categoryId: string;
    version?: number;
  }): Promise<CategorySummary>;
  archiveCategory(categoryId: string): Promise<CategorySummary>;
  restoreCategory(categoryId: string): Promise<CategorySummary>;
  deleteCategory(categoryId: string): Promise<void>;
  createDemoOperation(input: {
    accountId: string;
    categoryId: string | null;
    currency: CurrencyCode;
  }): Promise<OperationSummary>;
  updateOperation(input: {
    transactionId: string;
    version?: number;
  }): Promise<OperationSummary>;
  archiveOperation(transactionId: string): Promise<void>;
  restoreOperation(transactionId: string): Promise<OperationSummary>;
  createDemoTransfer(input: {
    fromAccountId: string;
    toAccountId: string;
    currency: CurrencyCode;
  }): Promise<TransferSummary>;
  updateTransfer(input: {
    transactionId: string;
    version?: number;
  }): Promise<TransferSummary>;
  archiveTransfer(transactionId: string): Promise<void>;
  restoreTransfer(transactionId: string): Promise<TransferSummary>;
}

export type LiveFinanceApiClientOptions = {
  baseUrl?: string;
  fetcher?: Fetcher;
  demoEmail?: string;
  demoPassword?: string;
};

export function getApiBaseUrl(): string {
  return (
    import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
  ).replace(/\/+$/, "");
}

export class LiveFinanceApiClient implements FinanceApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: Fetcher;
  private readonly demoEmail: string;
  private readonly demoPassword: string;
  private csrfToken: string | null;

  constructor(options: LiveFinanceApiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? getApiBaseUrl()).replace(/\/+$/, "");
    this.fetcher = options.fetcher ?? fetch.bind(globalThis);
    this.demoEmail = options.demoEmail ?? DEFAULT_EMAIL;
    this.demoPassword = options.demoPassword ?? DEFAULT_PASSWORD;
    this.csrfToken = readCookie(CSRF_COOKIE_NAME);
  }

  async getDashboardSnapshot(): Promise<DashboardSnapshot> {
    const session = await this.ensureSession();
    const [accountsEnvelope, categoriesEnvelope, transactionsEnvelope] =
      await Promise.all([
        this.get<PageEnvelope<AccountDto>>("/api/v1/accounts"),
        this.get<PageEnvelope<CategoryDto>>("/api/v1/categories"),
        this.get<PageEnvelope<TransactionDto>>("/api/v1/transactions")
      ]);

    const accounts = accountsEnvelope.items.map(mapAccount);
    const categories = categoriesEnvelope.items.map(mapCategory);
    const operations = transactionsEnvelope.items
      .filter((transaction) => transaction.transactionType !== "transfer")
      .map((transaction) => mapOperation(transaction, accounts, categories));
    const transfers = transactionsEnvelope.items
      .filter((transaction) => transaction.transactionType === "transfer")
      .map((transaction) => mapTransfer(transaction, accounts));
    const householdId = pickHouseholdId(session.actor);
    const currency = accounts[0]?.balance.currency ?? "RUB";
    const reports = await this.getReports(householdId, currency);

    return {
      session: {
        viewerName: "Demo owner",
        householdName: householdId ? "Демо-семья" : "Личный режим",
        accessLabel: `Live API: ${session.actor.sessionId.slice(0, 8)}`
      },
      accounts,
      categories,
      operations,
      transfers,
      reports
    };
  }

  async createDemoAccount(): Promise<AccountSummary> {
    const envelope = await this.request<DataEnvelope<AccountDto>>(
      "/api/v1/accounts",
      {
        method: "POST",
        body: JSON.stringify({
          name: `PWA E2E счет ${uniqueSuffix()}`,
          accountType: "cash",
          ownershipType: "personal",
          currency: "RUB",
          initialBalance: "123.0000"
        })
      }
    );

    return mapAccount(envelope.data);
  }

  async updateAccount(input: {
    accountId: string;
    version?: number;
  }): Promise<AccountSummary> {
    const envelope = await this.request<DataEnvelope<AccountDto>>(
      `/api/v1/accounts/${input.accountId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          name: `PWA E2E счет обновлен ${uniqueSuffix()}`,
          ...(input.version ? { version: input.version } : {})
        })
      }
    );

    return mapAccount(envelope.data);
  }

  async archiveAccount(accountId: string): Promise<AccountSummary> {
    const envelope = await this.request<DataEnvelope<AccountDto>>(
      `/api/v1/accounts/${accountId}/archive`,
      { method: "POST" }
    );

    return mapAccount(envelope.data);
  }

  async restoreAccount(accountId: string): Promise<AccountSummary> {
    const envelope = await this.request<DataEnvelope<AccountDto>>(
      `/api/v1/accounts/${accountId}/restore`,
      { method: "POST" }
    );

    return mapAccount(envelope.data);
  }

  async deleteAccount(accountId: string): Promise<void> {
    await this.request<void>(
      `/api/v1/accounts/${accountId}`,
      { method: "DELETE" },
      { empty: true }
    );
  }

  async createDemoCategory(): Promise<CategorySummary> {
    const envelope = await this.request<DataEnvelope<CategoryDto>>(
      "/api/v1/categories",
      {
        method: "POST",
        body: JSON.stringify({
          name: `PWA E2E категория ${uniqueSuffix()}`,
          type: "expense",
          scope: "personal",
          iconKey: "tag",
          color: "#2563EB"
        })
      }
    );

    return mapCategory(envelope.data);
  }

  async updateCategory(input: {
    categoryId: string;
    version?: number;
  }): Promise<CategorySummary> {
    const envelope = await this.request<DataEnvelope<CategoryDto>>(
      `/api/v1/categories/${input.categoryId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          name: `PWA E2E категория обновлена ${uniqueSuffix()}`,
          iconKey: "wallet",
          color: "#087F5B",
          ...(input.version ? { version: input.version } : {})
        })
      }
    );

    return mapCategory(envelope.data);
  }

  async archiveCategory(categoryId: string): Promise<CategorySummary> {
    const envelope = await this.request<DataEnvelope<CategoryDto>>(
      `/api/v1/categories/${categoryId}/archive`,
      { method: "POST" }
    );

    return mapCategory(envelope.data);
  }

  async restoreCategory(categoryId: string): Promise<CategorySummary> {
    const envelope = await this.request<DataEnvelope<CategoryDto>>(
      `/api/v1/categories/${categoryId}/restore`,
      { method: "POST" }
    );

    return mapCategory(envelope.data);
  }

  async deleteCategory(categoryId: string): Promise<void> {
    await this.request<void>(
      `/api/v1/categories/${categoryId}`,
      { method: "DELETE" },
      { empty: true }
    );
  }

  async createDemoOperation(input: {
    accountId: string;
    categoryId: string | null;
    currency: CurrencyCode;
  }): Promise<OperationSummary> {
    const envelope = await this.request<DataEnvelope<TransactionDto>>(
      "/api/v1/transactions",
      {
        method: "POST",
        body: JSON.stringify({
          transactionType: "expense",
          accountId: input.accountId,
          categoryId: input.categoryId,
          amount: "17.0000",
          currency: input.currency,
          occurredAt: new Date().toISOString(),
          description: "PWA lifecycle: создано",
          sourceType: "manual"
        })
      }
    );

    return mapOperation(envelope.data, [], []);
  }

  async updateOperation(input: {
    transactionId: string;
    version?: number;
  }): Promise<OperationSummary> {
    const envelope = await this.request<DataEnvelope<TransactionDto>>(
      `/api/v1/transactions/${input.transactionId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          amount: "18.0000",
          description: "PWA lifecycle: обновлено",
          ...(input.version ? { version: input.version } : {})
        })
      }
    );

    return mapOperation(envelope.data, [], []);
  }

  async archiveOperation(transactionId: string): Promise<void> {
    await this.request<void>(
      `/api/v1/transactions/${transactionId}`,
      { method: "DELETE" },
      { empty: true }
    );
  }

  async restoreOperation(transactionId: string): Promise<OperationSummary> {
    const envelope = await this.request<DataEnvelope<TransactionDto>>(
      `/api/v1/transactions/${transactionId}/restore`,
      { method: "POST" }
    );

    return mapOperation(envelope.data, [], []);
  }

  async createDemoTransfer(input: {
    fromAccountId: string;
    toAccountId: string;
    currency: CurrencyCode;
  }): Promise<TransferSummary> {
    const envelope = await this.request<DataEnvelope<TransactionDto>>(
      "/api/v1/transactions",
      {
        method: "POST",
        body: JSON.stringify({
          transactionType: "transfer",
          accountId: input.fromAccountId,
          counterpartyAccountId: input.toAccountId,
          amount: "11.0000",
          currency: input.currency,
          occurredAt: new Date().toISOString(),
          description: "PWA transfer lifecycle: создано",
          sourceType: "manual"
        })
      }
    );

    return mapTransfer(envelope.data, []);
  }

  async updateTransfer(input: {
    transactionId: string;
    version?: number;
  }): Promise<TransferSummary> {
    const envelope = await this.request<DataEnvelope<TransactionDto>>(
      `/api/v1/transactions/${input.transactionId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          amount: "12.0000",
          description: "PWA transfer lifecycle: обновлено",
          ...(input.version ? { version: input.version } : {})
        })
      }
    );

    return mapTransfer(envelope.data, []);
  }

  async archiveTransfer(transactionId: string): Promise<void> {
    await this.request<void>(
      `/api/v1/transactions/${transactionId}`,
      { method: "DELETE" },
      { empty: true }
    );
  }

  async restoreTransfer(transactionId: string): Promise<TransferSummary> {
    const envelope = await this.request<DataEnvelope<TransactionDto>>(
      `/api/v1/transactions/${transactionId}/restore`,
      { method: "POST" }
    );

    return mapTransfer(envelope.data, []);
  }

  private async ensureSession(): Promise<SessionResponseDto> {
    try {
      const session = await this.get<SessionResponseDto>("/api/v1/sessions/current");
      this.csrfToken = readCookie(CSRF_COOKIE_NAME);
      return session;
    } catch {
      this.csrfToken = null;
    }

    const loginResponse = await this.login();
    return { actor: loginResponse.actor };
  }

  private async login(): Promise<LoginResponseDto> {
    const loginResponse = await this.request<LoginResponseDto>(
      "/api/v1/sessions",
      {
        method: "POST",
        body: JSON.stringify({
          email: this.demoEmail,
          password: this.demoPassword,
          transport: "pwa_cookie"
        })
      },
      { csrf: "omit" }
    );

    this.csrfToken = loginResponse.csrfToken || readCookie(CSRF_COOKIE_NAME);
    return loginResponse;
  }

  private async getReports(
    householdId: string | null,
    currency: CurrencyCode
  ): Promise<ReportSummary[]> {
    if (!householdId) {
      return [
        emptyReport("combined_viewer_overview", currency),
        emptyReport("shared_family_report", currency)
      ];
    }

    const modes: ReportMode[] = [
      "shared_family_report",
      "combined_viewer_overview"
    ];
    const reports = await Promise.all(
      modes.map(async (mode) => {
        const params = new URLSearchParams({
          reportMode: mode,
          householdId,
          currency
        });
        const envelope = await this.get<DataEnvelope<ReportSummaryDto>>(
          `/api/v1/reports/summary?${params.toString()}`
        );

        return mapReport(envelope.data, currency);
      })
    );

    return reports;
  }

  private get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "GET" });
  }

  private async request<T>(
    path: string,
    init: RequestInit,
    options: { csrf?: "auto" | "omit"; empty?: boolean } = {}
  ): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body) {
      headers.set("Content-Type", "application/json");
    }

    const method = (init.method ?? "GET").toUpperCase();
    if (options.csrf !== "omit" && isUnsafeMethod(method)) {
      const csrfToken = this.csrfToken ?? readCookie(CSRF_COOKIE_NAME);
      if (csrfToken) {
        headers.set(CSRF_HEADER_NAME, csrfToken);
      }
    }

    let response = await this.fetcher(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers
    });
    if (
      response.status === 403 &&
      options.csrf !== "omit" &&
      isUnsafeMethod(method) &&
      path !== "/api/v1/sessions"
    ) {
      await this.login();
      const csrfToken = this.csrfToken ?? readCookie(CSRF_COOKIE_NAME);
      if (csrfToken) {
        headers.set(CSRF_HEADER_NAME, csrfToken);
      }
      response = await this.fetcher(`${this.baseUrl}${path}`, {
        ...init,
        credentials: "include",
        headers
      });
    }
    if (!response.ok) {
      throw new Error(`API ${init.method ?? "GET"} ${path} failed: ${response.status}`);
    }

    if (options.empty || response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  }
}

function isUnsafeMethod(method: string): boolean {
  return ["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase());
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));

  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

function mapAccount(account: AccountDto): AccountSummary {
  return {
    id: account.id,
    name: account.name,
    ownerName: account.ownershipType === "shared" ? "Семья" : "Личный",
    kind: mapAccountKind(account.accountType),
    ownershipType: account.ownershipType,
    householdId: account.householdId,
    status: account.status,
    version: account.version,
    balance: money(account.currentBalance, account.currency)
  };
}

function mapAccountKind(accountType: string): AccountKind {
  if (accountType === "cash") {
    return "cash";
  }
  if (accountType === "bank" || accountType === "card" || accountType === "debit") {
    return "debit";
  }

  return "savings";
}

function mapCategory(category: CategoryDto): CategorySummary {
  return {
    id: category.id,
    name: category.name,
    direction: category.type,
    scope: category.scope,
    householdId: category.householdId,
    status: category.status,
    version: category.version,
    planned: money(0, "RUB"),
    actual: money(0, "RUB")
  };
}

function mapOperation(
  transaction: TransactionDto,
  accounts: AccountSummary[],
  categories: CategorySummary[]
): OperationSummary {
  const signedAmount =
    transaction.transactionType === "expense"
      ? -Math.abs(Number(transaction.amount))
      : Math.abs(Number(transaction.amount));

  return {
    id: transaction.id,
    date: transaction.occurredAt,
    title: transaction.description || transactionTypeLabel(transaction.transactionType),
    accountId: transaction.accountId,
    categoryId: transaction.categoryId,
    version: transaction.version,
    categoryName:
      categories.find((category) => category.id === transaction.categoryId)?.name ??
      "Без категории",
    accountName:
      accounts.find((account) => account.id === transaction.accountId)?.name ??
      "Счет",
    amount: money(signedAmount, transaction.currency)
  };
}

function mapTransfer(
  transaction: TransactionDto,
  accounts: AccountSummary[]
): TransferSummary {
  return {
    id: transaction.id,
    date: transaction.occurredAt,
    accountId: transaction.accountId,
    counterpartyAccountId: transaction.counterpartyAccountId,
    version: transaction.version,
    transferScope: transaction.transferScope,
    transferStatus: transaction.transferStatus,
    fromAccountName:
      accounts.find((account) => account.id === transaction.accountId)?.name ??
      "Счет списания",
    toAccountName:
      accounts.find((account) => account.id === transaction.counterpartyAccountId)
        ?.name ?? "Счет зачисления",
    amount: money(transaction.amount, transaction.currency)
  };
}

function mapReport(
  report: ReportSummaryDto,
  fallbackCurrency: CurrencyCode
): ReportSummary {
  const total = report.totalsByCurrency?.[0];
  const mode = report.reportMode ?? report.scope?.reportMode;
  const currency = normalizeCurrency(
    report.currency ?? total?.currency ?? fallbackCurrency,
    fallbackCurrency
  );
  const income = report.incomeTotal ?? report.totalIncome ?? total?.incomeTotal ?? 0;
  const expense =
    report.expenseTotal ?? report.totalExpense ?? total?.expenseTotal ?? 0;
  const delta =
    report.netTotal ??
    report.balanceDelta ??
    report.netAmount ??
    total?.netTotal ??
    Number(income) - Number(expense);

  return {
    mode: mode ?? "combined_viewer_overview",
    title: reportModeLabels[mode ?? "combined_viewer_overview"],
    periodLabel: "Текущий период",
    income: money(income, currency),
    expense: money(expense, currency),
    balanceDelta: money(delta, currency)
  };
}

function emptyReport(mode: ReportMode, currency: CurrencyCode): ReportSummary {
  return {
    mode,
    title: reportModeLabels[mode],
    periodLabel: "Текущий период",
    income: money(0, currency),
    expense: money(0, currency),
    balanceDelta: money(0, currency)
  };
}

function money(value: string | number, currency: string): MoneyAmount {
  return {
    value: Number(value),
    currency: normalizeCurrency(currency, "RUB")
  };
}

function normalizeCurrency(
  currency: string,
  fallback: CurrencyCode
): CurrencyCode {
  if (currency === "RUB" || currency === "USD" || currency === "EUR") {
    return currency;
  }

  return fallback;
}

function pickHouseholdId(actor: ActorDto): string | null {
  const activeMembership = actor.memberships.find(
    (membership) => membership.status === "active"
  );

  return activeMembership?.householdId ?? null;
}

function transactionTypeLabel(type: TransactionDto["transactionType"]): string {
  const labels: Record<TransactionDto["transactionType"], string> = {
    income: "Доход",
    expense: "Расход",
    transfer: "Перевод"
  };

  return labels[type];
}

const reportModeLabels: Record<ReportMode, string> = {
  shared_family_report: "Общий семейный отчет",
  combined_viewer_overview: "Сводный обзор участника"
};

function uniqueSuffix(): string {
  return new Date().toISOString().replace(/\D/g, "").slice(4, 14);
}

export const financeApiClient: FinanceApiClient = new LiveFinanceApiClient();
