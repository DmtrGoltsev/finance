import Foundation

final class LiveApiClient: FinanceApiClient, @unchecked Sendable {
    private let builder: RequestBuilder
    private let session: URLSession
    private let tokenStore: CSRFTokenStore

    convenience init(environment: AppEnvironment, tokenStore: CSRFTokenStore = .shared) {
        self.init(baseURL: environment.apiBaseURL.absoluteString, tokenStore: tokenStore)
    }

    init(
        baseURL: String = AppEnvironment.current.apiBaseURL.absoluteString,
        tokenStore: CSRFTokenStore = .shared,
        session: URLSession? = nil
    ) {
        self.builder = RequestBuilder(baseURL: baseURL)
        self.tokenStore = tokenStore
        if let session {
            self.session = session
            return
        }
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
        return SessionStatus(
            isAuthenticated: actor != nil,
            displayName: actor.map { "Пользователь \($0.userId.prefix(8))" },
            householdId: nil,
            userId: actor?.userId,
            sessionId: actor?.sessionId
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
            return .authenticated(SessionStatus(
                isAuthenticated: true,
                displayName: nil,
                householdId: nil,
                userId: loginResp.actor?.userId,
                sessionId: loginResp.actor?.sessionId
            ))
        }
        return .accepted(message: "Заявка на регистрацию принята")
    }

    func sessionStatus() async throws -> SessionStatus {
        let url = builder.makeURL(path: "/api/v1/sessions/current")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try parseSessionStatus(from: data)
    }

    func logout() async -> LogoutResult {
        let url = builder.makeURL(path: "/api/v1/sessions/current")
        let request = builder.makeURLRequest(url: url, method: "DELETE", csrfToken: csrfToken)
        let remoteSessionRevoked: Bool
        do {
            _ = try await performRequestRaw(request, expectedCodes: [200, 204])
            remoteSessionRevoked = true
        } catch where SessionRestorePolicy.isConfirmedInvalidIdentity(error) {
            // A 401 on logout proves the server session is already gone.
            remoteSessionRevoked = true
        } catch {
            remoteSessionRevoked = false
        }
        tokenStore.clear()
        clearSessionCookies()
        return LogoutResult(
            remoteSessionRevoked: remoteSessionRevoked,
            localCredentialsCleared: true
        )
    }

    // MARK: - Accounts

    func listAccounts(limit: Int? = nil, cursor: String? = nil, ownershipType: OwnershipType? = nil, householdId: String? = nil, status: RecordStatus? = nil, q: String? = nil, sort: String? = nil) async throws -> ([Account], PageInfo) {
        var query = [String: String]()
        if let v = limit { query["limit"] = String(v) }
        if let v = cursor { query["cursor"] = v }
        query["ownershipType"] = OwnershipType.personal.rawValue
        if let v = status { query["status"] = v.rawValue }
        if let v = q { query["q"] = v }
        if let v = sort { query["sort"] = v }
        let url = builder.makeURL(path: "/api/v1/accounts", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let result = try ResponseParser.unwrapPageEnvelope(Account.self, from: data)
        return (result.items.filter(isPersonalAccount), result.page)
    }

    func getAccount(accountId: String) async throws -> Account {
        let url = builder.makeURL(path: "/api/v1/accounts/\(accountId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let account = try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
        guard isPersonalAccount(account) else { throw FinanceApiError.notFound }
        return account
    }

    func createAccount(_ request: AccountCreateRequest) async throws -> Account {
        let personalRequest = AccountCreateRequest(
            name: request.name,
            accountType: request.accountType,
            ownershipType: .personal,
            householdId: nil,
            assetCategoryId: request.assetCategoryId,
            currency: request.currency,
            initialBalance: request.initialBalance,
            isPaymentAccount: request.isPaymentAccount
        )
        let body = try ResponseParser.encode(personalRequest)
        let url = builder.makeURL(path: "/api/v1/accounts")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        let account = try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
        guard isPersonalAccount(account) else { throw FinanceApiError.notFound }
        return account
    }

    func updateAccount(accountId: String, _ request: AccountUpdateRequest) async throws -> Account {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/accounts/\(accountId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        let account = try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
        guard isPersonalAccount(account) else { throw FinanceApiError.notFound }
        return account
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
        let account = try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
        guard isPersonalAccount(account) else { throw FinanceApiError.notFound }
        return account
    }

    func restoreAccount(accountId: String) async throws -> Account {
        let url = builder.makeURL(path: "/api/v1/accounts/\(accountId)/restore")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        let account = try ResponseParser.unwrapDataEnvelope(Account.self, from: data)
        guard isPersonalAccount(account) else { throw FinanceApiError.notFound }
        return account
    }

    func autocompleteAccounts(q: String, limit: Int? = nil, ownershipType: OwnershipType? = nil, householdId: String? = nil) async throws -> [AccountAutocompleteItem] {
        var query = ["q": q]
        if let v = limit { query["limit"] = String(v) }
        query["ownershipType"] = OwnershipType.personal.rawValue
        let url = builder.makeURL(path: "/api/v1/accounts/autocomplete", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapItemsOnly(AccountAutocompleteItem.self, from: data)
            .filter { $0.ownershipType == .personal && $0.householdId == nil }
    }

    // MARK: - Asset Categories

    func listAssetCategories(limit: Int? = nil, cursor: String? = nil, scopeType: AssetCategoryScope? = nil, householdId: String? = nil, recordStatus: RecordStatus? = nil, isInvestment: Bool? = nil, q: String? = nil) async throws -> ([AssetCategory], PageInfo) {
        var query = [String: String]()
        if let v = limit { query["limit"] = String(v) }
        if let v = cursor { query["cursor"] = v }
        query["scopeType"] = AssetCategoryScope.personal.rawValue
        if let v = recordStatus { query["recordStatus"] = v.rawValue }
        if let v = isInvestment { query["isInvestment"] = String(v) }
        if let v = q { query["q"] = v }
        let url = builder.makeURL(path: "/api/v1/asset-categories", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let result = try ResponseParser.unwrapPageEnvelope(AssetCategory.self, from: data)
        return (result.items.filter(isPersonalAssetCategory), result.page)
    }

    func getAssetCategory(assetCategoryId: String) async throws -> AssetCategory {
        let url = builder.makeURL(path: "/api/v1/asset-categories/\(assetCategoryId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let category = try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
        guard isPersonalAssetCategory(category) else { throw FinanceApiError.notFound }
        return category
    }

    func createAssetCategory(_ request: AssetCategoryCreateRequest) async throws -> AssetCategory {
        let personalRequest = AssetCategoryCreateRequest(
            name: request.name,
            scopeType: .personal,
            householdId: nil,
            currency: request.currency,
            assetType: request.assetType,
            iconKey: request.iconKey,
            manualAmount: request.manualAmount,
            isInvestment: request.isInvestment
        )
        let body = try ResponseParser.encode(personalRequest)
        let url = builder.makeURL(path: "/api/v1/asset-categories")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        let category = try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
        guard isPersonalAssetCategory(category) else { throw FinanceApiError.notFound }
        return category
    }

    func updateAssetCategory(assetCategoryId: String, _ request: AssetCategoryUpdateRequest) async throws -> AssetCategory {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/asset-categories/\(assetCategoryId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        let category = try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
        guard isPersonalAssetCategory(category) else { throw FinanceApiError.notFound }
        return category
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
        let category = try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
        guard isPersonalAssetCategory(category) else { throw FinanceApiError.notFound }
        return category
    }

    func restoreAssetCategory(assetCategoryId: String) async throws -> AssetCategory {
        let url = builder.makeURL(path: "/api/v1/asset-categories/\(assetCategoryId)/restore")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        let category = try ResponseParser.unwrapDataEnvelope(AssetCategory.self, from: data)
        guard isPersonalAssetCategory(category) else { throw FinanceApiError.notFound }
        return category
    }

    // MARK: - Transactions

    func listTransactions(limit: Int? = nil, cursor: String? = nil, accountId: String? = nil, categoryId: String? = nil, transactionType: TransactionType? = nil, householdId: String? = nil, ownershipType: OwnershipType? = nil, startDate: String? = nil, endDate: String? = nil, status: RecordStatus? = nil, q: String? = nil, sort: String? = nil) async throws -> ([Transaction], PageInfo) {
        var query = [String: String]()
        if let v = limit { query["limit"] = String(v) }
        if let v = cursor { query["cursor"] = v }
        if let v = accountId { query["accountId"] = v }
        if let v = categoryId { query["categoryId"] = v }
        if let v = transactionType { query["transactionType"] = v.rawValue }
        query["ownershipType"] = OwnershipType.personal.rawValue
        if let v = startDate { query["startDate"] = v }
        if let v = endDate { query["endDate"] = v }
        if let v = status { query["status"] = v.rawValue }
        if let v = q { query["q"] = v }
        if let v = sort { query["sort"] = v }
        let url = builder.makeURL(path: "/api/v1/transactions", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let result = try ResponseParser.unwrapPageEnvelope(Transaction.self, from: data)
        return (result.items, result.page)
    }

    func getTransaction(transactionId: String) async throws -> Transaction {
        let url = builder.makeURL(path: "/api/v1/transactions/\(transactionId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let transaction = try ResponseParser.unwrapDataEnvelope(Transaction.self, from: data)
        try await validatePersonalTransactionReferences(
            accountId: transaction.accountId,
            counterpartyAccountId: transaction.counterpartyAccountId,
            categoryId: transaction.categoryId
        )
        return transaction
    }

    func createTransaction(_ request: TransactionCreateRequest) async throws -> Transaction {
        try await validatePersonalTransactionReferences(
            accountId: request.accountId,
            counterpartyAccountId: request.counterpartyAccountId,
            categoryId: request.categoryId
        )
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/transactions")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        return try ResponseParser.unwrapDataEnvelope(Transaction.self, from: data)
    }

    func updateTransaction(transactionId: String, _ request: TransactionUpdateRequest) async throws -> Transaction {
        if request.accountId != nil || request.counterpartyAccountId != nil || request.categoryId != nil {
            let current = try await getTransaction(transactionId: transactionId)
            try await validatePersonalTransactionReferences(
                accountId: request.accountId ?? current.accountId,
                counterpartyAccountId: request.counterpartyAccountId ?? current.counterpartyAccountId,
                categoryId: request.categoryId ?? current.categoryId
            )
        }
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
        query["scope"] = CategoryScope.personal.rawValue
        if let v = type { query["type"] = v.rawValue }
        if let v = status { query["status"] = v.rawValue }
        if let v = q { query["q"] = v }
        if let v = sort { query["sort"] = v }
        let url = builder.makeURL(path: "/api/v1/categories", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let result = try ResponseParser.unwrapPageEnvelope(Category.self, from: data)
        return (result.items.filter(isPersonalCategory), result.page)
    }

    func getCategory(categoryId: String) async throws -> Category {
        let url = builder.makeURL(path: "/api/v1/categories/\(categoryId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let category = try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
        guard isPersonalCategory(category) else { throw FinanceApiError.notFound }
        return category
    }

    func createCategory(_ request: CategoryCreateRequest) async throws -> Category {
        let personalRequest = CategoryCreateRequest(
            name: request.name,
            type: request.type,
            scope: .personal,
            householdId: nil,
            iconKey: request.iconKey,
            color: request.color
        )
        let body = try ResponseParser.encode(personalRequest)
        let url = builder.makeURL(path: "/api/v1/categories")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        let category = try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
        guard isPersonalCategory(category) else { throw FinanceApiError.notFound }
        return category
    }

    func updateCategory(categoryId: String, _ request: CategoryUpdateRequest) async throws -> Category {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/categories/\(categoryId)")
        let req = builder.makeURLRequest(url: url, method: "PATCH", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        let category = try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
        guard isPersonalCategory(category) else { throw FinanceApiError.notFound }
        return category
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
        let category = try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
        guard isPersonalCategory(category) else { throw FinanceApiError.notFound }
        return category
    }

    func restoreCategory(categoryId: String) async throws -> Category {
        let url = builder.makeURL(path: "/api/v1/categories/\(categoryId)/restore")
        let req = builder.makeURLRequest(url: url, method: "POST", csrfToken: csrfToken)
        let data = try await performRequest(req)
        let category = try ResponseParser.unwrapDataEnvelope(Category.self, from: data)
        guard isPersonalCategory(category) else { throw FinanceApiError.notFound }
        return category
    }

    func autocompleteCategories(q: String, limit: Int? = nil, scope: CategoryScope? = nil, type: CategoryType? = nil, householdId: String? = nil) async throws -> [CategoryAutocompleteItem] {
        var query = ["q": q]
        if let v = limit { query["limit"] = String(v) }
        query["scope"] = CategoryScope.personal.rawValue
        if let v = type { query["type"] = v.rawValue }
        let url = builder.makeURL(path: "/api/v1/categories/autocomplete", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapItemsOnly(CategoryAutocompleteItem.self, from: data)
            .filter { $0.scope == .personal && $0.householdId == nil }
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
        let req = builder.makeMultipartRequest(
            url: url, fields: fields, fileData: imageData,
            fileName: "screenshot.jpg", contentType: contentType,
            csrfToken: csrfToken
        )
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(ScreenshotOcrResponse.self, from: data)
    }

    func putCategoryMapping(externalLabel: String, categoryId: String, householdId: String?) async throws -> CategoryMappingResult {
        let body: [String: String] = ["externalLabel": externalLabel, "categoryId": categoryId]
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
        let report = try ResponseParser.unwrapDataEnvelope(ReportCategoryBreakdown.self, from: data)
        return ReportCategoryBreakdown(
            scope: report.scope,
            period: report.period,
            items: report.items.filter { $0.categoryScope != .household }
        )
    }

    func getReportAccountBalances(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, currency: CurrencyCode? = nil) async throws -> ReportAccountBalances {
        var query = reportQuery(reportMode: reportMode, householdId: householdId, startDate: startDate, endDate: endDate, timezone: timezone, accountIds: accountIds, currency: currency)
        let url = builder.makeURL(path: "/api/v1/reports/account-balances", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let report = try ResponseParser.unwrapDataEnvelope(ReportAccountBalances.self, from: data)
        return ReportAccountBalances(
            scope: report.scope,
            asOfDate: report.asOfDate,
            timezone: report.timezone,
            items: report.items.filter { $0.ownershipType == .personal && $0.householdId == nil },
            balanceGroups: report.balanceGroups,
            assetsByType: report.assetsByType,
            assetCategoryGroups: report.assetCategoryGroups.filter { $0.scopeType == .personal && $0.householdId == nil },
            legacyAssetTypeGroups: report.legacyAssetTypeGroups,
            totalsByCurrency: report.totalsByCurrency,
            investmentsByCurrency: report.investmentsByCurrency
        )
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
        let report = try ResponseParser.unwrapDataEnvelope(ReportTransactionDrillDown.self, from: data)
        let personalAccountIds = try await personalAccountIdsForFiltering()
        return ReportTransactionDrillDown(
            scope: report.scope,
            period: report.period,
            items: report.items.filter { transaction in
                personalAccountIds.contains(transaction.accountId) &&
                transaction.counterpartyAccountId.map(personalAccountIds.contains) != false
            },
            page: report.page
        )
    }

    // MARK: - Planning

    func getPlanningPlan(scope: PlanningScope, month: String, householdId: String? = nil) async throws -> PlanningPlan? {
        let query = ["scope": PlanningScope.personal.rawValue, "month": month]
        let url = builder.makeURL(path: "/api/v1/planning/plans", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        do {
            let data = try await performRequest(request, expectedCodes: [200, 404])
            if let plan = try? ResponseParser.unwrapDataEnvelope(PlanningPlan.self, from: data),
               plan.scope == .personal, plan.householdId == nil {
                return plan
            }
            return nil
        } catch let error as FinanceApiError {
            if case .httpError(let code, _) = error, code == 404 { return nil }
            throw error
        }
    }

    func listPlanningPlanHistory(scope: PlanningScope, householdId: String? = nil) async throws -> [PlanningPlanHistoryItem] {
        let query = ["scope": PlanningScope.personal.rawValue]
        let url = builder.makeURL(path: "/api/v1/planning/plans/history", query: query)
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        return try ResponseParser.unwrapItemsOnly(PlanningPlanSummaryDTO.self, from: data)
            .map(\.historyItem)
            .filter { $0.scope == .personal && $0.householdId == nil }
    }

    func createPlanningPlan(_ request: PlanningPlanCreateRequest) async throws -> PlanningPlan {
        let personalRequest = PlanningPlanCreateRequest(
            scope: .personal,
            month: request.month,
            currency: request.currency,
            householdId: nil
        )
        let body = try ResponseParser.encode(personalRequest)
        let url = builder.makeURL(path: "/api/v1/planning/plans")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        let plan = try ResponseParser.unwrapDataEnvelope(PlanningPlan.self, from: data)
        guard plan.scope == .personal && plan.householdId == nil else { throw FinanceApiError.notFound }
        return plan
    }

    func getPlanningPlan(planId: String) async throws -> PlanningPlan {
        let url = builder.makeURL(path: "/api/v1/planning/plans/\(planId)")
        let request = builder.makeURLRequest(url: url, method: "GET")
        let data = try await performRequest(request)
        let plan = try ResponseParser.unwrapDataEnvelope(PlanningPlan.self, from: data)
        guard plan.scope == .personal && plan.householdId == nil else { throw FinanceApiError.notFound }
        return plan
    }

    func copyPlanningPlan(planId: String, _ request: PlanningPlanCopyRequest) async throws -> PlanningPlan {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/planning/plans/\(planId)/copy")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req, expectedCodes: [200, 201])
        let plan = try ResponseParser.unwrapDataEnvelope(PlanningPlan.self, from: data)
        guard plan.scope == .personal && plan.householdId == nil else { throw FinanceApiError.notFound }
        return plan
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

    // MARK: - Sync

    func syncPush(_ request: SyncPushRequest) async throws -> SyncPushResponse {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/sync/push")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(SyncPushResponse.self, from: data)
    }

    func syncPull(_ request: SyncPullRequest) async throws -> SyncPullResponse {
        let body = try ResponseParser.encode(request)
        let url = builder.makeURL(path: "/api/v1/sync/pull")
        let req = builder.makeURLRequest(url: url, method: "POST", body: body, csrfToken: csrfToken)
        let data = try await performRequest(req)
        return try ResponseParser.unwrapDataEnvelope(SyncPullResponse.self, from: data)
    }

    // MARK: - Dashboard

    func dashboard(startDate: String? = nil, endDate: String? = nil) async throws -> FinanceDashboard {
        let sessionStatus = try await sessionStatus()
        var dateQuery = [String: String]()
        if let v = startDate { dateQuery["startDate"] = v }
        if let v = endDate { dateQuery["endDate"] = v }

        async let accountsResult = loadAllAccounts()
        async let categoriesResult = loadAllCategories()
        async let transactionsResult = loadAllTransactions(startDate: startDate, endDate: endDate)
        async let assetCategoriesResult = loadAllAssetCategories()

        let accounts = try await accountsResult
        let categories = try await categoriesResult
        let personalAccountIds = Set(accounts.map(\.id))
        let loadedTransactions = try await transactionsResult
        let transactions = loadedTransactions.filter { transaction in
            personalAccountIds.contains(transaction.accountId) &&
            transaction.counterpartyAccountId.map(personalAccountIds.contains) != false
        }
        let assetCategories = (try? await assetCategoriesResult) ?? []

        let currency = accounts.first?.currency ?? .RUB
        let reportQuery: [String: String] = [
            "reportMode": ReportMode.personal.rawValue,
            "startDate": startDate ?? "",
            "endDate": endDate ?? "",
            "timezone": TimeZone.current.identifier,
            "currency": currency.rawValue,
        ].merging(dateQuery) { _, new in new }

        let reportSummary = try? await getReportSummary(
            reportMode: .personal,
            householdId: nil,
            startDate: startDate ?? "",
            endDate: endDate ?? "",
            timezone: TimeZone.current.identifier,
            accountIds: nil,
            categoryIds: nil,
            transactionTypes: nil,
            currency: currency
        )
        let totals = reportSummary?.totalsByCurrency ?? []
        let balancesData = try? await getReportAccountBalances(
            reportMode: .personal,
            householdId: nil,
            startDate: startDate ?? "",
            endDate: endDate ?? "",
            timezone: TimeZone.current.identifier,
            accountIds: nil,
            currency: currency
        )
        let categoryBreakdown = (try? await getReportCategoryBreakdown(
            reportMode: .personal,
            householdId: nil,
            startDate: startDate ?? "",
            endDate: endDate ?? "",
            timezone: TimeZone.current.identifier,
            accountIds: nil,
            categoryIds: nil,
            transactionTypes: [.expense],
            currency: currency
        ))?.items ?? []

        let assetCategoryGroups = balancesData?.assetCategoryGroups ?? []
        let investmentsByCurrency = totals.compactMap { total in
            total.investmentsTotal.map { MoneyAmount(currency: total.currency, amount: $0) }
        }
        let investmentsTotal = totals
            .first(where: { $0.currency == currency })?
            .investmentsTotal
            .map { MoneyAmount(currency: currency, amount: $0) }

        var txQuery = reportQuery
        txQuery["transactionTypes"] = "transfer"
        let reportTransferCount = (try? await fetchTransferCount(query: txQuery)) ?? 0

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
        dashboard.categoryBreakdown = categoryBreakdown
        return dashboard
    }

    // MARK: - Private helpers

    static func collectAllPages<Item>(
        pageSize: Int = 100,
        maximumPageCount: Int = 10_000,
        id: (Item) -> String,
        fetchPage: (_ limit: Int, _ cursor: String?) async throws -> ([Item], PageInfo)
    ) async throws -> [Item] {
        guard pageSize > 0, maximumPageCount > 0 else {
            throw FinanceApiError.serverError("Некорректные параметры пагинации.")
        }

        var cursor: String?
        var visitedCursors = Set<String>()
        var seenIds = Set<String>()
        var result: [Item] = []

        for _ in 0..<maximumPageCount {
            let (items, page) = try await fetchPage(pageSize, cursor)
            for item in items where seenIds.insert(id(item)).inserted {
                result.append(item)
            }

            guard page.hasMore else { return result }
            guard let nextCursor = page.nextCursor, !nextCursor.isEmpty else {
                throw FinanceApiError.serverError("Сервер не вернул курсор следующей страницы.")
            }
            guard visitedCursors.insert(nextCursor).inserted, nextCursor != cursor else {
                throw FinanceApiError.serverError("Сервер повторил курсор страницы.")
            }
            cursor = nextCursor
        }

        throw FinanceApiError.serverError("Превышен лимит страниц при загрузке данных.")
    }

    private func loadAllAccounts() async throws -> [Account] {
        try await Self.collectAllPages(id: \.id) { limit, cursor in
            try await self.listAccounts(limit: limit, cursor: cursor, ownershipType: .personal)
        }
    }

    private func loadAllCategories() async throws -> [Category] {
        try await Self.collectAllPages(id: \.id) { limit, cursor in
            try await self.listCategories(limit: limit, cursor: cursor, scope: .personal)
        }
    }

    private func loadAllAssetCategories() async throws -> [AssetCategory] {
        try await Self.collectAllPages(id: \.id) { limit, cursor in
            try await self.listAssetCategories(limit: limit, cursor: cursor, scopeType: .personal)
        }
    }

    private func loadAllTransactions(startDate: String?, endDate: String?) async throws -> [Transaction] {
        let transactions = try await Self.collectAllPages(id: \.id) { limit, cursor in
            try await self.listTransactions(
                limit: limit,
                cursor: cursor,
                ownershipType: .personal,
                startDate: startDate,
                endDate: endDate,
                sort: "-occurredAt"
            )
        }
        return transactions.sorted(by: transactionComesBefore)
    }

    private func transactionComesBefore(_ lhs: Transaction, _ rhs: Transaction) -> Bool {
        let lhsDate = lhs.transactionDate ?? String(lhs.occurredAt.prefix(10))
        let rhsDate = rhs.transactionDate ?? String(rhs.occurredAt.prefix(10))
        if lhsDate != rhsDate { return lhsDate > rhsDate }
        let lhsVersion = lhs.version ?? 0
        let rhsVersion = rhs.version ?? 0
        if lhsVersion != rhsVersion { return lhsVersion > rhsVersion }
        return lhs.id > rhs.id
    }

    private var csrfToken: String? { tokenStore.csrfToken }

    private func clearSessionCookies() {
        let storages = [HTTPCookieStorage.shared, session.configuration.httpCookieStorage].compactMap { $0 }
        for storage in storages {
            for cookie in storage.cookies ?? [] where cookie.name == FinanceConstants.sessionCookieName {
                storage.deleteCookie(cookie)
            }
        }
    }

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
        if SessionHTTPStatusPolicy.invalidatesIdentity(statusCode: http.statusCode) {
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
        if SessionHTTPStatusPolicy.invalidatesIdentity(statusCode: http.statusCode) {
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
        return SessionStatus(
            isAuthenticated: actor != nil,
            displayName: actor.map { "Пользователь \($0.userId.prefix(8))" },
            householdId: nil,
            userId: actor?.userId,
            sessionId: actor?.sessionId
        )
    }

    func reportQuery(reportMode: ReportMode, householdId: String? = nil, startDate: String, endDate: String, timezone: String, accountIds: [String]? = nil, categoryIds: [String]? = nil, transactionTypes: [TransactionType]? = nil, currency: CurrencyCode? = nil) -> [String: String] {
        var query = [
            "reportMode": ReportMode.personal.rawValue,
            "startDate": startDate,
            "endDate": endDate,
            "timezone": timezone,
        ]
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
        let transactions = try await Self.collectAllPages(id: \.id) { limit, cursor in
            var pageQuery = query
            pageQuery["limit"] = String(limit)
            if let cursor { pageQuery["cursor"] = cursor }
            let url = self.builder.makeURL(path: "/api/v1/reports/transactions", query: pageQuery)
            let request = self.builder.makeURLRequest(url: url, method: "GET")
            let data = try await self.performRequest(request)
            let drill = try ResponseParser.unwrapDataEnvelope(ReportTransactionDrillDown.self, from: data)
            return (drill.items, drill.page)
        }
        return transactions.count
    }

    private func personalAccountIdsForFiltering() async throws -> Set<String> {
        let accounts = try await loadAllAccounts()
        return Set(accounts.map(\.id))
    }

    private func isPersonalAccount(_ account: Account) -> Bool {
        account.ownershipType == .personal && account.householdId == nil
    }

    private func isPersonalCategory(_ category: Category) -> Bool {
        category.scope == .personal && category.householdId == nil
    }

    private func isPersonalAssetCategory(_ category: AssetCategory) -> Bool {
        category.scopeType == .personal && category.householdId == nil
    }

    private func validatePersonalTransactionReferences(
        accountId: String,
        counterpartyAccountId: String?,
        categoryId: String?
    ) async throws {
        _ = try await getAccount(accountId: accountId)
        if let counterpartyAccountId {
            _ = try await getAccount(accountId: counterpartyAccountId)
        }
        if let categoryId {
            _ = try await getCategory(categoryId: categoryId)
        }
    }
}
