export type CurrencyCode = "RUB" | "USD" | "EUR";

export type MoneyAmount = {
  value: number;
  currency: CurrencyCode;
};

export type AccountKind =
  | "card"
  | "bank"
  | "cash"
  | "deposit"
  | "brokerage"
  | "metal"
  | "other";

export type AccountSummary = {
  id: string;
  name: string;
  ownerName: string;
  kind: AccountKind;
  ownershipType?: "personal" | "shared";
  householdId?: string | null;
  status?: "active" | "archived" | "deleted";
  version?: number;
  balance: MoneyAmount;
};

export type CategoryDirection = "income" | "expense";
export type CategoryScope = "personal" | "household";

export type CategorySummary = {
  id: string;
  name: string;
  direction: CategoryDirection;
  iconKey?: string | null;
  color?: string | null;
  scope?: CategoryScope;
  householdId?: string | null;
  status?: "active" | "archived" | "deleted";
  version?: number;
  planned: MoneyAmount;
  actual: MoneyAmount;
};

export type OperationSummary = {
  id: string;
  date: string;
  title: string;
  accountId: string;
  categoryId: string | null;
  version?: number;
  categoryName: string;
  accountName: string;
  amount: MoneyAmount;
};

export type ScreenshotOcrCandidate = {
  candidateType: "categoryAggregate";
  externalLabel: string;
  amount: MoneyAmount;
  operationCount: number;
  description: string;
  confidence: number;
  idempotencyKey: string;
  evidenceHash: string;
  suggestedCategoryId: string | null;
};

export type ScreenshotOcrWarning = {
  code: "NO_CATEGORY_AGGREGATES_FOUND";
  message: string;
};

export type ScreenshotOcrResult = {
  captureSource: "screenshot";
  parseVersion: "category-aggregate-v1";
  recognizedAt: string;
  items: ScreenshotOcrCandidate[];
  warnings: ScreenshotOcrWarning[];
};

export type CaptureDraftCreateInput = {
  idempotencyKey: string;
  captureSource: "screenshot";
  capturedAt: string;
  amount: number;
  currency: CurrencyCode;
  description: string;
  occurredAt?: string | null;
  merchantName?: string | null;
  accountId?: string | null;
  categoryId?: string | null;
  confidence?: number | null;
  sourceAppPackage?: string | null;
  sourceAppLabel?: string | null;
  evidenceHash?: string | null;
};

export type CaptureDraftUpdateInput = {
  draftId: string;
  amount?: number;
  currency?: CurrencyCode;
  description?: string;
  occurredAt?: string | null;
  accountId?: string | null;
  categoryId?: string | null;
  confidence?: number | null;
};

export type CaptureDraftSummary = {
  id: string;
  status: "pending" | "confirmed" | "discarded";
  idempotencyKey: string;
  captureSource: "screenshot";
  capturedAt: string;
  occurredAt: string | null;
  amount: MoneyAmount;
  description: string;
  accountId: string | null;
  categoryId: string | null;
  confidence: number | null;
};

export type TransferSummary = {
  id: string;
  date: string;
  accountId: string;
  counterpartyAccountId: string | null;
  version?: number;
  transferScope?: string | null;
  transferStatus?: string | null;
  fromAccountName: string;
  toAccountName: string;
  amount: MoneyAmount;
};

export type ReportMode =
  | "shared_family_report"
  | "combined_viewer_overview";

export type ReportSummary = {
  mode: ReportMode;
  title: string;
  periodLabel: string;
  income: MoneyAmount;
  expense: MoneyAmount;
  balanceDelta: MoneyAmount;
};

export type SessionSnapshot = {
  viewerName: string;
  householdName: string;
  accessLabel: string;
  householdId: string | null;
};

export type DashboardSnapshot = {
  session: SessionSnapshot;
  accounts: AccountSummary[];
  categories: CategorySummary[];
  operations: OperationSummary[];
  transfers: TransferSummary[];
  reports: ReportSummary[];
};
