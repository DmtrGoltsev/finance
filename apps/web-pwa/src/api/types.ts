export type CurrencyCode = "RUB" | "USD" | "EUR" | "XAU";

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
  isPaymentAccount: boolean;
  ownershipType?: "personal" | "shared";
  householdId?: string | null;
  status?: "active" | "archived" | "deleted";
  version?: number;
  balance: MoneyAmount;
  assetCategoryId?: string | null;
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
  occurredDate?: string | null;
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
  occurredDate?: string | null;
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
  occurredDate: string | null;
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
  | "personal"
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

export type RecordStatus = "active" | "archived" | "deleted";

export type AssetCategoryScope = "personal" | "household";
export type AssetCategoryType = AccountKind;

export type AssetCategory = {
  id: string;
  name: string;
  scopeType: AssetCategoryScope;
  householdId?: string | null;
  ownerUserId?: string | null;
  currency: CurrencyCode;
  manualAmount: MoneyAmount;
  isInvestment: boolean;
  assetType: AssetCategoryType;
  iconKey?: string | null;
  recordStatus: RecordStatus;
  version?: number;
};

export type AssetCategoryGroup = {
  assetCategoryId: string;
  name: string;
  scopeType: AssetCategoryScope;
  householdId?: string | null;
  currency: CurrencyCode;
  manualAmount: MoneyAmount;
  accountsTotal: MoneyAmount;
  totalAmount: MoneyAmount;
  isInvestment: boolean;
  assetType: AssetCategoryType;
  iconKey?: string | null;
  accountCount?: number | null;
};

export type AssetCategoryCreateInput = {
  name: string;
  scopeType: AssetCategoryScope;
  householdId?: string | null;
  currency: CurrencyCode;
  manualAmount?: number;
  isInvestment?: boolean;
  assetType?: AssetCategoryType;
  iconKey?: string | null;
};

export type AssetCategoryUpdateInput = {
  assetCategoryId: string;
  name?: string;
  manualAmount?: number;
  assetType?: AssetCategoryType;
  iconKey?: string | null;
  isInvestment?: boolean;
  version?: number;
};

export type PlanningScope = "personal" | "household";

export type IncomeConfirmationState = "planned" | "confirmed";

export type AllocationTargetType =
  | "expense_category"
  | "account"
  | "asset"
  | "investment_asset_category";

export type AllocationMode = "amount" | "percent";
export type AllocationRecurrenceType = "regular" | "one_off";

export type AllocationProgressStatus =
  | "on_track"
  | "needs_attention"
  | "no_actuals"
  | "target_attention"
  | "not_applicable";

export type PlanningPlan = {
  id: string;
  scope: PlanningScope;
  month: string;
  currency: CurrencyCode;
  householdId?: string | null;
  totalPlannedIncome: MoneyAmount;
  previousMonthSurplus: MoneyAmount;
  allocatedTotal: MoneyAmount;
  remainingAmount: MoneyAmount;
  overallocatedAmount: MoneyAmount;
  isUnderallocated: boolean;
  isOverallocated: boolean;
  status?: string | null;
  progressStatus?: string | null;
  progressPercent?: string | null;
  incomeSources: PlanningIncomeSource[];
  allocations: PlanningAllocation[];
  version?: number;
};

export type PlanningIncomeSource = {
  id: string;
  planId: string;
  amount: MoneyAmount;
  source: string;
  description?: string | null;
  dayOfMonth: number;
  confirmed: boolean;
  effectiveDate?: string | null;
  version?: number;
};

export type PlanningAllocation = {
  id: string;
  planId: string;
  targetType: AllocationTargetType;
  targetId?: string | null;
  targetSnapshot?: Record<string, unknown> | null;
  requiresAttention: boolean;
  attentionReason?: string | null;
  comment?: string | null;
  allocationMode: AllocationMode;
  allocationValue: number;
  calculatedAmount: MoneyAmount;
  recurrenceType?: AllocationRecurrenceType | null;
  isSavingsGoal: boolean;
  goalTargetAmount?: MoneyAmount | null;
  goalDueMonth?: string | null;
  goalMonthlyAmount?: MoneyAmount | null;
  actualAmount?: MoneyAmount | null;
  varianceAmount?: MoneyAmount | null;
  progressPercent?: string | null;
  progressStatus?: AllocationProgressStatus | null;
  status?: string | null;
  version?: number;
};

export type PlanningPlanCreateInput = {
  scope: PlanningScope;
  month: string;
  currency: CurrencyCode;
  householdId?: string | null;
};

export type PlanningPlanCopyInput = {
  planId: string;
  targetMonth: string;
};

export type PlanningIncomeSourceCreateInput = {
  planId: string;
  amount: number;
  source: string;
  description?: string | null;
  dayOfMonth: number;
  effectiveDate?: string | null;
};

export type PlanningIncomeSourceUpdateInput = {
  incomeSourceId: string;
  amount?: number;
  source?: string;
  description?: string | null;
  dayOfMonth?: number;
  confirmed?: boolean;
  effectiveDate?: string | null;
  version?: number;
};

export type PlanningAllocationCreateInput = {
  planId: string;
  targetType: AllocationTargetType;
  targetId: string;
  comment?: string | null;
  allocationMode: AllocationMode;
  allocationValue: number;
  recurrenceType?: AllocationRecurrenceType | null;
  isSavingsGoal?: boolean;
  goalTargetAmount?: number | null;
  goalDueMonth?: string | null;
};

export type PlanningAllocationUpdateInput = {
  allocationId: string;
  targetType?: AllocationTargetType;
  targetId?: string;
  comment?: string | null;
  allocationMode?: AllocationMode;
  allocationValue?: number;
  recurrenceType?: AllocationRecurrenceType | null;
  isSavingsGoal?: boolean;
  goalTargetAmount?: number | null;
  goalDueMonth?: string | null;
  version?: number;
};

export type InvestmentsByCurrency = {
  currency: CurrencyCode;
  investmentsTotal: MoneyAmount;
};

export type AccountBalancesReport = {
  assetCategoryGroups: AssetCategoryGroup[];
  investmentsByCurrency: InvestmentsByCurrency[];
  investmentsTotal?: MoneyAmount | null;
};

export type DashboardSnapshot = {
  session: SessionSnapshot;
  accounts: AccountSummary[];
  categories: CategorySummary[];
  operations: OperationSummary[];
  transfers: TransferSummary[];
  reports: ReportSummary[];
  assetCategories: AssetCategory[];
  assetCategoryGroups: AssetCategoryGroup[];
  investmentsByCurrency: InvestmentsByCurrency[];
  investmentsTotal?: MoneyAmount | null;
};
