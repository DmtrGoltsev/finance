# План реализации iOS-приложения на SwiftUI

> Паритет с Android-клиентом (apps/android). Исходный контракт: api/openapi/openapi.yaml.
> Ветка: glm. Дата плана: 2026-06-12.

---

## 1. Архитектура

| Параметр | Значение |
|---|---|
| Расположение | `apps/ios/FinanceApp/` |
| Минимальная iOS | 17.0 |
| Язык | Swift 5.9+ |
| UI-фреймворк | SwiftUI (только натив) |
| State management | `@Observable` макрос + `@Environment` |
| Зависимости | **Никаких SPM-зависимостей**. Только Foundation, SwiftUI, URLSession |
| Auth модель | Cookie-based CSRF (как PWA, НЕ bearer). HttpOnly cookie `__Host-finance_session` + header `X-CSRF-Token` |
| Сериализация | `Codable` + `JSONDecoder`/`JSONEncoder` |
| Async | `async/await`, `Task`, `@MainActor` |
| Хранение токена CSRF | Keychain (Security framework, нативно) |
| Хранение маппингов OCR | Keychain (аналог EncryptedSharedPreferences) |
| Money | `Decimal` (НЕ `Double`/`Float`). Строки API → `Decimal` → форматирование |
| Таймзоны | `TimeZone.current`, даты API — ISO 8601 / `DateOnly` строки `yyyy-MM-dd` |

### Auth-поток (cookie-based, паритет с PWA)

1. POST `/api/v1/sessions` с `transport: "pwa_cookie"` → сервер ставит HttpOnly cookie `__Host-finance_session` и возвращает `{ transport: "pwa_cookie", csrfToken: "...", expiresAt: "...", actor: {...} }`.
2. iOS сохраняет `csrfToken` в Keychain, `expiresAt` для проверки сессии.
3. Каждому state-changing запросу добавляется header `X-CSRF-Token: <saved>`.
4. GET-запросы используют cookie автоматически через `URLSession` cookie storage.
5. POST `/api/v1/sessions/current` (DELETE) → logout, очистка Keychain.

### Cookie storage

Используем `HTTPCookieStorage.shared` или конфигурируем `URLSessionConfiguration` с `.httpCookieStorage = .shared`. Cookie `__Host-finance_session` автоматически отправляется с запросами к тому же домену.

---

## 2. Структура директорий

```
apps/ios/
  FinanceApp/
    FinanceApp.swift                    // @main entry point
    App/
      AppDelegate.swift                 // UNUserNotificationCenter, lifecycle
      FinanceAppView.swift              // Root view: TabView + auth gate
      AppRoute.swift                    // Navigation routes enum
    Models/
      Account.swift                     // Account, AccountType, OwnershipType
      Category.swift                    // Category, CategoryScope, CategoryType
      Transaction.swift                 // Transaction, TransactionType, TransferScope, TransferStatus
      AssetCategory.swift               // AssetCategory, AssetCategoryGroup, AssetCategoryScope
      Money.swift                       // MoneyAmount, MoneyTotal, CurrencyCode
      CaptureDraft.swift                // CaptureDraft, CaptureDraftStatus, CaptureSource, ScreenshotOcrCandidate
      Planning.swift                    // PlanningPlan, PlanningIncomeSource, PlanningAllocation, PlanningScope, AllocationMode, AllocationTargetType, AllocationRecurrenceType, AllocationProgressStatus, IncomeConfirmationState
      Report.swift                      // ReportMode, ReportSummary, CategoryBreakdownItem, AccountBalance, CashFlowPoint
      Session.swift                     // SessionStatus, ActorContext, ActorMembership, RegistrationResult
      Dashboard.swift                   // FinanceDashboard, DashboardView
      Error.swift                       // FinanceError, ErrorCode
      Enums.swift                       // RecordStatus, AuthTransport, PlanMonth helpers
    Networking/
      ApiClient.swift                   // protocol FinanceApiClient
      LiveApiClient.swift               // URLSession-based implementation
      ApiResult.swift                   // enum ApiResult<T>
      ApiError.swift                    // FinanceApiError
      CSRFTokenStore.swift              // Keychain-based CSRF token + session cookie
      RequestBuilder.swift              // URL + query params + multipart helpers
      ResponseParser.swift              // JSON parsing helpers
      CategoryAggregateMappingStore.swift // Keychain-based label→categoryId mapping
    Views/
      Home/
        HomeTab.swift                   // Capital, expenses, assets chips, top categories, recent ops
        CapitalCard.swift
        MonthExpenseCard.swift
        PlanningEntryCard.swift
      Operations/
        OperationsTab.swift             // Transaction list + capture drafts + OCR
        TransactionRow.swift
        CaptureDraftReviewCard.swift
        CaptureDraftRow.swift
        ScreenshotAggregateDraftList.swift
      Assets/
        AssetsTab.swift                 // AssetCategory groups + legacy groups + add account
        AssetCategoryGroupCard.swift
        AssetCategorySheet.swift        // Modal: new asset category
        AddAccountSheet.swift           // Modal: new account
        AccountRow.swift
        AccountEditDialog.swift
        AssetCategoryIcons.swift
      Categories/
        CategoriesTab.swift             // Category CRUD
        CategoryManagementCard.swift
      Analytics/
        AnalyticsTab.swift              // Summary + Planning tabs
        AnalyticsSummaryCard.swift
        InvestmentsCard.swift
        CategoryBreakdownCard.swift
        CapitalBreakdownCard.swift
        ReportMonthSwitcher.swift
        Planning/
          PlanningView.swift            // Full planning module
          PlanningScopeCard.swift
          PlanningPlanCard.swift
          IncomeSourcesCard.swift
          AllocationsCard.swift
          PlanningHistoryCard.swift
          PlanningAllocationEditor.swift
          PlanningCreateCategorySheet.swift
          PlanningCreateAccountSheet.swift
      Auth/
        SignInCard.swift                // Login/Register form
      Capture/
        CaptureParser.swift             // Client-side OCR text parsing (fallback)
        CaptureCandidate.swift          // CaptureCandidate, CategoryAggregateCandidate models
      Common/
        ModeChips.swift                 // FinanceMode picker (Personal/Shared/Overview)
        DatePickerField.swift
        IconBubble.swift
        MetricLine.swift
        EmptyState.swift
        MoneyFormatting.swift
        DateFormatting.swift
    Utilities/
      MoneyHelpers.swift                // Decimal formatting, currency labels
      DateHelpers.swift                 // YearMonth, date boundaries, formatting
      DashboardView.swift              // DashboardView computed properties
      Constants.swift                   // Colors, currencies list, asset kinds
      UserFacingText.swift             // Seed text → localized labels
    Resources/
      Assets.xcassets                   // App icons, SF Symbols overrides
      Localizable.strings               // Russian localization
  FinanceApp.xcodeproj
  FinanceAppTests/
  FinanceAppUITests/
```

---

## 3. Модели данных (Codable structs)

Все модели реализуют `Codable`. Денежные суммы — `String` (DecimalString из OpenAPI), конвертируются в `Decimal` при форматировании.

### 3.1 CurrencyCode

```swift
enum CurrencyCode: String, Codable, CaseIterable {
    case RUB, USD, EUR, XAU
}
```

### 3.2 MoneyAmount

```swift
struct MoneyAmount: Codable, Identifiable {
    var id: String { currency }
    let currency: CurrencyCode
    let amount: String // DecimalString
}
```

### 3.3 MoneyTotal

```swift
struct MoneyTotal: Codable {
    let currency: CurrencyCode
    let incomeTotal: String
    let expenseTotal: String
    let netTotal: String
}
```

### 3.4 OwnershipType

```swift
enum OwnershipType: String, Codable {
    case personal, shared
}
```

### 3.5 AccountType

```swift
enum AccountType: String, Codable, CaseIterable {
    case cash, bank, card, deposit, brokerage, metal, other
}
```

### 3.6 RecordStatus

```swift
enum RecordStatus: String, Codable {
    case active, archived, deleted
}
```

### 3.7 Account

```swift
struct Account: Codable, Identifiable {
    let id: String
    let name: String
    let accountType: AccountType
    let ownershipType: OwnershipType
    let ownerUserId: String?
    let householdId: String?
    let assetCategoryId: String?
    let currency: CurrencyCode
    let initialBalance: String
    let currentBalance: String
    let isPaymentAccount: Bool
    let status: RecordStatus
    let version: Int?
}
```

### 3.8 AccountCreateRequest

```swift
struct AccountCreateRequest: Codable {
    let name: String
    let accountType: AccountType
    let ownershipType: OwnershipType
    let householdId: String?
    let assetCategoryId: String?
    let currency: CurrencyCode
    let initialBalance: String
    let isPaymentAccount: Bool?
}
```

### 3.9 AccountUpdateRequest

```swift
struct AccountUpdateRequest: Codable {
    let name: String?
    let currentBalance: String?
    let currency: CurrencyCode?
    let accountType: AccountType?
    let assetCategoryId: String?? // Optional<String?> → null / value / absent
    let isPaymentAccount: Bool?
    let version: Int?
}
```

### 3.10 CategoryScope

```swift
enum CategoryScope: String, Codable {
    case personal, household
}
```

### 3.11 CategoryType

```swift
enum CategoryType: String, Codable {
    case income, expense
}
```

### 3.12 Category

```swift
struct Category: Codable, Identifiable {
    let id: String
    let name: String
    let type: CategoryType
    let scope: CategoryScope
    let ownerUserId: String?
    let householdId: String?
    let iconKey: String?
    let color: String?
    let status: RecordStatus
    let version: Int?
}
```

### 3.13 CategoryCreateRequest

```swift
struct CategoryCreateRequest: Codable {
    let name: String
    let type: CategoryType
    let scope: CategoryScope
    let householdId: String?
    let iconKey: String?
    let color: String?
}
```

### 3.14 CategoryUpdateRequest

```swift
struct CategoryUpdateRequest: Codable {
    let name: String?
    let iconKey: String?
    let color: String?
    let version: Int?
}
```

### 3.15 TransactionType

```swift
enum TransactionType: String, Codable {
    case income, expense, transfer, brokerage, asset_buy, asset_sell, interest, dividend, adjustment
}
```

### 3.16 TransferScope

```swift
enum TransferScope: String, Codable {
    case personal_same_owner, household_same_household
}
```

### 3.17 TransferStatus

```swift
enum TransferStatus: String, Codable {
    case posted, voided
}
```

### 3.18 Transaction

```swift
struct Transaction: Codable, Identifiable {
    let id: String
    let transactionType: TransactionType
    let accountId: String
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String
    let currency: CurrencyCode
    let occurredAt: String // DateTime ISO 8601
    let transactionDate: String? // DateOnly yyyy-MM-dd
    let description: String?
    let sourceType: String // always "manual" in MVP
    let transferScope: TransferScope?
    let transferStatus: TransferStatus?
    let version: Int?
}
```

### 3.19 TransactionCreateRequest

```swift
struct TransactionCreateRequest: Codable {
    let transactionType: TransactionType
    let accountId: String
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String
    let currency: CurrencyCode
    let occurredAt: String?
    let transactionDate: String?
    let description: String?
    let sourceType: String // "manual"
}
```

### 3.20 TransactionUpdateRequest

```swift
struct TransactionUpdateRequest: Codable {
    let transactionType: TransactionType?
    let accountId: String?
    let counterpartyAccountId: String?
    let categoryId: String?
    let amount: String?
    let currency: CurrencyCode?
    let occurredAt: String?
    let transactionDate: String?
    let description: String?
    let sourceType: String?
    let version: Int?
}
```

### 3.21 AssetCategoryScope

```swift
enum AssetCategoryScope: String, Codable {
    case personal, household
}
```

### 3.22 AssetCategory

```swift
struct AssetCategory: Codable, Identifiable {
    let id: String
    let name: String
    let scopeType: AssetCategoryScope
    let ownerUserId: String?
    let householdId: String?
    let currency: CurrencyCode
    let assetType: AccountType
    let iconKey: String?
    let manualAmount: String
    let isInvestment: Bool
    let recordStatus: RecordStatus
    let version: Int?
}
```

### 3.23 AssetCategoryCreateRequest

```swift
struct AssetCategoryCreateRequest: Codable {
    let name: String
    let scopeType: AssetCategoryScope
    let householdId: String?
    let currency: CurrencyCode
    let assetType: AccountType?
    let iconKey: String?
    let manualAmount: String?
    let isInvestment: Bool?
}
```

### 3.24 AssetCategoryUpdateRequest

```swift
struct AssetCategoryUpdateRequest: Codable {
    let name: String?
    let manualAmount: String?
    let assetType: AccountType?
    let iconKey: String?
    let isInvestment: Bool?
    let version: Int?
}
```

### 3.25 AssetCategoryGroup

```swift
struct AssetCategoryGroup: Codable, Identifiable {
    var id: String { assetCategoryId }
    let assetCategoryId: String
    let name: String
    let scopeType: AssetCategoryScope
    let householdId: String?
    let currency: CurrencyCode
    let manualAmount: String
    let accountsTotal: String
    let totalAmount: String
    let isInvestment: Bool
    let assetType: AccountType
    let iconKey: String?
    let accountCount: Int?
}
```

### 3.26 CaptureDraftStatus

```swift
enum CaptureDraftStatus: String, Codable {
    case pending, confirmed, discarded
}
```

### 3.27 CaptureSource

```swift
enum CaptureSource: String, Codable {
    case screenshot
}
```

### 3.28 CaptureDraft

```swift
struct CaptureDraft: Codable, Identifiable {
    let id: String
    let status: CaptureDraftStatus
    let idempotencyKey: String
    let captureSource: CaptureSource
    let capturedAt: String
    let occurredAt: String?
    let occurredDate: String?
    let amount: String
    let currency: CurrencyCode
    let description: String
    let merchantName: String?
    let accountId: String?
    let categoryId: String?
    let transactionId: String?
    let confidence: String?
    let sourceAppPackage: String?
    let sourceAppLabel: String?
    let evidenceHash: String?
    let version: Int?
}
```

### 3.29 CaptureDraftCreateRequest

```swift
struct CaptureDraftCreateRequest: Codable {
    let idempotencyKey: String
    let captureSource: CaptureSource
    let capturedAt: String
    let occurredAt: String?
    let occurredDate: String?
    let amount: String
    let currency: CurrencyCode
    let description: String
    let merchantName: String?
    let accountId: String?
    let categoryId: String?
    let confidence: String?
    let sourceAppPackage: String?
    let sourceAppLabel: String?
    let evidenceHash: String?
}
```

### 3.30 CaptureDraftUpdateRequest

```swift
struct CaptureDraftUpdateRequest: Codable {
    let occurredAt: String?
    let occurredDate: String?
    let amount: String?
    let currency: CurrencyCode?
    let description: String?
    let merchantName: String?
    let accountId: String?
    let categoryId: String?
    let confidence: String?
}
```

### 3.31 ScreenshotOcrCandidate

```swift
struct ScreenshotOcrCandidate: Codable, Identifiable {
    var id: String { idempotencyKey }
    let candidateType: String
    let externalLabel: String
    let amount: String
    let currency: CurrencyCode
    let operationCount: Int
    let description: String
    let confidence: String
    let idempotencyKey: String
    let evidenceHash: String
    let suggestedCategoryId: String?
}
```

### 3.32 ScreenshotOcrResponse

```swift
struct ScreenshotOcrResponse: Codable {
    let captureSource: CaptureSource
    let parseVersion: String
    let recognizedAt: String
    let items: [ScreenshotOcrCandidate]
    let warnings: [ScreenshotOcrWarning]
}

struct ScreenshotOcrWarning: Codable {
    let code: String
    let message: String
}
```

### 3.33 PlanningScope

```swift
enum PlanningScope: String, Codable {
    case personal, household
}
```

### 3.34 IncomeConfirmationState

```swift
enum IncomeConfirmationState: String, Codable {
    case planned, confirmed
}
```

### 3.35 AllocationTargetType

```swift
enum AllocationTargetType: String, Codable {
    case expense_category, account, asset, investment_asset_category
}
```

### 3.36 AllocationMode

```swift
enum AllocationMode: String, Codable {
    case amount, percent
}
```

### 3.37 AllocationRecurrenceType

```swift
enum AllocationRecurrenceType: String, Codable {
    case regular, one_off
}
```

### 3.38 AllocationProgressStatus

```swift
enum AllocationProgressStatus: String, Codable {
    case on_track, needs_attention, no_actuals, target_attention, not_applicable
}
```

### 3.39 PlanningPlan

```swift
struct PlanningPlan: Codable, Identifiable {
    let id: String
    let scope: PlanningScope
    let month: String // YYYY-MM
    let currency: CurrencyCode
    let householdId: String?
    let summary: PlanningSummary
    let incomeSources: [PlanningIncomeSource]
    let allocations: [PlanningAllocation]
    let version: Int?
}

struct PlanningSummary: Codable {
    let totalPlannedIncome: String
    let totalConfirmedIncome: String
    let totalAllocatedAmount: String
    let unallocatedAmount: String
    let previousMonthSurplus: String
    let underallocated: Bool
    let overallocated: Bool
}
```

### 3.40 PlanningIncomeSource

```swift
struct PlanningIncomeSource: Codable, Identifiable {
    let id: String
    let planId: String
    let amount: String
    let source: String
    let description: String?
    let dayOfMonth: Int
    let effectiveDate: String?
    let confirmationState: IncomeConfirmationState
    let confirmedAt: String?
    let version: Int?
}
```

### 3.41 PlanningAllocation

```swift
struct PlanningAllocation: Codable, Identifiable {
    let id: String
    let planId: String
    let targetType: AllocationTargetType
    let targetId: String?
    let targetSnapshot: [String: JSONValue]? // flexible object
    let requiresAttention: Bool
    let attentionReason: String?
    let comment: String?
    let allocationMode: AllocationMode
    let allocationValue: String
    let recurrenceType: AllocationRecurrenceType?
    let isSavingsGoal: Bool
    let goalTargetAmount: String?
    let goalDueMonth: String?
    let goalMonthlyAmount: String?
    let calculatedAmount: String
    let actualAmount: String?
    let varianceAmount: String?
    let progressPercent: String?
    let progressStatus: AllocationProgressStatus?
    let status: String?
    let version: Int?
}

// Helper for flexible JSON values
enum JSONValue: Codable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null
}
```

### 3.42 PlanningPlanCreateRequest

```swift
struct PlanningPlanCreateRequest: Codable {
    let scope: PlanningScope
    let month: String
    let currency: CurrencyCode
    let householdId: String?
}
```

### 3.43 PlanningPlanCopyRequest

```swift
struct PlanningPlanCopyRequest: Codable {
    let targetMonth: String
}
```

### 3.44 PlanningIncomeSourceCreateRequest

```swift
struct PlanningIncomeSourceCreateRequest: Codable {
    let amount: String
    let source: String
    let description: String?
    let dayOfMonth: Int
    let effectiveDate: String?
}
```

### 3.45 PlanningIncomeSourceUpdateRequest

```swift
struct PlanningIncomeSourceUpdateRequest: Codable {
    let amount: String?
    let source: String?
    let description: String?
    let dayOfMonth: Int?
    let version: Int?
}
```

### 3.46 PlanningAllocationCreateRequest

```swift
struct PlanningAllocationCreateRequest: Codable {
    let targetType: AllocationTargetType
    let targetId: String
    let comment: String?
    let allocationMode: AllocationMode
    let allocationValue: String
    let recurrenceType: AllocationRecurrenceType?
    let isSavingsGoal: Bool?
    let goalTargetAmount: String?
    let goalDueMonth: String?
}
```

### 3.47 PlanningAllocationUpdateRequest

```swift
struct PlanningAllocationUpdateRequest: Codable {
    let targetType: AllocationTargetType?
    let targetId: String?
    let comment: String?
    let allocationMode: AllocationMode?
    let allocationValue: String?
    let recurrenceType: AllocationRecurrenceType?
    let isSavingsGoal: Bool?
    let goalTargetAmount: String?
    let goalDueMonth: String?
    let version: Int?
}
```

### 3.48 ReportMode

```swift
enum ReportMode: String, Codable {
    case personal
    case shared_family_report
    case combined_viewer_overview
}
```

### 3.49 ReportBucket

```swift
enum ReportBucket: String, Codable {
    case day, month
}
```

### 3.50 SessionStatus

```swift
struct SessionStatus: Codable {
    let isAuthenticated: Bool
    let displayName: String?
    let householdId: String?
}
```

### 3.51 ActorContext

```swift
struct ActorContext: Codable {
    let userId: String
    let sessionId: String?
    let memberships: [ActorMembership]
}

struct ActorMembership: Codable {
    let householdId: String
    let status: String
}
```

### 3.52 RegistrationResult

```swift
enum RegistrationResult {
    case authenticated(SessionStatus)
    case accepted(message: String)
}
```

### 3.53 FinanceError

```swift
struct FinanceError: Codable {
    let code: String
    let message: String
    let requestId: String
    let details: [FinanceErrorDetail]?
}

struct FinanceErrorDetail: Codable {
    let field: String?
    let reason: String?
    let allowedValues: [String]?
}
```

### 3.54 PageInfo

```swift
struct PageInfo: Codable {
    let limit: Int
    let nextCursor: String?
    let hasMore: Bool
}
```

### 3.55 FinanceDashboard (aggregation model)

```swift
@Observable
final class FinanceDashboard {
    var session: SessionStatus
    var accounts: [Account]
    var categories: [Category]
    var transactions: [Transaction]
    var totals: [MoneyTotal]
    var reportTransferCount: Int
    var assetCategories: [AssetCategory]
    var assetCategoryGroups: [AssetCategoryGroup]
    var investmentsByCurrency: [MoneyAmount]
    var investmentsTotal: MoneyAmount?
}
```

### 3.56 FinanceMode (UI enum)

```swift
enum FinanceMode: String, CaseIterable {
    case personal, shared, overview

    var title: String {
        switch self {
        case .personal: return "Личное"
        case .shared: return "Общее"
        case .overview: return "Мой обзор"
        }
    }
}
```

---

## 4. API Client

Протокол `FinanceApiClient`. Реализация `LiveFinanceApiClient` через `URLSession`.

### 4.1 Auth

```swift
func login(email: String, password: String) async throws -> SessionStatus
func register(email: String, password: String, displayName: String?) async throws -> RegistrationResult
func sessionStatus() async throws -> SessionStatus
func logout() async throws
```

### 4.2 Accounts

```swift
func listAccounts(limit: Int? = nil, cursor: String? = nil, ownershipType: OwnershipType? = nil, householdId: String? = nil, status: RecordStatus? = nil, q: String? = nil, sort: String? = nil) async throws -> ([Account], PageInfo)
func getAccount(accountId: String) async throws -> Account
func createAccount(_ request: AccountCreateRequest) async throws -> Account
func updateAccount(accountId: String, _ request: AccountUpdateRequest) async throws -> Account
func deleteAccount(accountId: String) async throws
func archiveAccount(accountId: String) async throws -> Account
func restoreAccount(accountId: String) async throws -> Account
func autocompleteAccounts(q: String, limit: Int? = nil, ownershipType: OwnershipType? = nil, householdId: String? = nil) async throws -> [AccountAutocompleteItem]
```

### 4.3 Asset Categories

```swift
func listAssetCategories(limit: Int? = nil, cursor: String? = nil, scopeType: AssetCategoryScope? = nil, householdId: String? = nil, recordStatus: RecordStatus? = nil, isInvestment: Bool? = nil, q: String? = nil) async throws -> ([AssetCategory], PageInfo)
func getAssetCategory(assetCategoryId: String) async throws -> AssetCategory
func createAssetCategory(_ request: AssetCategoryCreateRequest) async throws -> AssetCategory
func updateAssetCategory(assetCategoryId: String, _ request: AssetCategoryUpdateRequest) async throws -> AssetCategory
func deleteAssetCategory(assetCategoryId: String) async throws
func archiveAssetCategory(assetCategoryId: String) async throws -> AssetCategory
func restoreAssetCategory(assetCategoryId: String) async throws -> AssetCategory
```

### 4.4 Transactions

```swift
func listTransactions(limit: Int? = nil, cursor: String? = nil, accountId: String? = nil, categoryId: String? = nil, transactionType: TransactionType? = nil, householdId: String? = nil, ownershipType: OwnershipType? = nil, startDate: String? = nil, endDate: String? = nil, status: RecordStatus? = nil, q: String? = nil, sort: String? = nil) async throws -> ([Transaction], PageInfo)
func getTransaction(transactionId: String) async throws -> Transaction
func createTransaction(_ request: TransactionCreateRequest) async throws -> Transaction
func updateTransaction(transactionId: String, _ request: TransactionUpdateRequest) async throws -> Transaction
func deleteTransaction(transactionId: String) async throws
func restoreTransaction(transactionId: String) async throws -> Transaction
```

### 4.5 Categories

```swift
func listCategories(limit: Int? = nil, cursor: String? = nil, scope: CategoryScope? = nil, type: CategoryType? = nil, householdId: String? = nil, status: RecordStatus? = nil, q: String? = nil, sort: String? = nil) async throws -> ([Category], PageInfo)
func getCategory(categoryId: String) async throws -> Category
func createCategory(_ request: CategoryCreateRequest) async throws -> Category
func updateCategory(categoryId: String, _ request: CategoryUpdateRequest) async throws -> Category
func deleteCategory(categoryId: String) async throws
func archiveCategory(categoryId: String) async throws -> Category
func restoreCategory(categoryId: String) async throws -> Category
func autocompleteCategories(q: String, limit: Int? = nil, scope: CategoryScope? = nil, type: CategoryType? = nil, householdId: String? = nil) async throws -> [CategoryAutocompleteItem]
```

### 4.6 Capture Drafts

```swift
func listCaptureDrafts(limit: Int? = nil, status: CaptureDraftStatus? = nil) async throws -> ([CaptureDraft], PageInfo)
func createCaptureDraft(_ request: CaptureDraftCreateRequest) async throws -> CaptureDraft
func updateCaptureDraft(draftId: String, _ request: CaptureDraftUpdateRequest) async throws -> CaptureDraft
func confirmCaptureDraft(draftId: String) async throws -> CaptureDraft
func discardCaptureDraft(draftId: String) async throws
func screenshotOcr(imageData: Data, contentType: String, capturedAt: String?, householdId: String?) async throws -> ScreenshotOcrResponse
func putCategoryMapping(externalLabel: String, categoryId: String, householdId: String?) async throws -> CategoryMappingResult
```

### 4.7 Reports

```swift
func getReportSummary(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil) async throws -> ReportSummary
func getReportCategoryBreakdown(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil) async throws -> ReportCategoryBreakdown
func getReportAccountBalances(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, currency: CurrencyCode? = nil) async throws -> ReportAccountBalances
func getReportCashFlow(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, bucket: ReportBucket? = nil, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil) async throws -> ReportCashFlow
func getReportTransactions(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil, limit: Int? = nil, cursor: String? = nil, sort: String? = nil) async throws -> ReportTransactionDrillDown
```

### 4.8 Planning

```swift
func getPlanningPlan(scope: PlanningScope, month: String, householdId: String? = nil) async throws -> PlanningPlan?
func listPlanningPlanHistory(scope: PlanningScope, householdId: String? = nil) async throws -> [PlanningPlan]
func createPlanningPlan(_ request: PlanningPlanCreateRequest) async throws -> PlanningPlan
func getPlanningPlan(planId: String) async throws -> PlanningPlan
func copyPlanningPlan(planId: String, _ request: PlanningPlanCopyRequest) async throws -> PlanningPlan
func createPlanningIncomeSource(planId: String, _ request: PlanningIncomeSourceCreateRequest) async throws -> PlanningIncomeSource
func updatePlanningIncomeSource(incomeSourceId: String, _ request: PlanningIncomeSourceUpdateRequest) async throws -> PlanningIncomeSource
func confirmPlanningIncomeSource(incomeSourceId: String) async throws -> PlanningIncomeSource
func deletePlanningIncomeSource(incomeSourceId: String) async throws
func createPlanningAllocation(planId: String, _ request: PlanningAllocationCreateRequest) async throws -> PlanningAllocation
func updatePlanningAllocation(allocationId: String, _ request: PlanningAllocationUpdateRequest) async throws -> PlanningAllocation
func deletePlanningAllocation(allocationId: String) async throws
```

### 4.9 Dashboard (aggregate helper)

```swift
func dashboard(startDate: String? = nil, endDate: String? = nil) async throws -> FinanceDashboard
```

Метод `dashboard` выполняет несколько последовательных запросов (как в Android `ApiClient.dashboard()`):
1. GET `/sessions/current` → session
2. GET `/accounts` → accounts
3. GET `/categories` → categories
4. GET `/asset-categories` → asset categories
5. GET `/transactions` с date filter → transactions
6. GET `/reports/summary` → totals
7. GET `/reports/account-balances` → assetCategoryGroups, investmentsByCurrency, investmentsTotal
8. GET `/reports/transactions` (transfer count) → reportTransferCount

---

## 5. Экраны (SwiftUI Views)

### 5.1 FinanceAppView (Root)

| Параметр | Значение |
|---|---|
| Имя | `FinanceAppView` |
| Навигация | `TabView` |
| Содержимое | Если не аутентифицирован → `SignInCard`. Иначе → 5 табов |
| @State | `selectedTab: Tab`, `financeMode: FinanceMode`, `dashboard: FinanceDashboard?`, `isLoading: Bool`, `message: String?` |

### 5.2 SignInCard

| Параметр | Значение |
|---|---|
| Имя | `SignInCard` |
| Навигация | Встроен в FinanceAppView, не отдельный экран |
| UI | Card с переключателем Login/Register. Email, Password, Confirm Password (register), DisplayName (register). Кнопка «Войти» / «Создать аккаунт» |
| API | `login()`, `register()` |
| @State | `authMode: AuthMode`, `email: String`, `password: String`, `confirmPassword: String`, `displayName: String` |

### 5.3 HomeTab

| Параметр | Значение |
|---|---|
| Имя | `HomeTab` |
| NavigationContext | Внутри Tab 0 |
| UI | ModeChips, PlanningEntryCard, CapitalCard, AssetChips (LazyRow), MonthExpenseCard, TopCategoriesCard (top 3), RecentOperationsCard (top 4) |
| API | Данные из `dashboard` |
| @State | Зависит от `DashboardView` |

### 5.4 OperationsTab

| Параметр | Значение |
|---|---|
| Имя | `OperationsTab` |
| NavigationContext | Внутри Tab 1 |
| UI | ModeChips, CaptureDraftReviewCard, список операций (сортировка ASC — от ранних к поздним по `sortDateKey`), TransactionRow для каждой |
| API | `dashboard`, `listCaptureDrafts()`, `screenshotOcr()`, `createCaptureDraft()`, `confirmCaptureDraft()`, `discardCaptureDraft()`, `deleteTransaction()` |
| @State | `captureDrafts`, `screenshotAggregateDrafts`, `captureIsLoading`, `captureMessage`, `screenshotOcrStatus` |

**КРИТИЧНО**: Операции сортируются ASC (от ранних к поздним), НЕ DESC.

### 5.5 CaptureDraftReviewCard

| Параметр | Значение |
|---|---|
| Имя | `CaptureDraftReviewCard` |
| UI | Кнопка «Выбрать скриншот», OCR статус, ScreenshotAggregateDraftList, список CaptureDraftRow |
| API | Косвенно через OperationsTab |
| Особенность | PhotosPicker для выбора скриншота → отправка в backend OCR |

### 5.6 CaptureDraftRow

| Параметр | Значение |
|---|---|
| Имя | `CaptureDraftRow` |
| UI | Название, сумма, точность, дата, picker для счёта, picker для категории, кнопки «Отклонить» / «Подтвердить» |
| @State | `selectedAccountId`, `selectedCategoryId`, `amount`, `occurredDate` |

### 5.7 AssetsTab

| Параметр | Значение |
|---|---|
| Имя | `AssetsTab` |
| NavigationContext | Внутри Tab 2 |
| UI | ModeChips, кнопка «Добавить категорию активов», ReorderableAssetCategoryList (категории с вложенными счетами), legacy AssetCategoryCard группы |
| API | `dashboard`, `createAssetCategory()`, `updateAssetCategory()`, `archiveAssetCategory()`, `createAccount()`, `updateAccount()`, `archiveAccount()` |
| @State | `assetGroupNames`, `addAccountState`, `showAssetCategorySheet` |

### 5.8 AssetCategoryGroupCard

| Параметр | Значение |
|---|---|
| Имя | `AssetCategoryGroupCard` |
| UI | Expandable card: иконка + название + баланс. Внутри: список AccountRow, кнопка «Добавить счет». Edit dialog для имени, ручной суммы, флага инвестиции. Delete confirmation. |
| API | Через callbacks |
| @State | `isExpanded`, `isEditing`, `editName`, `editInvestment`, `editManualAmount`, `confirmArchive` |

### 5.9 AssetCategorySheet (modal)

| Параметр | Значение |
|---|---|
| Имя | `AssetCategorySheet` |
| UI | Sheet с полями: название, доступ (Personal/Shared), тип актива, иконка picker, валюта, ручная сумма, чекбокс «Инвестиционная» |
| API | `createAssetCategory()` |

### 5.10 AddAccountSheet (modal)

| Параметр | Значение |
|---|---|
| Имя | `AddAccountSheet` |
| UI | Sheet: название, баланс, валюта, режим (Personal/Shared) |
| API | `createAccount()` |

### 5.11 CategoriesTab

| Параметр | Значение |
|---|---|
| Имя | `CategoriesTab` |
| NavigationContext | Внутри Tab 3 |
| UI | CategoryManagementCard: тип (expense/income), режим, поле нового названия, кнопка «Добавить», список активных категорий с inline edit и архив |
| API | `createCategory()`, `updateCategory()`, `archiveCategory()` |
| @State | `type`, `mode`, `newCategoryName` |

### 5.12 AnalyticsTab

| Параметр | Значение |
|---|---|
| Имя | `AnalyticsTab` |
| NavigationContext | Внутри Tab 4 |
| UI | ModeChips, AnalyticsSubsectionTabs (Summary / Planning). **Summary**: ReportMonthSwitcher, AnalyticsSummaryCard, InvestmentsCard, CategoryBreakdownCard (**ВСЕ категории**, не 5), CapitalBreakdownCard. **Planning**: PlanningView |
| API | `dashboard()`, все planning API |
| @State | `selectedSubsection`, `selectedReportMonth` |

**КРИТИЧНО**: Категории в аналитике отображаются ВСЕ, а не ограниченное количество. Фильтровать использованные allocation категории нужно (исключать уже привязанные к allocations при создании новых).

### 5.13 PlanningView

| Параметр | Значение |
|---|---|
| Имя | `PlanningView` |
| UI | PlanningScopeCard (month picker, mode chips, currency), PlanningOverviewGate (если Overview), PlanningPlanCard (создать/метрики), IncomeSourcesCard, AllocationsCard, PlanningHistoryCard |
| API | Все planning API |
| @State | `month`, `plan`, `history`, `isLoading`, `message`, `showCategorySheet`, `showAccountSheet` |

### 5.14 AllocationsCard

| Параметр | Значение |
|---|---|
| Имя | `AllocationsCard` |
| UI | PlanningAllocationEditor (target type chips, category/account picker, recurrence, allocation mode amount/percent, value input, savings goal toggle, goal target amount, goal due month picker, comment), кнопка «Добавить распределение», список AllocationRow |
| API | `createPlanningAllocation()`, `updatePlanningAllocation()`, `deletePlanningAllocation()` |

**КРИТИЧНО**: Фильтровать использованные allocation категории (usedTargetIds). Накопительная цель (savings goal) доступна ТОЛЬКО для `investment_asset_category`. Убрать дублирование план/сумма в allocations — `calculatedAmount` рассчитывается сервером, не дублируется клиентом.

### 5.15 QuickAddSheet (modal)

| Параметр | Значение |
|---|---|
| Имя | `QuickAddSheet` |
| UI | Sheet: тип (Expense/Income/Transfer), режим, сумма, дата, picker счёта, picker категории, picker destination (transfer) |
| API | `createTransaction()` (expense/income/transfer) |
| @State | `draft: QuickAddDraft`, `errorMessage` |

### 5.16 PlanningCreateCategorySheet (modal)

| Параметр | Значение |
|---|---|
| Имя | `PlanningCreateCategorySheet` |
| UI | Sheet: название категории, кнопки Отмена/Создать |
| API | `createCategory()` |

### 5.17 PlanningCreateAccountSheet (modal)

| Параметр | Значение |
|---|---|
| Имя | `PlanningCreateAccountSheet` |
| UI | Sheet: название, тип (brokerage/deposit/metal/other), валюта |
| API | `createAccount()` |

---

## 6. Навигация

### 6.1 TabView

```
Tab 0: Home        → "Главная"
Tab 1: Operations  → "Операции"
Tab 2: Assets      → "Активы"
Tab 3: Categories  → "Категории"
Tab 4: Analytics   → "Аналитика"
```

### 6.2 NavigationStack

Каждый таб имеет свой `NavigationStack`. Внутри табов навигация через `NavigationLink` к детальным экранам (пока нет отдельных detail screen — всё inline).

### 6.3 Modal sheets

| Sheet | Trigger |
|---|---|
| QuickAddSheet | FAB кнопка «+» |
| AddAccountSheet | Кнопка «Добавить счёт» в Assets |
| AssetCategorySheet | Кнопка «Добавить категорию активов» в Assets |
| PlanningCreateCategorySheet | Кнопка в Planning allocations |
| PlanningCreateAccountSheet | Кнопка в Planning allocations |
| AccountEditDialog | IconButton edit на AccountRow |
| DatePickerDialog | DatePickerField |

### 6.4 FAB

Плавающая кнопка «+» (доступна только при аутентификации). Открывает `QuickAddSheet`.

---

## 7. Волны реализации

### Волна 0: Foundation (Models + API Client)

**Задачи:**
- Создать Xcode проект в `apps/ios/`
- Все Codable модели (секция 3)
- `ApiResult<T>` enum
- `FinanceApiClient` protocol
- `LiveApiClient` (URLSession): auth endpoints
- `CSRFTokenStore` (Keychain)
- `RequestBuilder` (URL, query, JSON body, multipart)
- `ResponseParser` (JSON parsing, envelope unwrapping)
- Модульные тесты на модели (Codable round-trip)
- Модульные тесты на API client (mock URLProtocol)

**Definition of Done:** Unit-тесты проходят. Login/register/logout работает на реальном сервере.

### Волна 1: Auth + Home + Operations

**Задачи:**
- `FinanceAppView` с TabView
- `SignInCard` (login/register)
- `HomeTab`: CapitalCard, MonthExpenseCard, TopCategoriesCard, RecentOperationsCard, PlanningEntryCard, AssetChips
- `OperationsTab`: TransactionRow, OperationsList (ASC sort)
- `QuickAddSheet` (expense/income/transfer)
- `DashboardView` helper (фильтрация по FinanceMode, capital, expenses, top categories)
- `ModeChips` (Personal/Shared/Overview)
- Money/Date formatting utilities
- `UserFacingText` (seed text translations)

**Definition of Done:** Логин, просмотр дома, операций, добавление расхода/дохода/перевода.

### Волна 2: Assets + Categories

**Задачи:**
- `AssetsTab`: AssetCategoryGroupCard, ReorderableAssetCategoryList, AccountRow, AccountEditDialog
- `AssetCategorySheet` (create asset category)
- `AddAccountSheet` (create account)
- Legacy group migration (аналог `onMigrateLegacyGroupToInvestment`, `onCreateLegacyManualCategory`)
- AssetCategoryIcons
- `CategoriesTab`: CategoryManagementCard, inline edit/rename, archive
- Drag-and-drop reordering для asset categories (аналог Android `detectDragGesturesAfterLongPress`)

**Definition of Done:** CRUD счетов, категорий активов, категорий. Редактирование баланса, имени, валюты.

### Волна 3: Analytics + Planning

**Задачи:**
- `AnalyticsTab`: Summary/Planning subsection tabs
- `ReportMonthSwitcher`
- `AnalyticsSummaryCard`, `InvestmentsCard`, `CategoryBreakdownCard` (**ВСЕ категории**), `CapitalBreakdownCard`
- `PlanningView`: PlanningScopeCard, PlanningPlanCard, IncomeSourcesCard, AllocationsCard, PlanningHistoryCard
- `PlanningAllocationEditor`: target type, category picker, allocation mode, recurrence, savings goal
- `PlanningCreateCategorySheet`, `PlanningCreateAccountSheet`
- Копирование планов из истории
- Фильтрация использованных allocation targets
- Уведомления (UNUserNotificationCenter) — планирование напоминаний

**Definition of Done:** Полный CRUD планирования. Аналитика показывает все категории. Копирование планов.

### Волна 4: Capture Drafts + OCR

**Задачи:**
- `CaptureDraftReviewCard`, `CaptureDraftRow`
- `ScreenshotAggregateDraftList`
- PhotosPicker → screenshot upload
- `screenshotOcr()` multipart API
- `createCaptureDraft()`, `confirmCaptureDraft()`, `discardCaptureDraft()`
- `CategoryAggregateMappingStore` (Keychain)
- Client-side `CaptureParser` (fallback для нераспознанных скринов)
- `CaptureCandidate`, `CategoryAggregateCandidate` models
- Category mapping: auto-match из сохранённых маппингов

**Definition of Done:** OCR скриншотов → кандидаты → маппинг категорий → черновики → подтверждение → транзакция.

### Волна 5: Полировка

**Задачи:**
- Accessibility: VoiceOver labels, Dynamic Type
- Haptic feedback на действиях
- Pull-to-refresh на каждом табе
- Error banner (retry)
- Empty states (иллюстрации + текст)
- Loading skeletons
- Тёмная тема (dark mode colors)
- Localizable.strings — все строки на русском
- iPad adaptation (NavigationSplitView)
- Keyboard avoidance
- Unit/UI test coverage > 70% критических путей
- Performance: Instruments, memory leaks

**Definition of Done:** Приложение готово к TestFlight. Нет crashes. Все экраны соответствуют Android-паритету.

---

## 8. UX-решения

### 8.1 Форматирование денег

- `Decimal` → строка через `NumberFormatter` с locale `ru_RU`
- 2 знака после запятой
- Формат: `1 234,56 $currency` (пробел как разделитель тысяч, запятая как десятичный)
- Валюта: `₽ RUB`, `$ USD`, `€ EUR`, `граммы XAU`
- Отрицательные суммы: красный `Color(0xFFE35D4F)`
- Доходы: зелёный `Color(0xFF2E7D62)`
- Расходы: красный `Color(0xFFE35D4F)`
- Переводы: синий `Color(0xFF5B6EE1)`
- Инвестиции: бирюзовый `Color(0xFF227C9D)`

### 8.2 Даты

- Отображение: `d MMMM yyyy` (25 июня 2026) через `DateFormatter` с locale `ru_RU`
- API-формат: `yyyy-MM-dd` (DateOnly), `yyyy-MM-ddTHH:mm:ssZ` (DateTime)
- Месяц в аналитике/planning: `Июнь 2026` (standalone month name)
- YearMonth: `yyyy-MM` строка

### 8.3 Ошибки

- Красный баннер внизу экрана при ошибке
- Текст ошибки из `FinanceError.message` (userFacing)
- Кнопка «Повторить» при network error
- Специальные сообщения:
  - `ACCOUNT_CURRENCY_IMMUTABLE_AFTER_TRANSACTIONS` → «Валюту счёта нельзя изменить после создания операций»
  - 401/403 → «Сессия истекла. Войдите снова.» → auto-logout
  - Planning 404 → «План для выбранного месяца ещё не создан»

### 8.4 Loading states

- `ProgressView()` ( spinner) при загрузке
- Кнопки disabled при `isLoading`
- Текст «Обновляем данные», «Сохраняем», «Удаляем» и т.д.

### 8.5 Цветовая палитра (из Android Theme.kt)

| Элемент | Цвет |
|---|---|
| Primary | `#256B5F` (тёмно-бирюзовый) |
| OnPrimary | White |
| PrimaryContainer | `#D3F2EA` |
| Background | `#FBFCFA` |
| Surface | `#FBFCFA` |
| Income | `#2E7D62` |
| Expense | `#E35D4F` |
| Transfer | `#5B6EE1` |
| Investment | `#227C9D` |
| Warning | `#8A6A12` |
| Error | `#E35D4F` |
| Planning primary | `#4267D5` |
| Analytics accent | `#6D5BD0` |

### 8.6 Иконки (SF Symbols)

| Android drawable | iOS SF Symbol |
|---|---|
| ic_wallet_24 | `wallet.pass` |
| ic_refresh_24 | `arrow.clockwise` |
| ic_add_24 | `plus` |
| ic_delete_24 | `trash` |
| ic_edit_24 | `pencil` |
| ic_receipt_24 | `receipt` |
| ic_analytics_24 | `chart.bar` |
| ic_category_24 | `tag` |
| ic_card_24 | `creditcard` |
| ic_bank_24 | `building.columns` |
| ic_cash_24 | `banknote` |
| ic_savings_24 | `piggybank` |
| ic_chart_24 | `chart.line.uptrend.xyaxis` |
| ic_gold_bar_24 | `bitcoinsign.bank` |
| ic_trending_up_24 | `arrow.up.right` |
| ic_coin_24 | `centsign.circle` |

---

## 9. Privacy инварианты (из OpenAPI)

1. **Personal data is owner-only** — личные данные доступны только владельцу.
2. **Shared data visible to active household members only** — общие данные видны только активным членам семьи.
3. **Reports support `personal`, `shared_family_report`, `combined_viewer_overview`** — iOS поддерживает все три режима.
4. **Every list, report, search, autocomplete filters visible rows BEFORE any aggregation or pagination** — фильтрация видимости ДО агрегации.
5. **Responses never expose hidden counts, filtered-out counts, hidden facets, or diagnostics** — iOS не отображает скрытые счётчики.
6. **Screenshot OCR: raw image bytes and OCR text are never stored or returned** — iOS отправляет скриншот как temporary upload, не сохраняет raw данные.
7. **Capture drafts: only sanitized structured fields** — iOS работает только с `CaptureDraftDto` полями.
8. **Category mapping stores only hash, not externalLabel** — `CategoryAggregateMappingStore` хранит хэш, не сырой label.
9. **Search queries are not logged as raw payload** — поиск через параметр `q` без логирования.
10. **`sourceType` is always `manual` in MVP** — iOS не отправляет другие sourceType.
11. **Transfers: same-scope only** — `personal_same_owner` или `household_same_household`. iOS валидирует transfer pair перед отправкой.
12. **Password minimum 12 characters** — валидация при регистрации.

---

## 10. Риски

### 10.1 Что можно упростить

| Компонент | Упрощение | Причина |
|---|---|---|
| Drag-and-drop reorder asset categories | Долгое нажатие + move, вместо полноценного drag | SwiftUI `.onMove` работает иначе, чем Android `detectDragGesturesAfterLongPress` |
| Client-side CaptureParser | Отложить на Волну 5, полагаться на backend OCR | Backend OCR уже в проде, клиентский парсер — fallback |
| Legacy group migration | Упростить: только rename + manual category creation | Полный migration с rollback — сложный multi-step, можно упростить |
| Notifications (UNUserNotificationCenter) | Базовые local notifications, без scheduling | Полная система уведомлений — отдельный проект |
| iPad NavigationSplitView | Базовая адаптация, без sidebar | Можно добавить позже |

### 10.2 Что критично (НЕ упрощать)

| Компонент | Причина |
|---|---|
| Cookie-based CSRF auth | Паритет с PWA, безопасность. НЕ bearer token |
| Money как Decimal/String | Потеря точности при Float/Double недопустима |
| Operations ASC sort | Пользовательский паттерн: от ранних к поздним |
| ВСЕ категории в аналитике | Не обрезать список. Пользователь должен видеть полную разбивку |
| Фильтрация использованных allocation targets | Предотвращает дублирование allocations |
| Privacy invariants (секция 9) | Безопасность данных пользователей |
| Savings goal только для investment_asset_category | Бизнес-логика сервера |
| Подтверждение capture draft → manual transaction | Черновик НЕ создаёт транзакцию автоматически |
| Planning confirm income source → НЕ создаёт транзакцию | Только устанавливает confirmation state |
| `isPaymentAccount` → фильтрация source accounts для expense | Счета с `isPaymentAccount: false` не предлагать как source для расходов |

### 10.3 Technical risks

| Риск | Mitigation |
|---|---|
| CSRF token rotation | Проверять `expiresAt` перед каждым запросом, обновлять при login |
| Cookie не отправляется автоматически | Убедиться что `URLSession` configuration использует shared cookie storage, и домен совпадает |
| Multipart upload (screenshot OCR) | Ручная сборка multipart body через `Data` writing, покрыть unit-тестами |
| `targetSnapshot` — flexible JSON | Использовать `JSONValue` enum или `[String: Any]` с ручным парсингом |
| Keychain access в background | Минимизировать keychain calls, кэшировать в memory |
| SwiftUI performance с большими списками | `LazyVStack`/`LazyHStack`, не загружать все данные сразу |
| YearMonth parsing | Использовать `DateComponents` + `Calendar`, не парсить строку вручную |
