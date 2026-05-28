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
