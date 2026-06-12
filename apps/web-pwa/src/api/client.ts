import type {
  AccountKind,
  AccountSummary,
  CaptureDraftCreateInput,
  CaptureDraftSummary,
  CaptureDraftUpdateInput,
  CategoryDirection,
  CategoryScope,
  CategorySummary,
  CurrencyCode,
  DashboardSnapshot,
  MoneyAmount,
  OperationSummary,
  ReportMode,
  ReportSummary,
  ScreenshotOcrResult,
  TransferSummary
} from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_PROD_API_BASE_URL = "/finance-api";
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
  isPaymentAccount?: boolean;
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
  iconKey?: string | null;
  color?: string | null;
  scope?: "personal" | "household";
  householdId?: string | null;
  status?: "active" | "archived" | "deleted";
  version?: number;
};

type TransactionDto = {
  id: string;
  transactionType:
    | "income"
    | "expense"
    | "transfer"
    | "brokerage"
    | "asset_buy"
    | "asset_sell"
    | "interest"
    | "dividend"
    | "adjustment";
  accountId: string;
  counterpartyAccountId: string | null;
  categoryId: string | null;
  amount: string | number;
  currency: string;
  occurredAt: string;
  transactionDate?: string | null;
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

type CaptureDraftDto = {
  id: string;
  status: "pending" | "confirmed" | "discarded";
  idempotencyKey: string;
  captureSource: "screenshot";
  capturedAt: string;
  occurredDate?: string | null;
  occurredAt?: string | null;
  amount: string | number;
  currency: string;
  description: string;
  accountId: string | null;
  categoryId: string | null;
  confidence: string | number | null;
};

type ScreenshotOcrResponseDto = {
  captureSource: "screenshot";
  parseVersion: "category-aggregate-v1";
  recognizedAt: string;
  items: Array<{
    candidateType: "categoryAggregate";
    categoryAggregate: {
      externalLabel: string;
    };
    amount: string | number;
    currency: string;
    operationCount: number;
    description: string;
    confidence: string | number;
    idempotencyKey: string;
    evidenceHash: string;
    suggestedCategoryId: string | null;
  }>;
  warnings: Array<{
    code: "NO_CATEGORY_AGGREGATES_FOUND";
    message: string;
  }>;
};

type PageEnvelope<T> = {
  items: T[];
};

type DataEnvelope<T> = {
  data: T;
};

type AccountCreateInput = {
  name?: string;
  kind?: AccountKind;
  isPaymentAccount?: boolean;
  currency?: CurrencyCode;
  initialBalance?: number;
  ownershipType?: "personal" | "shared";
  householdId?: string | null;
};

type LoginInput = {
  email: string;
  password: string;
};

type CategoryCreateInput = {
  name: string;
  direction: CategoryDirection;
  scope: CategoryScope;
  householdId: string | null;
  iconKey: string | null;
  color: string | null;
};

type CategoryUpdateInput = {
  categoryId: string;
  name?: string;
  iconKey?: string | null;
  color?: string | null;
  version?: number;
};

type OperationCreateInput = {
  accountId: string;
  categoryId: string | null;
  currency: CurrencyCode;
  transactionType?: "income" | "expense";
  amount?: number;
  transactionDate?: string;
  occurredAt?: string;
  description?: string | null;
};

type ReportPeriodInput = {
  startDate?: string;
  endDate?: string;
};

type TransferCreateInput = {
  fromAccountId: string;
  toAccountId: string;
  currency: CurrencyCode;
  amount?: number;
  occurredAt?: string;
  description?: string | null;
};

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly method: string,
    readonly path: string
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export interface FinanceApiClient {
  loginWithPassword(input: LoginInput): Promise<void>;
  logout(): Promise<void>;
  getDashboardSnapshot(input?: ReportPeriodInput): Promise<DashboardSnapshot>;
  createDemoAccount(input?: AccountCreateInput): Promise<AccountSummary>;
  updateAccount(input: {
    accountId: string;
    isPaymentAccount?: boolean;
    version?: number;
  }): Promise<AccountSummary>;
  archiveAccount(accountId: string): Promise<AccountSummary>;
  restoreAccount(accountId: string): Promise<AccountSummary>;
  deleteAccount(accountId: string): Promise<void>;
  createDemoCategory(input: CategoryCreateInput): Promise<CategorySummary>;
  updateCategory(input: CategoryUpdateInput): Promise<CategorySummary>;
  archiveCategory(categoryId: string): Promise<CategorySummary>;
  restoreCategory(categoryId: string): Promise<CategorySummary>;
  deleteCategory(categoryId: string): Promise<void>;
  createDemoOperation(input: OperationCreateInput): Promise<OperationSummary>;
  updateOperation(input: {
    transactionId: string;
    version?: number;
  }): Promise<OperationSummary>;
  archiveOperation(transactionId: string): Promise<void>;
  restoreOperation(transactionId: string): Promise<OperationSummary>;
  createDemoTransfer(input: TransferCreateInput): Promise<TransferSummary>;
  updateTransfer(input: {
    transactionId: string;
    version?: number;
  }): Promise<TransferSummary>;
  archiveTransfer(transactionId: string): Promise<void>;
  restoreTransfer(transactionId: string): Promise<TransferSummary>;
  uploadScreenshotOcr(
    image: File,
    capturedAt?: string,
    householdId?: string | null
  ): Promise<ScreenshotOcrResult>;
  saveCategoryMapping(
    externalLabel: string,
    categoryId: string,
    householdId?: string | null
  ): Promise<void>;
  createCaptureDraft(input: CaptureDraftCreateInput): Promise<CaptureDraftSummary>;
  listCaptureDrafts(input?: {
    status?: "pending" | "confirmed" | "discarded";
    limit?: number;
  }): Promise<CaptureDraftSummary[]>;
  updateCaptureDraft(input: CaptureDraftUpdateInput): Promise<CaptureDraftSummary>;
  confirmCaptureDraft(draftId: string): Promise<CaptureDraftSummary>;
  discardCaptureDraft(draftId: string): Promise<CaptureDraftSummary>;
}

export type LiveFinanceApiClientOptions = {
  baseUrl?: string;
  fetcher?: Fetcher;
};

export function getApiBaseUrl(): string {
  return (
    import.meta.env.VITE_API_BASE_URL?.trim() ||
    (import.meta.env.PROD ? DEFAULT_PROD_API_BASE_URL : DEFAULT_API_BASE_URL)
  ).replace(/\/+$/, "");
}

export class LiveFinanceApiClient implements FinanceApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: Fetcher;
  private csrfToken: string | null;

  constructor(options: LiveFinanceApiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? getApiBaseUrl()).replace(/\/+$/, "");
    this.fetcher = options.fetcher ?? fetch.bind(globalThis);
    this.csrfToken = readCookie(CSRF_COOKIE_NAME);
  }

  async loginWithPassword(input: LoginInput): Promise<void> {
    const loginResponse = await this.request<LoginResponseDto>(
      "/api/v1/sessions",
      {
        method: "POST",
        body: JSON.stringify({
          email: input.email.trim(),
          password: input.password,
          transport: "pwa_cookie"
        })
      },
      { csrf: "omit" }
    );

    this.csrfToken = loginResponse.csrfToken || readCookie(CSRF_COOKIE_NAME);
  }

  async logout(): Promise<void> {
    await this.request<void>(
      "/api/v1/sessions/current",
      { method: "DELETE" },
      { empty: true }
    );
    this.csrfToken = null;
    clearCookie(CSRF_COOKIE_NAME);
  }

  async getDashboardSnapshot(input: ReportPeriodInput = {}): Promise<DashboardSnapshot> {
    const session = await this.get<SessionResponseDto>("/api/v1/sessions/current");
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
    const reports = await this.getReports(householdId, currency, input);

    return {
      session: {
        viewerName: "Владелец",
        householdName: householdId ? "Общие финансы" : "Личный режим",
        accessLabel: "Вход выполнен",
        householdId
      },
      accounts,
      categories,
      operations,
      transfers,
      reports
    };
  }

  async createDemoAccount(input: AccountCreateInput = {}): Promise<AccountSummary> {
    const envelope = await this.request<DataEnvelope<AccountDto>>(
      "/api/v1/accounts",
      {
        method: "POST",
        body: JSON.stringify({
          name: input.name?.trim() || `Новый актив ${uniqueSuffix()}`,
          accountType: accountTypeFromKind(input.kind ?? "cash"),
          isPaymentAccount: input.isPaymentAccount ?? true,
          ownershipType: input.ownershipType ?? "personal",
          householdId: input.ownershipType === "shared" ? input.householdId : null,
          currency: input.currency ?? "RUB",
          initialBalance: String(input.initialBalance ?? 0)
        })
      }
    );

    return mapAccount(envelope.data);
  }

  async updateAccount(input: {
    accountId: string;
    isPaymentAccount?: boolean;
    version?: number;
  }): Promise<AccountSummary> {
    const body =
      input.isPaymentAccount === undefined
        ? {
            name: `Updated account ${uniqueSuffix()}`,
            ...(input.version ? { version: input.version } : {})
          }
        : {
            isPaymentAccount: input.isPaymentAccount,
            ...(input.version ? { version: input.version } : {})
          };
    const envelope = await this.request<DataEnvelope<AccountDto>>(
      `/api/v1/accounts/${input.accountId}`,
      {
        method: "PATCH",
        body: JSON.stringify(body)
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

  async createDemoCategory(input: CategoryCreateInput): Promise<CategorySummary> {
    const envelope = await this.request<DataEnvelope<CategoryDto>>(
      "/api/v1/categories",
      {
        method: "POST",
        body: JSON.stringify({
          name: input.name.trim(),
          type: input.direction,
          scope: input.scope,
          householdId: input.scope === "household" ? input.householdId : null,
          iconKey: input.iconKey,
          color: input.color
        })
      }
    );

    return mapCategory(envelope.data);
  }

  async updateCategory(input: CategoryUpdateInput): Promise<CategorySummary> {
    const envelope = await this.request<DataEnvelope<CategoryDto>>(
      `/api/v1/categories/${input.categoryId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          ...(input.name ? { name: input.name.trim() } : {}),
          ...(input.iconKey !== undefined ? { iconKey: input.iconKey } : {}),
          ...(input.color !== undefined ? { color: input.color } : {}),
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

  async createDemoOperation(input: OperationCreateInput): Promise<OperationSummary> {
    const transactionType = input.transactionType ?? "expense";
    const amount = Math.max(0, input.amount ?? 17);
    const envelope = await this.request<DataEnvelope<TransactionDto>>(
      "/api/v1/transactions",
      {
        method: "POST",
        body: JSON.stringify({
          transactionType,
          accountId: input.accountId,
          categoryId: input.categoryId,
          amount: amount.toFixed(4),
          currency: input.currency,
          transactionDate:
            input.transactionDate ?? dateOnlyFromValue(input.occurredAt) ?? todayDateOnly(),
          ...(input.occurredAt ? { occurredAt: input.occurredAt } : {}),
          description: input.description?.trim() || transactionTypeLabel(transactionType),
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
          description: "Обновлено",
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

  async createDemoTransfer(input: TransferCreateInput): Promise<TransferSummary> {
    const amount = Math.max(0, input.amount ?? 11);
    const envelope = await this.request<DataEnvelope<TransactionDto>>(
      "/api/v1/transactions",
      {
        method: "POST",
        body: JSON.stringify({
          transactionType: "transfer",
          accountId: input.fromAccountId,
          counterpartyAccountId: input.toAccountId,
          amount: amount.toFixed(4),
          currency: input.currency,
          occurredAt: input.occurredAt ?? new Date().toISOString(),
          description: input.description?.trim() || "Перевод",
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
          description: "Перевод обновлен",
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

  async uploadScreenshotOcr(
    image: File,
    capturedAt?: string,
    householdId?: string | null
  ): Promise<ScreenshotOcrResult> {
    const body = new FormData();
    body.append("image", image);
    if (capturedAt) {
      body.append("capturedAt", capturedAt);
    }
    if (householdId) {
      body.append("householdId", householdId);
    }

    const envelope = await this.request<DataEnvelope<ScreenshotOcrResponseDto>>(
      "/api/v1/capture-drafts/screenshot-ocr",
      {
        method: "POST",
        body
      }
    );

    return {
      ...envelope.data,
      items: envelope.data.items.map((item) => ({
        candidateType: item.candidateType,
        externalLabel: item.categoryAggregate.externalLabel,
        amount: money(item.amount, item.currency),
        operationCount: item.operationCount,
        description: item.description,
        confidence: Number(item.confidence),
        idempotencyKey: item.idempotencyKey,
        evidenceHash: item.evidenceHash,
        suggestedCategoryId: item.suggestedCategoryId
      }))
    };
  }

  async saveCategoryMapping(
    externalLabel: string,
    categoryId: string,
    householdId?: string | null
  ): Promise<void> {
    await this.request<DataEnvelope<{ categoryId: string; householdId: string | null }>>(
      "/api/v1/capture-drafts/category-mappings",
      {
        method: "PUT",
        body: JSON.stringify({
          externalLabel,
          categoryId,
          ...(householdId ? { householdId } : {})
        })
      }
    );
  }

  async createCaptureDraft(input: CaptureDraftCreateInput): Promise<CaptureDraftSummary> {
    const envelope = await this.request<DataEnvelope<CaptureDraftDto>>(
      "/api/v1/capture-drafts",
      {
        method: "POST",
        body: JSON.stringify({
          idempotencyKey: input.idempotencyKey,
          captureSource: input.captureSource,
          capturedAt: input.capturedAt,
          amount: input.amount.toFixed(4),
          currency: input.currency,
          description: input.description.trim(),
          ...(input.occurredDate ? { occurredDate: input.occurredDate } : {}),
          ...(input.occurredAt ? { occurredAt: input.occurredAt } : {}),
          ...(input.merchantName ? { merchantName: input.merchantName } : {}),
          ...(input.accountId ? { accountId: input.accountId } : {}),
          ...(input.categoryId ? { categoryId: input.categoryId } : {}),
          ...(input.confidence !== undefined && input.confidence !== null
            ? { confidence: input.confidence.toFixed(4) }
            : {}),
          ...(input.sourceAppPackage ? { sourceAppPackage: input.sourceAppPackage } : {}),
          ...(input.sourceAppLabel ? { sourceAppLabel: input.sourceAppLabel } : {}),
          ...(input.evidenceHash ? { evidenceHash: input.evidenceHash } : {})
        })
      }
    );

    return mapCaptureDraft(envelope.data);
  }

  async listCaptureDrafts(
    input: { status?: "pending" | "confirmed" | "discarded"; limit?: number } = {}
  ): Promise<CaptureDraftSummary[]> {
    const params = new URLSearchParams();
    if (input.status) {
      params.set("status", input.status);
    }
    params.set("limit", String(input.limit ?? 50));

    const envelope = await this.get<PageEnvelope<CaptureDraftDto>>(
      `/api/v1/capture-drafts?${params.toString()}`
    );

    return envelope.items.map(mapCaptureDraft);
  }

  async updateCaptureDraft(input: CaptureDraftUpdateInput): Promise<CaptureDraftSummary> {
    const envelope = await this.request<DataEnvelope<CaptureDraftDto>>(
      `/api/v1/capture-drafts/${input.draftId}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          ...(input.amount !== undefined ? { amount: input.amount.toFixed(4) } : {}),
          ...(input.currency !== undefined ? { currency: input.currency } : {}),
          ...(input.description !== undefined
            ? { description: input.description.trim() }
            : {}),
          ...(input.occurredDate !== undefined
            ? { occurredDate: input.occurredDate }
            : {}),
          ...(input.occurredAt !== undefined ? { occurredAt: input.occurredAt } : {}),
          ...(input.accountId !== undefined ? { accountId: input.accountId } : {}),
          ...(input.categoryId !== undefined ? { categoryId: input.categoryId } : {}),
          ...(input.confidence !== undefined && input.confidence !== null
            ? { confidence: input.confidence.toFixed(4) }
            : input.confidence === null
              ? { confidence: null }
              : {})
        })
      }
    );

    return mapCaptureDraft(envelope.data);
  }

  async confirmCaptureDraft(draftId: string): Promise<CaptureDraftSummary> {
    const envelope = await this.request<DataEnvelope<CaptureDraftDto>>(
      `/api/v1/capture-drafts/${draftId}/confirm`,
      { method: "POST" }
    );

    return mapCaptureDraft(envelope.data);
  }

  async discardCaptureDraft(draftId: string): Promise<CaptureDraftSummary> {
    const envelope = await this.request<DataEnvelope<CaptureDraftDto>>(
      `/api/v1/capture-drafts/${draftId}/discard`,
      { method: "POST" }
    );

    return mapCaptureDraft(envelope.data);
  }

  private async getReports(
    householdId: string | null,
    currency: CurrencyCode,
    period: ReportPeriodInput = {}
  ): Promise<ReportSummary[]> {
    const modes: ReportMode[] = [
      "shared_family_report",
      "combined_viewer_overview"
    ];

    if (!householdId) {
      return modes.map((mode) => emptyReport(mode, currency));
    }

    return Promise.all(
      modes.map(async (mode) => {
        const params = new URLSearchParams({
          reportMode: mode,
          householdId,
          currency
        });
        if (period.startDate) {
          params.set("startDate", period.startDate);
        }
        if (period.endDate) {
          params.set("endDate", period.endDate);
        }
        const envelope = await this.get<DataEnvelope<ReportSummaryDto>>(
          `/api/v1/reports/summary?${params.toString()}`
        );

        return mapReport(envelope.data, currency, period);
      })
    );
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
    if (init.body && !isFormDataBody(init.body)) {
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
    if (response.status === 403 && options.csrf !== "omit" && isUnsafeMethod(method)) {
      this.csrfToken = null;
    }
    if (!response.ok) {
      throw new ApiRequestError(
        `API ${method} ${path} failed: ${response.status}`,
        response.status,
        method,
        path
      );
    }

    if (options.empty || response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  }
}

function isFormDataBody(body: BodyInit): boolean {
  return typeof FormData !== "undefined" && body instanceof FormData;
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

function clearCookie(name: string): void {
  if (typeof document === "undefined") {
    return;
  }

  document.cookie = `${encodeURIComponent(name)}=; Max-Age=0; path=/`;
}

export function isApiRequestError(error: unknown, status?: number): error is ApiRequestError {
  return error instanceof ApiRequestError && (status === undefined || error.status === status);
}

function mapAccount(account: AccountDto): AccountSummary {
  return {
    id: account.id,
    name: userFacingSeedText(account.name),
    ownerName: account.ownershipType === "shared" ? "Общее" : "Личное",
    kind: mapAccountKind(account.accountType),
    isPaymentAccount: account.isPaymentAccount ?? true,
    ownershipType: account.ownershipType,
    householdId: account.householdId,
    status: account.status,
    version: account.version,
    balance: money(account.currentBalance, account.currency)
  };
}

function mapAccountKind(accountType: string): AccountKind {
  const normalized = accountType.toLowerCase();
  if (["cash", "наличные"].includes(normalized)) {
    return "cash";
  }
  if (["card", "debit", "credit_card"].includes(normalized)) {
    return "card";
  }
  if (["bank", "checking"].includes(normalized)) {
    return "bank";
  }
  if (["deposit", "savings", "saving"].includes(normalized)) {
    return "deposit";
  }
  if (["broker", "brokerage", "investment"].includes(normalized)) {
    return "brokerage";
  }
  if (["metal", "metals", "gold"].includes(normalized)) {
    return "metal";
  }

  return "other";
}

function accountTypeFromKind(kind: AccountKind): string {
  const accountTypes: Record<AccountKind, string> = {
    bank: "bank",
    brokerage: "brokerage",
    card: "card",
    cash: "cash",
    deposit: "deposit",
    metal: "metal",
    other: "other"
  };

  return accountTypes[kind];
}

function mapCategory(category: CategoryDto): CategorySummary {
  return {
    id: category.id,
    name: userFacingSeedText(category.name),
    direction: category.type,
    iconKey: category.iconKey,
    color: category.color,
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
    date: transaction.transactionDate ?? transaction.occurredAt,
    title:
      userFacingSeedText(transaction.description) ||
      transactionTypeLabel(transaction.transactionType),
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
    date: transaction.transactionDate ?? transaction.occurredAt,
    accountId: transaction.accountId,
    counterpartyAccountId: transaction.counterpartyAccountId,
    version: transaction.version,
    transferScope: transaction.transferScope,
    transferStatus: transaction.transferStatus,
    fromAccountName:
      accounts.find((account) => account.id === transaction.accountId)?.name ??
      "Откуда",
    toAccountName:
      accounts.find((account) => account.id === transaction.counterpartyAccountId)
        ?.name ?? "Куда",
    amount: money(transaction.amount, transaction.currency)
  };
}

function mapCaptureDraft(draft: CaptureDraftDto): CaptureDraftSummary {
  return {
    id: draft.id,
    status: draft.status,
    idempotencyKey: draft.idempotencyKey,
    captureSource: draft.captureSource,
    capturedAt: draft.capturedAt,
    occurredDate: draft.occurredDate ?? dateOnlyFromValue(draft.occurredAt) ?? null,
    occurredAt: draft.occurredAt ?? null,
    amount: money(draft.amount, draft.currency),
    description: draft.description,
    accountId: draft.accountId,
    categoryId: draft.categoryId,
    confidence: draft.confidence === null ? null : Number(draft.confidence)
  };
}

function mapReport(
  report: ReportSummaryDto,
  fallbackCurrency: CurrencyCode,
  period: ReportPeriodInput = {}
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
    periodLabel: reportPeriodLabel(period),
    income: money(income, currency),
    expense: money(expense, currency),
    balanceDelta: money(delta, currency)
  };
}

function emptyReport(mode: ReportMode, currency: CurrencyCode): ReportSummary {
  return {
    mode,
    title: reportModeLabels[mode],
    periodLabel: "Текущий месяц",
    income: money(0, currency),
    expense: money(0, currency),
    balanceDelta: money(0, currency)
  };
}

function reportPeriodLabel(period: ReportPeriodInput): string {
  if (period.startDate && period.endDate) {
    return `${period.startDate} - ${period.endDate}`;
  }

  return "Текущий месяц";
}

function todayDateOnly(): string {
  const date = new Date();
  return formatDateOnly(date.getFullYear(), date.getMonth() + 1, date.getDate());
}

function dateOnlyFromValue(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return formatDateOnly(date.getFullYear(), date.getMonth() + 1, date.getDate());
}

function formatDateOnly(year: number, month: number, day: number): string {
  return [
    String(year).padStart(4, "0"),
    String(month).padStart(2, "0"),
    String(day).padStart(2, "0")
  ].join("-");
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
    transfer: "Перевод",
    brokerage: "Актив",
    asset_buy: "Покупка актива",
    asset_sell: "Продажа актива",
    interest: "Проценты",
    dividend: "Дивиденды",
    adjustment: "Корректировка"
  };

  return labels[type];
}

const reportModeLabels: Record<ReportMode, string> = {
  shared_family_report: "Общее",
  combined_viewer_overview: "Обзор"
};

function userFacingSeedText(value: string | null | undefined): string {
  const trimmed = value?.trim() ?? "";
  const labels: Record<string, string> = {
    "Dev Personal Cash": "Личные наличные",
    "Dev Household Card": "Семейная карта",
    "Dev Household Deposit": "Общий вклад",
    "Dev Brokerage": "Брокерский счет",
    "Dev Metal": "Металлы",
    "Dev Groceries": "Продукты",
    "Dev Home": "Дом",
    "Dev Salary": "Зарплата",
    "Dev household supplies": "Домашние покупки",
    "Dev sample income": "Зарплата",
    "Dev same-household transfer": "Между общими счетами",
    "Dev brokerage asset buy": "Покупка актива",
    "Dev deposit interest": "Проценты по вкладу",
    "Dev brokerage dividend": "Дивиденды"
  };

  return labels[trimmed] ?? trimmed.replace(/^Dev\s+/i, "");
}

function uniqueSuffix(): string {
  return new Date().toISOString().replace(/\D/g, "").slice(4, 14);
}

export const financeApiClient: FinanceApiClient = new LiveFinanceApiClient();
