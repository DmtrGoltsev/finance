import {
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  Check,
  CircleDollarSign,
  CreditCard,
  FileUp,
  Landmark,
  Layers3,
  LineChart,
  Lock,
  Plus,
  ReceiptText,
  Settings,
  Shield,
  ShoppingCart,
  Tag,
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
import { financeApiClient, type FinanceApiClient } from "./api/client";
import type {
  AccountKind,
  AccountSummary,
  CategorySummary,
  CurrencyCode,
  DashboardSnapshot,
  ImportReportPreviewResponse,
  ImportReportType,
  MoneyAmount,
  OperationSummary,
  ReportMode,
  ReportSummary,
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
type QuickKind = "expense" | "income" | "transfer" | "asset";
type ImportMode = ViewMode;

type QuickAddInput = {
  kind: QuickKind;
  amount: number;
  accountId: string;
  toAccountId: string;
  categoryId: string;
  assetKind: AccountKind;
  date: string;
  comment: string;
  visibility: VisibilityMode;
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

const importReportTypeLabels: Record<ImportReportType, string> = {
  generic_finance_report: "Общий финансовый",
  bank_statement: "Выписка банка",
  brokerage_report: "Отчет брокера",
  deposit_report: "Вклад",
  metals_report: "Металлы"
};

function formatMoney(amount: MoneyAmount): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: amount.currency,
    maximumFractionDigits: 0
  }).format(amount.value);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short"
  }).format(new Date(value));
}

function formatFileSize(value?: number): string {
  if (!Number.isFinite(value)) {
    return "Размер не указан";
  }

  const bytes = Math.max(0, value ?? 0);
  if (bytes < 1024) {
    return `${bytes} Б`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} КБ`;
  }

  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

function todayInputValue(): string {
  return new Date().toISOString().slice(0, 10);
}

export function App({ client = financeApiClient }: { client?: FinanceApiClient }) {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<SectionId>("money");
  const [viewMode, setViewMode] = useState<ViewMode>("personal");
  const [isQuickAddOpen, setQuickAddOpen] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string>("");

  const loadSnapshot = useCallback(async () => {
    const nextSnapshot = await client.getDashboardSnapshot();
    setSnapshot(nextSnapshot);
    return nextSnapshot;
  }, [client]);

  useEffect(() => {
    let isMounted = true;
    setError(null);

    void loadSnapshot().catch(() => {
      if (isMounted) {
        setError("Не удалось загрузить финансы");
      }
    });

    return () => {
      isMounted = false;
    };
  }, [loadSnapshot]);

  const activeReport = useMemo(() => {
    if (!snapshot) {
      return null;
    }

    return reportForView(snapshot, viewMode);
  }, [snapshot, viewMode]);

  const saveQuickAdd = async (input: QuickAddInput) => {
    if (!snapshot) {
      return;
    }

    const sourceAccount = snapshot.accounts.find((account) => account.id === input.accountId);
    const currency = sourceAccount?.balance.currency ?? "RUB";
    const occurredAt = new Date(`${input.date || todayInputValue()}T12:00:00`).toISOString();

    setSaveStatus("Сохраняем");
    if (input.kind === "asset") {
      await client.createDemoAccount({
        name: input.comment.trim() || accountKindLabels[input.assetKind],
        kind: input.assetKind,
        currency,
        initialBalance: input.amount,
        ownershipType: input.visibility === "shared" ? "shared" : "personal"
      });
    } else if (input.kind === "transfer") {
      await client.createDemoTransfer({
        fromAccountId: input.accountId,
        toAccountId: input.toAccountId,
        currency,
        amount: input.amount,
        occurredAt,
        description: input.comment || "Перевод"
      });
    } else {
      await client.createDemoOperation({
        accountId: input.accountId,
        categoryId: input.categoryId || null,
        currency,
        transactionType: input.kind,
        amount: input.amount,
        occurredAt,
        description: input.comment || null
      });
    }

    await loadSnapshot();
    setSaveStatus("Добавлено");
    setQuickAddOpen(false);
  };

  if (error) {
    return <main className="loading">{error}</main>;
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
          </div>
          <div className="topActions">
            <ViewSwitch value={viewMode} onChange={setViewMode} />
            <button className="primaryButton" type="button" onClick={() => setQuickAddOpen(true)}>
              <Plus size={18} aria-hidden="true" />
              Добавить
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
          <OperationsPage snapshot={snapshot} viewMode={viewMode} client={client} />
        )}
        {activeSection === "assets" && (
          <AssetsPage snapshot={snapshot} viewMode={viewMode} />
        )}
        {activeSection === "categories" && (
          <CategoriesPage snapshot={snapshot} viewMode={viewMode} />
        )}
        {activeSection === "analytics" && (
          <AnalyticsPage
            snapshot={snapshot}
            report={activeReport}
            viewMode={viewMode}
            client={client}
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
          accounts={visibleAccounts(snapshot.accounts, viewMode)}
          allAccounts={snapshot.accounts.filter((account) => account.status !== "deleted")}
          categories={visibleCategories(snapshot.categories, viewMode)}
          defaultVisibility={viewMode === "shared" ? "shared" : "personal"}
          onClose={() => setQuickAddOpen(false)}
          onSubmit={saveQuickAdd}
          saveStatus={saveStatus}
        />
      )}
    </div>
  );
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
  const recentItems = recentTimeline(operations, transfers).slice(0, 6);

  return (
    <section className="screenStack" aria-labelledby="money-title">
      <div className="sectionHead">
        <h3 id="money-title">Обзор</h3>
        <button type="button" className="ghostButton" onClick={onAdd}>
          <Plus size={17} aria-hidden="true" />
          Операция
        </button>
      </div>

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
            {groups.length === 0 && <EmptyState text="Нет активов в этом режиме" />}
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
            {topCategories.length === 0 && <EmptyState text="Пока нет расходов" />}
          </div>
        </section>
      </div>

      <section className="plainSection" aria-labelledby="latest-title">
        <div className="sectionHead compact">
          <h3 id="latest-title">Последние операции</h3>
        </div>
        <TimelineList items={recentItems} />
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
  snapshot,
  viewMode,
  client
}: {
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
  client: FinanceApiClient;
}) {
  const accounts = visibleAccounts(snapshot.accounts, viewMode);
  const operations = visibleOperations(snapshot.operations, accounts);
  const transfers = visibleTransfers(snapshot.transfers, accounts);
  const timeline = recentTimeline(operations, transfers);

  return (
    <section className="screenStack" aria-labelledby="operations-title">
      <div className="sectionHead">
        <h3 id="operations-title">Операции</h3>
        <span>{timeline.length} записей</span>
      </div>
      <ImportReportPanel client={client} snapshot={snapshot} viewMode={viewMode} compact />
      <TimelineList items={timeline} />
    </section>
  );
}

function AssetsPage({
  snapshot,
  viewMode
}: {
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
}) {
  const accounts = visibleAccounts(snapshot.accounts, viewMode);

  return (
    <section className="screenStack" aria-labelledby="assets-title">
      <div className="sectionHead">
        <h3 id="assets-title">Счета и активы</h3>
        <span>{accounts.length} активов</span>
      </div>
      <div className="assetGrid">
        {accounts.map((account) => (
          <AssetTile key={account.id} account={account} />
        ))}
        {accounts.length === 0 && <EmptyState text="Нет активов в этом режиме" />}
      </div>
    </section>
  );
}

function CategoriesPage({
  snapshot,
  viewMode
}: {
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
}) {
  const categories = visibleCategories(snapshot.categories, viewMode);

  return (
    <section className="screenStack" aria-labelledby="categories-title">
      <div className="sectionHead">
        <h3 id="categories-title">Категории</h3>
        <span>{categories.length} категорий</span>
      </div>
      <div className="categoryGrid">
        {categories.map((category, index) => (
          <CategoryTile key={category.id} category={category} index={index} />
        ))}
        {categories.length === 0 && <EmptyState text="Нет категорий в этом режиме" />}
      </div>
    </section>
  );
}

function AnalyticsPage({
  snapshot,
  report,
  viewMode,
  client
}: {
  snapshot: DashboardSnapshot;
  report: ReportSummary;
  viewMode: ViewMode;
  client: FinanceApiClient;
}) {
  const accounts = visibleAccounts(snapshot.accounts, viewMode);
  const operations = visibleOperations(snapshot.operations, accounts);
  const currency = accounts[0]?.balance.currency ?? report.income.currency;
  const topCategories = categoryTotals(operations, snapshot.categories, currency);
  const groups = groupAssets(accounts, currency);

  return (
    <section className="screenStack" aria-labelledby="analytics-title">
      <div className="sectionHead">
        <h3 id="analytics-title">Аналитика</h3>
        <span>{report.periodLabel}</span>
      </div>
      <ImportReportPanel client={client} snapshot={snapshot} viewMode={viewMode} />
      <div className="metricGrid three">
        <Metric label="Доходы" value={formatMoney(report.income)} tone="success" />
        <Metric label="Расходы" value={formatMoney(report.expense)} tone="danger" />
        <Metric label="Итог" value={formatMoney(report.balanceDelta)} />
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
    </section>
  );
}

function ImportReportPanel({
  client,
  snapshot,
  viewMode,
  compact = false
}: {
  client: FinanceApiClient;
  snapshot: DashboardSnapshot;
  viewMode: ViewMode;
  compact?: boolean;
}) {
  const [reportType, setReportType] = useState<ImportReportType>("generic_finance_report");
  const [mode, setMode] = useState<ImportMode>(viewMode);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportReportPreviewResponse | null>(null);
  const [isLoading, setLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const householdId =
    snapshot.accounts.find((account) => account.ownershipType === "shared" && account.householdId)
      ?.householdId ?? null;
  const targetScope = mode === "shared" ? "shared" : "personal";
  const canPreview = Boolean(file) && (!mode || mode !== "shared" || householdId);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || !canPreview) {
      return;
    }

    setLoading(true);
    setPreviewError(null);
    try {
      const nextPreview = await client.previewImportReport({
        reportType,
        sourceType: "file_metadata_only",
        targetScope,
        householdId: targetScope === "shared" ? householdId : null,
        fileName: file.name,
        fileSizeBytes: file.size,
        mimeType: file.type || "application/octet-stream"
      });
      setPreview(nextPreview);
    } catch {
      setPreviewError("Не удалось показать сводку. Попробуйте выбрать файл еще раз.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      className={compact ? "importPanel compact" : "importPanel"}
      aria-labelledby={compact ? "import-entry-operations" : "import-entry-analytics"}
    >
      <form className="importForm" onSubmit={submit}>
        <div className="sectionHead compact">
          <div>
            <h3 id={compact ? "import-entry-operations" : "import-entry-analytics"}>
              Импорт отчета
            </h3>
            <span>Показана только предварительная сводка</span>
          </div>
          <FileUp size={20} aria-hidden="true" />
        </div>

        <div className="importFields">
          <label className="field">
            <span>Тип отчета</span>
            <select
              value={reportType}
              onChange={(event) => setReportType(event.target.value as ImportReportType)}
            >
              {Object.entries(importReportTypeLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Файл</span>
            <input
              aria-label="Файл отчета"
              type="file"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setPreview(null);
              }}
            />
          </label>
          <fieldset className="visibilityGroup importModeGroup">
            <legend>Режим</legend>
            <label>
              <input
                checked={mode === "personal"}
                name={compact ? "import-mode-operations" : "import-mode-analytics"}
                type="radio"
                onChange={() => setMode("personal")}
              />
              Личное
            </label>
            <label>
              <input
                checked={mode === "shared"}
                name={compact ? "import-mode-operations" : "import-mode-analytics"}
                type="radio"
                onChange={() => setMode("shared")}
              />
              Общее
            </label>
            <label>
              <input
                checked={mode === "overview"}
                name={compact ? "import-mode-operations" : "import-mode-analytics"}
                type="radio"
                onChange={() => setMode("overview")}
              />
              Обзор
            </label>
          </fieldset>
        </div>

        <div className="importActions">
          <button className="ghostButton" type="submit" disabled={!canPreview || isLoading}>
            <FileUp size={17} aria-hidden="true" />
            {isLoading ? "Показываем" : "Показать сводку"}
          </button>
          <span>Данные не изменятся без подтверждения</span>
        </div>
        <p className="importGuardrail">Содержимое файла не сохраняется и не разбирается.</p>
        {mode === "shared" && !householdId && (
          <p className="importError">Для общего режима нужен семейный доступ.</p>
        )}
        {previewError && <p className="importError">{previewError}</p>}
      </form>

      {preview && (
        <div className="importPreview" aria-label="Предварительный просмотр импорта">
          <div className="importPreviewHead">
            <div>
              <strong>{preview.summary.title}</strong>
              <span>{preview.summary.statusText}</span>
            </div>
            <b>Файл не разобран</b>
          </div>
          <dl className="importMeta">
            <div>
              <dt>Источник</dt>
              <dd>{importReportTypeLabels[reportType]}</dd>
            </div>
            <div>
              <dt>Режим</dt>
              <dd>{modeLabel(mode)}</dd>
            </div>
            <div>
              <dt>Имя файла</dt>
              <dd>{preview.file.fileName || "Файл выбран"}</dd>
            </div>
            <div>
              <dt>Размер</dt>
              <dd>{formatFileSize(preview.file.fileSizeBytes)}</dd>
            </div>
            <div>
              <dt>Статус</dt>
              <dd>{preview.summary.statusText}</dd>
            </div>
          </dl>
          <div className="recognitionGrid" aria-label="Секции распознавания">
            {preview.summary.sections.map((section) => (
              <article key={section.key} className="recognitionItem">
                <strong>{section.title}</strong>
                <span>{section.text}</span>
              </article>
            ))}
          </div>
          <div className="importWarnings" aria-label="Перед импортом">
            {preview.warnings.map((warning) => (
              <span key={warning.code}>{warning.text}</span>
            ))}
          </div>
        </div>
      )}
    </section>
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
  accounts,
  allAccounts,
  categories,
  defaultVisibility,
  onClose,
  onSubmit,
  saveStatus
}: {
  accounts: AccountSummary[];
  allAccounts: AccountSummary[];
  categories: CategorySummary[];
  defaultVisibility: VisibilityMode;
  onClose: () => void;
  onSubmit: (input: QuickAddInput) => Promise<void>;
  saveStatus: string;
}) {
  const firstAccount = accounts[0] ?? allAccounts[0];
  const secondAccount = allAccounts.find((account) => account.id !== firstAccount?.id);
  const [kind, setKind] = useState<QuickKind>("expense");
  const [amount, setAmount] = useState("1000");
  const [accountId, setAccountId] = useState(firstAccount?.id ?? "");
  const [toAccountId, setToAccountId] = useState(secondAccount?.id ?? "");
  const [categoryId, setCategoryId] = useState(categories[0]?.id ?? "");
  const [assetKind, setAssetKind] = useState<AccountKind>("card");
  const [date, setDate] = useState(todayInputValue());
  const [comment, setComment] = useState("");
  const [visibility, setVisibility] = useState<VisibilityMode>(defaultVisibility);
  const [isSaving, setSaving] = useState(false);

  const filteredCategories = categories.filter((category) => {
    if (kind === "income") {
      return category.direction === "income";
    }
    if (kind === "expense") {
      return category.direction === "expense";
    }
    return false;
  });

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedAmount = Number(amount);
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      return;
    }

    setSaving(true);
    try {
      await onSubmit({
        kind,
        amount: parsedAmount,
        accountId,
        toAccountId,
        categoryId,
        assetKind,
        date,
        comment,
        visibility
      });
    } finally {
      setSaving(false);
    }
  };

  const canSubmit =
    Number(amount) > 0 &&
    (kind === "asset" ||
      (kind === "transfer" ? accountId && toAccountId && accountId !== toAccountId : accountId));

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
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>

        {kind === "asset" ? (
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
        ) : (
          <label className="field">
            <span>{kind === "transfer" ? "Откуда" : "Счет"}</span>
            <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
              {allAccounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
        )}

        {kind === "transfer" && (
          <label className="field">
            <span>Куда</span>
            <select value={toAccountId} onChange={(event) => setToAccountId(event.target.value)}>
              {allAccounts
                .filter((account) => account.id !== accountId)
                .map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name}
                  </option>
                ))}
            </select>
          </label>
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
          <fieldset className="visibilityGroup">
            <legend>Видимость</legend>
            <label>
              <input
                checked={visibility === "personal"}
                name="visibility"
                type="radio"
                onChange={() => setVisibility("personal")}
              />
              Личное
            </label>
            <label>
              <input
                checked={visibility === "shared"}
                name="visibility"
                type="radio"
                onChange={() => setVisibility("shared")}
              />
              Общее
            </label>
          </fieldset>
        </details>

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

function AssetTile({ account }: { account: AccountSummary }) {
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
      </div>
      <b>{formatMoney(account.balance)}</b>
    </article>
  );
}

function CategoryTile({
  category,
  index
}: {
  category: CategorySummary;
  index: number;
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
        <span>{category.direction === "income" ? "Доход" : "Расход"}</span>
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

function TimelineList({ items }: { items: TimelineItem[] }) {
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
      {items.length === 0 && <EmptyState text="Записей пока нет" />}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="emptyState">{text}</div>;
}

function visibleAccounts(accounts: AccountSummary[], mode: ViewMode): AccountSummary[] {
  return accounts.filter((account) => {
    if (account.status === "deleted" || account.status === "archived") {
      return false;
    }

    if (mode === "overview") {
      return true;
    }

    return mode === "shared"
      ? account.ownershipType === "shared"
      : account.ownershipType !== "shared";
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

    return mode === "shared" ? category.scope === "household" : category.scope !== "household";
  });
}

function visibleOperations(
  operations: OperationSummary[],
  accounts: AccountSummary[]
): OperationSummary[] {
  const accountIds = new Set(accounts.map((account) => account.id));
  return operations.filter((operation) => accountIds.has(operation.accountId));
}

function visibleTransfers(
  transfers: TransferSummary[],
  accounts: AccountSummary[]
): TransferSummary[] {
  const accountIds = new Set(accounts.map((account) => account.id));
  return transfers.filter(
    (transfer) =>
      accountIds.has(transfer.accountId) ||
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
  transfers: TransferSummary[]
): TimelineItem[] {
  const operationItems: TimelineItem[] = operations.map((operation) => ({
    type: "operation",
    id: operation.id,
    date: operation.date,
    title: operation.title,
    subtitle: `${formatDate(operation.date)} · ${operation.categoryName} · ${operation.accountName}`,
    amount: operation.amount
  }));
  const transferItems: TimelineItem[] = transfers.map((transfer) => ({
    type: "transfer",
    id: transfer.id,
    date: transfer.date,
    title: `${transfer.fromAccountName} → ${transfer.toAccountName}`,
    subtitle: `${formatDate(transfer.date)} · Перевод`,
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
    overview: "Сводный обзор"
  };

  return descriptions[mode];
}

function modeLabel(mode: ImportMode): string {
  const labels: Record<ImportMode, string> = {
    personal: "Личное",
    shared: "Общее",
    overview: "Обзор"
  };

  return labels[mode];
}

function shortCategoryName(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).join(" ");
}

function reportForView(snapshot: DashboardSnapshot, mode: ViewMode): ReportSummary {
  const currency = snapshot.accounts[0]?.balance.currency ?? "RUB";

  if (mode === "personal") {
    const accounts = visibleAccounts(snapshot.accounts, "personal");
    const operations = visibleOperations(snapshot.operations, accounts);
    return reportFromOperations("personal", operations, currency);
  }

  const reportMode = reportModeByView[mode];
  return (
    snapshot.reports.find((report) => report.mode === reportMode) ??
    snapshot.reports[0] ??
    emptyReport(mode, currency)
  );
}

function reportFromOperations(
  mode: ViewMode,
  operations: OperationSummary[],
  currency: CurrencyCode
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
