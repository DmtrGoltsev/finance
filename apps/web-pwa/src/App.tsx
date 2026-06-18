import {
  AlertTriangle,
  Archive,
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Check,
  CircleDollarSign,
  Copy,
  CreditCard,
  Landmark,
  Layers3,
  LineChart,
  Lock,
  LogOut,
  Pencil,
  Plus,
  ReceiptText,
  RotateCcw,
  Settings,
  Shield,
  ShoppingCart,
  Tag,
  Target,
  Trash2,
  TrendingUp,
  Upload,
  WalletCards,
  X
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode
} from "react";
import { financeApiClient, isApiRequestError, type FinanceApiClient } from "./api/client";
import type {
  AccountKind,
  AccountSummary,
  AllocationMode,
  AllocationProgressStatus,
  AllocationRecurrenceType,
  AllocationTargetType,
  AssetCategory,
  AssetCategoryGroup,
  AssetCategoryScope,
  AssetCategoryType,
  CaptureDraftSummary,
  CategoryDirection,
  CategoryScope,
  CategorySummary,
  CurrencyCode,
  DashboardSnapshot,
  MoneyAmount,
  OperationSummary,
  PlanningAllocation,
  PlanningIncomeSource,
  PlanningPlan,
  PlanningScope,
  RecordStatus,
  ReportMode,
  ReportSummary,
  ScreenshotOcrCandidate,
  TransferSummary
} from "./api/types";

type SectionId =
  | "money"
  | "operations"
  | "assets"
  | "categories"
  | "analytics"
  | "settings";

type ViewMode = "personal" | "shared" | "overview";
type VisibilityMode = "personal" | "shared";
type DraftVisibilityMode = VisibilityMode | "";
type QuickKind = "expense" | "income" | "transfer" | "asset";

type QuickAddInput = {
  kind: QuickKind;
  amount: number;
  accountId: string;
  toAccountId: string;
  categoryId: string;
  assetKind: AccountKind;
  isPaymentAccount: boolean;
  date: string;
  comment: string;
  visibility: VisibilityMode;
};

type CategoryFormInput = {
  categoryId?: string;
  version?: number;
  name: string;
  direction: CategoryDirection;
  scope: CategoryScope;
  iconKey: string;
  color: string;
};

type AssetCategoryFormInput = {
  assetCategoryId?: string;
  name: string;
  scopeType: AssetCategoryScope;
  currency: CurrencyCode;
  manualAmount: number;
  isInvestment: boolean;
  assetType: AssetCategoryType;
  iconKey: string;
  version?: number;
};

type AccountEditFormInput = {
  accountId: string;
  name: string;
  balance: number;
  currency: CurrencyCode;
  assetCategoryId: string;
  isPaymentAccount: boolean;
  version?: number;
};

type OperationEditFormInput = {
  operationId: string;
  amount: number;
  description: string;
  categoryId: string;
  accountId: string;
  occurredDate: string;
  version?: number;
};

type AnalyticsTab = "summary" | "planning";

type AllocationDraft = {
  targetType: AllocationTargetType;
  targetId: string;
  allocationMode: AllocationMode;
  allocationValue: string;
  recurrenceType: AllocationRecurrenceType;
  isSavingsGoal: boolean;
  goalTargetAmount: string;
  goalDueMonth: string;
  comment: string;
};

const desktopSections: Array<{
  id: SectionId;
  label: string;
  icon: typeof WalletCards;
}> = [
  { id: "money", label: "Деньги", icon: WalletCards },
  { id: "operations", label: "Операции", icon: ReceiptText },
  { id: "assets", label: "Счета и активы", icon: Landmark },
  { id: "categories", label: "Категории", icon: Tag },
  { id: "analytics", label: "Аналитика", icon: BarChart3 },
  { id: "settings", label: "Настройки", icon: Settings }
];

const mobileSections: Array<{
  id: SectionId;
  label: string;
  icon: typeof WalletCards;
}> = [
  { id: "money", label: "Деньги", icon: WalletCards },
  { id: "operations", label: "Операции", icon: ReceiptText },
  { id: "assets", label: "Активы", icon: Landmark },
  { id: "categories", label: "Категории", icon: Tag },
  { id: "analytics", label: "Аналитика", icon: BarChart3 }
];

const reportModeByView: Record<Exclude<ViewMode, "personal">, ReportMode> = {
  shared: "shared_family_report",
  overview: "combined_viewer_overview"
};

const accountKindLabels: Record<AccountKind, string> = {
  bank: "Банк",
  brokerage: "Брокер",
  card: "Карта",
  cash: "Наличные",
  deposit: "Вклад",
  metal: "Металл",
  other: "Прочее"
};

const accountKindIcons: Record<AccountKind, typeof WalletCards> = {
  bank: Building2,
  brokerage: LineChart,
  card: CreditCard,
  cash: WalletCards,
  deposit: Landmark,
  metal: Layers3,
  other: CircleDollarSign
};

const categoryPalette = [
  "#2563eb",
  "#0f766e",
  "#c2410c",
  "#7c3aed",
  "#be123c",
  "#15803d",
  "#b45309"
];

const assetCategoryIconOptions = [
  { value: "wallet", label: "Кошелек" },
  { value: "card", label: "Карта" },
  { value: "coin", label: "Монета" },
  { value: "safe", label: "Сейф" },
  { value: "chart", label: "График" },
  { value: "home", label: "Дом" },
  { value: "phone", label: "Телефон" },
  { value: "book", label: "Книга" }
];

const currencyOptions: CurrencyCode[] = ["RUB", "USD", "EUR", "XAU"];

function formatMoney(amount: MoneyAmount): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: amount.currency,
    maximumFractionDigits: 0
  }).format(amount.value);
}

function formatDate(value: string): string {
  const dateOnly = parseDateOnly(value);
  if (dateOnly) {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "short"
    }).format(new Date(dateOnly.year, dateOnly.month - 1, dateOnly.day));
  }

  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short"
  }).format(new Date(value));
}

function todayInputValue(): string {
  const date = new Date();
  return formatDateOnly(date.getFullYear(), date.getMonth() + 1, date.getDate());
}

function currentMonthValue(): string {
  const date = new Date();
  return formatMonthValue(date.getFullYear(), date.getMonth() + 1);
}

function formatDateOnly(year: number, month: number, day: number): string {
  return [
    String(year).padStart(4, "0"),
    String(month).padStart(2, "0"),
    String(day).padStart(2, "0")
  ].join("-");
}

function formatMonthValue(year: number, month: number): string {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}`;
}

function parseDateOnly(value: string): { year: number; month: number; day: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }

  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3])
  };
}

function monthRange(monthValue: string): { startDate: string; endDate: string } {
  const [yearPart, monthPart] = monthValue.split("-");
  const year = Number(yearPart);
  const month = Number(monthPart);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return monthRange(currentMonthValue());
  }

  const lastDay = new Date(year, month, 0).getDate();
  return {
    startDate: formatDateOnly(year, month, 1),
    endDate: formatDateOnly(year, month, lastDay)
  };
}

function shiftMonth(monthValue: string, offset: number): string {
  const [yearPart, monthPart] = monthValue.split("-");
  const date = new Date(Number(yearPart), Number(monthPart) - 1 + offset, 1);
  return formatMonthValue(date.getFullYear(), date.getMonth() + 1);
}

function monthLabel(monthValue: string): string {
  const [yearPart, monthPart] = monthValue.split("-");
  const date = new Date(Number(yearPart), Number(monthPart) - 1, 1);
  return new Intl.DateTimeFormat("ru-RU", {
    month: "long",
    year: "numeric"
  }).format(date);
}

function planningMonthChoices(): Array<{ month: string; title: string }> {
  const results: Array<{ month: string; title: string }> = [];
  for (let i = 0; i <= 12; i++) {
    const date = new Date();
    date.setMonth(date.getMonth() + i, 1);
    const mv = formatMonthValue(date.getFullYear(), date.getMonth() + 1);
    const label = monthLabel(mv);
    let title = label;
    if (i === 0) title = `Текущий: ${label}`;
    else if (i === 1) title = `Следующий: ${label}`;
    results.push({ month: mv, title });
  }
  return results;
}

function planningGoalMonthChoices(): Array<{ month: string; title: string }> {
  const results: Array<{ month: string; title: string }> = [];
  for (let i = 1; i <= 36; i++) {
    const date = new Date();
    date.setMonth(date.getMonth() + i, 1);
    const mv = formatMonthValue(date.getFullYear(), date.getMonth() + 1);
    let title = monthLabel(mv);
    if (i === 1) title = `Следующий: ${title}`;
    else if (i === 6) title = `6 мес.: ${title}`;
    else if (i === 12) title = `1 год: ${title}`;
    else if (i === 24) title = `2 года: ${title}`;
    else if (i === 36) title = `3 года: ${title}`;
    results.push({ month: mv, title });
  }
  return results;
}

function planningScopeInfo(
  viewMode: ViewMode,
  householdId: string | null
): { scope: PlanningScope; householdId: string | null } | null {
  if (viewMode === "personal") return { scope: "personal", householdId: null };
  if (viewMode === "shared" && householdId) return { scope: "household", householdId };
  return null;
}

function coercePlanningMonth(monthValue: string): string {
  const current = currentMonthValue();
  return monthValue < current ? current : monthValue;
}

function nextPlanningMonth(): string {
  const date = new Date();
  date.setMonth(date.getMonth() + 1, 1);
  return formatMonthValue(date.getFullYear(), date.getMonth() + 1);
}

function localizedTargetType(type: string): string {
  if (type === "expense_category") return "Расходы";
  if (type === "investment_asset_category") return "Инвестиции";
  if (type === "account") return "Счёт";
  if (type === "asset") return "Актив";
  return "Цель";
}

function localizedAllocationMode(mode: string): string {
  return mode === "percent" ? "Процент" : "Сумма";
}

function localizedRecurrenceType(type: string): string {
  return type === "one_off" ? "Разовая" : "Регулярная";
}

function localizedPlanningStatus(status: string | null | undefined): string {
  if (!status) return "Ожидает данных";
  if (["active", "planned", "on_track"].includes(status)) return "По плану";
  if (["confirmed", "completed", "done"].includes(status)) return "Выполнено";
  if (["needs_attention", "target_attention", "warning", "attention"].includes(status)) return "Требует внимания";
  if (status === "no_actuals") return "Факт";
  if (status === "not_applicable") return "Не применяется";
  if (["under_plan", "underplanned", "behind"].includes(status)) return "Ниже плана";
  if (["over_plan", "overplanned", "ahead"].includes(status)) return "Выше плана";
  return "Ожидает данных";
}

function localizedAttentionReason(allocation: PlanningAllocation): string {
  if (allocation.targetType === "investment_asset_category") return "Инвестиции ниже плана";
  if (allocation.targetType === "expense_category") return "Расходы выше плана";
  return "Эта цель требует внимания";
}

function planningTargetOptions(
  targetType: string,
  categories: CategorySummary[],
  investments: AssetCategory[]
): Array<{ id: string; title: string }> {
  if (targetType === "expense_category") {
    return categories.map((c) => ({ id: c.id, title: c.name }));
  }
  if (targetType === "investment_asset_category") {
    return investments.map((inv) => ({ id: inv.id, title: inv.name }));
  }
  return [];
}

export function App({ client = financeApiClient }: { client?: FinanceApiClient }) {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [authStatus, setAuthStatus] = useState<"checking" | "authenticated" | "unauthenticated">(
    "checking"
  );
  const [loginError, setLoginError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<SectionId>("money");
  const [viewMode, setViewMode] = useState<ViewMode>("personal");
  const [isQuickAddOpen, setQuickAddOpen] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string>("");
  const [selectedMonth, setSelectedMonth] = useState(currentMonthValue());
  const [analyticsTab, setAnalyticsTab] = useState<AnalyticsTab>("summary");

  const loadSnapshot = useCallback(async () => {
    const nextSnapshot = await client.getDashboardSnapshot(monthRange(selectedMonth));
    setSnapshot(nextSnapshot);
    setAuthStatus("authenticated");
    return nextSnapshot;
  }, [client, selectedMonth]);

  useEffect(() => {
    let isMounted = true;
    setError(null);

    void loadSnapshot().catch((caughtError) => {
      if (isMounted) {
        if (isApiRequestError(caughtError, 401)) {
          setAuthStatus("unauthenticated");
          setSnapshot(null);
        } else {
          setError("Не удалось загрузить финансы");
        }
      }
    });

    return () => {
      isMounted = false;
    };
  }, [loadSnapshot]);

  const submitLogin = async (email: string, password: string) => {
    setLoginError(null);
    try {
      await client.loginWithPassword({ email, password });
      await loadSnapshot();
    } catch {
      setAuthStatus("unauthenticated");
      setLoginError("Не удалось войти. Проверьте email и пароль.");
    }
  };

  const submitRegistration = async (input: {
    email: string;
    password: string;
    displayName?: string;
  }) => {
    setLoginError(null);
    try {
      const result = await client.registerUser(input);
      if (result.status === "authenticated") {
        await loadSnapshot();
        return result;
      }

      setAuthStatus("unauthenticated");
      return result;
    } catch (caughtError) {
      setAuthStatus("unauthenticated");
      setLoginError("Не удалось создать вход. Проверьте данные и попробуйте еще раз.");
      throw caughtError;
    }
  };

  const logout = async () => {
    try {
      await client.logout();
    } finally {
      setSnapshot(null);
      setAuthStatus("unauthenticated");
      setActiveSection("money");
      setViewMode("personal");
      setQuickAddOpen(false);
      setSaveStatus("");
    }
  };

  const selectedMonthRange = useMemo(() => monthRange(selectedMonth), [selectedMonth]);
  const activeReport = useMemo(() => {
    if (!snapshot) {
      return null;
    }

    return reportForView(snapshot, viewMode, selectedMonthRange);
  }, [snapshot, selectedMonthRange, viewMode]);

  const saveQuickAdd = async (input: QuickAddInput) => {
    if (!snapshot) {
      return;
    }

    const sourceAccount = snapshot.accounts.find((account) => account.id === input.accountId);
    const destinationAccount = snapshot.accounts.find(
      (account) => account.id === input.toAccountId
    );
    const currency = sourceAccount?.balance.currency ?? "RUB";
    const transactionDate = input.date || todayInputValue();
    const sharedHouseholdId = input.visibility === "shared" ? snapshot.session.householdId : null;
    const expectedOwnership = input.visibility === "shared" ? "shared" : "personal";

    if (input.kind !== "asset") {
      if (!sourceAccount || accountOwnership(sourceAccount) !== expectedOwnership) {
        setSaveStatus("Выберите счет в нужном scope");
        return;
      }
    }

    if (input.kind === "transfer") {
      if (
        !destinationAccount ||
        accountOwnership(destinationAccount) !== expectedOwnership ||
        destinationAccount.balance.currency !== currency
      ) {
        setSaveStatus("Для перевода нужны два совместимых счета одного scope и валюты");
        return;
      }
    }

    const selectedOperationCategory =
      input.kind === "expense" || input.kind === "income"
        ? snapshot.categories.find(
            (category) =>
              category.id === input.categoryId &&
              category.status !== "deleted" &&
              category.status !== "archived" &&
              categoryScopeVisibility(category) === input.visibility &&
              category.direction === input.kind
          )
        : null;

    if ((input.kind === "expense" || input.kind === "income") && !selectedOperationCategory) {
      setSaveStatus("Выберите категорию в нужном scope");
      return;
    }

    setSaveStatus("Сохраняем");
    if (input.kind === "asset") {
      if (input.visibility === "shared" && !sharedHouseholdId) {
        setSaveStatus("Нужен семейный доступ");
        return;
      }
      await client.createDemoAccount({
        name: input.comment.trim() || accountKindLabels[input.assetKind],
        kind: input.assetKind,
        isPaymentAccount: input.isPaymentAccount,
        currency,
        initialBalance: input.amount,
        ownershipType: input.visibility === "shared" ? "shared" : "personal",
        householdId: sharedHouseholdId
      });
    } else if (input.kind === "transfer") {
      await client.createDemoTransfer({
        fromAccountId: input.accountId,
        toAccountId: input.toAccountId,
        currency,
        amount: input.amount,
        occurredAt: new Date(`${transactionDate}T12:00:00`).toISOString(),
        description: input.comment || "Перевод"
      });
    } else {
      await client.createDemoOperation({
        accountId: input.accountId,
        categoryId: selectedOperationCategory?.id ?? null,
        currency,
        transactionType: input.kind,
        amount: input.amount,
        transactionDate,
        description: input.comment || null
      });
    }

    await loadSnapshot();
    setSaveStatus(input.visibility === "shared" ? "Сохранено в общее" : "Сохранено в личное");
    setQuickAddOpen(false);
  };

  const saveCategory = async (input: CategoryFormInput) => {
    if (!snapshot) {
      return;
    }

    if (input.scope === "household" && !snapshot.session.householdId) {
      throw new Error("household access required");
    }

    if (input.categoryId) {
      await client.updateCategory({
        categoryId: input.categoryId,
        name: input.name,
        iconKey: input.iconKey || null,
        color: input.color || null,
        version: input.version
      });
    } else {
      await client.createDemoCategory({
        name: input.name,
        direction: input.direction,
        scope: input.scope,
        householdId: input.scope === "household" ? snapshot.session.householdId : null,
        iconKey: input.iconKey || null,
        color: input.color || null
      });
    }

    await loadSnapshot();
  };

  if (error) {
    return <main className="loading">{error}</main>;
  }

  if (authStatus === "unauthenticated") {
    return (
      <LoginScreen
        onLogin={submitLogin}
        onRegister={submitRegistration}
        error={loginError}
      />
    );
  }

  if (!snapshot || !activeReport) {
    return <main className="loading">Загружаем деньги...</main>;
  }

  return (
    <div className="appShell">
      <aside className="sidebar" aria-label="Разделы">
        <div className="brandBlock">
          <div className="brandMark" aria-hidden="true">
            <WalletCards size={21} />
          </div>
          <div>
            <p>{snapshot.session.householdName}</p>
            <h1>Финансы</h1>
          </div>
        </div>
        <nav className="desktopNav" aria-label="Основная навигация">
          {desktopSections.map((section) => (
            <NavButton
              key={section.id}
              active={activeSection === section.id}
              icon={section.icon}
              label={section.label}
              onClick={() => setActiveSection(section.id)}
            />
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div className="titleGroup">
            <p>{viewModeDescription(viewMode)}</p>
            <h2>{sectionTitle(activeSection)}</h2>
            <ScopeBadge mode={viewMode} />
          </div>
          <div className="topActions">
            <ViewSwitch value={viewMode} onChange={setViewMode} />
            <button className="primaryButton" type="button" onClick={() => setQuickAddOpen(true)}>
              <Plus size={18} aria-hidden="true" />
              Добавить
            </button>
            <button className="ghostButton" type="button" onClick={logout}>
              <LogOut size={17} aria-hidden="true" />
              Выйти
            </button>
          </div>
        </header>

        {activeSection === "money" && (
          <MoneyDashboard
            client={client}
            snapshot={snapshot}
            report={activeReport}
            viewMode={viewMode}
            onAdd={() => setQuickAddOpen(true)}
            onNavigateToPlanning={() => { setActiveSection("analytics"); setAnalyticsTab("planning"); }}
          />
        )}
        {activeSection === "operations" && (
          <OperationsPage
            client={client}
            snapshot={snapshot}
            viewMode={viewMode}
            onCaptureDraftsSaved={loadSnapshot}
          />
        )}
        {activeSection === "assets" && (
          <AssetsPage
            client={client}
            onChanged={loadSnapshot}
            snapshot={snapshot}
            viewMode={viewMode}
          />
        )}
        {activeSection === "categories" && (
          <CategoriesPage
            snapshot={snapshot}
            viewMode={viewMode}
            onSave={saveCategory}
          />
        )}
        {activeSection === "analytics" && (
          <AnalyticsPage
            client={client}
            monthValue={selectedMonth}
            onMonthChange={setSelectedMonth}
            snapshot={snapshot}
            report={activeReport}
            viewMode={viewMode}
            tab={analyticsTab}
            onTabChange={setAnalyticsTab}
          />
        )}
        {activeSection === "settings" && (
          <SettingsPage viewMode={viewMode} onViewModeChange={setViewMode} />
        )}
      </main>

      <nav className="mobileNav" aria-label="Нижняя навигация">
        {mobileSections.map((section) => (
          <NavButton
            key={section.id}
            active={activeSection === section.id}
            icon={section.icon}
            label={section.label}
            onClick={() => setActiveSection(section.id)}
            testId={`mobile-nav-${section.id}`}
            iconOnly
          />
        ))}
      </nav>
      <button
        className="fab"
        type="button"
        aria-label="Добавить"
        data-testid="mobile-quick-add"
        onClick={() => setQuickAddOpen(true)}
      >
        <Plus size={24} aria-hidden="true" />
      </button>

      {isQuickAddOpen && (
        <QuickAdd
          allAccounts={snapshot.accounts.filter((account) => account.status !== "deleted")}
          categories={snapshot.categories.filter((category) => category.status !== "deleted")}
          canUseShared={Boolean(snapshot.session.householdId)}
          defaultVisibility={viewMode === "overview" ? "" : viewMode}
          onClose={() => setQuickAddOpen(false)}
          onSubmit={saveQuickAdd}
          saveStatus={saveStatus}
        />
      )}
    </div>
  );
}

function LoginScreen({
  error,
  onLogin,
  onRegister
}: {
  error: string | null;
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (input: {
    email: string;
    password: string;
    displayName?: string;
  }) => Promise<{ status: "authenticated" } | { status: "accepted" }>;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);
  const isRegistering = mode === "register";

  const switchMode = (nextMode: "login" | "register") => {
    setMode(nextMode);
    setLocalError(null);
    setNotice(null);
    setPassword("");
    setConfirmPassword("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedEmail = email.trim();
    setLocalError(null);
    setNotice(null);

    if (!trimmedEmail) {
      setLocalError("Укажите email.");
      return;
    }
    if (!isEmailLike(trimmedEmail)) {
      setLocalError("Укажите корректный email.");
      return;
    }
    if (!password) {
      setLocalError("Укажите пароль.");
      return;
    }
    if (isRegistering) {
      if (password.length < 12) {
        setLocalError("Пароль должен быть не короче 12 символов.");
        return;
      }
      if (password !== confirmPassword) {
        setLocalError("Пароли не совпадают.");
        return;
      }
    }

    setSubmitting(true);
    try {
      if (isRegistering) {
        const result = await onRegister({
          email: trimmedEmail,
          password,
          displayName
        });
        if (result.status === "accepted") {
          setEmail(trimmedEmail);
          switchMode("login");
          setNotice(
            "Запрос принят. Если аккаунт с этим email уже есть, войдите с ним."
          );
        }
      } else {
        await onLogin(trimmedEmail, password);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="loginShell">
      <form className="loginPanel" aria-label="Вход в финансы" noValidate onSubmit={submit}>
        <div className="brandMark" aria-hidden="true">
          <WalletCards size={22} />
        </div>
        <div>
          <p>Семейные финансы</p>
          <h1>{isRegistering ? "Регистрация" : "Вход"}</h1>
        </div>
        <div className="authModeSwitch" role="group" aria-label="Access mode">
          <button
            className={!isRegistering ? "selected" : ""}
            type="button"
            onClick={() => switchMode("login")}
          >
            Вход
          </button>
          <button
            className={isRegistering ? "selected" : ""}
            type="button"
            onClick={() => switchMode("register")}
          >
            Регистрация
          </button>
        </div>
        <label className="field">
          <span>Email</span>
          <input
            autoComplete="email"
            inputMode="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        {isRegistering && (
          <label className="field">
            <span>Имя</span>
            <input
              autoComplete="name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
            />
          </label>
        )}
        <label className="field">
          <span>Пароль</span>
          <input
            autoComplete={isRegistering ? "new-password" : "current-password"}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {isRegistering && (
          <label className="field">
            <span>Подтвердите пароль</span>
            <input
              autoComplete="new-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>
        )}
        {notice && <p className="formHint">{notice}</p>}
        {localError && <p className="formError">{localError}</p>}
        {error && <p className="formError">{error}</p>}
        <button
          className="submitButton"
          aria-label={isRegistering ? "Create account" : undefined}
          type="submit"
          disabled={isSubmitting}
        >
          <Check size={18} aria-hidden="true" />
          {isSubmitting
            ? isRegistering
              ? "Создаем"
              : "Входим"
            : isRegistering
              ? "Создать аккаунт"
              : "Войти"}
        </button>
      </form>
    </main>
  );
}

function isEmailLike(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function NavButton({
  active,
  icon: Icon,
  label,
  onClick,
  testId,
  iconOnly = false
}: {
  active: boolean;
  icon: typeof WalletCards;
  label: string;
  onClick: () => void;
  testId?: string;
  iconOnly?: boolean;
}) {
  return (
    <button
      className={active ? "active" : ""}
      type="button"
      aria-label={iconOnly ? label : undefined}
      title={label}
      onClick={onClick}
      data-testid={testId}
    >
      <Icon size={18} aria-hidden="true" />
      <span className={iconOnly ? "visuallyHidden" : undefined}>{label}</span>
    </button>
  );
}

function ViewSwitch({
  value,
  onChange
}: {
  value: ViewMode;
  onChange: (value: ViewMode) => void;
}) {
  return (
    <div className="segmentedControl" role="group" aria-label="Режим просмотра">
      <button
        className={value === "personal" ? "selected" : ""}
        type="button"
        onClick={() => onChange("personal")}
      >
        <Lock size={16} aria-hidden="true" />
        Личное
      </button>
      <button
        className={value === "shared" ? "selected" : ""}
        type="button"
        onClick={() => onChange("shared")}
      >
        <Shield size={16} aria-hidden="true" />
        Общее
      </button>
      <button
        className={value === "overview" ? "selected" : ""}
        type="button"
        onClick={() => onChange("overview")}
      >
        <BarChart3 size={16} aria-hidden="true" />
        Обзор
      </button>
    </div>
  );
}

function ScopeBadge({ mode }: { mode: ViewMode | VisibilityMode }) {
  const label = mode === "overview" ? "Мой обзор" : mode === "shared" ? "Общее" : "Личное";
  return <span className={`scopeBadge ${mode}`}>{label}</span>;
}

function MoneyDashboard({
  client,
  snapshot,
  report,
  viewMode,
  onAdd,
  onNavigateToPlanning
}: {
  client: FinanceApiClient;
  snapshot: DashboardSnapshot;
  report: ReportSummary;
  viewMode: ViewMode;
  onAdd: () => void;
  onNavigateToPlanning: () => void;
}) {
  const accounts = visibleAccounts(snapshot.accounts, viewMode);
  const operations = visibleOperations(snapshot.operations, accounts);
  const transfers = visibleTransfers(snapshot.transfers, accounts);
  const currency = accounts[0]?.balance.currency ?? report.income.currency;
  const capital = accounts.reduce((sum, account) => sum + account.balance.value, 0);
  const groups = groupAssets(accounts, currency);
  const topCategories = categoryTotals(operations, snapshot.categories, currency);
  const recentItems = recentTimeline(operations, transfers, accounts).slice(0, 6);

  return (
    <section className="screenStack" aria-labelledby="money-title">
      <div className="sectionHead">
        <h3 id="money-title">Обзор</h3>
        <button type="button" className="ghostButton" onClick={onAdd}>
          <Plus size={17} aria-hidden="true" />
          Операция
        </button>
      </div>
      <p className="scopeCopy">{scopeDescription(viewMode)}</p>

      <div className="metricGrid">
        <Metric label="Капитал" value={formatMoney({ value: capital, currency })} />
        <Metric label="Расходы месяца" value={formatMoney(report.expense)} tone="danger" />
        <Metric label="Доходы" value={formatMoney(report.income)} tone="success" />
        <Metric label="Чистый поток" value={formatMoney(report.balanceDelta)} />
      </div>

      <div className="dashboardGrid">
        <section className="plainSection" aria-labelledby="asset-groups-title">
          <div className="sectionHead compact">
            <h3 id="asset-groups-title">Группы активов</h3>
          </div>
          <div className="listStack">
            {groups.map((group) => (
              <AssetGroupRow key={group.kind} group={group} />
            ))}
            {groups.length === 0 && (
              <EmptyState text={scopeEmptyText(viewMode, "активов", "добавьте актив в выбранный scope или переключите режим")} />
            )}
          </div>
        </section>

        <section className="plainSection" aria-labelledby="top-categories-title">
          <div className="sectionHead compact">
            <h3 id="top-categories-title">Топ категорий</h3>
          </div>
          <div className="listStack">
            {topCategories.map((category) => (
              <CategoryTotalRow key={category.name} category={category} />
            ))}
            {topCategories.length === 0 && (
              <EmptyState text={scopeEmptyText(viewMode, "расходов", "добавьте расход или проверьте другой scope")} />
            )}
          </div>
        </section>
      </div>

      <PlanningMiniCard
        client={client}
        viewMode={viewMode}
        householdId={snapshot.session.householdId}
        onOpen={onNavigateToPlanning}
      />

      <section className="plainSection" aria-labelledby="latest-title">
        <div className="sectionHead compact">
          <h3 id="latest-title">Последние операции</h3>
        </div>
        <TimelineList
          emptyText={scopeEmptyText(viewMode, "записей", "добавьте операцию или выберите другой scope")}
          items={recentItems}
        />
      </section>
    </section>
  );
}

function Metric({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string;
  tone?: "neutral" | "success" | "danger";
}) {
  return (
    <article className={`metricCard ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function OperationsPage({
  client,
  onCaptureDraftsSaved,
  snapshot,
  viewMode
}: {
  client: FinanceApiClient;
  onCaptureDraftsSaved: () => Promise<DashboardSnapshot>;
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
}) {
  const accounts = visibleAccounts(snapshot.accounts, viewMode);
  const operations = visibleOperations(snapshot.operations, accounts);
  const transfers = visibleTransfers(snapshot.transfers, accounts);
  const timeline = recentTimeline(operations, transfers, accounts);
  const categories = visibleCategories(snapshot.categories, viewMode);
  const allCategories = snapshot.categories.filter(
    (c) => c.status !== "deleted" && c.status !== "archived"
  );
  const paymentAccounts = accounts.filter(isPaymentAccount);
  const expenseCategories = categories.filter(
    (category) => category.direction === "expense"
  );
  const [draftsRefreshKey, setDraftsRefreshKey] = useState(0);
  const [editingOp, setEditingOp] = useState<OperationSummary | null>(null);
  const [deletingOpId, setDeletingOpId] = useState<string | null>(null);

  const refreshAfterDraftChange = useCallback(async () => {
    const nextSnapshot = await onCaptureDraftsSaved();
    setDraftsRefreshKey((current) => current + 1);
    return nextSnapshot;
  }, [onCaptureDraftsSaved]);

  const handleDelete = async (id: string) => {
    try {
      await client.deleteOperation(id);
      await onCaptureDraftsSaved();
    } catch {
      return;
    }
    setDeletingOpId(null);
  };

  const handleEditSave = async (input: OperationEditFormInput) => {
    await client.updateOperation({
      transactionId: input.operationId,
      amount: input.amount,
      description: input.description || null,
      categoryId: input.categoryId || null,
      accountId: input.accountId,
      occurredDate: input.occurredDate || null,
      version: input.version
    });
    await onCaptureDraftsSaved();
    setEditingOp(null);
  };

  return (
    <section className="screenStack" aria-labelledby="operations-title">
      <div className="sectionHead">
        <h3 id="operations-title">Операции</h3>
        <span>{timeline.length} записей</span>
      </div>
      <p className="scopeCopy">{scopeDescription(viewMode)}</p>
      <ScreenshotOcrCapture
        accounts={paymentAccounts}
        canUseHousehold={Boolean(snapshot.session.householdId)}
        categories={expenseCategories}
        client={client}
        householdId={viewMode === "shared" ? snapshot.session.householdId : null}
        onSaved={refreshAfterDraftChange}
      />
      <PendingCaptureDraftsPanel
        accounts={paymentAccounts}
        categories={expenseCategories}
        client={client}
        onChanged={refreshAfterDraftChange}
        refreshKey={draftsRefreshKey}
      />
      <div className="listStack">
        {timeline.map((item) => {
          const isTransfer = item.type === "transfer";
          const isExpense = item.amount.value < 0;
          const Icon = isTransfer ? ArrowLeftRight : isExpense ? ArrowUpRight : ArrowDownLeft;
          const originalOp = !isTransfer
            ? operations.find((op) => op.id === item.id)
            : null;

          return (
            <article className="operationRow" key={`${item.type}-${item.id}`}>
              <div className="rowIcon" aria-hidden="true">
                <Icon size={18} />
              </div>
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
              </div>
              <div className="operationAmountArea">
                <b className={isTransfer ? "neutral" : isExpense ? "negative" : "positive"}>
                  {formatMoney(item.amount)}
                </b>
                {originalOp && (
                  <div className="operationActions">
                    <button
                      className="tileAction"
                      type="button"
                      onClick={() => setEditingOp(originalOp)}
                      title="Редактировать"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      className="tileAction dangerAction"
                      type="button"
                      onClick={() => setDeletingOpId(originalOp.id)}
                      title="Удалить"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
            </article>
          );
        })}
        {timeline.length === 0 && (
          <EmptyState
            text={scopeEmptyText(
              viewMode,
              "операций",
              "добавьте расход, доход или выберите другой scope"
            )}
          />
        )}
      </div>

      {editingOp && (
        <OperationEditModal
          operation={editingOp}
          accounts={accounts}
          categories={allCategories}
          onCancel={() => setEditingOp(null)}
          onSave={handleEditSave}
        />
      )}

      {deletingOpId && (
        <div className="modalLayer" role="presentation">
          <div className="quickSheet">
            <div className="sheetHead">
              <h3>Удалить операцию?</h3>
              <button type="button" onClick={() => setDeletingOpId(null)}>
                <X size={19} aria-hidden="true" />
              </button>
            </div>
            <p className="scopeCopy">Это действие нельзя отменить.</p>
            <div className="draftActions">
              <button
                className="ghostButton"
                type="button"
                onClick={() => setDeletingOpId(null)}
              >
                Отмена
              </button>
              <button
                className="submitButton"
                style={{ background: "var(--danger)", borderColor: "var(--danger)" }}
                type="button"
                onClick={() => void handleDelete(deletingOpId)}
              >
                Удалить
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

type OcrReviewRow = {
  candidate: ScreenshotOcrCandidate;
  include: boolean;
  categoryId: string;
};

const screenshotMimeTypes = new Set(["image/png", "image/jpeg", "image/webp"]);

function captureDraftDescriptionForAggregate(candidate: ScreenshotOcrCandidate): string {
  return `Скрин: агрегированные расходы, ${candidate.operationCount} операций`;
}

type PendingDraftFormState = {
  amount: string;
  description: string;
  accountId: string;
  categoryId: string;
  date: string;
};

function PendingCaptureDraftsPanel({
  accounts,
  categories,
  client,
  onChanged,
  refreshKey
}: {
  accounts: AccountSummary[];
  categories: CategorySummary[];
  client: FinanceApiClient;
  onChanged: () => Promise<DashboardSnapshot>;
  refreshKey: number;
}) {
  const [drafts, setDrafts] = useState<CaptureDraftSummary[]>([]);
  const [draftForms, setDraftForms] = useState<Record<string, PendingDraftFormState>>({});
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setLoading] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);

  const loadDrafts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const nextDrafts = await client.listCaptureDrafts({ status: "pending", limit: 50 });
      setDrafts(nextDrafts);
      setDraftForms(
        Object.fromEntries(
          nextDrafts.map((draft) => [draft.id, draftFormFromDraft(draft)])
        )
      );
    } catch {
      setError("Не удалось загрузить черновики");
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void loadDrafts();
  }, [loadDrafts, refreshKey]);

  const updateDraftForm = (draftId: string, patch: Partial<PendingDraftFormState>) => {
    setDraftForms((current) => ({
      ...current,
      [draftId]: {
        ...(current[draftId] ?? emptyDraftForm()),
        ...patch
      }
    }));
  };

  const saveDraftEdits = async (draft: CaptureDraftSummary) => {
    const form = draftForms[draft.id] ?? draftFormFromDraft(draft);
    const amount = Number(form.amount);
    if (!Number.isFinite(amount) || amount <= 0 || !form.description.trim()) {
      throw new Error("invalid draft form");
    }

    return client.updateCaptureDraft({
      draftId: draft.id,
      amount,
      currency: draft.amount.currency,
      description: form.description,
      occurredDate: draftOccurredDateFromInput(form.date),
      accountId: form.accountId || null,
      categoryId: form.categoryId || null,
      confidence: draft.confidence
    });
  };

  const runDraftAction = async (
    draft: CaptureDraftSummary,
    action: "save" | "confirm" | "discard"
  ) => {
    setActiveAction(`${action}:${draft.id}`);
    setError("");
    setStatus("");
    try {
      if (action === "discard") {
        await client.discardCaptureDraft(draft.id);
        setStatus("Черновик отклонен");
      } else {
        const updatedDraft = await saveDraftEdits(draft);
        if (action === "confirm") {
          await client.confirmCaptureDraft(updatedDraft.id);
          setStatus("Черновик подтвержден");
        } else {
          setStatus("Изменения сохранены");
        }
      }
      await onChanged();
    } catch {
      setError(
        action === "confirm"
          ? "Не удалось подтвердить черновик"
          : action === "discard"
            ? "Не удалось отклонить черновик"
            : "Не удалось сохранить черновик"
      );
    } finally {
      setActiveAction(null);
    }
  };

  return (
    <section className="plainSection" aria-labelledby="pending-drafts-title">
      <div className="sectionHead compact">
        <h3 id="pending-drafts-title">Черновики OCR</h3>
        <button
          className="ghostButton"
          disabled={isLoading || Boolean(activeAction)}
          type="button"
          onClick={() => void loadDrafts()}
        >
          {isLoading ? "Обновляем" : "Обновить"}
        </button>
      </div>
      <p className="scopeCopy">
        Черновики из OCR не являются операциями, пока вы не проверите счет, категорию и не подтвердите их.
      </p>

      {error && <p className="formError">{error}</p>}
      {status && <p className="formHint">{status}</p>}

      <div className="pendingDraftList">
        {drafts.map((draft) => {
          const form = draftForms[draft.id] ?? draftFormFromDraft(draft);
          const isBusy = activeAction?.endsWith(`:${draft.id}`) ?? false;
          const canConfirm =
            Number(form.amount) > 0 &&
            Boolean(form.description.trim()) &&
            Boolean(form.accountId) &&
            Boolean(form.categoryId) &&
            Boolean(form.date) &&
            !isBusy;

          return (
            <article
              className="pendingDraftRow"
              data-testid={`pending-draft-${draft.id}`}
              key={draft.id}
            >
              <div className="pendingDraftMeta">
                <strong>{formatMoney(draft.amount)}</strong>
                <span>{draft.amount.currency}</span>
                <span>{formatDate(draft.occurredDate ?? draft.occurredAt ?? draft.capturedAt)}</span>
                <span>
                  {draft.confidence === null
                    ? "Уверенность не задана"
                    : `${Math.round(draft.confidence * 100)}%`}
                </span>
              </div>

              <div className="pendingDraftFields">
                <label className="field compactField">
                  <span>Сумма</span>
                  <input
                    aria-label={`Сумма ${draft.id}`}
                    inputMode="decimal"
                    min="0"
                    type="number"
                    value={form.amount}
                    onChange={(event) =>
                      updateDraftForm(draft.id, { amount: event.target.value })
                    }
                  />
                </label>
                <label className="field compactField">
                  <span>Дата</span>
                  <input
                    aria-label={`Дата ${draft.id}`}
                    type="date"
                    value={form.date}
                    onChange={(event) =>
                      updateDraftForm(draft.id, { date: event.target.value })
                    }
                  />
                </label>
                <label className="field compactField">
                  <span>Описание</span>
                  <input
                    aria-label={`Описание ${draft.id}`}
                    value={form.description}
                    onChange={(event) =>
                      updateDraftForm(draft.id, { description: event.target.value })
                    }
                  />
                </label>
                <label className="field compactField">
                  <span>Счет</span>
                  <select
                    aria-label={`Счет ${draft.id}`}
                    value={form.accountId}
                    onChange={(event) =>
                      updateDraftForm(draft.id, { accountId: event.target.value })
                    }
                  >
                    <option value="">Выберите</option>
                    {accounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field compactField">
                  <span>Категория</span>
                  <select
                    aria-label={`Категория ${draft.id}`}
                    value={form.categoryId}
                    onChange={(event) =>
                      updateDraftForm(draft.id, { categoryId: event.target.value })
                    }
                  >
                    <option value="">Выберите</option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="draftActions">
                <button
                  className="ghostButton"
                  disabled={isBusy}
                  type="button"
                  onClick={() => void runDraftAction(draft, "save")}
                >
                  Сохранить
                </button>
                <button
                  className="submitButton"
                  disabled={!canConfirm}
                  type="button"
                  onClick={() => void runDraftAction(draft, "confirm")}
                >
                  <Check size={18} aria-hidden="true" />
                  Подтвердить
                </button>
                <button
                  className="ghostButton"
                  disabled={isBusy}
                  type="button"
                  onClick={() => void runDraftAction(draft, "discard")}
                >
                  <X size={17} aria-hidden="true" />
                  Отклонить
                </button>
              </div>
            </article>
          );
        })}
        {!isLoading && drafts.length === 0 && (
          <EmptyState text="Черновиков OCR для проверки нет. Загрузите скрин расходов или обновите список после OCR-запроса." />
        )}
      </div>
    </section>
  );
}

function draftFormFromDraft(draft: CaptureDraftSummary): PendingDraftFormState {
  return {
    amount: String(draft.amount.value),
    description: draft.description,
    accountId: draft.accountId ?? "",
    categoryId: draft.categoryId ?? "",
    date: dateInputValue(draft.occurredDate ?? draft.occurredAt ?? draft.capturedAt)
  };
}

function emptyDraftForm(): PendingDraftFormState {
  return {
    amount: "",
    description: "",
    accountId: "",
    categoryId: "",
    date: todayInputValue()
  };
}

function dateInputValue(value: string): string {
  if (!value) {
    return todayInputValue();
  }
  if (parseDateOnly(value)) {
    return value;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return todayInputValue();
  }

  return date.toISOString().slice(0, 10);
}

function draftOccurredDateFromInput(value: string): string | null {
  if (!value) {
    return null;
  }

  return value;
}

function ScreenshotOcrCapture({
  accounts,
  canUseHousehold,
  categories,
  client,
  householdId,
  onSaved
}: {
  accounts: AccountSummary[];
  canUseHousehold: boolean;
  categories: CategorySummary[];
  client: FinanceApiClient;
  householdId: string | null;
  onSaved: () => Promise<DashboardSnapshot>;
}) {
  const [accountId, setAccountId] = useState("");
  const [capturedAt, setCapturedAt] = useState<string | null>(null);
  const [rows, setRows] = useState<OcrReviewRow[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [isRecognizing, setRecognizing] = useState(false);
  const [isSaving, setSaving] = useState(false);

  useEffect(() => {
    setAccountId((current) =>
      current && accounts.some((account) => account.id === current)
        ? current
        : ""
    );
  }, [accounts]);

  const recognize = async (file: File | undefined) => {
    setStatus("");
    setError("");
    setWarnings([]);
    setRows([]);

    if (!file) {
      return;
    }
    if (!screenshotMimeTypes.has(file.type)) {
      setError("Поддерживаются только PNG, JPEG или WebP скриншоты.");
      return;
    }

    const nextCapturedAt = new Date().toISOString();
    setCapturedAt(nextCapturedAt);
    setRecognizing(true);
    try {
      const result = await client.uploadScreenshotOcr(
        file,
        nextCapturedAt,
        canUseHousehold ? householdId : null
      );
      setWarnings(result.warnings.map((warning) => warning.message));
      setRows(
        result.items.map((candidate) => ({
          candidate,
          include: true,
          categoryId:
            candidate.suggestedCategoryId &&
            categories.some((category) => category.id === candidate.suggestedCategoryId)
              ? candidate.suggestedCategoryId
              : ""
        }))
      );
      setStatus(
        result.items.length > 0
          ? "Проверьте найденные категории перед сохранением."
          : "Категории расходов на скриншоте не найдены."
      );
    } catch {
      setError(
        "OCR-запрос не выполнен: проверьте сеть, сессию и формат скриншота. Черновики не созданы."
      );
    } finally {
      setRecognizing(false);
    }
  };

  const updateRow = (idempotencyKey: string, patch: Partial<OcrReviewRow>) => {
    setRows((currentRows) =>
      currentRows.map((row) =>
        row.candidate.idempotencyKey === idempotencyKey ? { ...row, ...patch } : row
      )
    );
  };

  const selectedRows = rows.filter((row) => row.include);
  const canConfirm =
    selectedRows.length > 0 &&
    selectedRows.every((row) => row.categoryId) &&
    Boolean(accountId) &&
    !isRecognizing &&
    !isSaving;

  const confirmRows = async () => {
    if (!canConfirm || !capturedAt) {
      return;
    }

    setSaving(true);
    setError("");
    setStatus("Сохраняем черновики");
    try {
      for (const row of selectedRows) {
        await client.saveCategoryMapping(
          row.candidate.externalLabel,
          row.categoryId,
          canUseHousehold ? householdId : null
        );
        await client.createCaptureDraft({
          idempotencyKey: row.candidate.idempotencyKey,
          captureSource: "screenshot",
          capturedAt,
          amount: Math.abs(row.candidate.amount.value),
          currency: row.candidate.amount.currency,
          description: captureDraftDescriptionForAggregate(row.candidate),
          occurredDate: dateInputValue(capturedAt),
          accountId,
          categoryId: row.categoryId,
          confidence: row.candidate.confidence,
          evidenceHash: row.candidate.evidenceHash
        });
      }
      await onSaved();
      setRows([]);
      setWarnings([]);
      setStatus("Черновики готовы к подтверждению");
    } catch {
      setError("Не удалось сохранить черновики. Проверьте категории и счет.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="plainSection" aria-labelledby="screenshot-ocr-title">
      <div className="sectionHead compact">
        <h3 id="screenshot-ocr-title">Скрин расходов</h3>
        <label className="ghostButton uploadButton">
          <Upload size={17} aria-hidden="true" />
          {isRecognizing ? "Распознаем" : "Распознать скрин расходов"}
          <input
            accept="image/png,image/jpeg,image/webp"
            disabled={isRecognizing || isSaving}
            type="file"
            onChange={(event) => {
              void recognize(event.target.files?.[0]);
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      <p className="scopeCopy">
        Скриншот отправляется как OCR-запрос. Результат сохраняется только как черновики для проверки, без импорта и автосоздания операций.
      </p>

      {accounts.length > 0 && (
        <label className="field compactField">
          <span>Счет для черновиков</span>
          <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
            <option value="">Выберите счет</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {accounts.length === 0 && (
        <EmptyState text="В выбранном scope нет счета для черновиков OCR. Сначала добавьте счет или переключите режим." />
      )}

      {error && <p className="formError">{error}</p>}
      {status && <p className={error ? "formError" : "formHint"}>{status}</p>}
      {warnings.map((warning) => (
        <p className="formError" key={warning}>
          {warning}
        </p>
      ))}

      {rows.length > 0 && (
        <div className="captureReviewList" aria-label="Проверка распознанных расходов">
          {rows.map((row) => (
            <article className="captureReviewRow" key={row.candidate.idempotencyKey}>
              <label className="includeToggle">
                <input
                  checked={row.include}
                  type="checkbox"
                  onChange={(event) =>
                    updateRow(row.candidate.idempotencyKey, { include: event.target.checked })
                  }
                />
                <span>Сохранить</span>
              </label>
              <div>
                <strong>{row.candidate.externalLabel}</strong>
                <span>{row.candidate.description}</span>
              </div>
              <div>
                <strong>{formatMoney(row.candidate.amount)}</strong>
                <span>{row.candidate.operationCount} операций</span>
              </div>
              <label className="field compactField">
                <span>Категория</span>
                <select
                  aria-label={`Категория для ${row.candidate.externalLabel}`}
                  value={row.categoryId}
                  onChange={(event) =>
                    updateRow(row.candidate.idempotencyKey, {
                      categoryId: event.target.value
                    })
                  }
                >
                  <option value="">Выберите</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
            </article>
          ))}
          <button className="submitButton" disabled={!canConfirm} type="button" onClick={confirmRows}>
            <Check size={18} aria-hidden="true" />
            {isSaving ? "Сохраняем" : "Создать черновики для проверки"}
          </button>
        </div>
      )}
    </section>
  );
}

function AssetsPage({
  client,
  onChanged,
  snapshot,
  viewMode
}: {
  client: FinanceApiClient;
  onChanged: () => Promise<DashboardSnapshot>;
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
}) {
  const accounts = visibleAccounts(snapshot.accounts, viewMode);
  const assetCategories = snapshot.assetCategories.filter(
    (ac) => ac.recordStatus === "active"
  );
  const archivedAccounts = snapshot.accounts.filter(
    (a) => a.status === "archived"
  );
  const archivedAssetCategories = snapshot.assetCategories.filter(
    (ac) => ac.recordStatus === "archived"
  );

  const [updatingAccountId, setUpdatingAccountId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [editingAccount, setEditingAccount] = useState<AccountSummary | null>(null);
  const [editingAssetCategory, setEditingAssetCategory] = useState<AssetCategory | null>(null);
  const [showCreateAssetCategory, setShowCreateAssetCategory] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [categoryOrder, setCategoryOrder] = useState<string[]>([]);

  const updatePaymentAccount = async (account: AccountSummary, isPaymentAccount: boolean) => {
    setUpdatingAccountId(account.id);
    setStatus("");
    try {
      await client.updateAccount({
        accountId: account.id,
        isPaymentAccount,
        version: account.version
      });
      await onChanged();
      setStatus(isPaymentAccount ? "Счет доступен для расходов" : "Счет скрыт из оплаты расходов");
    } catch {
      setStatus("Не удалось обновить счет для оплаты");
    } finally {
      setUpdatingAccountId(null);
    }
  };

  const saveAssetCategory = async (input: AssetCategoryFormInput) => {
    if (input.assetCategoryId) {
      await client.updateAssetCategory({
        assetCategoryId: input.assetCategoryId,
        name: input.name,
        manualAmount: input.manualAmount,
        assetType: input.assetType,
        iconKey: input.iconKey,
        isInvestment: input.isInvestment,
        version: input.version
      });
    } else {
      await client.createAssetCategory({
        name: input.name,
        scopeType: input.scopeType,
        currency: input.currency,
        manualAmount: input.manualAmount,
        isInvestment: input.isInvestment,
        assetType: input.assetType,
        iconKey: input.iconKey,
        householdId:
          input.scopeType === "household" ? snapshot.session.householdId : null
      });
    }
    await onChanged();
  };

  const saveAccount = async (input: AccountEditFormInput) => {
    await client.updateAccount({
      accountId: input.accountId,
      name: input.name,
      balance: input.balance,
      currency: input.currency,
      assetCategoryId: input.assetCategoryId || null,
      isPaymentAccount: input.isPaymentAccount,
      version: input.version
    });
    await onChanged();
  };

  const toggleCategoryExpand = (id: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const accountsByCategory = (catId: string) =>
    accounts.filter((a) => a.assetCategoryId === catId);

  const uncategorizedAccounts = accounts.filter((a) => !a.assetCategoryId);

  const orderedAssetCategories = useMemo(() => {
    if (categoryOrder.length === 0) return assetCategories;
    const indexed = new Map(assetCategories.map((c) => [c.id, c]));
    const ordered = categoryOrder
      .map((id) => indexed.get(id))
      .filter((c): c is AssetCategory => c !== undefined);
    for (const cat of assetCategories) {
      if (!ordered.includes(cat)) ordered.push(cat);
    }
    return ordered;
  }, [assetCategories, categoryOrder]);

  const moveCategoryUp = (id: string) => {
    const ids = orderedAssetCategories.map((c) => c.id);
    const idx = ids.indexOf(id);
    if (idx <= 0) return;
    [ids[idx - 1], ids[idx]] = [ids[idx], ids[idx - 1]];
    setCategoryOrder(ids);
  };

  const moveCategoryDown = (id: string) => {
    const ids = orderedAssetCategories.map((c) => c.id);
    const idx = ids.indexOf(id);
    if (idx < 0 || idx >= ids.length - 1) return;
    [ids[idx], ids[idx + 1]] = [ids[idx + 1], ids[idx]];
    setCategoryOrder(ids);
  };

  return (
    <section className="screenStack" aria-labelledby="assets-title">
      <div className="sectionHead">
        <h3 id="assets-title">Счета и активы</h3>
        <span>{accounts.length} активов</span>
      </div>
      <p className="scopeCopy">{scopeDescription(viewMode)}</p>
      {status && (
        <p className={status.startsWith("Не") ? "formError" : "formHint"}>
          {status}
        </p>
      )}

      {snapshot.investmentsByCurrency.length > 0 && (
        <section className="plainSection" aria-labelledby="investments-title">
          <div className="sectionHead compact">
            <h3 id="investments-title">
              <TrendingUp
                size={18}
                style={{
                  display: "inline",
                  verticalAlign: "middle",
                  marginRight: 6
                }}
              />
              Инвестиции
            </h3>
          </div>
          <div className="metricGrid">
            {snapshot.investmentsByCurrency.map((inv, i) => (
              <Metric
                key={i}
                label={`Инвестиции (${inv.currency})`}
                value={formatMoney(inv.investmentsTotal)}
              />
            ))}
          </div>
        </section>
      )}

      <section className="plainSection" aria-labelledby="asset-categories-title">
        <div className="sectionHead compact">
          <h3 id="asset-categories-title">Категории активов</h3>
          <button
            className="ghostButton"
            type="button"
            onClick={() => setShowCreateAssetCategory(true)}
          >
            <Plus size={17} aria-hidden="true" />
            Категория
          </button>
        </div>

        {showCreateAssetCategory && (
          <AssetCategoryForm
            category={null}
            householdId={snapshot.session.householdId}
            onCancel={() => setShowCreateAssetCategory(false)}
            onSave={async (input) => {
              await saveAssetCategory(input);
              setShowCreateAssetCategory(false);
            }}
          />
        )}
        {editingAssetCategory && (
          <AssetCategoryForm
            category={editingAssetCategory}
            householdId={snapshot.session.householdId}
            onCancel={() => setEditingAssetCategory(null)}
            onSave={async (input) => {
              await saveAssetCategory(input);
              setEditingAssetCategory(null);
            }}
          />
        )}

        <div className="listStack">
          {orderedAssetCategories.map((cat, catIndex) => {
            const isExpanded = expandedCategories.has(cat.id);
            const catAccounts = accountsByCategory(cat.id);
            return (
              <div key={cat.id} className="assetCategoryItem">
                <div className="assetCategoryHeader">
                  <div className="reorderButtons">
                    <button
                      className="ghostButton compact"
                      type="button"
                      disabled={catIndex === 0}
                      onClick={() => moveCategoryUp(cat.id)}
                      title="Вверх"
                    >
                      <ChevronUp size={12} />
                    </button>
                    <button
                      className="ghostButton compact"
                      type="button"
                      disabled={catIndex === orderedAssetCategories.length - 1}
                      onClick={() => moveCategoryDown(cat.id)}
                      title="Вниз"
                    >
                      <ChevronDown size={12} />
                    </button>
                  </div>
                  <button
                    className="ghostButton compact"
                    type="button"
                    onClick={() => toggleCategoryExpand(cat.id)}
                  >
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                  <div className="assetCategoryInfo">
                    <strong>{cat.name}</strong>
                    <span>
                      {cat.scopeType === "household" ? "Общее" : "Личное"} · {cat.currency}
                      {cat.isInvestment ? " · Инвестиция" : ""}
                    </span>
                  </div>
                  <b className="neutral">{formatMoney(cat.manualAmount)}</b>
                  <div className="assetCategoryActions">
                    <button
                      className="tileAction"
                      type="button"
                      onClick={() => setEditingAssetCategory(cat)}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      className="tileAction"
                      type="button"
                      onClick={async () => {
                        await client.archiveAssetCategory(cat.id);
                        await onChanged();
                      }}
                    >
                      <Archive size={14} />
                    </button>
                  </div>
                </div>
                {isExpanded && catAccounts.length > 0 && (
                  <div className="assetCategoryAccounts">
                    {catAccounts.map((account) => (
                      <AssetTile
                        key={account.id}
                        account={account}
                        isUpdating={updatingAccountId === account.id}
                        onPaymentAccountChange={updatePaymentAccount}
                        onEdit={() => setEditingAccount(account)}
                        onArchive={async () => {
                          await client.archiveAccount(account.id);
                          await onChanged();
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {orderedAssetCategories.length === 0 && (
            <EmptyState text="Нет категорий активов. Создайте категорию для группировки счетов." />
          )}
        </div>
      </section>

      {uncategorizedAccounts.length > 0 && (
        <section className="plainSection" aria-labelledby="legacy-accounts-title">
          <div className="sectionHead compact">
            <h3 id="legacy-accounts-title">
              <AlertTriangle
                size={18}
                style={{
                  display: "inline",
                  verticalAlign: "middle",
                  marginRight: 6
                }}
              />
              Без категории
            </h3>
          </div>
          <p className="scopeCopy">
            Эти счета не привязаны к категории активов. Нажмите «Изменить» для привязки.
          </p>
          <div className="assetGrid">
            {uncategorizedAccounts.map((account) => (
              <AssetTile
                key={account.id}
                account={account}
                isUpdating={updatingAccountId === account.id}
                onPaymentAccountChange={updatePaymentAccount}
                onEdit={() => setEditingAccount(account)}
                onArchive={async () => {
                  await client.archiveAccount(account.id);
                  await onChanged();
                }}
              />
            ))}
          </div>
        </section>
      )}

      {(archivedAccounts.length > 0 || archivedAssetCategories.length > 0) && (
        <div>
          <button
            className="ghostButton"
            type="button"
            onClick={() => setShowArchived(!showArchived)}
          >
            {showArchived
              ? "Скрыть архив"
              : `Архив (${archivedAccounts.length + archivedAssetCategories.length})`}
          </button>
        </div>
      )}
      {showArchived && (
        <section className="plainSection" aria-labelledby="archived-assets-title">
          <div className="sectionHead compact">
            <h3 id="archived-assets-title">Архив</h3>
          </div>
          <div className="listStack">
            {archivedAccounts.map((account) => (
              <div key={account.id} className="listRow archivedRow">
                <div className="rowIcon">
                  <Landmark size={18} />
                </div>
                <div>
                  <strong>{account.name}</strong>
                  <span>Счет · Архив</span>
                </div>
                <div className="assetCategoryActions">
                  <button
                    className="tileAction"
                    type="button"
                    onClick={async () => {
                      await client.restoreAccount(account.id);
                      await onChanged();
                    }}
                  >
                    <RotateCcw size={14} />
                  </button>
                </div>
              </div>
            ))}
            {archivedAssetCategories.map((cat) => (
              <div key={cat.id} className="listRow archivedRow">
                <div className="rowIcon">
                  <Layers3 size={18} />
                </div>
                <div>
                  <strong>{cat.name}</strong>
                  <span>Категория актива · Архив</span>
                </div>
                <div className="assetCategoryActions">
                  <button
                    className="tileAction"
                    type="button"
                    onClick={async () => {
                      await client.restoreAssetCategory(cat.id);
                      await onChanged();
                    }}
                  >
                    <RotateCcw size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {editingAccount && (
        <AccountEditModal
          account={editingAccount}
          assetCategories={assetCategories}
          onCancel={() => setEditingAccount(null)}
          onSave={async (input) => {
            await saveAccount(input);
            setEditingAccount(null);
          }}
        />
      )}
    </section>
  );
}

function CategoriesPage({
  snapshot,
  viewMode,
  onSave
}: {
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
  onSave: (input: CategoryFormInput) => Promise<void>;
}) {
  const categories = visibleCategories(snapshot.categories, viewMode);
  const archivedCategories = snapshot.categories.filter(
    (c) => c.status === "archived"
  );
  const [editingCategory, setEditingCategory] = useState<CategorySummary | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  return (
    <section className="screenStack" aria-labelledby="categories-title">
      <div className="sectionHead">
        <h3 id="categories-title">Категории</h3>
        <span>{categories.length} категорий</span>
      </div>
      <p className="scopeCopy">{scopeDescription(viewMode)}</p>
      {viewMode === "overview" ? (
        <EmptyState text="Обзор показывает видимые категории только для чтения. Для создания или редактирования выберите личное или общее." />
      ) : (
        <CategoryForm
          category={editingCategory}
          defaultScope={viewMode === "shared" ? "household" : "personal"}
          householdId={snapshot.session.householdId}
          onCancel={() => setEditingCategory(null)}
          onSave={async (input) => {
            await onSave(input);
            setEditingCategory(null);
          }}
        />
      )}
      <div className="categoryGrid">
        {categories.map((category, index) => (
          <CategoryTile
            key={category.id}
            category={category}
            index={index}
            onEdit={() => setEditingCategory(category)}
            onArchive={
              viewMode !== "overview"
                ? async () => {
                    await financeApiClient.archiveCategory(category.id);
                    await onSave({
                      categoryId: category.id,
                      name: category.name,
                      direction: category.direction,
                      scope: category.scope ?? "personal",
                      iconKey: category.iconKey ?? "tag",
                      color: category.color ?? "#2563eb"
                    });
                  }
                : undefined
            }
          />
        ))}
        {categories.length === 0 && (
          <EmptyState text={scopeEmptyText(viewMode, "категорий", "создайте категорию в личном или общем режиме")} />
        )}
      </div>
      {archivedCategories.length > 0 && (
        <div>
          <button
            className="ghostButton"
            type="button"
            onClick={() => setShowArchived(!showArchived)}
          >
            {showArchived
              ? "Скрыть архив"
              : `Архив категорий (${archivedCategories.length})`}
          </button>
        </div>
      )}
      {showArchived && (
        <section className="plainSection" aria-labelledby="archived-categories-title">
          <div className="sectionHead compact">
            <h3 id="archived-categories-title">Архив категорий</h3>
          </div>
          <div className="listStack">
            {archivedCategories.map((cat) => (
              <div key={cat.id} className="listRow archivedRow">
                <div className="rowIcon">
                  <Tag size={18} />
                </div>
                <div>
                  <strong>{cat.name}</strong>
                  <span>
                    {cat.direction === "income" ? "Доход" : "Расход"} · Архив
                  </span>
                </div>
                <div className="assetCategoryActions">
                  <button
                    className="tileAction"
                    type="button"
                    onClick={async () => {
                      const client = financeApiClient;
                      await client.restoreCategory(cat.id);
                      await onSave({
                        categoryId: cat.id,
                        name: cat.name,
                        direction: cat.direction,
                        scope: cat.scope ?? "personal",
                        iconKey: cat.iconKey ?? "tag",
                        color: cat.color ?? "#2563eb"
                      });
                    }}
                  >
                    <RotateCcw size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}

function CategoryForm({
  category,
  defaultScope,
  householdId,
  onCancel,
  onSave
}: {
  category: CategorySummary | null;
  defaultScope: CategoryScope;
  householdId: string | null;
  onCancel: () => void;
  onSave: (input: CategoryFormInput) => Promise<void>;
}) {
  const [name, setName] = useState(category?.name ?? "");
  const [direction, setDirection] = useState<CategoryDirection>(category?.direction ?? "expense");
  const [scope, setScope] = useState<CategoryScope>(category?.scope ?? defaultScope);
  const [iconKey, setIconKey] = useState(category?.iconKey ?? "tag");
  const [color, setColor] = useState(category?.color ?? "#2563EB");
  const [status, setStatus] = useState<string>("");
  const [isSaving, setSaving] = useState(false);

  useEffect(() => {
    setName(category?.name ?? "");
    setDirection(category?.direction ?? "expense");
    setScope(category?.scope ?? defaultScope);
    setIconKey(category?.iconKey ?? "tag");
    setColor(category?.color ?? "#2563EB");
    setStatus("");
  }, [category, defaultScope]);

  const isHouseholdBlocked = scope === "household" && !householdId;
  const canSubmit = Boolean(name.trim()) && !isHouseholdBlocked && !isSaving;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }

    setSaving(true);
    setStatus("");
    try {
      await onSave({
        categoryId: category?.id,
        version: category?.version,
        name,
        direction,
        scope,
        iconKey,
        color
      });
      setName("");
      setStatus(category ? "Категория обновлена" : "Категория создана");
    } catch {
      setStatus("Не удалось сохранить категорию");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="categoryForm" aria-label="Управление категорией" onSubmit={submit}>
      <div className="sectionHead compact">
        <h3>{category ? "Редактировать" : "Новая категория"}</h3>
        {category && (
          <button className="ghostButton" type="button" onClick={onCancel}>
            <X size={17} aria-hidden="true" />
            Отмена
          </button>
        )}
      </div>
      <div className="categoryFormGrid">
        <label className="field">
          <span>Название</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="field">
          <span>Тип</span>
          <select
            value={direction}
            disabled={Boolean(category)}
            onChange={(event) => setDirection(event.target.value as CategoryDirection)}
          >
            <option value="expense">Расход</option>
            <option value="income">Доход</option>
          </select>
        </label>
        <label className="field">
          <span>Доступ</span>
          <select
            value={scope}
            disabled={Boolean(category)}
            onChange={(event) => setScope(event.target.value as CategoryScope)}
          >
            <option value="personal">Личное</option>
            <option value="household">Общее</option>
          </select>
        </label>
        <label className="field">
          <span>Иконка</span>
          <select value={iconKey} onChange={(event) => setIconKey(event.target.value)}>
            <option value="tag">Метка</option>
            <option value="shopping">Покупки</option>
            <option value="home">Дом</option>
            <option value="income">Доход</option>
            <option value="wallet">Кошелек</option>
          </select>
        </label>
        <label className="field colorField">
          <span>Цвет</span>
          <input type="color" value={color} onChange={(event) => setColor(event.target.value)} />
        </label>
      </div>
      {isHouseholdBlocked && (
        <p className="formError">Для общей категории нужен семейный доступ.</p>
      )}
      {status && <p className={status.startsWith("Не") ? "formError" : "formHint"}>{status}</p>}
      <button className="submitButton categorySubmit" type="submit" disabled={!canSubmit}>
        <Check size={18} aria-hidden="true" />
        {isSaving ? "Сохраняем" : category ? "Сохранить" : "Создать"}
      </button>
    </form>
  );
}

function AnalyticsPage({
  client,
  monthValue,
  onMonthChange,
  snapshot,
  report,
  viewMode,
  tab,
  onTabChange
}: {
  client: FinanceApiClient;
  monthValue: string;
  onMonthChange: (value: string) => void;
  snapshot: DashboardSnapshot;
  report: ReportSummary;
  viewMode: ViewMode;
  tab: AnalyticsTab;
  onTabChange: (tab: AnalyticsTab) => void;
}) {
  const range = monthRange(monthValue);
  const accounts = visibleAccounts(snapshot.accounts, viewMode);
  const operations = filterOperationsByDateRange(
    visibleOperations(snapshot.operations, accounts),
    range
  );
  const currency = accounts[0]?.balance.currency ?? report.income.currency;
  const analyticsReport =
    viewMode === "personal" ? reportFromOperations("personal", operations, currency, range) : report;
  const topCategories = categoryTotals(operations, snapshot.categories, currency);
  const groups = groupAssets(accounts, currency);
  const investmentsTotal = snapshot.investmentsTotal ?? { value: 0, currency };

  return (
    <section className="screenStack" aria-labelledby="analytics-title">
      <div className="sectionHead">
        <h3 id="analytics-title">Аналитика</h3>
        <MonthSwitcher value={monthValue} onChange={onMonthChange} />
      </div>
      <div className="segmentedControl" role="group" aria-label="Раздел аналитики">
        <button
          className={tab === "summary" ? "selected" : ""}
          type="button"
          onClick={() => onTabChange("summary")}
        >
          <BarChart3 size={16} aria-hidden="true" />
          Сводка
        </button>
        <button
          className={tab === "planning" ? "selected" : ""}
          type="button"
          onClick={() => onTabChange("planning")}
        >
          <CalendarDays size={16} aria-hidden="true" />
          План месяца
        </button>
      </div>

      {tab === "summary" ? (
        <>
          <p className="scopeCopy">{scopeDescription(viewMode)}</p>
          <p className="scopeCopy">{analyticsReport.periodLabel}</p>
          <div className="metricGrid">
            <Metric label="Доходы" value={formatMoney(analyticsReport.income)} tone="success" />
            <Metric label="Расходы" value={formatMoney(analyticsReport.expense)} tone="danger" />
            <Metric label="Итог" value={formatMoney(analyticsReport.balanceDelta)} />
            <Metric label="Инвестиции" value={formatMoney(investmentsTotal)} />
          </div>
          <div className="dashboardGrid">
            <section className="plainSection" aria-labelledby="analytics-categories-title">
              <div className="sectionHead compact">
                <h3 id="analytics-categories-title">Категории</h3>
              </div>
              <div className="barList">
                {topCategories.map((category) => (
                  <BarRow key={category.name} label={category.name} amount={category.amount} />
                ))}
                {topCategories.length === 0 && <EmptyState text="Пока нет расходов" />}
              </div>
            </section>
            <section className="plainSection" aria-labelledby="analytics-assets-title">
              <div className="sectionHead compact">
                <h3 id="analytics-assets-title">Капитал</h3>
              </div>
              <div className="barList">
                {groups.map((group) => (
                  <BarRow key={group.kind} label={accountKindLabels[group.kind]} amount={group.total} />
                ))}
                {groups.length === 0 && <EmptyState text="Нет активов" />}
              </div>
            </section>
          </div>
        </>
      ) : (
        <PlanningPage
          client={client}
          snapshot={snapshot}
          viewMode={viewMode}
        />
      )}
    </section>
  );
}

function MonthSwitcher({
  value,
  onChange
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const currentMonth = currentMonthValue();

  return (
    <div className="monthSwitcher" role="group" aria-label="Месяц аналитики">
      <button
        aria-label="Предыдущий месяц"
        type="button"
        onClick={() => onChange(shiftMonth(value, -1))}
      >
        <ChevronLeft size={17} aria-hidden="true" />
      </button>
      <span>
        <CalendarDays size={16} aria-hidden="true" />
        {monthLabel(value)}
      </span>
      <button
        aria-label="Следующий месяц"
        type="button"
        onClick={() => onChange(shiftMonth(value, 1))}
      >
        <ChevronRight size={17} aria-hidden="true" />
      </button>
      <button
        className="currentMonthButton"
        disabled={value === currentMonth}
        type="button"
        onClick={() => onChange(currentMonth)}
      >
        Текущий
      </button>
    </div>
  );
}

function PlanningPage({
  client,
  snapshot,
  viewMode
}: {
  client: FinanceApiClient;
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
}) {
  const scopeInfo = planningScopeInfo(viewMode, snapshot.session.householdId);
  const currency = snapshot.accounts.find((a) => a.status === "active")?.balance.currency ?? "RUB";
  const [plan, setPlan] = useState<PlanningPlan | null>(null);
  const [history, setHistory] = useState<PlanningPlan[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [planningMonth, setPlanningMonth] = useState(() => coercePlanningMonth(currentMonthValue()));
  const monthChoices = useMemo(() => planningMonthChoices(), []);
  const goalMonthChoices = useMemo(() => planningGoalMonthChoices(), []);

  const loadPlanning = useCallback(
    async (successMsg?: string) => {
      if (!scopeInfo) return;
      setLoading(true);
      setMessage(null);
      try {
        const found = await client.listPlanningPlans(
          scopeInfo.scope,
          planningMonth,
          scopeInfo.householdId
        );
        if (found) {
          const full = await client.getPlanningPlan(found.id);
          setPlan(full);
        } else {
          setPlan(null);
        }
        setMessage(successMsg ?? null);
      } catch (e) {
        if (isApiRequestError(e, 404)) {
          setPlan(null);
          setMessage(successMsg ?? null);
        } else {
          setMessage("Не удалось загрузить план");
        }
      }
      try {
        const hist = await client.listPlanningPlanHistory(
          scopeInfo.scope,
          scopeInfo.householdId
        );
        setHistory(hist);
      } catch {}
      setLoading(false);
    },
    [client, scopeInfo, planningMonth]
  );

  useEffect(() => {
    void loadPlanning();
  }, [loadPlanning]);

  const createPlan = async () => {
    if (!scopeInfo) return;
    setLoading(true);
    try {
      await client.createPlanningPlan({
        scope: scopeInfo.scope,
        month: planningMonth,
        currency: currency as CurrencyCode,
        householdId: scopeInfo.householdId
      });
      await loadPlanning("План создан");
    } catch {
      setMessage("Не удалось создать план");
      setLoading(false);
    }
  };

  const copyPlan = async (sourcePlan: PlanningPlan) => {
    setLoading(true);
    try {
      await client.copyPlanningPlan({
        planId: sourcePlan.id,
        targetMonth: planningMonth
      });
      await loadPlanning(`План скопирован на ${monthLabel(planningMonth)}`);
    } catch {
      setMessage("Не удалось скопировать план");
      setLoading(false);
    }
  };

  if (!scopeInfo) {
    return (
      <div className="planningCard">
        <p className="scopeCopy">
          Обзор не создаёт единый план. Выберите личный или общий режим для планирования.
        </p>
      </div>
    );
  }

  return (
    <div className="screenStack">
      {message && (
        <p className={message.startsWith("Не") ? "formError" : "formHint"}>{message}</p>
      )}

      <div className="planningCard">
        <div className="planningCardHead">
          <div>
            <strong>План месяца</strong>
            <span>
              {monthLabel(planningMonth)} · {currency}
            </span>
          </div>
          <button
            className="ghostButton compact"
            type="button"
            disabled={isLoading}
            onClick={() => void loadPlanning()}
          >
            <RotateCcw size={14} />
          </button>
        </div>
        <label className="field">
          <span>Месяц плана</span>
          <select
            value={planningMonth}
            onChange={(e) => setPlanningMonth(coercePlanningMonth(e.target.value))}
          >
            {monthChoices.map((c) => (
              <option key={c.month} value={c.month}>
                {c.title}
              </option>
            ))}
          </select>
        </label>
      </div>

      <PlanningPlanCard
        plan={plan}
        month={planningMonth}
        currency={currency}
        isLoading={isLoading}
        onCreate={createPlan}
      />

      {plan && (
        <>
          <PlanningIncomeSourcesCard
            plan={plan}
            currency={currency}
            isLoading={isLoading}
            onAdd={async (input) => {
              if (!plan) return;
              setLoading(true);
              try {
                await client.createPlanningIncomeSource({
                  planId: plan.id,
                  source: input.source,
                  amount: input.amount,
                  dayOfMonth: input.dayOfMonth
                });
                await loadPlanning("Источник дохода добавлен");
              } catch {
                setMessage("Не удалось добавить источник дохода");
                setLoading(false);
              }
            }}
            onUpdate={async (sourceId, input) => {
              setLoading(true);
              try {
                await client.updatePlanningIncomeSource({
                  incomeSourceId: sourceId,
                  ...input
                });
                await loadPlanning("Источник дохода обновлён");
              } catch {
                setMessage("Не удалось обновить источник дохода");
                setLoading(false);
              }
            }}
            onConfirm={async (sourceId) => {
              setLoading(true);
              try {
                await client.confirmPlanningIncomeSource(sourceId);
                await loadPlanning("Доход подтверждён");
              } catch {
                setMessage("Не удалось подтвердить доход");
                setLoading(false);
              }
            }}
            onDelete={async (sourceId) => {
              setLoading(true);
              try {
                await client.deletePlanningIncomeSource(sourceId);
                await loadPlanning("Источник дохода удалён");
              } catch {
                setMessage("Не удалось удалить источник дохода");
                setLoading(false);
              }
            }}
          />

          <PlanningAllocationsCard
            plan={plan}
            snapshot={snapshot}
            viewMode={viewMode}
            currency={currency}
            isLoading={isLoading}
            goalMonthChoices={goalMonthChoices}
            onAdd={async (draft) => {
              if (!plan) return;
              const savingsEnabled =
                draft.isSavingsGoal && draft.targetType === "investment_asset_category";
              setLoading(true);
              try {
                await client.createPlanningAllocation({
                  planId: plan.id,
                  targetType: draft.targetType,
                  targetId: draft.targetId,
                  comment: draft.comment.trim() || null,
                  allocationMode: draft.allocationMode,
                  allocationValue: Number(draft.allocationValue),
                  recurrenceType: draft.recurrenceType,
                  isSavingsGoal: savingsEnabled,
                  goalTargetAmount: savingsEnabled ? Number(draft.goalTargetAmount) || null : null,
                  goalDueMonth: savingsEnabled ? draft.goalDueMonth : null
                });
                await loadPlanning("Распределение добавлено");
              } catch {
                setMessage("Не удалось добавить распределение");
                setLoading(false);
              }
            }}
            onUpdate={async (allocationId, draft, version) => {
              const savingsEnabled =
                draft.isSavingsGoal && draft.targetType === "investment_asset_category";
              setLoading(true);
              try {
                await client.updatePlanningAllocation({
                  allocationId,
                  targetType: draft.targetType,
                  targetId: draft.targetId,
                  comment: draft.comment.trim() || null,
                  allocationMode: draft.allocationMode,
                  allocationValue: Number(draft.allocationValue),
                  recurrenceType: draft.recurrenceType,
                  isSavingsGoal: savingsEnabled,
                  goalTargetAmount: savingsEnabled ? Number(draft.goalTargetAmount) || null : null,
                  goalDueMonth: savingsEnabled ? draft.goalDueMonth : null,
                  version
                });
                await loadPlanning("Распределение обновлено");
              } catch {
                setMessage("Не удалось обновить распределение");
                setLoading(false);
              }
            }}
            onDelete={async (allocationId) => {
              setLoading(true);
              try {
                await client.deletePlanningAllocation(allocationId);
                await loadPlanning("Распределение удалено");
              } catch {
                setMessage("Не удалось удалить распределение");
                setLoading(false);
              }
            }}
          />
        </>
      )}

      <PlanningHistoryCard
        history={history}
        currentMonth={planningMonth}
        isLoading={isLoading}
        onCopy={copyPlan}
      />
    </div>
  );
}

function PlanningPlanCard({
  plan,
  month,
  currency,
  isLoading,
  onCreate
}: {
  plan: PlanningPlan | null;
  month: string;
  currency: string;
  isLoading: boolean;
  onCreate: () => void;
}) {
  return (
    <div className="planningCard">
      <div className="planningCardHead">
        <div>
          <strong>Текущий план</strong>
          <span>
            {plan
              ? `${plan.scope === "household" ? "Общее" : "Личное"} · ${monthLabel(plan.month)} · ${plan.currency}`
              : `План на ${monthLabel(month)} ещё не создан`}
          </span>
        </div>
      </div>
      {!plan ? (
        <button
          className="submitButton"
          type="button"
          disabled={isLoading}
          onClick={onCreate}
        >
          <Plus size={18} aria-hidden="true" />
          Создать план на {monthLabel(month)}
        </button>
      ) : (
        <>
          <div className="planningMetricGrid">
            <div className="planningMetric">
              <span>Доход</span>
              <strong>{formatMoney(plan.totalPlannedIncome)}</strong>
            </div>
            <div className="planningMetric">
              <span>Распределено</span>
              <strong>{formatMoney(plan.allocatedTotal)}</strong>
            </div>
          </div>
          {plan.previousMonthSurplus.value > 0 && (
            <p className="scopeCopy" style={{ marginTop: 6 }}>
              Остаток прошлого месяца: {formatMoney(plan.previousMonthSurplus)}
            </p>
          )}
          <div className="planningMetricGrid">
            <div className="planningMetric">
              <span>Осталось</span>
              <strong>{formatMoney(plan.remainingAmount)}</strong>
            </div>
            <div className="planningMetric">
              <span>Сверх</span>
              <strong>{formatMoney(plan.overallocatedAmount)}</strong>
            </div>
          </div>
          {plan.isUnderallocated && (
            <div className="planningBanner warning">
              Есть доход без распределений. Добавьте распределение или уменьшите плановый доход.
            </div>
          )}
          {plan.isOverallocated && (
            <div className="planningBanner danger">
              Распределения выше планового дохода. Исправьте распределения.
            </div>
          )}
        </>
      )}
    </div>
  );
}

function PlanningIncomeSourcesCard({
  plan,
  currency,
  isLoading,
  onAdd,
  onUpdate,
  onConfirm,
  onDelete
}: {
  plan: PlanningPlan;
  currency: string;
  isLoading: boolean;
  onAdd: (input: { source: string; amount: number; dayOfMonth: number }) => Promise<void>;
  onUpdate: (
    sourceId: string,
    input: { source?: string; amount?: number; dayOfMonth?: number; version?: number }
  ) => Promise<void>;
  onConfirm: (sourceId: string) => Promise<void>;
  onDelete: (sourceId: string) => Promise<void>;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [source, setSource] = useState("");
  const [amount, setAmount] = useState("");
  const [day, setDay] = useState("");

  const submitAdd = () => {
    const amt = Number(amount);
    const d = Number(day);
    if (!source.trim() || !Number.isFinite(amt) || amt <= 0 || d < 1 || d > 31) return;
    void onAdd({ source: source.trim(), amount: amt, dayOfMonth: d });
    setSource("");
    setAmount("");
    setDay("");
    setShowAdd(false);
  };

  return (
    <div className="planningCard">
      <div className="sectionHead compact">
        <h3>Источники дохода</h3>
      </div>
      {!showAdd ? (
        <button
          className="ghostButton"
          type="button"
          disabled={isLoading}
          onClick={() => setShowAdd(true)}
        >
          <Plus size={17} aria-hidden="true" />
          Добавить источник
        </button>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          <label className="field">
            <span>Источник</span>
            <input value={source} onChange={(e) => setSource(e.target.value)} />
          </label>
          <div className="planningFormRow">
            <label className="field">
              <span>Сумма</span>
              <input
                type="number"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            <label className="field" style={{ maxWidth: 100 }}>
              <span>День</span>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                max={31}
                value={day}
                onChange={(e) => setDay(e.target.value)}
              />
            </label>
          </div>
          <button
            className="submitButton"
            type="button"
            disabled={isLoading || !source.trim() || !Number(amount) || !Number(day)}
            onClick={submitAdd}
          >
            <Plus size={18} aria-hidden="true" />
            Добавить
          </button>
        </div>
      )}
      {plan.incomeSources.length === 0 ? (
        <p className="scopeCopy">Источников дохода пока нет</p>
      ) : (
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {plan.incomeSources.map((item) => (
            <PlanningIncomeSourceRow
              key={item.id}
              source={item}
              currency={currency}
              isLoading={isLoading}
              onUpdate={onUpdate}
              onConfirm={onConfirm}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function PlanningIncomeSourceRow({
  source,
  currency,
  isLoading,
  onUpdate,
  onConfirm,
  onDelete
}: {
  source: PlanningIncomeSource;
  currency: string;
  isLoading: boolean;
  onUpdate: (
    sourceId: string,
    input: { source?: string; amount?: number; dayOfMonth?: number; version?: number }
  ) => Promise<void>;
  onConfirm: (sourceId: string) => Promise<void>;
  onDelete: (sourceId: string) => Promise<void>;
}) {
  const [isEditing, setEditing] = useState(false);
  const [editSource, setEditSource] = useState(source.source);
  const [editAmount, setEditAmount] = useState(String(source.amount.value));
  const [editDay, setEditDay] = useState(String(source.dayOfMonth));

  const save = () => {
    const amt = Number(editAmount);
    const d = Number(editDay);
    if (!editSource.trim() || !Number.isFinite(amt) || amt <= 0 || d < 1 || d > 31) return;
    void onUpdate(source.id, {
      source: editSource.trim(),
      amount: amt,
      dayOfMonth: d,
      version: source.version
    });
    setEditing(false);
  };

  return (
    <div className="planningRow">
      <div className="planningRowHead">
        <div>
          <strong>{source.source}</strong>
          <span>
            {formatMoney(source.amount)} · день {source.dayOfMonth} ·{" "}
            {source.confirmed ? "подтверждён" : "ожидает"}
          </span>
        </div>
        <button className="ghostButton compact" type="button" onClick={() => setEditing(!isEditing)}>
          {isEditing ? "Закрыть" : "Править"}
        </button>
      </div>
      {isEditing && (
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          <label className="field">
            <span>Источник</span>
            <input value={editSource} onChange={(e) => setEditSource(e.target.value)} />
          </label>
          <div className="planningFormRow">
            <label className="field">
              <span>Сумма</span>
              <input
                type="number"
                inputMode="decimal"
                value={editAmount}
                onChange={(e) => setEditAmount(e.target.value)}
              />
            </label>
            <label className="field" style={{ maxWidth: 100 }}>
              <span>День</span>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                max={31}
                value={editDay}
                onChange={(e) => setEditDay(e.target.value)}
              />
            </label>
          </div>
          <div className="planningRowActions">
            <button
              className="ghostButton"
              type="button"
              disabled={isLoading}
              onClick={() => void onDelete(source.id)}
            >
              <Trash2 size={14} />
              Удалить
            </button>
            <button
              className="submitButton"
              type="button"
              disabled={isLoading}
              onClick={save}
            >
              <Check size={16} />
              Сохранить
            </button>
          </div>
        </div>
      )}
      {!source.confirmed && !isEditing && (
        <button
          className="ghostButton"
          type="button"
          disabled={isLoading}
          style={{ marginTop: 6, width: "100%" }}
          onClick={() => void onConfirm(source.id)}
        >
          <Check size={16} />
          Подтвердить доход
        </button>
      )}
    </div>
  );
}

function PlanningAllocationsCard({
  plan,
  snapshot,
  viewMode,
  currency,
  isLoading,
  goalMonthChoices,
  onAdd,
  onUpdate,
  onDelete
}: {
  plan: PlanningPlan;
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
  currency: string;
  isLoading: boolean;
  goalMonthChoices: Array<{ month: string; title: string }>;
  onAdd: (draft: AllocationDraft) => Promise<void>;
  onUpdate: (allocationId: string, draft: AllocationDraft, version?: number) => Promise<void>;
  onDelete: (allocationId: string) => Promise<void>;
}) {
  const expenseCategories = snapshot.categories.filter(
    (c) => c.status !== "deleted" && c.status !== "archived" && c.direction === "expense"
  );
  const investmentCategories = snapshot.assetCategories.filter(
    (ac) => ac.recordStatus === "active" && ac.isInvestment
  );
  const [draft, setDraft] = useState<AllocationDraft>({
    targetType: "expense_category",
    targetId: "",
    allocationMode: "amount",
    allocationValue: "",
    recurrenceType: "regular",
    isSavingsGoal: false,
    goalTargetAmount: "",
    goalDueMonth: nextPlanningMonth(),
    comment: ""
  });

  const usedTargetIds = new Set(plan.allocations.map((a) => a.targetId));
  const targetOptions = planningTargetOptions(
    draft.targetType,
    expenseCategories,
    investmentCategories
  ).filter((opt) => !usedTargetIds.has(opt.id));

  const canCreate =
    !isLoading &&
    draft.targetId &&
    Number(draft.allocationValue) > 0 &&
    (!draft.isSavingsGoal || Number(draft.goalTargetAmount) > 0);

  const submitAdd = () => {
    if (!canCreate) return;
    void onAdd(draft);
    setDraft({
      targetType: draft.targetType,
      targetId: "",
      allocationMode: "amount",
      allocationValue: "",
      recurrenceType: "regular",
      isSavingsGoal: false,
      goalTargetAmount: "",
      goalDueMonth: nextPlanningMonth(),
      comment: ""
    });
  };

  return (
    <>
      <div className="planningCard">
      <div className="sectionHead compact">
        <h3>Добавить распределение</h3>
      </div>

      <div className="planningChipRow">
        <button
          className={`planningChip ${draft.targetType === "expense_category" ? "selected" : ""}`}
          type="button"
          onClick={() =>
            setDraft((d) => ({
              ...d,
              targetType: "expense_category",
              targetId: "",
              isSavingsGoal: false
            }))
          }
        >
          Расходы
        </button>
        <button
          className={`planningChip ${draft.targetType === "investment_asset_category" ? "selected" : ""}`}
          type="button"
          onClick={() =>
            setDraft((d) => ({
              ...d,
              targetType: "investment_asset_category",
              targetId: ""
            }))
          }
        >
          Инвестиции
        </button>
      </div>

      {targetOptions.length > 0 ? (
        <label className="field">
          <span>
            {draft.targetType === "expense_category"
              ? "Категория расходов"
              : "Категория инвестиций"}
          </span>
          <select
            value={draft.targetId}
            onChange={(e) => setDraft((d) => ({ ...d, targetId: e.target.value }))}
          >
            <option value="">Выберите</option>
            {targetOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.title}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className="scopeCopy">Целей этого типа пока нет.</p>
      )}

      <div className="planningChipRow">
        <button
          className={`planningChip ${draft.recurrenceType === "regular" ? "selected" : ""}`}
          type="button"
          onClick={() => setDraft((d) => ({ ...d, recurrenceType: "regular" }))}
        >
          Регулярная
        </button>
        <button
          className={`planningChip ${draft.recurrenceType === "one_off" ? "selected" : ""}`}
          type="button"
          onClick={() => setDraft((d) => ({ ...d, recurrenceType: "one_off" }))}
        >
          Разовая
        </button>
      </div>

      <div className="planningChipRow">
        <button
          className={`planningChip ${draft.allocationMode === "amount" ? "selected" : ""}`}
          type="button"
          onClick={() => setDraft((d) => ({ ...d, allocationMode: "amount" }))}
        >
          Сумма
        </button>
        <button
          className={`planningChip ${draft.allocationMode === "percent" ? "selected" : ""}`}
          type="button"
          onClick={() => setDraft((d) => ({ ...d, allocationMode: "percent" }))}
        >
          Процент
        </button>
      </div>

      <label className="field">
        <span>{draft.allocationMode === "percent" ? "Процент" : "Сумма"}</span>
        <input
          type="number"
          inputMode="decimal"
          value={draft.allocationValue}
          onChange={(e) => setDraft((d) => ({ ...d, allocationValue: e.target.value }))}
        />
      </label>

      {draft.targetType === "investment_asset_category" && (
        <label className="paymentToggle prominent">
          <input
            checked={draft.isSavingsGoal}
            type="checkbox"
            onChange={(e) =>
              setDraft((d) => ({
                ...d,
                isSavingsGoal: e.target.checked,
                goalDueMonth: e.target.checked ? nextPlanningMonth() : d.goalDueMonth
              }))
            }
          />
          <span>Цель накопления</span>
        </label>
      )}

      {draft.isSavingsGoal && draft.targetType === "investment_asset_category" && (
        <>
          <label className="field">
            <span>Целевая сумма</span>
            <input
              type="number"
              inputMode="decimal"
              value={draft.goalTargetAmount}
              onChange={(e) => setDraft((d) => ({ ...d, goalTargetAmount: e.target.value }))}
            />
          </label>
          <label className="field">
            <span>Срок цели</span>
            <select
              value={draft.goalDueMonth}
              onChange={(e) => setDraft((d) => ({ ...d, goalDueMonth: e.target.value }))}
            >
              {goalMonthChoices.map((c) => (
                <option key={c.month} value={c.month}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
        </>
      )}

      <label className="field">
        <span>Комментарий</span>
        <input
          value={draft.comment}
          onChange={(e) => setDraft((d) => ({ ...d, comment: e.target.value }))}
        />
      </label>

      <button
        className="submitButton"
        type="button"
        disabled={!canCreate}
        onClick={submitAdd}
      >
        <Plus size={18} aria-hidden="true" />
        Добавить распределение
      </button>
      </div>

      <div className="planningCard">
      <div className="sectionHead compact">
        <h3>Распределения</h3>
      </div>
      {plan.allocations.length === 0 ? (
        <p className="scopeCopy">Распределений пока нет</p>
      ) : (
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          {plan.allocations.map((allocation) => (
            <PlanningAllocationRow
              key={allocation.id}
              allocation={allocation}
              currency={currency}
              expenseCategories={expenseCategories}
              investmentCategories={investmentCategories}
              isLoading={isLoading}
              goalMonthChoices={goalMonthChoices}
              onUpdate={onUpdate}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
      </div>
    </>
  );
}

function PlanningAllocationRow({
  allocation,
  currency,
  expenseCategories,
  investmentCategories,
  isLoading,
  goalMonthChoices,
  onUpdate,
  onDelete
}: {
  allocation: PlanningAllocation;
  currency: string;
  expenseCategories: CategorySummary[];
  investmentCategories: AssetCategory[];
  isLoading: boolean;
  goalMonthChoices: Array<{ month: string; title: string }>;
  onUpdate: (allocationId: string, draft: AllocationDraft, version?: number) => Promise<void>;
  onDelete: (allocationId: string) => Promise<void>;
}) {
  const [isEditing, setEditing] = useState(false);
  const targetOptions = planningTargetOptions(
    allocation.targetType,
    expenseCategories,
    investmentCategories
  );
  const targetName =
    targetOptions.find((o) => o.id === allocation.targetId)?.title ??
    localizedTargetType(allocation.targetType);
  const isInvestmentAllocation = allocation.targetType === "investment_asset_category";

  const [draft, setDraft] = useState<AllocationDraft>({
    targetType: allocation.targetType,
    targetId: allocation.targetId ?? "",
    allocationMode: allocation.allocationMode,
    allocationValue: String(allocation.allocationValue),
    recurrenceType: allocation.recurrenceType ?? "regular",
    isSavingsGoal: allocation.isSavingsGoal,
    goalTargetAmount: allocation.goalTargetAmount ? String(allocation.goalTargetAmount.value) : "",
    goalDueMonth: allocation.goalDueMonth ?? nextPlanningMonth(),
    comment: allocation.comment ?? ""
  });

  const save = () => {
    if (!Number(draft.allocationValue) || Number(draft.allocationValue) <= 0) return;
    void onUpdate(allocation.id, draft, allocation.version);
    setEditing(false);
  };

  return (
    <div className="planningRow">
      <div className="planningRowHead">
        <div>
          <strong className="planningRowTitle">
            {targetName}
          </strong>
          <span>
            {localizedTargetType(allocation.targetType)} ·{" "}
            {localizedRecurrenceType(allocation.recurrenceType ?? "regular")} ·{" "}
            {allocation.allocationMode === "percent"
              ? `${localizedAllocationMode(allocation.allocationMode)}: ${allocation.allocationValue} = ${formatMoney(allocation.calculatedAmount)}`
              : formatMoney(allocation.calculatedAmount)}{" "}
          </span>
          {allocation.actualAmount ? (
            <span>
              Факт: {formatMoney(allocation.actualAmount)}
              {allocation.progressPercent ? ` · ${allocation.progressPercent}%` : ""}
            </span>
          ) : (
            <span className="scopeCopy">Факт</span>
          )}
          {allocation.isSavingsGoal && (
            <span>
              Цель:{" "}
              {allocation.goalTargetAmount ? formatMoney(allocation.goalTargetAmount) : "не задана"}{" "}
              к {allocation.goalDueMonth ? monthLabel(allocation.goalDueMonth) : "срок не задан"}
            </span>
          )}
          {allocation.comment && <span>{allocation.comment}</span>}
        </div>
        <button
          className="ghostButton compact"
          type="button"
          onClick={() => setEditing(!isEditing)}
        >
          {isEditing ? "Закрыть" : "Править"}
        </button>
        {isInvestmentAllocation && (
          <span className="planningInvestmentBadge" title="Инвестиции" aria-label="Инвестиции">
            <TrendingUp size={9} aria-hidden="true" />
          </span>
        )}
      </div>
      {allocation.requiresAttention && (
        <div className="planningBanner warning" style={{ marginTop: 6 }}>
          {localizedAttentionReason(allocation)}
        </div>
      )}
      {isEditing && (
        <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
          <div className="planningChipRow">
            <button
              className={`planningChip ${draft.targetType === "expense_category" ? "selected" : ""}`}
              type="button"
              onClick={() =>
                setDraft((d) => ({
                  ...d,
                  targetType: "expense_category",
                  targetId: "",
                  isSavingsGoal: false
                }))
              }
            >
              Расходы
            </button>
            <button
              className={`planningChip ${draft.targetType === "investment_asset_category" ? "selected" : ""}`}
              type="button"
              onClick={() =>
                setDraft((d) => ({ ...d, targetType: "investment_asset_category", targetId: "" }))
              }
            >
              Инвестиции
            </button>
          </div>
          <label className="field">
            <span>Цель</span>
            <select
              value={draft.targetId}
              onChange={(e) => setDraft((d) => ({ ...d, targetId: e.target.value }))}
            >
              <option value="">Выберите</option>
              {planningTargetOptions(draft.targetType, expenseCategories, investmentCategories).map(
                (opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.title}
                  </option>
                )
              )}
            </select>
          </label>
          <div className="planningChipRow">
            <button
              className={`planningChip ${draft.allocationMode === "amount" ? "selected" : ""}`}
              type="button"
              onClick={() => setDraft((d) => ({ ...d, allocationMode: "amount" }))}
            >
              Сумма
            </button>
            <button
              className={`planningChip ${draft.allocationMode === "percent" ? "selected" : ""}`}
              type="button"
              onClick={() => setDraft((d) => ({ ...d, allocationMode: "percent" }))}
            >
              Процент
            </button>
          </div>
          <label className="field">
            <span>{draft.allocationMode === "percent" ? "Процент" : "Сумма"}</span>
            <input
              type="number"
              inputMode="decimal"
              value={draft.allocationValue}
              onChange={(e) => setDraft((d) => ({ ...d, allocationValue: e.target.value }))}
            />
          </label>
          {draft.targetType === "investment_asset_category" && (
            <>
              <label className="paymentToggle prominent">
                <input
                  checked={draft.isSavingsGoal}
                  type="checkbox"
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, isSavingsGoal: e.target.checked }))
                  }
                />
                <span>Цель накопления</span>
              </label>
              {draft.isSavingsGoal && (
                <>
                  <label className="field">
                    <span>Целевая сумма</span>
                    <input
                      type="number"
                      inputMode="decimal"
                      value={draft.goalTargetAmount}
                      onChange={(e) =>
                        setDraft((d) => ({ ...d, goalTargetAmount: e.target.value }))
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Срок</span>
                    <select
                      value={draft.goalDueMonth}
                      onChange={(e) =>
                        setDraft((d) => ({ ...d, goalDueMonth: e.target.value }))
                      }
                    >
                      {goalMonthChoices.map((c) => (
                        <option key={c.month} value={c.month}>
                          {c.title}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              )}
            </>
          )}
          <div className="planningRowActions">
            <button
              className="ghostButton"
              type="button"
              disabled={isLoading}
              onClick={() => void onDelete(allocation.id)}
            >
              <Trash2 size={14} />
              Удалить
            </button>
            <button
              className="submitButton"
              type="button"
              disabled={isLoading || !Number(draft.allocationValue)}
              onClick={save}
            >
              <Check size={16} />
              Сохранить
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanningHistoryCard({
  history,
  currentMonth,
  isLoading,
  onCopy
}: {
  history: PlanningPlan[];
  currentMonth: string;
  isLoading: boolean;
  onCopy: (plan: PlanningPlan) => Promise<void>;
}) {
  const pastPlans = history.filter((p) => p.month !== currentMonth).slice(0, 6);

  return (
    <div className="planningCard">
      <div className="sectionHead compact">
        <h3>История</h3>
      </div>
      {pastPlans.length === 0 ? (
        <p className="scopeCopy">Истории планов пока нет</p>
      ) : (
        <div>
          {pastPlans.map((p) => (
            <div key={p.id} className="planningHistoryRow">
              <div>
                <strong>{monthLabel(p.month)}</strong>
                <span>
                  {p.scope === "household" ? "Общее" : "Личное"} · {p.currency}
                </span>
              </div>
              <button
                className="ghostButton compact"
                type="button"
                disabled={isLoading}
                onClick={() => void onCopy(p)}
              >
                <Copy size={14} />
                Копировать
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PlanningMiniCard({
  client,
  viewMode,
  householdId,
  onOpen
}: {
  client: FinanceApiClient;
  viewMode: ViewMode;
  householdId: string | null;
  onOpen: () => void;
}) {
  const scopeInfo = planningScopeInfo(viewMode, householdId);
  const [plan, setPlan] = useState<PlanningPlan | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!scopeInfo) {
      setLoaded(true);
      return;
    }
    let mounted = true;
    void client
      .listPlanningPlans(scopeInfo.scope, currentMonthValue(), scopeInfo.householdId)
      .then((p) => {
        if (mounted) setPlan(p);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted) setLoaded(true);
      });
    return () => {
      mounted = false;
    };
  }, [client, scopeInfo]);

  if (!scopeInfo || !loaded) return null;

  return (
    <div
      className="planningMiniCard"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onOpen();
      }}
    >
      <div>
        <strong>
          <Target size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
          План месяца
        </strong>
        {plan ? (
          <span>
            Доход: {formatMoney(plan.totalPlannedIncome)} · Распределено:{" "}
            {formatMoney(plan.allocatedTotal)} · Осталось: {formatMoney(plan.remainingAmount)}
          </span>
        ) : (
          <span>План на текущий месяц не создан</span>
        )}
      </div>
      <button className="ghostButton compact" type="button">
        Открыть
      </button>
    </div>
  );
}

function SettingsPage({
  viewMode,
  onViewModeChange
}: {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
}) {
  return (
    <section className="screenStack" aria-labelledby="settings-title">
      <div className="sectionHead">
        <h3 id="settings-title">Настройки</h3>
      </div>
      <div className="settingsList">
        <div className="settingRow">
          <div>
            <strong>Режим по умолчанию</strong>
            <span>Личное остается приватным</span>
          </div>
          <ViewSwitch value={viewMode} onChange={onViewModeChange} />
        </div>
        <div className="settingRow">
          <div>
            <strong>Валюта</strong>
            <span>Берется из первого счета</span>
          </div>
          <b>Авто</b>
        </div>
      </div>
    </section>
  );
}

function QuickAdd({
  allAccounts,
  canUseShared,
  categories,
  defaultVisibility,
  onClose,
  onSubmit,
  saveStatus
}: {
  allAccounts: AccountSummary[];
  canUseShared: boolean;
  categories: CategorySummary[];
  defaultVisibility: DraftVisibilityMode;
  onClose: () => void;
  onSubmit: (input: QuickAddInput) => Promise<void>;
  saveStatus: string;
}) {
  const [kind, setKind] = useState<QuickKind>("expense");
  const [amount, setAmount] = useState("");
  const [accountId, setAccountId] = useState("");
  const [toAccountId, setToAccountId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [assetKind, setAssetKind] = useState<AccountKind>("card");
  const [isPaymentAccountChecked, setPaymentAccountChecked] = useState(true);
  const [date, setDate] = useState(todayInputValue());
  const [comment, setComment] = useState("");
  const [visibility, setVisibility] = useState<DraftVisibilityMode>(defaultVisibility);
  const [isSaving, setSaving] = useState(false);

  const writableAccounts = allAccounts.filter(
    (account) =>
      visibility &&
      account.status !== "deleted" &&
      account.status !== "archived" &&
      accountOwnership(account) === visibility
  );
  const operationAccounts = kind === "expense" ? writableAccounts.filter(isPaymentAccount) : writableAccounts;
  const sourceAccount = writableAccounts.find((account) => account.id === accountId);
  const transferTargets = writableAccounts.filter(
    (account) =>
      account.id !== accountId &&
      Boolean(sourceAccount) &&
      account.balance.currency === sourceAccount?.balance.currency
  );
  const accountOptions = kind === "transfer" ? writableAccounts : operationAccounts;
  const selectedTransferTarget = transferTargets.find((account) => account.id === toAccountId);

  const filteredCategories = categories.filter((category) => {
    if (category.status === "deleted" || category.status === "archived") {
      return false;
    }
    if (!visibility || categoryScopeVisibility(category) !== visibility) {
      return false;
    }
    if (kind === "income") {
      return category.direction === "income";
    }
    if (kind === "expense") {
      return category.direction === "expense";
    }
    return false;
  });
  const selectedCategory = filteredCategories.find((category) => category.id === categoryId);

  useEffect(() => {
    if (categoryId && !selectedCategory) {
      setCategoryId("");
    }
  }, [categoryId, selectedCategory]);

  useEffect(() => {
    if (
      kind !== "asset" &&
      accountId &&
      !operationAccounts.some((account) => account.id === accountId)
    ) {
      setAccountId("");
      setToAccountId("");
    }
  }, [accountId, kind, operationAccounts]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedAmount = Number(amount);
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      return;
    }
    if (!visibility) {
      return;
    }
    if ((kind === "expense" || kind === "income") && !selectedCategory) {
      return;
    }

    setSaving(true);
    try {
      await onSubmit({
        kind,
        amount: parsedAmount,
        accountId,
        toAccountId,
        categoryId: selectedCategory?.id ?? "",
        assetKind,
        isPaymentAccount: isPaymentAccountChecked,
        date,
        comment,
        visibility
      });
    } finally {
      setSaving(false);
    }
  };

  const hasAmount = amount.trim() !== "" && Number(amount) > 0;
  const hasVisibility = visibility === "personal" || visibility === "shared";
  const isSharedBlocked = visibility === "shared" && !canUseShared;
  const transferNeedsCompatibleTarget =
    kind === "transfer" && Boolean(accountId) && transferTargets.length === 0;
  const hasValidOperationCategory =
    (kind !== "expense" && kind !== "income") || Boolean(selectedCategory);
  const canSubmit =
    hasAmount &&
    hasVisibility &&
    !isSharedBlocked &&
    hasValidOperationCategory &&
      (kind === "asset" ||
      (kind === "transfer"
        ? Boolean(accountId) && Boolean(selectedTransferTarget) && !transferNeedsCompatibleTarget
        : Boolean(accountId)));

  return (
    <div className="modalLayer" role="presentation">
      <form className="quickSheet" aria-label="Быстро добавить" onSubmit={submit}>
        <div className="sheetHead">
          <h3>Добавить</h3>
          <button type="button" aria-label="Закрыть" onClick={onClose}>
            <X size={19} aria-hidden="true" />
          </button>
        </div>

        <div className="kindGrid" role="group" aria-label="Тип записи">
          <ChoiceButton active={kind === "expense"} onClick={() => setKind("expense")}>
            <ArrowUpRight size={17} aria-hidden="true" />
            Расход
          </ChoiceButton>
          <ChoiceButton active={kind === "income"} onClick={() => setKind("income")}>
            <ArrowDownLeft size={17} aria-hidden="true" />
            Доход
          </ChoiceButton>
          <ChoiceButton active={kind === "transfer"} onClick={() => setKind("transfer")}>
            <ArrowLeftRight size={17} aria-hidden="true" />
            Перевод
          </ChoiceButton>
          <ChoiceButton active={kind === "asset"} onClick={() => setKind("asset")}>
            <Landmark size={17} aria-hidden="true" />
            Актив
          </ChoiceButton>
        </div>

        <label className="field">
          <span>Сумма</span>
          <input
            min="0"
            inputMode="decimal"
            type="number"
            placeholder="Введите сумму"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>

        <fieldset className="visibilityGroup prominent">
          <legend>Куда сохранить</legend>
          <label>
            <input
              checked={visibility === "personal"}
              name="visibility"
              type="radio"
              onChange={() => {
                setVisibility("personal");
                setAccountId("");
                setToAccountId("");
                setCategoryId("");
              }}
            />
            Личное
          </label>
          <label>
            <input
              checked={visibility === "shared"}
              disabled={!canUseShared}
              name="visibility"
              type="radio"
              onChange={() => {
                setVisibility("shared");
                setAccountId("");
                setToAccountId("");
                setCategoryId("");
              }}
            />
            Общее
          </label>
        </fieldset>
        {!visibility && (
          <p className="formError">Обзор только читает данные. Выберите личное или общее для записи.</p>
        )}
        {isSharedBlocked && (
          <p className="formError">Для общего режима нужен семейный доступ.</p>
        )}

        {kind === "asset" ? (
          <div className="assetCreateFields">
          <label className="field">
            <span>Тип</span>
            <select
              value={assetKind}
              onChange={(event) => setAssetKind(event.target.value as AccountKind)}
            >
              {Object.entries(accountKindLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            </label>
            <label className="paymentToggle prominent">
              <input
                checked={isPaymentAccountChecked}
                type="checkbox"
                onChange={(event) => setPaymentAccountChecked(event.target.checked)}
              />
              <span>Счёт для оплаты</span>
            </label>
          </div>
        ) : (
          <label className="field">
            <span>{kind === "transfer" ? "Откуда" : "Счет"}</span>
            <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
              <option value="">Выберите счет</option>
              {accountOptions.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {hasVisibility && kind !== "asset" && accountOptions.length === 0 && (
          <EmptyState text="В выбранном scope нет счета для записи. Сначала добавьте актив или выберите другой scope." />
        )}

        {kind === "transfer" && (
          <label className="field">
            <span>Куда</span>
            <select value={toAccountId} onChange={(event) => setToAccountId(event.target.value)}>
              <option value="">Выберите совместимый счет</option>
              {transferTargets.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {transferNeedsCompatibleTarget && (
          <p className="formError">
            Для перевода нужны два счета одного scope и валюты. Создайте совместимый счет или выберите другой.
          </p>
        )}

        {(kind === "expense" || kind === "income") && (
          <label className="field">
            <span>Категория</span>
            <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
              <option value="">Без категории</option>
              {filteredCategories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
        )}

        <details className="moreFields">
          <summary data-testid="quick-add-more">Еще</summary>
          <label className="field">
            <span>Дата</span>
            <input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Комментарий</span>
            <input value={comment} onChange={(event) => setComment(event.target.value)} />
          </label>
        </details>

        {!hasAmount && <p className="formError">Введите сумму вручную: опасные значения по умолчанию отключены.</p>}

        <button
          className="submitButton"
          type="submit"
          disabled={isSaving || !canSubmit}
          data-testid="quick-add-submit"
        >
          <Check size={18} aria-hidden="true" />
          {isSaving ? "Сохраняем" : saveStatus || "Готово"}
        </button>
      </form>
    </div>
  );
}

function ChoiceButton({
  active,
  children,
  onClick
}: {
  active: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className={active ? "selected" : ""} type="button" onClick={onClick}>
      {children}
    </button>
  );
}

function AssetTile({
  account,
  isUpdating,
  onPaymentAccountChange,
  onEdit,
  onArchive
}: {
  account: AccountSummary;
  isUpdating: boolean;
  onPaymentAccountChange: (account: AccountSummary, isPaymentAccount: boolean) => Promise<void>;
  onEdit?: () => void;
  onArchive?: () => Promise<void>;
}) {
  const Icon = accountKindIcons[account.kind];

  return (
    <article className="assetTile">
      <div className="tileIcon" aria-hidden="true">
        <Icon size={20} />
      </div>
      <div>
        <strong>{account.name}</strong>
        <span>
          {accountKindLabels[account.kind]} · {account.ownerName}
        </span>
        <ScopeBadge mode={accountOwnership(account)} />
        <label className="paymentToggle">
          <input
            checked={account.isPaymentAccount !== false}
            disabled={isUpdating}
            type="checkbox"
            onChange={(event) => {
              void onPaymentAccountChange(account, event.target.checked);
            }}
          />
          <span>Счёт для оплаты</span>
        </label>
        {(onEdit || onArchive) && (
          <div className="tileActionRow">
            {onEdit && (
              <button className="tileAction" type="button" onClick={onEdit}>
                <Pencil size={14} />
                <span>Изменить</span>
              </button>
            )}
            {onArchive && (
              <button
                className="tileAction"
                type="button"
                onClick={() => void onArchive()}
              >
                <Archive size={14} />
                <span>Архив</span>
              </button>
            )}
          </div>
        )}
      </div>
      <b>{formatMoney(account.balance)}</b>
    </article>
  );
}

function CategoryTile({
  category,
  index,
  onEdit,
  onArchive
}: {
  category: CategorySummary;
  index: number;
  onEdit: () => void;
  onArchive?: () => Promise<void>;
}) {
  const Icon = category.direction === "income" ? CircleDollarSign : ShoppingCart;
  const color = category.color || categoryPalette[index % categoryPalette.length];

  return (
    <article className="categoryTile">
      <div className="categoryIcon" style={{ backgroundColor: color }} aria-hidden="true">
        <Icon size={18} />
      </div>
      <div>
        <strong>{shortCategoryName(category.name)}</strong>
        <span>
          {category.direction === "income" ? "Доход" : "Расход"} ·{" "}
          {category.scope === "household" ? "Общее" : "Личное"}
        </span>
        <ScopeBadge mode={categoryScopeVisibility(category)} />
      </div>
      <div className="categoryTileActions">
        <button className="tileAction" type="button" onClick={onEdit}>
          Изменить
        </button>
        {onArchive && (
          <button
            className="tileAction"
            type="button"
            onClick={() => void onArchive()}
            title="Архивировать"
          >
            <Archive size={14} />
          </button>
        )}
      </div>
    </article>
  );
}

function AssetGroupRow({
  group
}: {
  group: { kind: AccountKind; total: MoneyAmount; count: number };
}) {
  const Icon = accountKindIcons[group.kind];

  return (
    <div className="listRow">
      <div className="rowIcon" aria-hidden="true">
        <Icon size={18} />
      </div>
      <div>
        <strong>{accountKindLabels[group.kind]}</strong>
        <span>{group.count} шт.</span>
      </div>
      <b>{formatMoney(group.total)}</b>
    </div>
  );
}

function CategoryTotalRow({
  category
}: {
  category: { name: string; amount: MoneyAmount; color: string };
}) {
  return (
    <div className="listRow">
      <span className="colorDot" style={{ backgroundColor: category.color }} />
      <div>
        <strong>{shortCategoryName(category.name)}</strong>
        <span>Расходы</span>
      </div>
      <b>{formatMoney(category.amount)}</b>
    </div>
  );
}

function BarRow({
  label,
  amount
}: {
  label: string;
  amount: MoneyAmount;
}) {
  return (
    <div className="barRow">
      <span>{label}</span>
      <strong>{formatMoney(amount)}</strong>
    </div>
  );
}

type TimelineItem =
  | {
      type: "operation";
      id: string;
      date: string;
      title: string;
      subtitle: string;
      amount: MoneyAmount;
    }
  | {
      type: "transfer";
      id: string;
      date: string;
      title: string;
      subtitle: string;
      amount: MoneyAmount;
    };

function TimelineList({
  emptyText = "Записей пока нет",
  items
}: {
  emptyText?: string;
  items: TimelineItem[];
}) {
  return (
    <div className="listStack">
      {items.map((item) => {
        const isTransfer = item.type === "transfer";
        const isExpense = item.amount.value < 0;
        const Icon = isTransfer ? ArrowLeftRight : isExpense ? ArrowUpRight : ArrowDownLeft;

        return (
          <article className="operationRow" key={`${item.type}-${item.id}`}>
            <div className="rowIcon" aria-hidden="true">
              <Icon size={18} />
            </div>
            <div>
              <strong>{item.title}</strong>
              <span>{item.subtitle}</span>
            </div>
            <b className={isTransfer ? "neutral" : isExpense ? "negative" : "positive"}>
              {isTransfer ? formatMoney(item.amount) : formatMoney(item.amount)}
            </b>
          </article>
        );
      })}
      {items.length === 0 && <EmptyState text={emptyText} />}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="emptyState">{text}</div>;
}

function AssetCategoryForm({
  category,
  householdId,
  onCancel,
  onSave
}: {
  category: AssetCategory | null;
  householdId: string | null;
  onCancel: () => void;
  onSave: (input: AssetCategoryFormInput) => Promise<void>;
}) {
  const [name, setName] = useState(category?.name ?? "");
  const [scopeType, setScopeType] = useState<AssetCategoryScope>(
    category?.scopeType ?? "personal"
  );
  const [currency, setCurrency] = useState<CurrencyCode>(category?.currency ?? "RUB");
  const [manualAmount, setManualAmount] = useState(
    String(category?.manualAmount?.value ?? 0)
  );
  const [isInvestment, setIsInvestment] = useState(category?.isInvestment ?? false);
  const [assetType, setAssetType] = useState<AssetCategoryType>(
    category?.assetType ?? "cash"
  );
  const [iconKey, setIconKey] = useState(category?.iconKey ?? "wallet");
  const [status, setStatus] = useState("");
  const [isSaving, setSaving] = useState(false);

  useEffect(() => {
    setName(category?.name ?? "");
    setScopeType(category?.scopeType ?? "personal");
    setCurrency(category?.currency ?? "RUB");
    setManualAmount(String(category?.manualAmount?.value ?? 0));
    setIsInvestment(category?.isInvestment ?? false);
    setAssetType(category?.assetType ?? "cash");
    setIconKey(category?.iconKey ?? "wallet");
    setStatus("");
  }, [category]);

  const isHouseholdBlocked = scopeType === "household" && !householdId;
  const canSubmit = Boolean(name.trim()) && !isHouseholdBlocked && !isSaving;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setStatus("");
    try {
      await onSave({
        assetCategoryId: category?.id,
        name,
        scopeType,
        currency,
        manualAmount: Number(manualAmount) || 0,
        isInvestment,
        assetType,
        iconKey,
        version: category?.version
      });
      setStatus(category ? "Категория обновлена" : "Категория создана");
    } catch {
      setStatus("Не удалось сохранить категорию активов");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="categoryForm" aria-label="Категория активов" onSubmit={submit}>
      <div className="sectionHead compact">
        <h3>{category ? "Редактировать категорию" : "Новая категория актива"}</h3>
        <button className="ghostButton" type="button" onClick={onCancel}>
          <X size={17} aria-hidden="true" />
          Отмена
        </button>
      </div>
      <div className="categoryFormGrid">
        <label className="field">
          <span>Название</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span>Доступ</span>
          <select
            value={scopeType}
            disabled={Boolean(category)}
            onChange={(e) => setScopeType(e.target.value as AssetCategoryScope)}
          >
            <option value="personal">Личное</option>
            <option value="household">Общее</option>
          </select>
        </label>
        <label className="field">
          <span>Валюта</span>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value as CurrencyCode)}
          >
            {currencyOptions.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Тип актива</span>
          <select
            value={assetType}
            onChange={(e) => setAssetType(e.target.value as AssetCategoryType)}
          >
            {Object.entries(accountKindLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Иконка</span>
          <select value={iconKey} onChange={(e) => setIconKey(e.target.value)}>
            {assetCategoryIconOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="categoryFormGrid">
        <label className="field">
          <span>Ручная сумма</span>
          <input
            type="number"
            inputMode="decimal"
            value={manualAmount}
            onChange={(e) => setManualAmount(e.target.value)}
          />
        </label>
        <label className="paymentToggle prominent">
          <input
            checked={isInvestment}
            type="checkbox"
            onChange={(e) => setIsInvestment(e.target.checked)}
          />
          <span>Инвестиция</span>
        </label>
      </div>
      {isHouseholdBlocked && (
        <p className="formError">Для общей категории нужен семейный доступ.</p>
      )}
      {status && (
        <p className={status.startsWith("Не") ? "formError" : "formHint"}>
          {status}
        </p>
      )}
      <button className="submitButton categorySubmit" type="submit" disabled={!canSubmit}>
        <Check size={18} aria-hidden="true" />
        {isSaving ? "Сохраняем" : category ? "Сохранить" : "Создать"}
      </button>
    </form>
  );
}

function AccountEditModal({
  account,
  assetCategories,
  onCancel,
  onSave
}: {
  account: AccountSummary;
  assetCategories: AssetCategory[];
  onCancel: () => void;
  onSave: (input: AccountEditFormInput) => Promise<void>;
}) {
  const [name, setName] = useState(account.name);
  const [balance, setBalance] = useState(String(account.balance.value));
  const [currency, setCurrency] = useState<CurrencyCode>(account.balance.currency);
  const [assetCategoryId, setAssetCategoryId] = useState(account.assetCategoryId ?? "");
  const [isPaymentAccount, setIsPaymentAccount] = useState(account.isPaymentAccount !== false);
  const [isSaving, setSaving] = useState(false);
  const [status, setStatus] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedBalance = Number(balance);
    if (!Number.isFinite(parsedBalance)) return;
    setSaving(true);
    setStatus("");
    try {
      await onSave({
        accountId: account.id,
        name,
        balance: parsedBalance,
        currency,
        assetCategoryId,
        isPaymentAccount,
        version: account.version
      });
    } catch {
      setStatus("Не удалось сохранить счет");
      setSaving(false);
    }
  };

  return (
    <div className="modalLayer" role="presentation">
      <form className="quickSheet" aria-label="Редактировать счет" onSubmit={submit}>
        <div className="sheetHead">
          <h3>Редактировать счет</h3>
          <button type="button" onClick={onCancel}>
            <X size={19} aria-hidden="true" />
          </button>
        </div>
        <label className="field">
          <span>Название</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span>Баланс</span>
          <input
            type="number"
            inputMode="decimal"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Валюта</span>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value as CurrencyCode)}
          >
            {currencyOptions.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Категория активов</span>
          <select
            value={assetCategoryId}
            onChange={(e) => setAssetCategoryId(e.target.value)}
          >
            <option value="">Без категории</option>
            {assetCategories.map((cat) => (
              <option key={cat.id} value={cat.id}>{cat.name}</option>
            ))}
          </select>
        </label>
        <label className="paymentToggle prominent">
          <input
            checked={isPaymentAccount}
            type="checkbox"
            onChange={(e) => setIsPaymentAccount(e.target.checked)}
          />
          <span>Счёт для оплаты</span>
        </label>
        {status && <p className="formError">{status}</p>}
        <button className="submitButton" type="submit" disabled={isSaving}>
          <Check size={18} aria-hidden="true" />
          {isSaving ? "Сохраняем" : "Сохранить"}
        </button>
      </form>
    </div>
  );
}

function OperationEditModal({
  operation,
  accounts,
  categories,
  onCancel,
  onSave
}: {
  operation: OperationSummary;
  accounts: AccountSummary[];
  categories: CategorySummary[];
  onCancel: () => void;
  onSave: (input: OperationEditFormInput) => Promise<void>;
}) {
  const [amount, setAmount] = useState(String(Math.abs(operation.amount.value)));
  const [description, setDescription] = useState(operation.title);
  const [categoryId, setCategoryId] = useState(operation.categoryId ?? "");
  const [accountId, setAccountId] = useState(operation.accountId);
  const [occurredDate, setOccurredDate] = useState(dateInputValue(operation.date));
  const [isSaving, setSaving] = useState(false);
  const [status, setStatus] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedAmount = Number(amount);
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) return;
    setSaving(true);
    setStatus("");
    try {
      await onSave({
        operationId: operation.id,
        amount: operation.amount.value < 0 ? -parsedAmount : parsedAmount,
        description,
        categoryId,
        accountId,
        occurredDate,
        version: operation.version
      });
    } catch {
      setStatus("Не удалось сохранить операцию");
      setSaving(false);
    }
  };

  return (
    <div className="modalLayer" role="presentation">
      <form className="quickSheet" aria-label="Редактировать операцию" onSubmit={submit}>
        <div className="sheetHead">
          <h3>Редактировать операцию</h3>
          <button type="button" onClick={onCancel}>
            <X size={19} aria-hidden="true" />
          </button>
        </div>
        <label className="field">
          <span>Сумма</span>
          <input
            type="number"
            inputMode="decimal"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Описание</span>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Счет</span>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
          >
            <option value="">Выберите</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Категория</span>
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
          >
            <option value="">Без категории</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Дата</span>
          <input
            type="date"
            value={occurredDate}
            onChange={(e) => setOccurredDate(e.target.value)}
          />
        </label>
        {status && <p className="formError">{status}</p>}
        <button className="submitButton" type="submit" disabled={isSaving}>
          <Check size={18} aria-hidden="true" />
          {isSaving ? "Сохраняем" : "Сохранить"}
        </button>
      </form>
    </div>
  );
}

function accountOwnership(account: AccountSummary): VisibilityMode {
  return account.ownershipType === "shared" ? "shared" : "personal";
}

function categoryScopeVisibility(category: CategorySummary): VisibilityMode {
  return category.scope === "household" ? "shared" : "personal";
}

function isPaymentAccount(account: AccountSummary): boolean {
  return (
    account.status !== "deleted" &&
    account.status !== "archived" &&
    account.isPaymentAccount !== false
  );
}

function scopeLabelForAccount(account: AccountSummary | undefined): string {
  if (!account) {
    return "Личное";
  }

  return accountOwnership(account) === "shared" ? "Общее" : "Личное";
}

function visibleAccounts(accounts: AccountSummary[], mode: ViewMode): AccountSummary[] {
  return accounts.filter((account) => {
    if (account.status === "deleted" || account.status === "archived") {
      return false;
    }

    if (mode === "overview") {
      return true;
    }

    return accountOwnership(account) === mode;
  });
}

function visibleCategories(categories: CategorySummary[], mode: ViewMode): CategorySummary[] {
  return categories.filter((category) => {
    if (category.status === "deleted" || category.status === "archived") {
      return false;
    }

    if (mode === "overview") {
      return true;
    }

    return categoryScopeVisibility(category) === mode;
  });
}

function visibleOperations(
  operations: OperationSummary[],
  accounts: AccountSummary[]
): OperationSummary[] {
  const accountIds = new Set(accounts.map((account) => account.id));
  return operations.filter((operation) => accountIds.has(operation.accountId));
}

function filterOperationsByDateRange(
  operations: OperationSummary[],
  range: { startDate: string; endDate: string }
): OperationSummary[] {
  return operations.filter((operation) => {
    const date = dateInputValue(operation.date);
    return date >= range.startDate && date <= range.endDate;
  });
}

function visibleTransfers(
  transfers: TransferSummary[],
  accounts: AccountSummary[]
): TransferSummary[] {
  const accountIds = new Set(accounts.map((account) => account.id));
  return transfers.filter(
    (transfer) =>
      accountIds.has(transfer.accountId) &&
      (transfer.counterpartyAccountId ? accountIds.has(transfer.counterpartyAccountId) : false)
  );
}

function groupAssets(accounts: AccountSummary[], currency: CurrencyCode) {
  const groups = new Map<AccountKind, { kind: AccountKind; total: MoneyAmount; count: number }>();
  for (const account of accounts) {
    const current =
      groups.get(account.kind) ??
      {
        kind: account.kind,
        total: { value: 0, currency: account.balance.currency || currency },
        count: 0
      };
    current.total.value += account.balance.value;
    current.count += 1;
    groups.set(account.kind, current);
  }

  return [...groups.values()].sort((left, right) => right.total.value - left.total.value);
}

function categoryTotals(
  operations: OperationSummary[],
  categories: CategorySummary[],
  currency: CurrencyCode
) {
  const totals = new Map<string, { name: string; amount: MoneyAmount; color: string }>();
  for (const operation of operations) {
    if (operation.amount.value >= 0) {
      continue;
    }
    const category = categories.find((item) => item.id === operation.categoryId);
    const name = operation.categoryName || category?.name || "Без категории";
    const current =
      totals.get(name) ??
      {
        name,
        amount: { value: 0, currency: operation.amount.currency || currency },
        color: category?.color || categoryPalette[totals.size % categoryPalette.length]
      };
    current.amount.value += Math.abs(operation.amount.value);
    totals.set(name, current);
  }

  return [...totals.values()].sort((left, right) => right.amount.value - left.amount.value);
}

function recentTimeline(
  operations: OperationSummary[],
  transfers: TransferSummary[],
  accounts: AccountSummary[]
): TimelineItem[] {
  const accountById = new Map(accounts.map((account) => [account.id, account]));
  const operationItems: TimelineItem[] = operations.map((operation) => ({
    type: "operation",
    id: operation.id,
    date: operation.date,
    title: operation.title,
    subtitle: `${formatDate(operation.date)} · ${scopeLabelForAccount(accountById.get(operation.accountId))} · ${operation.categoryName} · ${operation.accountName}`,
    amount: operation.amount
  }));
  const transferItems: TimelineItem[] = transfers.map((transfer) => ({
    type: "transfer",
    id: transfer.id,
    date: transfer.date,
    title: "Перевод между счетами",
    subtitle: `${formatDate(transfer.date)} · ${scopeLabelForAccount(accountById.get(transfer.accountId))} · ${transfer.fromAccountName} → ${transfer.toAccountName}`,
    amount: transfer.amount
  }));

  return [...operationItems, ...transferItems].sort(
    (left, right) => new Date(left.date).getTime() - new Date(right.date).getTime()
  );
}

function sectionTitle(section: SectionId): string {
  const titles: Record<SectionId, string> = {
    analytics: "Аналитика",
    assets: "Счета и активы",
    categories: "Категории",
    money: "Деньги",
    operations: "Операции",
    settings: "Настройки"
  };

  return titles[section];
}

function viewModeDescription(mode: ViewMode): string {
  const descriptions: Record<ViewMode, string> = {
    personal: "Личное видно только вам",
    shared: "Общее для семьи",
    overview: "Мой обзор: личное + общее, без личных данных других участников"
  };

  return descriptions[mode];
}

function scopeDescription(mode: ViewMode): string {
  const descriptions: Record<ViewMode, string> = {
    personal: "Scope: личное. Записи и счета видны только вам.",
    shared: "Scope: общее. Данные доступны участникам семейного доступа.",
    overview:
      "Scope: мой обзор. Это read-only срез видимого вам личного и общего, без записи в скрытый scope."
  };

  return descriptions[mode];
}

function scopeEmptyText(mode: ViewMode, subject: string, nextAction: string): string {
  const prefix =
    mode === "overview" ? "В моем обзоре" : mode === "shared" ? "В общем scope" : "В личном scope";
  return `${prefix} нет видимых ${subject}. Следующий шаг: ${nextAction}.`;
}

function shortCategoryName(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).join(" ");
}

function reportForView(
  snapshot: DashboardSnapshot,
  mode: ViewMode,
  range?: { startDate: string; endDate: string }
): ReportSummary {
  const currency = snapshot.accounts[0]?.balance.currency ?? "RUB";

  if (mode === "personal") {
    const accounts = visibleAccounts(snapshot.accounts, "personal");
    const visiblePersonalOperations = visibleOperations(snapshot.operations, accounts);
    const operations = range
      ? filterOperationsByDateRange(visiblePersonalOperations, range)
      : visiblePersonalOperations;
    return reportFromOperations("personal", operations, currency, range);
  }

  const reportMode = reportModeByView[mode];
  return snapshot.reports.find((report) => report.mode === reportMode) ?? emptyReport(mode, currency);
}

function reportFromOperations(
  mode: ViewMode,
  operations: OperationSummary[],
  currency: CurrencyCode,
  range?: { startDate: string; endDate: string }
): ReportSummary {
  const totals = operations.reduce(
    (current, operation) => {
      if (operation.amount.value > 0) {
        current.income += operation.amount.value;
      }
      if (operation.amount.value < 0) {
        current.expense += Math.abs(operation.amount.value);
      }
      current.delta += operation.amount.value;
      return current;
    },
    { income: 0, expense: 0, delta: 0 }
  );

  return {
    ...emptyReport(mode, currency),
    periodLabel: range ? `${range.startDate} - ${range.endDate}` : emptyReport(mode, currency).periodLabel,
    income: { value: totals.income, currency },
    expense: { value: totals.expense, currency },
    balanceDelta: { value: totals.delta, currency }
  };
}

function emptyReport(mode: ViewMode, currency: CurrencyCode): ReportSummary {
  const reportMode = mode === "shared" ? reportModeByView.shared : reportModeByView.overview;
  const titles: Record<ViewMode, string> = {
    personal: "Личное",
    shared: "Общее",
    overview: "Обзор"
  };

  return {
    mode: reportMode,
    title: titles[mode],
    periodLabel: "Текущий месяц",
    income: { value: 0, currency },
    expense: { value: 0, currency },
    balanceDelta: { value: 0, currency }
  };
}
