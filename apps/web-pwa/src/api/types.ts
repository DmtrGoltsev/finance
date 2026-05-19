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

export type ImportReportType =
  | "generic_finance_report"
  | "bank_statement"
  | "brokerage_report"
  | "deposit_report"
  | "metals_report";

export type ImportTargetScope = "personal" | "shared";

export type ImportReportPreviewRequest = {
  reportType: ImportReportType;
  sourceType: "file_metadata_only";
  targetScope: ImportTargetScope;
  householdId: string | null;
  fileName?: string;
  fileSizeBytes?: number;
  mimeType?: string;
};

export type ImportRecognitionSection = {
  key:
    | "accounts_assets"
    | "transactions"
    | "categories"
    | "transfers"
    | "brokerage_deposits_metals";
  title: string;
  status: "not_recognized_yet";
  text: string;
};

export type ImportReportPreviewResponse = {
  status: "preview_placeholder";
  canConfirm: false;
  willChangeData: false;
  message: string;
  scope: {
    targetScope: ImportTargetScope;
    householdId: string | null;
  };
  file: {
    fileName?: string;
    fileSizeBytes?: number;
    mimeType?: string;
  };
  summary: {
    title: string;
    statusText: string;
    sections: ImportRecognitionSection[];
  };
  warnings: Array<{
    code:
      | "NO_DATA_CHANGES_WITHOUT_CONFIRMATION"
      | "NO_FILE_STORAGE_OR_PARSING"
      | "PLACEHOLDER_ONLY";
    text: string;
  }>;
};
