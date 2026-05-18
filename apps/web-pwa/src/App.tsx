import {
  Archive,
  ArrowLeftRight,
  BarChart3,
  CheckCircle2,
  FolderTree,
  LayoutDashboard,
  LogIn,
  RotateCcw,
  ReceiptText,
  Save,
  Trash2,
  WalletCards
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { financeApiClient, type FinanceApiClient } from "./api/client";
import type {
  AccountSummary,
  CategorySummary,
  DashboardSnapshot,
  MoneyAmount,
  OperationSummary,
  ReportMode,
  ReportSummary,
  TransferSummary
} from "./api/types";

type SectionId =
  | "overview"
  | "accounts"
  | "categories"
  | "operations"
  | "transfers"
  | "reports";

type LifecycleState = {
  status: string;
  targetId: string | null;
  archivedId: string | null;
  deletedId: string | null;
};

const sections: Array<{
  id: SectionId;
  label: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "overview", label: "Обзор", icon: LayoutDashboard },
  { id: "accounts", label: "Счета", icon: WalletCards },
  { id: "categories", label: "Категории", icon: FolderTree },
  { id: "operations", label: "Операции", icon: ReceiptText },
  { id: "transfers", label: "Переводы", icon: ArrowLeftRight },
  { id: "reports", label: "Отчеты", icon: BarChart3 }
];

const reportModeLabels: Record<ReportMode, string> = {
  shared_family_report: "Общий семейный отчет",
  combined_viewer_overview: "Сводный обзор участника"
};

const initialAccountLifecycle: LifecycleState = {
  status: "Готово к проверке CRUD счета",
  targetId: null,
  archivedId: null,
  deletedId: null
};

const initialCategoryLifecycle: LifecycleState = {
  status: "Готово к проверке CRUD категории",
  targetId: null,
  archivedId: null,
  deletedId: null
};

const initialOperationLifecycle: LifecycleState = {
  status: "Готово к проверке lifecycle операции",
  targetId: null,
  archivedId: null,
  deletedId: null
};

const initialTransferLifecycle: LifecycleState = {
  status: "Готово к проверке ручного перевода",
  targetId: null,
  archivedId: null,
  deletedId: null
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

export function App({ client = financeApiClient }: { client?: FinanceApiClient }) {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<SectionId>("overview");
  const [activeReportMode, setActiveReportMode] = useState<ReportMode>(
    "shared_family_report"
  );
  const [accountLifecycle, setAccountLifecycle] = useState<LifecycleState>(
    initialAccountLifecycle
  );
  const [categoryLifecycle, setCategoryLifecycle] = useState<LifecycleState>(
    initialCategoryLifecycle
  );
  const [operationLifecycle, setOperationLifecycle] = useState<LifecycleState>(
    initialOperationLifecycle
  );
  const [transferLifecycle, setTransferLifecycle] = useState<LifecycleState>(
    initialTransferLifecycle
  );

  const loadSnapshot = useCallback(async () => {
    const nextSnapshot = await client.getDashboardSnapshot();
    setSnapshot(nextSnapshot);
    return nextSnapshot;
  }, [client]);

  useEffect(() => {
    let isMounted = true;
    setError(null);

    void loadSnapshot()
      .then((nextSnapshot) => {
        if (isMounted) {
          setSnapshot(nextSnapshot);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("Не удалось загрузить данные live API");
        }
      });

    return () => {
      isMounted = false;
    };
  }, [loadSnapshot]);

  const activeReport = useMemo(
    () => snapshot?.reports.find((report) => report.mode === activeReportMode),
    [activeReportMode, snapshot]
  );

  if (error) {
    return <main className="loading">{error}</main>;
  }

  if (!snapshot) {
    return <main className="loading">Загружаем рабочую панель...</main>;
  }

  return (
    <div className="appShell">
      <aside className="sidebar" aria-label="Основная навигация">
        <div className="sessionBlock">
          <div className="sessionIcon" aria-hidden="true">
            <LogIn size={20} />
          </div>
          <div>
            <p className="label">Сессия</p>
            <h1>{snapshot.session.viewerName}</h1>
            <p>{snapshot.session.householdName}</p>
          </div>
        </div>
        <nav className="navList">
          {sections.map((section) => {
            const Icon = section.icon;
            return (
              <button
                key={section.id}
                className={activeSection === section.id ? "active" : ""}
                type="button"
                onClick={() => setActiveSection(section.id)}
              >
                <Icon size={18} aria-hidden="true" />
                {section.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <p className="label">Manual-first MVP</p>
            <h2>Финансовая панель</h2>
          </div>
          <div className="statusPill">{snapshot.session.accessLabel}</div>
        </header>

        {activeSection === "overview" && (
          <Overview
            snapshot={snapshot}
            activeReport={activeReport ?? snapshot.reports[0]}
          />
        )}
        {activeSection === "accounts" && (
          <AccountsSection
            accounts={snapshot.accounts}
            lifecycle={accountLifecycle}
            onArchive={async (account) => {
              setAccountLifecycle((state) => ({
                ...state,
                status: "Архивируем счет..."
              }));
              const archived = await client.archiveAccount(account.id);
              setAccountLifecycle({
                status: "Синхронизируем список счетов...",
                targetId: archived.id,
                archivedId: archived.id,
                deletedId: null
              });
              await loadSnapshot();
              setAccountLifecycle((state) => ({
                ...state,
                status: "Счет архивирован через live API"
              }));
            }}
            onCreate={async () => {
              setAccountLifecycle((state) => ({
                ...state,
                status: "Создаем счет..."
              }));
              const created = await client.createDemoAccount();
              setAccountLifecycle({
                status: "Синхронизируем список счетов...",
                targetId: created.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setAccountLifecycle((state) => ({
                ...state,
                status: "Счет создан через live API"
              }));
            }}
            onDelete={async (account) => {
              setAccountLifecycle((state) => ({
                ...state,
                status: "Удаляем счет..."
              }));
              await client.deleteAccount(account.id);
              setAccountLifecycle({
                status: "Синхронизируем список счетов...",
                targetId: null,
                archivedId: null,
                deletedId: account.id
              });
              await loadSnapshot();
              setAccountLifecycle((state) => ({
                ...state,
                status: "Счет удален и скрыт из активного списка"
              }));
            }}
            onRestore={async (accountId) => {
              setAccountLifecycle((state) => ({
                ...state,
                status: "Восстанавливаем счет..."
              }));
              const restored = await client.restoreAccount(accountId);
              setAccountLifecycle({
                status: "Синхронизируем список счетов...",
                targetId: restored.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setAccountLifecycle((state) => ({
                ...state,
                status: "Счет восстановлен через live API"
              }));
            }}
            onUpdate={async (account) => {
              setAccountLifecycle((state) => ({
                ...state,
                status: "Обновляем счет..."
              }));
              const updated = await client.updateAccount({
                accountId: account.id,
                version: account.version
              });
              setAccountLifecycle({
                status: "Синхронизируем список счетов...",
                targetId: updated.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setAccountLifecycle((state) => ({
                ...state,
                status: "Счет обновлен через live API"
              }));
            }}
          />
        )}
        {activeSection === "categories" && (
          <CategoriesSection
            categories={snapshot.categories}
            householdId={snapshot.accounts.find((account) => account.householdId)?.householdId}
            lifecycle={categoryLifecycle}
            onArchive={async (category) => {
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Архивируем категорию..."
              }));
              const archived = await client.archiveCategory(category.id);
              setCategoryLifecycle({
                status: "Синхронизируем список категорий...",
                targetId: archived.id,
                archivedId: archived.id,
                deletedId: null
              });
              await loadSnapshot();
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Категория архивирована через live API"
              }));
            }}
            onCreate={async (householdId) => {
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Создаем категорию..."
              }));
              const created = await client.createDemoCategory({ householdId });
              setCategoryLifecycle({
                status: "Синхронизируем список категорий...",
                targetId: created.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Категория создана через live API"
              }));
            }}
            onDelete={async (category) => {
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Удаляем категорию..."
              }));
              await client.deleteCategory(category.id);
              setCategoryLifecycle({
                status: "Синхронизируем список категорий...",
                targetId: null,
                archivedId: null,
                deletedId: category.id
              });
              await loadSnapshot();
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Категория удалена и скрыта из активного списка"
              }));
            }}
            onRestore={async (categoryId) => {
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Восстанавливаем категорию..."
              }));
              const restored = await client.restoreCategory(categoryId);
              setCategoryLifecycle({
                status: "Синхронизируем список категорий...",
                targetId: restored.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Категория восстановлена через live API"
              }));
            }}
            onUpdate={async (category) => {
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Обновляем категорию..."
              }));
              const updated = await client.updateCategory({
                categoryId: category.id,
                version: category.version
              });
              setCategoryLifecycle({
                status: "Синхронизируем список категорий...",
                targetId: updated.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setCategoryLifecycle((state) => ({
                ...state,
                status: "Категория обновлена через live API"
              }));
            }}
          />
        )}
        {activeSection === "operations" && (
          <OperationsSection
            accounts={snapshot.accounts}
            categories={snapshot.categories}
            lifecycle={operationLifecycle}
            operations={snapshot.operations}
            onArchive={async (operation) => {
              setOperationLifecycle((state) => ({
                ...state,
                status: "Архивируем операцию..."
              }));
              await client.archiveOperation(operation.id);
              setOperationLifecycle({
                status: "Синхронизируем список операций...",
                targetId: null,
                archivedId: operation.id,
                deletedId: null
              });
              await loadSnapshot();
              setOperationLifecycle((state) => ({
                ...state,
                status: "Операция архивирована и скрыта из активного списка"
              }));
            }}
            onCreate={async (input) => {
              setOperationLifecycle((state) => ({
                ...state,
                status: "Создаем операцию..."
              }));
              const created = await client.createDemoOperation(input);
              setOperationLifecycle({
                status: "Синхронизируем список операций...",
                targetId: created.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setOperationLifecycle((state) => ({
                ...state,
                status: "Операция создана через live API"
              }));
            }}
            onRestore={async (transactionId) => {
              setOperationLifecycle((state) => ({
                ...state,
                status: "Восстанавливаем операцию..."
              }));
              const restored = await client.restoreOperation(transactionId);
              setOperationLifecycle({
                status: "Синхронизируем список операций...",
                targetId: restored.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setOperationLifecycle((state) => ({
                ...state,
                status: "Операция восстановлена через live API"
              }));
            }}
            onUpdate={async (operation) => {
              setOperationLifecycle((state) => ({
                ...state,
                status: "Обновляем операцию..."
              }));
              const updated = await client.updateOperation({
                transactionId: operation.id,
                version: operation.version
              });
              setOperationLifecycle({
                status: "Синхронизируем список операций...",
                targetId: updated.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setOperationLifecycle((state) => ({
                ...state,
                status: "Операция обновлена через live API"
              }));
            }}
          />
        )}
        {activeSection === "transfers" && (
          <TransfersSection
            accounts={snapshot.accounts}
            lifecycle={transferLifecycle}
            transfers={snapshot.transfers}
            onCreate={async (input) => {
              setTransferLifecycle((state) => ({
                ...state,
                status: "Создаем ручной перевод..."
              }));
              const created = await client.createDemoTransfer(input);
              setTransferLifecycle({
                status: "Синхронизируем список переводов...",
                targetId: created.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setTransferLifecycle((state) => ({
                ...state,
                status: "Ручной перевод создан через live API"
              }));
            }}
            onDelete={async (transfer) => {
              setTransferLifecycle((state) => ({
                ...state,
                status: "Удаляем перевод..."
              }));
              await client.archiveTransfer(transfer.id);
              setTransferLifecycle({
                status: "Синхронизируем список переводов...",
                targetId: null,
                archivedId: transfer.id,
                deletedId: transfer.id
              });
              await loadSnapshot();
              setTransferLifecycle((state) => ({
                ...state,
                status: "Перевод удален и скрыт из активного списка"
              }));
            }}
            onRestore={async (transferId) => {
              setTransferLifecycle((state) => ({
                ...state,
                status: "Восстанавливаем перевод..."
              }));
              const restored = await client.restoreTransfer(transferId);
              setTransferLifecycle({
                status: "Синхронизируем список переводов...",
                targetId: restored.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setTransferLifecycle((state) => ({
                ...state,
                status: "Перевод восстановлен через live API"
              }));
            }}
            onUpdate={async (transfer) => {
              setTransferLifecycle((state) => ({
                ...state,
                status: "Обновляем перевод..."
              }));
              const updated = await client.updateTransfer({
                transactionId: transfer.id,
                version: transfer.version
              });
              setTransferLifecycle({
                status: "Синхронизируем список переводов...",
                targetId: updated.id,
                archivedId: null,
                deletedId: null
              });
              await loadSnapshot();
              setTransferLifecycle((state) => ({
                ...state,
                status: "Перевод обновлен через live API"
              }));
            }}
          />
        )}
        {activeSection === "reports" && (
          <ReportsSection
            reports={snapshot.reports}
            activeMode={activeReportMode}
            onModeChange={setActiveReportMode}
          />
        )}
      </main>
    </div>
  );
}

function Overview({
  snapshot,
  activeReport
}: {
  snapshot: DashboardSnapshot;
  activeReport: ReportSummary;
}) {
  const totalBalance = snapshot.accounts.reduce(
    (sum, account) => sum + account.balance.value,
    0
  );
  const balanceCurrency = snapshot.accounts[0]?.balance.currency ?? "RUB";

  return (
    <section className="sectionGrid" aria-labelledby="overview-title">
      <div className="sectionHeader">
        <h3 id="overview-title">Обзор</h3>
        <p>Короткая сводка по live API за текущий период.</p>
      </div>
      <div className="metricGrid">
        <MetricCard
          label="Баланс счетов"
          value={formatMoney({ value: totalBalance, currency: balanceCurrency })}
        />
        <MetricCard label="Доход периода" value={formatMoney(activeReport.income)} />
        <MetricCard
          label="Расход периода"
          value={formatMoney(activeReport.expense)}
          tone="danger"
        />
        <MetricCard
          label="Итог периода"
          value={formatMoney(activeReport.balanceDelta)}
          tone="success"
        />
      </div>
      <div className="twoColumn">
        <AccountsSection accounts={snapshot.accounts.slice(0, 3)} compact />
        <OperationsSection operations={snapshot.operations.slice(0, 3)} compact />
      </div>
    </section>
  );
}

function MetricCard({
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

function ResourceLifecyclePanel<T>({
  label,
  status,
  target,
  archivedId,
  createDisabled = false,
  deleteDisabled = false,
  onArchive,
  onCreate,
  onDelete,
  onRestore,
  onUpdate,
  restoreLabel = "Восстановить"
}: {
  label: string;
  status: string;
  target: T | undefined;
  archivedId: string | null;
  createDisabled?: boolean;
  deleteDisabled?: boolean;
  onArchive?: (target: T) => Promise<void>;
  onCreate: () => Promise<void>;
  onDelete?: (target: T) => Promise<void>;
  onRestore: (id: string) => Promise<void>;
  onUpdate: (target: T) => Promise<void>;
  restoreLabel?: string;
}) {
  const [isBusy, setIsBusy] = useState(false);

  const runAction = async (action: () => Promise<void>) => {
    setIsBusy(true);
    try {
      await action();
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="lifecyclePanel" aria-label={label}>
      <div>
        <strong>{label}</strong>
        <span>{status}</span>
      </div>
      <div className="actionRow">
        <button
          type="button"
          disabled={isBusy || createDisabled}
          onClick={() => runAction(onCreate)}
        >
          <CheckCircle2 size={16} aria-hidden="true" />
          Создать
        </button>
        <button
          type="button"
          disabled={isBusy || !target}
          onClick={() => target ? runAction(() => onUpdate(target)) : undefined}
        >
          <Save size={16} aria-hidden="true" />
          Обновить
        </button>
        {onArchive && (
          <button
            type="button"
            disabled={isBusy || !target}
            onClick={() => target ? runAction(() => onArchive(target)) : undefined}
          >
            <Archive size={16} aria-hidden="true" />
            Архив
          </button>
        )}
        {onDelete && (
          <button
            type="button"
            disabled={isBusy || !target || deleteDisabled}
            onClick={() => target ? runAction(() => onDelete(target)) : undefined}
          >
            <Trash2 size={16} aria-hidden="true" />
            Удалить
          </button>
        )}
        <button
          type="button"
          disabled={isBusy || !archivedId}
          onClick={() => archivedId ? runAction(() => onRestore(archivedId)) : undefined}
        >
          <RotateCcw size={16} aria-hidden="true" />
          {restoreLabel}
        </button>
      </div>
    </div>
  );
}

function AccountsSection({
  accounts,
  compact = false,
  lifecycle,
  onArchive,
  onCreate,
  onDelete,
  onRestore,
  onUpdate
}: {
  accounts: AccountSummary[];
  compact?: boolean;
  lifecycle?: LifecycleState;
  onArchive?: (account: AccountSummary) => Promise<void>;
  onCreate?: () => Promise<void>;
  onDelete?: (account: AccountSummary) => Promise<void>;
  onRestore?: (accountId: string) => Promise<void>;
  onUpdate?: (account: AccountSummary) => Promise<void>;
}) {
  const lifecycleTarget =
    accounts.find((account) => account.id === lifecycle?.targetId) ??
    accounts.find((account) => account.status !== "archived");

  return (
    <section className="panel" aria-labelledby={compact ? undefined : "accounts-title"}>
      <div className="panelHeader">
        <h3 id={compact ? undefined : "accounts-title"}>Счета</h3>
        <span data-testid={compact ? undefined : "account-count"}>
          {accounts.length} видимых
        </span>
      </div>
      {!compact && lifecycle && onArchive && onCreate && onDelete && onRestore && onUpdate && (
        <ResourceLifecyclePanel
          label="CRUD / архив / восстановление счета"
          status={lifecycle.status}
          target={lifecycleTarget}
          archivedId={lifecycle.archivedId}
          onArchive={onArchive}
          onCreate={onCreate}
          onDelete={onDelete}
          onRestore={onRestore}
          onUpdate={onUpdate}
        />
      )}
      <div className="tableList">
        {accounts.map((account) => (
          <div className="tableRow" key={account.id} data-testid="account-row">
            <div>
              <strong>{account.name}</strong>
              <span>
                {account.ownerName} · {accountKindLabel(account.kind)} ·{" "}
                {statusLabel(account.status)}
              </span>
            </div>
            <b>{formatMoney(account.balance)}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function CategoriesSection({
  categories,
  householdId,
  lifecycle,
  onArchive,
  onCreate,
  onDelete,
  onRestore,
  onUpdate
}: {
  categories: CategorySummary[];
  householdId?: string | null;
  lifecycle?: LifecycleState;
  onArchive?: (category: CategorySummary) => Promise<void>;
  onCreate?: (householdId: string | null) => Promise<void>;
  onDelete?: (category: CategorySummary) => Promise<void>;
  onRestore?: (categoryId: string) => Promise<void>;
  onUpdate?: (category: CategorySummary) => Promise<void>;
}) {
  const lifecycleTarget =
    categories.find((category) => category.id === lifecycle?.targetId) ??
    categories.find((category) => category.status !== "archived");

  return (
    <section className="panel" aria-labelledby="categories-title">
      <div className="panelHeader">
        <h3 id="categories-title">Категории</h3>
        <span data-testid="category-count">{categories.length} видимых</span>
      </div>
      {lifecycle && onArchive && onCreate && onDelete && onRestore && onUpdate && (
        <ResourceLifecyclePanel
          label="CRUD / архив / восстановление категории"
          status={lifecycle.status}
          target={lifecycleTarget}
          archivedId={lifecycle.archivedId}
          onArchive={onArchive}
          onCreate={() => onCreate(householdId ?? null)}
          onDelete={onDelete}
          onRestore={onRestore}
          onUpdate={onUpdate}
        />
      )}
      <div className="tableList">
        {categories.map((category) => (
          <div className="tableRow" key={category.id} data-testid="category-row">
            <div>
              <strong>{category.name}</strong>
              <span>
                {category.direction === "income" ? "Доход" : "Расход"} ·{" "}
                {category.scope === "household" ? "семейная" : "личная"} ·{" "}
                {statusLabel(category.status)}
              </span>
            </div>
            <b>{category.direction === "income" ? "поступления" : "списания"}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function OperationsSection({
  accounts = [],
  categories = [],
  lifecycle,
  operations,
  compact = false,
  onArchive,
  onCreate,
  onRestore,
  onUpdate
}: {
  accounts?: AccountSummary[];
  categories?: CategorySummary[];
  lifecycle?: LifecycleState;
  operations: OperationSummary[];
  compact?: boolean;
  onArchive?: (operation: OperationSummary) => Promise<void>;
  onCreate?: (input: {
    accountId: string;
    categoryId: string | null;
    currency: MoneyAmount["currency"];
  }) => Promise<void>;
  onRestore?: (transactionId: string) => Promise<void>;
  onUpdate?: (operation: OperationSummary) => Promise<void>;
}) {
  const firstAccount = accounts.find((account) => account.status !== "archived");
  const compatibleExpenseCategory = categories.find((category) => {
    if (category.status === "archived" || category.direction !== "expense") {
      return false;
    }
    if (firstAccount?.ownershipType === "shared") {
      return (
        category.scope === "household" &&
        category.householdId === firstAccount.householdId
      );
    }

    return category.scope !== "household";
  });
  const targetOperation =
    operations.find((operation) => operation.id === lifecycle?.targetId) ?? operations[0];

  return (
    <section className="panel" aria-labelledby={compact ? undefined : "operations-title"}>
      <div className="panelHeader">
        <h3 id={compact ? undefined : "operations-title"}>Операции</h3>
        <span>{operations.length} активных</span>
      </div>
      {!compact && lifecycle && onCreate && onUpdate && onArchive && onRestore && (
        <ResourceLifecyclePanel
          label="CRUD / архив / восстановление операции"
          status={lifecycle.status}
          target={targetOperation}
          archivedId={lifecycle.archivedId}
          createDisabled={!firstAccount || !compatibleExpenseCategory}
          onArchive={onArchive}
          onCreate={() =>
            firstAccount && compatibleExpenseCategory
              ? onCreate({
                  accountId: firstAccount.id,
                  categoryId: compatibleExpenseCategory.id,
                  currency: firstAccount.balance.currency
                })
              : Promise.resolve()
          }
          onRestore={onRestore}
          onUpdate={onUpdate}
        />
      )}
      <div className="tableList">
        {operations.map((operation) => (
          <div className="tableRow" key={operation.id}>
            <div>
              <strong>{operation.title}</strong>
              <span>
                {formatDate(operation.date)} · {operation.categoryName} ·{" "}
                {operation.accountName}
              </span>
            </div>
            <b className={operation.amount.value < 0 ? "negative" : "positive"}>
              {formatMoney(operation.amount)}
            </b>
          </div>
        ))}
      </div>
    </section>
  );
}

function TransfersSection({
  accounts,
  lifecycle,
  transfers,
  onCreate,
  onDelete,
  onRestore,
  onUpdate
}: {
  accounts: AccountSummary[];
  lifecycle: LifecycleState;
  transfers: TransferSummary[];
  onCreate: (input: {
    fromAccountId: string;
    toAccountId: string;
    currency: MoneyAmount["currency"];
  }) => Promise<void>;
  onDelete: (transfer: TransferSummary) => Promise<void>;
  onRestore: (transferId: string) => Promise<void>;
  onUpdate: (transfer: TransferSummary) => Promise<void>;
}) {
  const transferPair = findCompatibleTransferPair(accounts);
  const targetTransfer =
    transfers.find((transfer) => transfer.id === lifecycle.targetId) ?? transfers[0];

  return (
    <section className="panel" aria-labelledby="transfers-title">
      <div className="panelHeader">
        <h3 id="transfers-title">Переводы</h3>
        <span data-testid="transfer-count">{transfers.length} между счетами</span>
      </div>
      <ResourceLifecyclePanel
        label="Ручной перевод: создать / обновить / удалить / восстановить"
        status={lifecycle.status}
        target={targetTransfer}
        archivedId={lifecycle.archivedId}
        createDisabled={!transferPair}
        onCreate={() =>
          transferPair
            ? onCreate({
                fromAccountId: transferPair.from.id,
                toAccountId: transferPair.to.id,
                currency: transferPair.from.balance.currency
              })
            : Promise.resolve()
        }
        onDelete={onDelete}
        onRestore={onRestore}
        onUpdate={onUpdate}
        restoreLabel="Восстановить"
      />
      <div className="tableList">
        {transfers.length === 0 && (
          <div className="emptyState">В live seed пока нет переводов.</div>
        )}
        {transfers.map((transfer) => (
          <div className="tableRow" key={transfer.id} data-testid="transfer-row">
            <div>
              <strong>
                {transfer.fromAccountName} → {transfer.toAccountName}
              </strong>
              <span>
                {formatDate(transfer.date)} · {transfer.transferStatus ?? "posted"} ·{" "}
                {transfer.transferScope ?? "same-scope"}
              </span>
            </div>
            <b>{formatMoney(transfer.amount)}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function ReportsSection({
  reports,
  activeMode,
  onModeChange
}: {
  reports: ReportSummary[];
  activeMode: ReportMode;
  onModeChange: (mode: ReportMode) => void;
}) {
  const activeReport = reports.find((report) => report.mode === activeMode) ?? reports[0];

  return (
    <section className="panel" aria-labelledby="reports-title">
      <div className="panelHeader">
        <h3 id="reports-title">Отчеты</h3>
        <span data-testid="report-mode-count">
          {activeReport.periodLabel} · {reports.length} режима
        </span>
      </div>
      <div className="segmentedControl" role="group" aria-label="Режим отчета">
        {reports.map((report) => (
          <button
            key={report.mode}
            className={report.mode === activeMode ? "selected" : ""}
            type="button"
            onClick={() => onModeChange(report.mode)}
          >
            {reportModeLabels[report.mode]}
          </button>
        ))}
      </div>
      <div className="reportSummary">
        <MetricCard
          label="Доход"
          value={formatMoney(activeReport.income)}
          tone="success"
        />
        <MetricCard
          label="Расход"
          value={formatMoney(activeReport.expense)}
          tone="danger"
        />
        <MetricCard label="Итог" value={formatMoney(activeReport.balanceDelta)} />
      </div>
    </section>
  );
}

function accountKindLabel(kind: AccountSummary["kind"]): string {
  const labels: Record<AccountSummary["kind"], string> = {
    cash: "наличные",
    debit: "карта",
    savings: "накопления"
  };

  return labels[kind];
}

function statusLabel(status: AccountSummary["status"] | CategorySummary["status"]): string {
  const labels = {
    active: "активно",
    archived: "архив",
    deleted: "удалено"
  };

  return labels[status ?? "active"];
}

function findCompatibleTransferPair(accounts: AccountSummary[]) {
  const activeAccounts = accounts.filter((account) => account.status !== "archived");
  for (const from of activeAccounts) {
    const to = activeAccounts.find((candidate) => {
      if (candidate.id === from.id || candidate.balance.currency !== from.balance.currency) {
        return false;
      }
      if (from.ownershipType === "shared" || candidate.ownershipType === "shared") {
        return (
          from.ownershipType === "shared" &&
          candidate.ownershipType === "shared" &&
          from.householdId === candidate.householdId
        );
      }

      return true;
    });
    if (to) {
      return { from, to };
    }
  }

  return null;
}
