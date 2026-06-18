import Foundation

final class LiveApiClient: FinanceApiClient, @unchecked Sendable {
    private let builder: RequestBuilder
    private let session: URLSession
    private let tokenStore: CSRFTokenStore

    init(baseURL: String = "http://45.10.110.42/finance-api", tokenStore: CSRFTokenStore = .shared) {
        self.builder = RequestBuilder(baseURL: baseURL)
        self.tokenStore = tokenStore
        let config = URLSessionConfiguration.default
        config.httpCookieStorage = HTTPCookieStorage.shared
        config.httpShouldSetCookies = true
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 30
        self.session = URLSession(configuration: config)
    }

    // MARK: - Auth

    func login(email: String, password: String) async throws -> SessionStatus {
        let body = try ResponseParser.encode([
            "email": email.trimmingCharacters(in: .whitespacesAndNewlines),
            "password": password,
            "transport": "pwa_cookie"
        ] as [String: String])
        let url = builder.makeURL(path: "/api/v1/sessions")
        var request = builder.makeURLRequest(url: url, method: "POST", body: body)
        request.setValue(nil, forHTTPHeaderField: "X-CSRF-Token")
        let data = try await performRequest(request, expectedCodes: [200, 201])
        let loginResp: LoginResponse = try ResponseParser.unwrapDataEnvelope(LoginResponse.self, from: data)
        if let token = loginResp.csrfToken {
            tokenStore.saveCsrfToken(token)
        }
        if let expiry = loginResp.expiresAt {
            tokenStore.saveSessionExpiry(expiry)
        }
        let actor = loginResp.actor
        let householdId = actor?.memberships.first(where: { $0.status == "active" })?.householdId
        return SessionStatus(
            isAuthenticated: actor != nil,
            displayName: actor.map { "Пользователь \($0.userId.prefix(8))" },
            householdId: householdId
        )
    }

    func register(email: String, password: String, displayName: String?) async throws -> RegistrationResult {
        var body: [String: String] = [
            "email": email.trimmingCharacters(in: .whitespacesAndNewlines),
            "password": password,
            "transport": "pwa_cookie"
        ]
        if let dn = displayName?.trimmingCharacters(in: .whitespacesAndNewlines), !dn.isEmpty {
            body["displayName"] = dn
        }
        let bodyData = try ResponseParser.encode(body)
        let url = builder.makeURL(path: "/api/v1/users")
        var request = builder.makeURLRequest(url: url, method: "POST", body: bodyData)
        request.setValue(nil, forHTTPHeaderField: "X-CSRF-Token")
        let data = try await performRequest(request, expectedCodes: [200, 201, 202])
        if let loginResp = try? ResponseParser.unwrapDataEnvelope(LoginResponse.self, from: data),
           loginResp.csrfToken != nil, loginResp.actor != nil {
            tokenStore.saveCsrfToken(loginResp.csrfToken!)
            if let expiry = loginResp.expiresAt { tokenStore.saveSessionExpiry(expiry) }
            let householdId = loginResp.actor?.memberships.first(where: { $0.status == "active" })?.householdId
            return .authenticated(SessionStatus(isAuthenticated: true, displayName: nil, householdId: householdId))
        }
        return .accepted(message: "Заявка на регистрацию принята")
    }

    func sessionStatus() async throws -> SessionStatus {
        let url = builder.makeURL(path: "/api/v1/sessions/current")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try parseSessionStatus(from: data)
    }

    func logout() async throws {
        let url = builder.makeURL(path: "/api/v1/sessions/current")
        let request = builder.makeURLRequest(url: url, method: "DELETE", csrfToken: csrfToken)
        _ = try? await performRequestRaw(request, expectedCodes: [200, 204])
        tokenStore.clear()
    }

    // MARK: - Accounts

    func listAccounts(limit: Int? = nil, cursor: String? = nil, ownershipType: OwnershipType? = nil, householdId: String? = nil, status: RecordStatus? = nil, q: String? = nil, sort: String? = nil) async throws -> ([Account], PageInfo) {
        var query = [String: String]()
        if let v = limit { query["limit"] = String(v) }
        if let v = cursor { query["cursor"] = v }
        if let v = ownershipType { query["ownershipType"] = v.rawValue }
        if let v = householdId { query["householdId"] = v }
        if let v = status { query["status"] = v.rawValue }
        if let v = q { query["q"] = v }
        if let v = sort { query["sort"] = v }
        let url = builder.makeURL(path: "/api/v1/accounts", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapPageEnvelope(Account.self, from: data)
    }

    func getAccount(accountId: String) async throws -> Account {
        let url = builder.makeURL(path: "/api/v1/accounts/\(accountId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
    }

    func createAccount(_ request: AccountCreateRequest) async throws -> Account {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/accounts")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
    }

    func updateAccount(accountId: String, _ request: AccountUpdateRequest) async throws -> Account {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/accounts/\(accountId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
    }

    func deleteAccount(accountId: String) async throws {
        let url = builder.makeURL(path: "/api/v1/accounts/\(accountId)")
        let req = builder.makeURLRequest(url: url, method: "DELETE", csrfToken: csrfToken)
        _ = try await performRequestRaw(req, expectedCodes: [200, 204])
    }

    func archiveAccount(accountId: String) async throws -> Account {
        let url = builder.makeURL(path: "/api/v1/accounts/\(accountId)/archive")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
    }

    func restoreAccount(accountId: String) async throws -> Account {
        let url = builder.makeURL(path: "/api/v1/accounts/\(accountId)/restore")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
    }

    func autocompleteAccounts(q: String, limit: Int? = nil, ownershipType: OwnershipType? = nil, householdId: String? = nil) async throws -> [AccountAutocompleteItem] {
        var query = ["q": q]
        if let v = limit { query["limit"] = String(v) }
        if let v = ownershipType { query["ownershipType"] = v.rawValue }
        if let v = householdId { query["householdId"] = v }
        let url = builder.makeURL(path: "/api/v1/accounts/autocomplete", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapItemsOnly(AccountAutocompleteItem.self, from: data)
    }

    // MARK: - Asset Categories

    func listAssetCategories(limit: Int? = nil, cursor: String? = nil, scopeType: AssetCategoryScope? = nil, householdId: String? = nil, recordStatus: RecordStatus? = nil, isInvestment: Bool? = nil, q: String? = nil) async throws -> ([AssetCategory], PageInfo) {
        var query = [String: String]()
        if let v = limit { query["limit"] = String(v) }
        if let v = cursor { query["cursor"] = v }
        if let v = scopeType { query["scopeType"] = v.rawValue }
        if let v = householdId { query["householdId"] = v }
        if let v = recordStatus { query["recordStatus"] = v.rawValue }
        if let v = isInvestment { query["isInvestment"] = String(v) }
        if let v = q { query["q"] = v }
        let url = builder.makeURL(path: "/api/v1/asset-categories", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapPageEnvelope(AssetCategory.self, from: data)
    }

    func getAssetCategory(assetCategoryId: String) async throws -> AssetCategory {
        let url = builder.makeURL(path: "/api/v1/asset-categories/\(assetCategoryId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
    }

    func createAssetCategory(_ request: AssetCategoryCreateRequest) async throws -> AssetCategory {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/asset-categories")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
    }

    func updateAssetCategory(assetCategoryId: String, _ request: AssetCategoryUpdateRequest) async throws -> AssetCategory {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/asset-categories/\(assetCategoryId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
    }

    func deleteAssetCategory(assetCategoryId: String) async throws {
        let url = builder.makeURL(path: "/api/v1/asset-categories/\(assetCategoryId)")
        let req = builder.makeURLRequest(url: url, method: "DELETE", csrfToken: csrfToken)
        _ = try await performRequestRaw(req, expectedCodes: [200, 204])
    }

    func archiveAssetCategory(assetCategoryId: String) async throws -> AssetCategory {
        let url = builder.makeURL(path: "/api/v1/asset-categories/\(assetCategoryId)/archive")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
    }

    func restoreAssetCategory(assetCategoryId: String) async throws -> AssetCategory {
        let url = builder.makeURL(path: "/api/v1/asset-categories/\(assetCategoryId)/restore")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
    }

    // MARK: - Transactions

    func listTransactions(limit: Int? = nil, cursor: String? = nil, accountId: String? = nil, categoryId: String? = nil, transactionType: TransactionType? = nil, householdId: String? = nil, ownershipType: OwnershipType? = nil, startDate: String? = nil, endDate: String? = nil, status: RecordStatus? = nil, q: String? = nil, sort: String? = nil) async throws -> ([Transaction], PageInfo) {
        var query = [String: String]()
        if let v = limit { query["limit"] = String(v) }
        if let v = cursor { query["cursor"] = v }
        if let v = accountId { query["accountId"] = v }
        if let v = categoryId { query["categoryId"] = v }
        if let v = transactionType { query["transactionType"] = v.rawValue }
        if let v = householdId { query["householdId"] = v }
        if let v = ownershipType { query["ownershipType"] = v.rawValue }
        if let v = startDate { query["startDate"] = v }
        if let v = endDate { query["endDate"] = v }
        if let v = status { query["status"] = v.rawValue }
        if let v = q { query["q"] = v }
        if let v = sort { query["sort"] = v }
        let url = builder.makeURL(path: "/api/v1/transactions", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapPageEnvelope(Transaction.self, from: data)
    }

    func getTransaction(transactionId: String) async throws -> Transaction {
        let url = builder.makeURL(path: "/api/v1/transactions/\(transactionId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(Transaction.self, from: data)
    }

    func createTransaction(_ request: TransactionCreateRequest) async throws -> Transaction {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/transactions")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(Transaction.self, from: data)
    }

    func updateTransaction(transactionId: String, _ request: TransactionUpdateRequest) async throws -> Transaction {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/transactions/\(transactionId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(Transaction.self, from: data)
    }

    func deleteTransaction(transactionId: String) async throws {
        let url = builder.makeURL(path: "/api/v1/transactions/\(transactionId)")
        let req = builder.makeURLRequest(url: url, method: "DELETE", csrfToken: csrfToken)
        _ = try await performRequestRaw(req, expectedCodes: [200, 204])
    }

    func restoreTransaction(transactionId: String) async throws -> Transaction {
        let url = builder.makeURL(path: "/api/v1/transactions/\(transactionId)/restore")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(Transaction.self, from: data)
    }

    // MARK: - Categories

    func listCategories(limit: Int? = nil, cursor: String? = nil, scope: CategoryScope? = nil, type: CategoryType? = nil, householdId: String? = nil, status: RecordStatus? = nil, q: String? = nil, sort: String? = nil) async throws -> ([Category], PageInfo) {
        var query = [String: String]()
        if let v = limit { query["limit"] = String(v) }
        if let v = cursor { query["cursor"] = v }
        if let v = scope { query["scope"] = v.rawValue }
        if let v = type { query["type"] = v.rawValue }
        if let v = householdId { query["householdId"] = v }
        if let v = status { query["status"] = v.rawValue }
        if let v = q { query["q"] = v }
        if let v = sort { query["sort"] = v }
        let url = builder.makeURL(path: "/api/v1/categories", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapPageEnvelope(Category.self, from: data)
    }

    func getCategory(categoryId: String) async throws -> Category {
        let url = builder.makeURL(path: "/api/v1/categories/\(categoryId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
    }

    func createCategory(_ request: CategoryCreateRequest) async throws -> Category {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/categories")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
    }

    func updateCategory(categoryId: String, _ request: CategoryUpdateRequest) async throws -> Category {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/categories/\(categoryId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
    }

    func deleteCategory(categoryId: String) async throws {
        let url = builder.makeURL(path: "/api/v1/categories/\(categoryId)")
        let req = builder.makeURLRequest(url: url, method: "DELETE", csrfToken: csrfToken)
        _ = try await performRequestRaw(req, expectedCodes: [200, 204])
    }

    func archiveCategory(categoryId: String) async throws -> Category {
        let url = builder.makeURL(path: "/api/v1/categories/\(categoryId)/archive")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
    }

    func restoreCategory(categoryId: String) async throws -> Category {
        let url = builder.makeURL(path: "/api/v1/categories/\(categoryId)/restore")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
    }

    func autocompleteCategories(q: String, limit: Int? = nil, scope: CategoryScope? = nil, type: CategoryType? = nil, householdId: String? = nil) async throws -> [CategoryAutocompleteItem] {
        var query = ["q": q]
        if let v = limit { query["limit"] = String(v) }
        if let v = scope { query["scope"] = v.rawValue }
        if let v = type { query["type"] = v.rawValue }
        if let v = householdId { query["householdId"] = v }
        let url = builder.makeURL(path: "/api/v1/categories/autocomplete", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapItemsOnly(CategoryAutocompleteItem.self, from: data)
    }

    // MARK: - Capture Drafts

    func listCaptureDrafts(limit: Int? = nil, status: CaptureDraftStatus? = nil) async throws -> ([CaptureDraft], PageInfo) {
        var query = [String: String]()
        if let v = limit { query["limit"] = String(v) }
        if let v = status { query["status"] = v.rawValue }
        let url = builder.makeURL(path: "/api/v1/capture-drafts", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapPageEnvelope(CaptureDraft.self, from: data)
    }

    func createCaptureDraft(_ request: CaptureDraftCreateRequest) async throws -> CaptureDraft {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/capture-drafts")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(CaptureDraft.self, from: data)
    }

    func updateCaptureDraft(draftId: String, _ request: CaptureDraftUpdateRequest) async throws -> CaptureDraft {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/capture-drafts/\(draftId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(CaptureDraft.self, from: data)
    }

    func confirmCaptureDraft(draftId: String) async throws -> CaptureDraft {
        let url = builder.makeURL(path: "/api/v1/capture-drafts/\(draftId)/confirm")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(CaptureDraft.self, from: data)
    }

    func discardCaptureDraft(draftId: String) async throws {
        let url = builder.makeURL(path: "/api/v1/capture-drafts/\(draftId)/discard")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        _ = try await performRequestRaw(req, expectedCodes: [200, 204])
    }

    func screenshotOcr(imageData: Data, contentType: String, capturedAt: String?, householdId: String?) async throws -> ScreenshotOcrResponse {
        let url = builder.makeURL(path: "/api/v1/capture-drafts/screenshot-ocr")
        var fields = [String: String]()
        if let v = capturedAt { fields["capturedAt"] = v }
        if let v = householdId { fields["householdId"] = v }
        let req = builder.makeMultipartRequest(
            url: url, fields: fields, fileData: imageData,
            fileName: "screenshot.jpg", contentType: contentType,
            csrfToken: csrfToken
        )
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(ScreenshotOcrResponse.self, from: data)
    }

    func putCategoryMapping(externalLabel: String, categoryId: String, householdId: String?) async throws -> CategoryMappingResult {
        var body: [String: String] = ["externalLabel": externalLabel, "categoryId": categoryId]
        if let v = householdId { body["householdId"] = v }
        let bodyData = try ResponseParser.encode(body)
        let url = builder.makeURL(path: "/api/v1/capture-drafts/category-mappings")
        let req = builder.makeURLRequest(url: url, method: "PUT", body: bodyData, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(CategoryMappingResult.self, from: data)
    }

    // MARK: - Reports

    func getReportSummary(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil) async throws -> ReportSummary {
        var query = reportQuery(reportMode: reportMode, householdId: householdId, startDate: startDate, endDate: endDate, timezone: timezone, accountIds: accountIds, categoryIds: categoryIds, transactionTypes: transactionTypes, currency: currency)
        let url = builder.makeURL(path: "/api/v1/reports/summary", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(ReportSummary.self, from: data)
    }

    func getReportCategoryBreakdown(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil) async throws -> ReportCategoryBreakdown {
        var query = reportQuery(reportMode: reportMode, householdId: householdId, startDate: startDate, endDate: endDate, timezone: timezone, accountIds: accountIds, categoryIds: categoryIds, transactionTypes: transactionTypes, currency: currency)
        let url = builder.makeURL(path: "/api/v1/reports/category-breakdown", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(ReportCategoryBreakdown.self, from: data)
    }

    func getReportAccountBalances(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, currency: CurrencyCode? = nil) async throws -> ReportAccountBalances {
        var query = reportQuery(reportMode: reportMode, householdId: householdId, startDate: startDate, endDate: endDate, timezone: timezone, accountIds: accountIds, currency: currency)
        let url = builder.makeURL(path: "/api/v1/reports/account-balances", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(ReportAccountBalances.self, from: data)
    }

    func getReportCashFlow(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, bucket: ReportBucket? = nil, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil) async throws -> ReportCashFlow {
        var query = reportQuery(reportMode: reportMode, householdId: householdId, startDate: startDate, endDate: endDate, timezone: timezone, accountIds: accountIds, categoryIds: categoryIds, transactionTypes: transactionTypes, currency: currency)
        if let v = bucket { query["bucket"] = v.rawValue }
        let url = builder.makeURL(path: "/api/v1/reports/cash-flow", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(ReportCashFlow.self, from: data)
    }

    func getReportTransactions(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil, limit: Int? = nil, cursor: String? = nil, sort: String? = nil) async throws -> ReportTransactionDrillDown {
        var query = reportQuery(reportMode: reportMode, householdId: householdId, startDate: startDate, endDate: endDate, timezone: timezone, accountIds: accountIds, categoryIds: categoryIds, transactionTypes: transactionTypes, currency: currency)
        if let v = limit { query["limit"] = String(v) }
        if let v = cursor { query["cursor"] = v }
        if let v = sort { query["sort"] = v }
        let url = builder.makeURL(path: "/api/v1/reports/transactions", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(ReportTransactionDrillDown.self, from: data)
    }

    // MARK: - Planning

    func getPlanningPlan(scope: PlanningScope, month: String, householdId: String? = nil) async throws -> PlanningPlan? {
        var query = ["scope": scope.rawValue, "month": month]
        if let v = householdId { query["householdId"] = v }
        let url = builder.makeURL(path: "/api/v1/planning/plans", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        do {
            let data = try await performRequest(request, expectedCodes: [200, 404])
            if let plan = try? ResponseParser.unwrapDataEnvelope(PlanningPlan.self, from: data) {
                return plan
            }
            return nil
        } catch let error as FinanceApiError {
            if case .httpError(let code, _) = error, code == 404 { return nil }
            throw error
        }
    }

    func listPlanningPlanHistory(scope: PlanningScope, householdId: String? = nil) async throws -> [PlanningPlan] {
        var query = ["scope": scope.rawValue]
        if let v = householdId { query["householdId"] = v }
        let url = builder.makeURL(path: "/api/v1/planning/plans/history", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapItemsOnly(PlanningPlan.self, from: data)
    }

    func createPlanningPlan(_ request: PlanningPlanCreateRequest) async throws -> PlanningPlan {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/planning/plans")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(PlanningPlan.self, from: data)
    }

    func getPlanningPlan(planId: String) async throws -> PlanningPlan {
        let url = builder.makeURL(path: "/api/v1/planning/plans/\(planId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(PlanningPlan.self, from: data)
    }

    func copyPlanningPlan(planId: String, _ request: PlanningPlanCopyRequest) async throws -> PlanningPlan {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/planning/plans/\(planId)/copy")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(PlanningPlan.self, from: data)
    }

    func createPlanningIncomeSource(planId: String, _ request: PlanningIncomeSourceCreateRequest) async throws -> PlanningIncomeSource {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/planning/plans/\(planId)/income-sources")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(PlanningIncomeSource.self, from: data)
    }

    func updatePlanningIncomeSource(incomeSourceId: String, _ request: PlanningIncomeSourceUpdateRequest) async throws -> PlanningIncomeSource {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/planning/income-sources/\(incomeSourceId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(PlanningIncomeSource.self, from: data)
    }

    func confirmPlanningIncomeSource(incomeSourceId: String) async throws -> PlanningIncomeSource {
        let url = builder.makeURL(path: "/api/v1/planning/income-sources/\(incomeSourceId)/confirm")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(PlanningIncomeSource.self, from: data)
    }

    func deletePlanningIncomeSource(incomeSourceId: String) async throws {
        let url = builder.makeURL(path: "/api/v1/planning/income-sources/\(incomeSourceId)")
        let req = builder.makeURLRequest(url: url, method: "DELETE", csrfToken: csrfToken)
        _ = try await performRequestRaw(req, expectedCodes: [200, 204])
    }

    func createPlanningAllocation(planId: String, _ request: PlanningAllocationCreateRequest) async throws -> PlanningAllocation {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/planning/plans/\(planId)/allocations")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(PlanningAllocation.self, from: data)
    }

    func updatePlanningAllocation(allocationId: String, _ request: PlanningAllocationUpdateRequest) async throws -> PlanningAllocation {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/planning/allocations/\(allocationId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(PlanningAllocation.self, from: data)
    }

    func deletePlanningAllocation(allocationId: String) async throws {
        let url = builder.makeURL(path: "/api/v1/planning/allocations/\(allocationId)")
        let req = builder.makeURLRequest(url: url, method: "DELETE", csrfToken: csrfToken)
        _ = try await performRequestRaw(req, expectedCodes: [200, 204])
    }

    // MARK: - Dashboard

    func dashboard(startDate: String? = nil, endDate: String? = nil) async throws -> FinanceDashboard {
        let sessionStatus = try await sessionStatus()
        var dateQuery = [String: String]()
        if let v = startDate { dateQuery["startDate"] = v }
        if let v = endDate { dateQuery["endDate"] = v }

        async let accountsResult = listAccounts(limit: 200, cursor: nil)
        async let categoriesResult = listCategories(limit: 200, cursor: nil)
        async let transactionsResult = listTransactions(limit: 200, cursor: nil, startDate: startDate, endDate: endDate)
        async let assetCategoriesResult = listAssetCategories(limit: 200, cursor: nil)

        let (accounts, _) = try await accountsResult
        let (categories, _) = try await categoriesResult
        let (transactions, _) = try await transactionsResult
        let assetCategories = (try? await assetCategoriesResult.0) ?? []

        let currency = accounts.first?.currency ?? .RUB
        let reportMode: ReportMode = sessionStatus.householdId != nil ? .combined_viewer_overview : .personal

        let reportQuery: [String: String] = [
            "reportMode": reportMode.rawValue,
            "startDate": startDate ?? "",
            "endDate": endDate ?? "",
            "timezone": TimeZone.current.identifier,
            "currency": currency.rawValue,
        ].merging(dateQuery) { _, new in new }

        let totals = (try? await fetchTotals(reportQuery: reportQuery)) ?? []
        let balancesData = try? await fetchAccountBalances(reportQuery: reportQuery)

        let assetCategoryGroups = balancesData?.assetCategoryGroups ?? []
        let investmentsByCurrency = balancesData?.investmentsByCurrency.map { MoneyAmount(currency: $0.currency, amount: $0.investmentsTotal) } ?? []
        let investmentsTotal = balancesData?.totalsByCurrency.first.map { MoneyAmount(currency: $0.currency, amount: $0.netWorthTotal) }

        let reportTransferCount: Int
        if let householdId = sessionStatus.householdId {
            var txQuery = reportQuery
            txQuery["householdId"] = householdId
            txQuery["transactionTypes"] = "transfer"
            reportTransferCount = (try? await fetchTransferCount(query: txQuery)) ?? 0
        } else {
            reportTransferCount = 0
        }

        let dashboard = FinanceDashboard()
        dashboard.session = sessionStatus
        dashboard.accounts = accounts
        dashboard.categories = categories
        dashboard.transactions = transactions
        dashboard.totals = totals
        dashboard.reportTransferCount = reportTransferCount
        dashboard.assetCategories = assetCategories
        dashboard.assetCategoryGroups = assetCategoryGroups
        dashboard.investmentsByCurrency = investmentsByCurrency
        dashboard.investmentsTotal = investmentsTotal
        return dashboard
    }

    // MARK: - Private helpers

    private var csrfToken: String? { tokenStore.csrfToken }

    private func performRequest(_ request: URLRequest, expectedCodes: [Int] = [200]) async throws -> Data {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw FinanceApiError.networkError(URLError(.badServerResponse))
        }
        if let authService = http.allHeaderFields["X-CSRF-Token"] as? String {
            tokenStore.saveCsrfToken(authService)
        }
        if expectedCodes.contains(http.statusCode) {
            return data
        }
        if http.statusCode == 401 || http.statusCode == 403 {
            tokenStore.clear()
            throw FinanceApiError.unauthorized
        }
        throw ResponseParser.parseError(from: data, statusCode: http.statusCode)
    }

    private func performRequestRaw(_ request: URLRequest, expectedCodes: [Int] = [200]) async throws -> Data {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw FinanceApiError.networkError(URLError(.badServerResponse))
        }
        if expectedCodes.contains(http.statusCode) {
            return data
        }
        if http.statusCode == 401 || http.statusCode == 403 {
            tokenStore.clear()
            throw FinanceApiError.unauthorized
        }
        throw ResponseParser.parseError(from: data, statusCode: http.statusCode)
    }

    private func parseSessionStatus(from data: Data) throws -> SessionStatus {
        struct SessionEnvelope: Decodable { let data: ActorContext? }
        struct SessionDirect: Decodable { let actor: ActorContext? }
        let actor: ActorContext?
        if let env = try? ResponseParser.decode(SessionEnvelope.self, from: data), let a = env.data {
            actor = a
        } else if let dir = try? ResponseParser.decode(SessionDirect.self, from: data), let a = dir.actor {
            actor = a
        } else {
            actor = nil
        }
        let householdId = actor?.memberships.first(where: { $0.status == "active" })?.householdId
        return SessionStatus(
            isAuthenticated: actor != nil,
            displayName: actor.map { "Пользователь \($0.userId.prefix(8))" },
            householdId: householdId
        )
    }

    private func reportQuery(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil) -> [String: String] {
        var query = [
            "reportMode": reportMode.rawValue,
            "startDate": startDate,
            "endDate": endDate,
            "timezone": timezone,
        ]
        if let v = householdId { query["householdId"] = v }
        if let v = accountIds { query["accountIds"] = v.joined(separator: ",") }
        if let v = categoryIds { query["categoryIds"] = v.joined(separator: ",") }
        if let v = transactionTypes { query["transactionTypes"] = v.map(\.rawValue).joined(separator: ",") }
        if let v = currency { query["currency"] = v.rawValue }
        return query
    }

    private func fetchTotals(reportQuery: [String: String]) async throws -> [MoneyTotal] {
        let url = builder.makeURL(path: "/api/v1/reports/summary", query: reportQuery)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let summary = try ResponseParser.unwrapDataEnvelope(ReportSummary.self, from: data)
        return summary.totalsByCurrency
    }

    private func fetchAccountBalances(reportQuery: [String: String]) async throws -> ReportAccountBalances {
        let url = builder.makeURL(path: "/api/v1/reports/account-balances", query: reportQuery)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapDataEnvelope(ReportAccountBalances.self, from: data)
    }

    private func fetchTransferCount(query: [String: String]) async throws -> Int {
        let url = builder.makeURL(path: "/api/v1/reports/transactions", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let drill = try ResponseParser.unwrapDataEnvelope(ReportTransactionDrillDown.self, from: data)
        return drill.items.count
    }
}
