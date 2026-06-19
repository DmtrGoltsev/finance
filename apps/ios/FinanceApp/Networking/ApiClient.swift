import Foundation

protocol FinanceApiClient: Sendable {
    func login(email: String, password: String) async throws -> SessionStatus
    func register(email: String, password: String, displayName: String?) async throws -> RegistrationResult
    func sessionStatus() async throws -> SessionStatus
    func logout() async throws

    func listAccounts(limit: Int?, cursor: String?, ownershipType: OwnershipType?, householdId: String?, status: RecordStatus?, q: String?, sort: String?) async throws -> ([Account], PageInfo)
    func getAccount(accountId: String) async throws -> Account
    func createAccount(_ request: AccountCreateRequest) async throws -> Account
    func updateAccount(accountId: String, _ request: AccountUpdateRequest) async throws -> Account
    func deleteAccount(accountId: String) async throws
    func archiveAccount(accountId: String) async throws -> Account
    func restoreAccount(accountId: String) async throws -> Account
    func autocompleteAccounts(q: String, limit: Int?, ownershipType: OwnershipType?, householdId: String?) async throws -> [AccountAutocompleteItem]

    func listAssetCategories(limit: Int?, cursor: String?, scopeType: AssetCategoryScope?, householdId: String?, recordStatus: RecordStatus?, isInvestment: Bool?, q: String?) async throws -> ([AssetCategory], PageInfo)
    func getAssetCategory(assetCategoryId: String) async throws -> AssetCategory
    func createAssetCategory(_ request: AssetCategoryCreateRequest) async throws -> AssetCategory
    func updateAssetCategory(assetCategoryId: String, _ request: AssetCategoryUpdateRequest) async throws -> AssetCategory
    func deleteAssetCategory(assetCategoryId: String) async throws
    func archiveAssetCategory(assetCategoryId: String) async throws -> AssetCategory
    func restoreAssetCategory(assetCategoryId: String) async throws -> AssetCategory

    func listTransactions(limit: Int?, cursor: String?, accountId: String?, categoryId: String?, transactionType: TransactionType?, householdId: String?, ownershipType: OwnershipType?, startDate: String?, endDate: String?, status: RecordStatus?, q: String?, sort: String?) async throws -> ([Transaction], PageInfo)
    func getTransaction(transactionId: String) async throws -> Transaction
    func createTransaction(_ request: TransactionCreateRequest) async throws -> Transaction
    func updateTransaction(transactionId: String, _ request: TransactionUpdateRequest) async throws -> Transaction
    func deleteTransaction(transactionId: String) async throws
    func restoreTransaction(transactionId: String) async throws -> Transaction

    func listCategories(limit: Int?, cursor: String?, scope: CategoryScope?, type: CategoryType?, householdId: String?, status: RecordStatus?, q: String?, sort: String?) async throws -> ([Category], PageInfo)
    func getCategory(categoryId: String) async throws -> Category
    func createCategory(_ request: CategoryCreateRequest) async throws -> Category
    func updateCategory(categoryId: String, _ request: CategoryUpdateRequest) async throws -> Category
    func deleteCategory(categoryId: String) async throws
    func archiveCategory(categoryId: String) async throws -> Category
    func restoreCategory(categoryId: String) async throws -> Category
    func autocompleteCategories(q: String, limit: Int?, scope: CategoryScope?, type: CategoryType?, householdId: String?) async throws -> [CategoryAutocompleteItem]

    func listCaptureDrafts(limit: Int?, status: CaptureDraftStatus?) async throws -> ([CaptureDraft], PageInfo)
    func createCaptureDraft(_ request: CaptureDraftCreateRequest) async throws -> CaptureDraft
    func updateCaptureDraft(draftId: String, _ request: CaptureDraftUpdateRequest) async throws -> CaptureDraft
    func confirmCaptureDraft(draftId: String) async throws -> CaptureDraft
    func discardCaptureDraft(draftId: String) async throws
    func screenshotOcr(imageData: Data, contentType: String, capturedAt: String?, householdId: String?) async throws -> ScreenshotOcrResponse
    func putCategoryMapping(externalLabel: String, categoryId: String, householdId: String?) async throws -> CategoryMappingResult

    func getReportSummary(reportMode: ReportMode, householdId: String?, startDate: String, endDate: String, timezone: String, accountIds: [String]?, categoryIds: [String]?, transactionTypes: [TransactionType]?, currency: CurrencyCode?) async throws -> ReportSummary
    func getReportCategoryBreakdown(reportMode: ReportMode, householdId: String?, startDate: String, endDate: String, timezone: String, accountIds: [String]?, categoryIds: [String]?, transactionTypes: [TransactionType]?, currency: CurrencyCode?) async throws -> ReportCategoryBreakdown
    func getReportAccountBalances(reportMode: ReportMode, householdId: String?, startDate: String, endDate: String, timezone: String, accountIds: [String]?, currency: CurrencyCode?) async throws -> ReportAccountBalances
    func getReportCashFlow(reportMode: ReportMode, householdId: String?, startDate: String, endDate: String, timezone: String, bucket: ReportBucket?, accountIds: [String]?, categoryIds: [String]?, transactionTypes: [TransactionType]?, currency: CurrencyCode?) async throws -> ReportCashFlow
    func getReportTransactions(reportMode: ReportMode, householdId: String?, startDate: String, endDate: String, timezone: String, accountIds: [String]?, categoryIds: [String]?, transactionTypes: [TransactionType]?, currency: CurrencyCode?, limit: Int?, cursor: String?, sort: String?) async throws -> ReportTransactionDrillDown

    func getPlanningPlan(scope: PlanningScope, month: String, householdId: String?) async throws -> PlanningPlan?
    func listPlanningPlanHistory(scope: PlanningScope, householdId: String?) async throws -> [PlanningPlan]
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

    func syncPush(_ request: SyncPushRequest) async throws -> SyncPushResponse
    func syncPull(_ request: SyncPullRequest) async throws -> SyncPullResponse

    func dashboard(startDate: String?, endDate: String?) async throws -> FinanceDashboard
}
