import {
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Check,
  CircleDollarSign,
  CreditCard,
  Landmark,
  Layers3,
  LineChart,
  Lock,
  LogOut,
  Plus,
  ReceiptText,
  Settings,
  Shield,
  ShoppingCart,
  Tag,
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
  CaptureDraftSummary,
  CategoryDirection,
  CategoryScope,
  CategorySummary,
  CurrencyCode,
  DashboardSnapshot,
  MoneyAmount,
  OperationSummary,
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
            snapshot={snapshot}
            report={activeReport}
            viewMode={viewMode}
            onAdd={() => setQuickAddOpen(true)}
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
            monthValue={selectedMonth}
            onMonthChange={setSelectedMonth}
            snapshot={snapshot}
            report={activeReport}
            viewMode={viewMode}
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
  testId
}: {
  active: boolean;
  icon: typeof WalletCards;
  label: string;
  onClick: () => void;
  testId?: string;
}) {
  return (
    <button className={active ? "active" : ""} type="button" onClick={onClick} data-testid={testId}>
      <Icon size={18} aria-hidden="true" />
      <span>{label}</span>
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
  snapshot,
  report,
  viewMode,
  onAdd
}: {
  snapshot: DashboardSnapshot;
  report: ReportSummary;
  viewMode: ViewMode;
  onAdd: () => void;
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
  const paymentAccounts = accounts.filter(isPaymentAccount);
  const expenseCategories = categories.filter(
    (category) => category.direction === "expense"
  );
  const [draftsRefreshKey, setDraftsRefreshKey] = useState(0);

  const refreshAfterDraftChange = useCallback(async () => {
    const nextSnapshot = await onCaptureDraftsSaved();
    setDraftsRefreshKey((current) => current + 1);
    return nextSnapshot;
  }, [onCaptureDraftsSaved]);

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
      <TimelineList
        emptyText={scopeEmptyText(viewMode, "операций", "добавьте расход, доход или выберите другой scope")}
        items={timeline}
      />
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
  const [updatingAccountId, setUpdatingAccountId] = useState<string | null>(null);
  const [status, setStatus] = useState("");

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

  return (
    <section className="screenStack" aria-labelledby="assets-title">
      <div className="sectionHead">
        <h3 id="assets-title">Счета и активы</h3>
        <span>{accounts.length} активов</span>
      </div>
      <p className="scopeCopy">{scopeDescription(viewMode)}</p>
      {status && <p className={status.startsWith("Не") ? "formError" : "formHint"}>{status}</p>}
      <div className="assetGrid">
        {accounts.map((account) => (
          <AssetTile
            key={account.id}
            account={account}
            isUpdating={updatingAccountId === account.id}
            onPaymentAccountChange={updatePaymentAccount}
          />
        ))}
        {accounts.length === 0 && (
          <EmptyState text={scopeEmptyText(viewMode, "активов", "добавьте актив через Quick Add или переключите режим")} />
        )}
      </div>
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
  const [editingCategory, setEditingCategory] = useState<CategorySummary | null>(null);

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
          />
        ))}
        {categories.length === 0 && (
          <EmptyState text={scopeEmptyText(viewMode, "категорий", "создайте категорию в личном или общем режиме")} />
        )}
      </div>
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
  monthValue,
  onMonthChange,
  snapshot,
  report,
  viewMode
}: {
  monthValue: string;
  onMonthChange: (value: string) => void;
  snapshot: DashboardSnapshot;
  report: ReportSummary;
  viewMode: ViewMode;
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

  return (
    <section className="screenStack" aria-labelledby="analytics-title">
      <div className="sectionHead">
        <h3 id="analytics-title">Аналитика</h3>
        <MonthSwitcher value={monthValue} onChange={onMonthChange} />
      </div>
      <p className="scopeCopy">{scopeDescription(viewMode)}</p>
      <p className="scopeCopy">{analyticsReport.periodLabel}</p>
      <div className="metricGrid three">
        <Metric label="Доходы" value={formatMoney(analyticsReport.income)} tone="success" />
        <Metric label="Расходы" value={formatMoney(analyticsReport.expense)} tone="danger" />
        <Metric label="Итог" value={formatMoney(analyticsReport.balanceDelta)} />
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
      <section className="plainSection" aria-labelledby="planning-pwa-title">
        <div className="sectionHead compact">
          <h3 id="planning-pwa-title">План месяца</h3>
          <ScopeBadge mode={viewMode} />
        </div>
        <EmptyState text="В PWA планирование пока не является рабочим путем. Для этой итерации планирование Android-first; PWA-путь будет добавлен отдельно." />
      </section>
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
  onPaymentAccountChange
}: {
  account: AccountSummary;
  isUpdating: boolean;
  onPaymentAccountChange: (account: AccountSummary, isPaymentAccount: boolean) => Promise<void>;
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
      </div>
      <b>{formatMoney(account.balance)}</b>
    </article>
  );
}

function CategoryTile({
  category,
  index,
  onEdit
}: {
  category: CategorySummary;
  index: number;
  onEdit: () => void;
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
      <button className="tileAction" type="button" onClick={onEdit}>
        Изменить
      </button>
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
    (left, right) => new Date(right.date).getTime() - new Date(left.date).getTime()
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
