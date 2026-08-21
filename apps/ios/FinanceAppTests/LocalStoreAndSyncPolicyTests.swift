import XCTest
@testable import FinanceApp

final class LocalStoreAndSyncPolicyTests: XCTestCase {
    func testLocalStoreSeparatesUsersAndSessionWiperRemovesOnlyRequestedScope() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceAppTests-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }

        let store = FileBackedFinanceLocalStore(rootURL: root)
        let scopeA = LocalStoreScope(viewerUserId: "user-a", accessVersion: "1")
        let scopeB = LocalStoreScope(viewerUserId: "user-b", accessVersion: "1")
        var snapshotA = FinanceLocalSnapshot.empty(scope: scopeA, deviceId: "device")
        var snapshotB = FinanceLocalSnapshot.empty(scope: scopeB, deviceId: "device")
        snapshotA.syncState.cursor = 11
        snapshotB.syncState.cursor = 22
        try await store.saveSnapshot(snapshotA)
        try await store.saveSnapshot(snapshotB)

        let loadedA = try await store.loadSnapshot(scope: scopeA, deviceId: "device")
        let loadedB = try await store.loadSnapshot(scope: scopeB, deviceId: "device")
        XCTAssertEqual(loadedA.syncState.cursor, 11)
        XCTAssertEqual(loadedB.syncState.cursor, 22)

        let wiper = FinanceSessionDataWiper(localStore: store)
        try await wiper.wipeCurrentUser(scope: scopeA)
        let wipedA = try await store.loadSnapshot(scope: scopeA, deviceId: "device")
        let preservedB = try await store.loadSnapshot(scope: scopeB, deviceId: "device")
        XCTAssertEqual(wipedA.syncState.cursor, 0)
        XCTAssertEqual(preservedB.syncState.cursor, 22)

        try await wiper.wipeAllProtectedLocalData()
        let wipedB = try await store.loadSnapshot(scope: scopeB, deviceId: "device")
        XCTAssertEqual(wipedB.syncState.cursor, 0)
    }

    func testLocalStoreRejectsSnapshotWhoseEmbeddedUserDoesNotMatchRequestedScope() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceAppScopeMismatch-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let scopeA = LocalStoreScope(viewerUserId: "user-a")
        let scopeB = LocalStoreScope(viewerUserId: "user-b")
        let store = FileBackedFinanceLocalStore(rootURL: root)
        try await store.saveSnapshot(.empty(scope: scopeB, deviceId: "device"))

        let foreignData = try JSONEncoder().encode(FinanceLocalSnapshot.empty(scope: scopeB, deviceId: "device"))
        try foreignData.write(
            to: root.appendingPathComponent("\(scopeA.storageKey).json"),
            options: [.atomic]
        )

        do {
            _ = try await store.loadSnapshot(scope: scopeA, deviceId: "device")
            XCTFail("Foreign snapshot must not be opened under another user scope")
        } catch let error as LocalStoreError {
            guard case .accountScopeMismatch = error else {
                XCTFail("Unexpected local store error: \(error)")
                return
            }
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testOfflineQueueRejectsSharedPayloads() throws {
        let scope = LocalStoreScope(viewerUserId: "user-a")
        let snapshot = FinanceLocalSnapshot.empty(scope: scope, deviceId: "device")
        let personalAccount = TestFixtures.account(id: UUID().uuidString, payment: true)
        let personalEvidence = try PersonalSyncOwnershipValidator.evidence(
            scope: scope,
            entityType: .accounts,
            entityId: personalAccount.id,
            ownershipPayload: SyncJSONValue.object(from: personalAccount),
            snapshot: snapshot
        )
        let personal = PendingMutation(
            deviceId: "device",
            scope: scope,
            entityType: .accounts,
            entityId: personalAccount.id,
            operation: .create,
            payload: try OfflineSyncPayloadContract.payload(
                entityType: .accounts,
                operation: .create,
                request: AccountCreateRequest(
                    name: "Card",
                    accountType: .card,
                    ownershipType: .personal,
                    householdId: nil,
                    assetCategoryId: nil,
                    currency: .RUB,
                    initialBalance: "0",
                    isPaymentAccount: true
                )
            ),
            ownershipEvidence: personalEvidence
        )
        let sharedAccount = TestFixtures.account(
            id: UUID().uuidString,
            ownership: .shared,
            householdId: "household"
        )

        XCTAssertTrue(FinanceSyncService.isPersonalOnlyMutation(personal, snapshot: snapshot))
        XCTAssertThrowsError(try PersonalSyncOwnershipValidator.evidence(
            scope: scope,
            entityType: .accounts,
            entityId: sharedAccount.id,
            ownershipPayload: SyncJSONValue.object(from: sharedAccount),
            snapshot: snapshot
        ))
    }

    func testNetworkFailureKeepsBoundUsersPendingQueue() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceAppNetworkRecovery-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }

        let store = FileBackedFinanceLocalStore(rootURL: root)
        let scope = LocalStoreScope(viewerUserId: "user-a")
        let mutationEntityId = UUID().uuidString
        let mutation = PendingMutation(
            deviceId: "device",
            scope: scope,
            entityType: .categories,
            entityId: mutationEntityId,
            operation: .create,
            payload: ["name": .string("Food"), "type": .string("expense"), "scope": .string("personal")],
            ownershipEvidence: SyncOwnershipEvidence(
                viewerUserId: "user-a",
                subjectEntityType: .categories,
                subjectEntityId: mutationEntityId,
                referencedAccountIds: [],
                referencedCategoryIds: [],
                referencedAssetCategoryIds: [],
                referencedPlanIds: [],
                attestedPersonalPlanIds: [],
                attestedPersonalAccountIds: [],
                attestedPersonalCategoryIds: [],
                attestedPersonalAssetCategoryIds: []
            )
        )
        try await store.enqueueMutation(mutation, planningMetadata: nil)

        let networkError = FinanceApiError.networkError(URLError(.notConnectedToInternet))
        XCTAssertFalse(SessionRestorePolicy.isConfirmedInvalidIdentity(networkError))
        XCTAssertFalse(SessionRestorePolicy.isConfirmedInvalidIdentity(
            FinanceApiError.httpError(statusCode: 403, message: "Forbidden")
        ))
        XCTAssertFalse(SessionRestorePolicy.isConfirmedInvalidIdentity(
            FinanceApiError.httpError(statusCode: 503, message: "Unavailable")
        ))
        XCTAssertFalse(SessionRestorePolicy.isConfirmedInvalidIdentity(
            FinanceApiError.decodingError(DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "bad")))
        ))
        let coldStore = FileBackedFinanceLocalStore(rootURL: root)
        let restored = try await coldStore.loadSnapshot(scope: scope, deviceId: "device")
        XCTAssertEqual(restored.pendingMutations.map(\.clientMutationId), [mutation.clientMutationId])
    }

    func testConfirmedUnauthorizedWipesOnlyBoundUser() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceAppUnauthorized-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }

        let store = FileBackedFinanceLocalStore(rootURL: root)
        let scopeA = LocalStoreScope(viewerUserId: "user-a")
        let scopeB = LocalStoreScope(viewerUserId: "user-b")
        var snapshotA = FinanceLocalSnapshot.empty(scope: scopeA, deviceId: "device")
        var snapshotB = FinanceLocalSnapshot.empty(scope: scopeB, deviceId: "device")
        snapshotA.syncState.cursor = 10
        snapshotB.syncState.cursor = 20
        try await store.saveSnapshot(snapshotA)
        try await store.saveSnapshot(snapshotB)

        XCTAssertTrue(SessionRestorePolicy.isConfirmedInvalidIdentity(FinanceApiError.unauthorized))
        XCTAssertTrue(SessionRestorePolicy.isConfirmedInvalidIdentity(
            FinanceApiError.httpError(statusCode: 401, message: "Unauthorized")
        ))
        try await FinanceSessionDataWiper(localStore: store).wipeCurrentUser(scope: scopeA)

        let wipedA = try await store.loadSnapshot(scope: scopeA, deviceId: "device")
        let preservedB = try await store.loadSnapshot(scope: scopeB, deviceId: "device")
        XCTAssertEqual(wipedA.syncState.cursor, 0)
        XCTAssertEqual(preservedB.syncState.cursor, 20)
    }

    func testStrictOfflineCreatePayloadContainsOnlyBackendRequestKeys() throws {
        let request = TransactionCreateRequest(
            transactionType: .expense,
            accountId: "account-a",
            counterpartyAccountId: nil,
            categoryId: "category-a",
            amount: "10",
            currency: .RUB,
            occurredAt: nil,
            transactionDate: "2026-08-21",
            description: nil,
            sourceType: "manual"
        )
        let payload = try OfflineSyncPayloadContract.payload(
            entityType: .transactions,
            operation: .create,
            request: request
        )

        XCTAssertEqual(Set(payload.keys), Set([
            "transactionType", "accountId", "categoryId", "amount", "currency", "transactionDate", "sourceType",
        ]))
        XCTAssertNil(payload["id"])
        XCTAssertNil(payload["version"])
        XCTAssertNil(payload["transferStatus"])

        let updatePayload = try OfflineSyncPayloadContract.payload(
            entityType: .transactions,
            operation: .update,
            request: TransactionOfflineUpdateRequest(TransactionUpdateRequest(
                transactionType: nil,
                accountId: nil,
                counterpartyAccountId: nil,
                categoryId: nil,
                amount: "11",
                currency: nil,
                occurredAt: nil,
                transactionDate: nil,
                description: nil,
                sourceType: nil,
                version: 7
            ))
        )
        XCTAssertEqual(Set(updatePayload.keys), Set(["amount"]))
        XCTAssertNil(updatePayload["version"])
    }

    func testResponseModelCannotBeQueuedAsStrictCreatePayload() throws {
        let response = TestFixtures.account(id: UUID().uuidString, payment: true)
        XCTAssertThrowsError(
            try OfflineSyncPayloadContract.payload(
                entityType: .accounts,
                operation: .create,
                request: response
            )
        )
    }

    func testEntityIdAndBaseVersionStayInSyncEnvelope() throws {
        let entityId = UUID().uuidString
        XCTAssertNoThrow(try OfflineSyncPayloadContract.validateEnvelope(
            entityId: entityId,
            operation: .create,
            baseVersion: nil
        ))
        XCTAssertNoThrow(try OfflineSyncPayloadContract.validateEnvelope(
            entityId: entityId,
            operation: .update,
            baseVersion: 2
        ))
        XCTAssertThrowsError(try OfflineSyncPayloadContract.validateEnvelope(
            entityId: "local-id",
            operation: .create,
            baseVersion: nil
        ))
        XCTAssertThrowsError(try OfflineSyncPayloadContract.validateEnvelope(
            entityId: entityId,
            operation: .delete,
            baseVersion: nil
        ))
    }

    func testStrictPayloadKeySetsCoverBackendSyncEntities() throws {
        let accountCreate = try OfflineSyncPayloadContract.payload(
            entityType: .accounts,
            operation: .create,
            request: AccountCreateRequest(
                name: "Card",
                accountType: .card,
                ownershipType: .personal,
                householdId: nil,
                assetCategoryId: nil,
                currency: .RUB,
                initialBalance: "0",
                isPaymentAccount: true
            )
        )
        XCTAssertEqual(
            Set(accountCreate.keys),
            Set(["name", "accountType", "ownershipType", "currency", "initialBalance", "isPaymentAccount"])
        )

        let accountUpdate = try OfflineSyncPayloadContract.payload(
            entityType: .accounts,
            operation: .update,
            request: AccountOfflineUpdateRequest(AccountUpdateRequest(
                name: "Card 2",
                currentBalance: "999",
                currency: nil,
                accountType: nil,
                assetCategoryId: nil,
                isPaymentAccount: false,
                version: 2
            ))
        )
        XCTAssertEqual(Set(accountUpdate.keys), Set(["name", "assetCategoryId", "isPaymentAccount"]))
        XCTAssertNil(accountUpdate["currentBalance"])
        XCTAssertNil(accountUpdate["version"])

        let categoryCreate = try OfflineSyncPayloadContract.payload(
            entityType: .categories,
            operation: .create,
            request: CategoryCreateRequest(
                name: "Food",
                type: .expense,
                scope: .personal,
                householdId: nil,
                iconKey: nil,
                color: nil
            )
        )
        XCTAssertEqual(Set(categoryCreate.keys), Set(["name", "type", "scope"]))

        let categoryUpdate = try OfflineSyncPayloadContract.payload(
            entityType: .categories,
            operation: .update,
            request: CategoryOfflineUpdateRequest(CategoryUpdateRequest(
                name: "Food 2",
                iconKey: nil,
                color: nil,
                version: 3
            ))
        )
        XCTAssertEqual(Set(categoryUpdate.keys), Set(["name"]))
        XCTAssertNil(categoryUpdate["version"])

        let assetCreate = try OfflineSyncPayloadContract.payload(
            entityType: .assetCategories,
            operation: .create,
            request: AssetCategoryCreateRequest(
                name: "Broker",
                scopeType: .personal,
                householdId: nil,
                currency: .RUB,
                assetType: .brokerage,
                iconKey: nil,
                manualAmount: "0",
                isInvestment: true
            )
        )
        XCTAssertEqual(
            Set(assetCreate.keys),
            Set(["name", "scopeType", "currency", "assetType", "manualAmount", "isInvestment"])
        )

        let assetUpdate = try OfflineSyncPayloadContract.payload(
            entityType: .assetCategories,
            operation: .update,
            request: AssetCategoryOfflineUpdateRequest(AssetCategoryUpdateRequest(
                name: "Broker 2",
                manualAmount: nil,
                assetType: nil,
                iconKey: nil,
                isInvestment: nil,
                version: 4
            ))
        )
        XCTAssertEqual(Set(assetUpdate.keys), Set(["name"]))
        XCTAssertNil(assetUpdate["version"])

        let detailedMigrationAccountId = UUID().uuidString
        let detailedMigrationCreate = try OfflineSyncPayloadContract.payload(
            entityType: .investmentMigrations,
            operation: .create,
            request: InvestmentMigrationCreateRequest(
                assetCategoryId: UUID().uuidString,
                name: "Broker",
                icon: nil,
                color: nil,
                assetType: .brokerage,
                currency: .RUB,
                scope: .personal,
                householdId: nil,
                accountIds: [detailedMigrationAccountId],
                accountVersions: [detailedMigrationAccountId: 1]
            )
        )
        XCTAssertEqual(
            Set(detailedMigrationCreate.keys),
            Set(["assetCategoryId", "name", "assetType", "currency", "scope", "accountIds", "accountVersions"])
        )
        XCTAssertNil(detailedMigrationCreate["id"])
        XCTAssertNil(detailedMigrationCreate["version"])

        let migrationAccountId = UUID().uuidString
        let migrationCreate = try OfflineSyncPayloadContract.payload(
            entityType: .investmentMigrations,
            operation: .create,
            request: InvestmentMigrationCreateRequest(
                assetCategoryId: UUID().uuidString,
                name: "Investments",
                icon: "chart.line.uptrend.xyaxis",
                color: "#112233",
                assetType: .brokerage,
                currency: .RUB,
                scope: .personal,
                householdId: nil,
                accountIds: [migrationAccountId],
                accountVersions: [migrationAccountId: 1]
            )
        )
        XCTAssertEqual(
            Set(migrationCreate.keys),
            Set([
                "assetCategoryId", "name", "icon", "color", "assetType", "currency",
                "scope", "accountIds", "accountVersions",
            ])
        )

        let planCreate = try OfflineSyncPayloadContract.payload(
            entityType: .planningPlans,
            operation: .create,
            request: PlanningPlanCreateRequest(scope: .personal, month: "2026-08", currency: .RUB, householdId: nil)
        )
        XCTAssertEqual(Set(planCreate.keys), Set(["scope", "month", "currency"]))

        let incomeCreate = try OfflineSyncPayloadContract.payload(
            entityType: .planningIncomeSources,
            operation: .create,
            request: PlanningIncomeSourceCreateRequest(amount: "100", source: "Salary", description: nil, dayOfMonth: 1),
            planId: UUID().uuidString
        )
        XCTAssertEqual(Set(incomeCreate.keys), Set(["planId", "amount", "source", "dayOfMonth"]))

        let incomeUpdate = try OfflineSyncPayloadContract.payload(
            entityType: .planningIncomeSources,
            operation: .update,
            request: PlanningIncomeSourceOfflineUpdateRequest(PlanningIncomeSourceUpdateRequest(
                amount: "120",
                source: nil,
                description: nil,
                dayOfMonth: nil,
                version: 5
            ))
        )
        XCTAssertEqual(Set(incomeUpdate.keys), Set(["amount"]))
        XCTAssertNil(incomeUpdate["version"])

        let allocationCreate = try OfflineSyncPayloadContract.payload(
            entityType: .planningAllocations,
            operation: .create,
            request: PlanningAllocationCreateRequest(
                targetType: .expense_category,
                targetId: UUID().uuidString,
                comment: nil,
                allocationMode: .amount,
                allocationValue: "50",
                recurrenceType: nil,
                isSavingsGoal: nil,
                goalTargetAmount: nil,
                goalDueMonth: nil
            ),
            planId: UUID().uuidString
        )
        XCTAssertEqual(
            Set(allocationCreate.keys),
            Set(["planId", "targetType", "targetId", "allocationMode", "allocationValue"])
        )

        let allocationUpdate = try OfflineSyncPayloadContract.payload(
            entityType: .planningAllocations,
            operation: .update,
            request: PlanningAllocationOfflineUpdateRequest(PlanningAllocationUpdateRequest(
                targetType: nil,
                targetId: nil,
                comment: nil,
                allocationMode: nil,
                allocationValue: "60",
                recurrenceType: nil,
                isSavingsGoal: nil,
                goalTargetAmount: nil,
                goalDueMonth: nil,
                version: 6
            ))
        )
        XCTAssertEqual(Set(allocationUpdate.keys), Set(["allocationValue"]))
        XCTAssertNil(allocationUpdate["version"])
    }

    func testStrictPayloadContractRejectsResponseOnlyFieldsForEverySyncEntity() {
        let responseFieldCases: [(SyncEntityType, [String: SyncJSONValue], String)] = [
            (.transactions, [
                "transactionType": .string("expense"), "accountId": .string(UUID().uuidString),
                "amount": .string("1"), "currency": .string("RUB"),
                "transactionDate": .string("2026-08-21"), "sourceType": .string("manual"),
                "transferStatus": .string("posted"),
            ], "transferStatus"),
            (.accounts, [
                "name": .string("Card"), "accountType": .string("card"),
                "ownershipType": .string("personal"), "currency": .string("RUB"),
                "initialBalance": .string("0"), "currentBalance": .string("0"),
            ], "currentBalance"),
            (.categories, [
                "name": .string("Food"), "type": .string("expense"),
                "scope": .string("personal"), "ownerUserId": .string("user-a"),
            ], "ownerUserId"),
            (.assetCategories, [
                "name": .string("Broker"), "scopeType": .string("personal"),
                "currency": .string("RUB"), "recordStatus": .string("active"),
            ], "recordStatus"),
            (.investmentMigrations, [
                "assetCategoryId": .string(UUID().uuidString), "name": .string("Investments"),
                "assetType": .string("brokerage"), "currency": .string("RUB"),
                "accountIds": .array([.string(UUID().uuidString)]),
                "accountVersions": .object([UUID().uuidString: .int(1)]),
                "accounts": .array([]),
            ], "accounts"),
            (.planningPlans, [
                "scope": .string("personal"), "month": .string("2026-08"),
                "currency": .string("RUB"), "summary": .object([:]),
            ], "summary"),
            (.planningIncomeSources, [
                "planId": .string(UUID().uuidString), "amount": .string("100"),
                "source": .string("Salary"), "dayOfMonth": .int(1),
                "confirmationState": .string("planned"),
            ], "confirmationState"),
            (.planningAllocations, [
                "planId": .string(UUID().uuidString), "targetType": .string("account"),
                "targetId": .string(UUID().uuidString), "allocationMode": .string("amount"),
                "allocationValue": .string("50"), "targetSnapshot": .object([:]),
            ], "targetSnapshot"),
        ]

        for (entityType, payload, responseField) in responseFieldCases {
            XCTAssertThrowsError(
                try OfflineSyncPayloadContract.validate(
                    payload: payload,
                    entityType: entityType,
                    operation: .create
                ),
                "\(entityType.rawValue) accepted response-only field \(responseField)"
            ) { error in
                guard case LocalStoreError.invalidOfflinePayload(let reason) = error else {
                    return XCTFail("Unexpected error: \(error)")
                }
                XCTAssertTrue(reason.contains(responseField), "Unexpected reason: \(reason)")
            }
        }
    }

    func testTombstoneRequiresPersistedPersonalEvidenceAndRejectsSharedReferences() throws {
        let scope = LocalStoreScope(viewerUserId: "user-a")
        var snapshot = FinanceLocalSnapshot.empty(scope: scope, deviceId: "device")
        snapshot.accounts = [
            localRecord(TestFixtures.account(id: "personal-account", payment: true), entityType: .accounts),
            localRecord(TestFixtures.account(id: "shared-account", ownership: .shared, householdId: "h"), entityType: .accounts),
        ]
        let personalTransaction = TestFixtures.transaction(id: UUID().uuidString, accountId: "personal-account")
        let evidence = try PersonalSyncOwnershipValidator.evidence(
            scope: scope,
            entityType: .transactions,
            entityId: personalTransaction.id,
            ownershipPayload: SyncJSONValue.object(from: personalTransaction),
            snapshot: snapshot
        )
        let tombstone = PendingMutation(
            deviceId: "device",
            scope: scope,
            entityType: .transactions,
            entityId: personalTransaction.id,
            operation: .delete,
            baseVersion: 1,
            ownershipEvidence: evidence
        )
        let uncertainLegacy = PendingMutation(
            deviceId: "device",
            scope: scope,
            entityType: .transactions,
            entityId: UUID().uuidString,
            operation: .delete,
            baseVersion: 1
        )
        let sharedTransaction = TestFixtures.transaction(id: UUID().uuidString, accountId: "shared-account")

        XCTAssertTrue(FinanceSyncService.isPersonalOnlyMutation(tombstone, snapshot: snapshot))
        XCTAssertFalse(FinanceSyncService.isPersonalOnlyMutation(uncertainLegacy, snapshot: snapshot))
        XCTAssertThrowsError(
            try PersonalSyncOwnershipValidator.evidence(
                scope: scope,
                entityType: .transactions,
                entityId: sharedTransaction.id,
                ownershipPayload: SyncJSONValue.object(from: sharedTransaction),
                snapshot: snapshot
            )
        )
    }

    func testPullRejectsUnknownTombstonesForeignOwnersAndMismatchedEntityIds() throws {
        let scope = LocalStoreScope(viewerUserId: "user-a")
        var snapshot = FinanceLocalSnapshot.empty(scope: scope, deviceId: "device")
        let knownAccount = TestFixtures.account(id: UUID().uuidString, payment: true)
        snapshot.accounts = [localRecord(knownAccount, entityType: .accounts)]
        let index = PersonalOwnershipIndex(snapshot: snapshot)

        let knownTombstone = syncChange(
            entityType: .accounts,
            entityId: knownAccount.id,
            changeType: "delete",
            payload: nil,
            tombstonePayload: [
                "id": .string(knownAccount.id),
                "entityType": .string(SyncEntityType.accounts.rawValue),
            ]
        )
        let unknownTombstone = syncChange(
            entityType: .accounts,
            entityId: UUID().uuidString,
            changeType: "delete",
            payload: nil,
            tombstonePayload: [
                "id": .string(UUID().uuidString),
                "entityType": .string(SyncEntityType.accounts.rawValue),
            ]
        )
        let foreignAccount = Account(
            id: UUID().uuidString,
            name: "Foreign",
            accountType: .card,
            ownershipType: .personal,
            ownerUserId: "user-b",
            householdId: nil,
            assetCategoryId: nil,
            currency: .RUB,
            initialBalance: "0",
            currentBalance: "0",
            isPaymentAccount: true,
            status: .active,
            version: 1
        )
        let foreignChange = syncChange(
            entityType: .accounts,
            entityId: foreignAccount.id,
            changeType: "update",
            payload: try SyncJSONValue.object(from: foreignAccount)
        )
        var mismatchedPayload = try SyncJSONValue.object(from: knownAccount)
        mismatchedPayload["id"] = .string(UUID().uuidString)
        let mismatchedChange = syncChange(
            entityType: .accounts,
            entityId: knownAccount.id,
            changeType: "update",
            payload: mismatchedPayload
        )

        XCTAssertTrue(PersonalSyncOwnershipValidator.allows(change: knownTombstone, snapshot: snapshot, index: index))
        XCTAssertFalse(PersonalSyncOwnershipValidator.allows(change: unknownTombstone, snapshot: snapshot, index: index))
        XCTAssertFalse(PersonalSyncOwnershipValidator.allows(change: foreignChange, snapshot: snapshot, index: index))
        XCTAssertFalse(PersonalSyncOwnershipValidator.allows(change: mismatchedChange, snapshot: snapshot, index: index))
    }

    func testPullRequiresValidatedPersonalParentPlanAndPersonalReferences() throws {
        let scope = LocalStoreScope(viewerUserId: "user-a")
        var snapshot = FinanceLocalSnapshot.empty(scope: scope, deviceId: "device")
        let personalAccount = TestFixtures.account(id: UUID().uuidString, payment: true)
        let sharedAccount = TestFixtures.account(
            id: UUID().uuidString,
            ownership: .shared,
            householdId: UUID().uuidString,
            payment: true
        )
        snapshot.accounts = [
            localRecord(personalAccount, entityType: .accounts),
            localRecord(sharedAccount, entityType: .accounts),
        ]

        let planId = UUID().uuidString
        let incomeId = UUID().uuidString
        let planChange = syncChange(
            entityType: .planningPlans,
            entityId: planId,
            changeType: "create",
            payload: [
                "id": .string(planId), "scope": .string("personal"),
                "ownerUserId": .string("user-a"), "householdId": .null,
                "month": .string("2026-08"), "currency": .string("RUB"),
            ]
        )
        let incomeChange = syncChange(
            entityType: .planningIncomeSources,
            entityId: incomeId,
            changeType: "create",
            payload: [
                "id": .string(incomeId), "planId": .string(planId),
                "amount": .string("100"), "source": .string("Salary"),
                "dayOfMonth": .int(1),
            ]
        )
        var index = PersonalOwnershipIndex(snapshot: snapshot)
        index.includeClearlyPersonalParents(from: [incomeChange, planChange], viewerUserId: scope.viewerUserId)

        XCTAssertTrue(PersonalSyncOwnershipValidator.allows(change: planChange, snapshot: snapshot, index: index))
        XCTAssertTrue(PersonalSyncOwnershipValidator.allows(change: incomeChange, snapshot: snapshot, index: index))

        let foreignPlanId = UUID().uuidString
        let foreignPlan = syncChange(
            entityType: .planningPlans,
            entityId: foreignPlanId,
            changeType: "create",
            payload: [
                "id": .string(foreignPlanId), "scope": .string("personal"),
                "ownerUserId": .string("user-b"), "householdId": .null,
                "month": .string("2026-08"), "currency": .string("RUB"),
            ]
        )
        let untrustedChildId = UUID().uuidString
        let untrustedChild = syncChange(
            entityType: .planningIncomeSources,
            entityId: untrustedChildId,
            changeType: "create",
            payload: [
                "id": .string(untrustedChildId), "planId": .string(foreignPlanId),
                "_parentScope": .string("personal"), "amount": .string("100"),
                "source": .string("Foreign"), "dayOfMonth": .int(1),
            ]
        )
        var foreignIndex = PersonalOwnershipIndex(snapshot: snapshot)
        foreignIndex.includeClearlyPersonalParents(from: [foreignPlan, untrustedChild], viewerUserId: scope.viewerUserId)
        XCTAssertFalse(PersonalSyncOwnershipValidator.allows(change: foreignPlan, snapshot: snapshot, index: foreignIndex))
        XCTAssertFalse(PersonalSyncOwnershipValidator.allows(change: untrustedChild, snapshot: snapshot, index: foreignIndex))

        let sharedTransactionId = UUID().uuidString
        let sharedTransaction = syncChange(
            entityType: .transactions,
            entityId: sharedTransactionId,
            changeType: "create",
            payload: [
                "id": .string(sharedTransactionId), "transactionType": .string("expense"),
                "accountId": .string(sharedAccount.id), "amount": .string("10"),
                "currency": .string("RUB"), "occurredAt": .string(Date().ISO8601Format()),
                "sourceType": .string("manual"),
            ]
        )
        XCTAssertFalse(PersonalSyncOwnershipValidator.allows(change: sharedTransaction, snapshot: snapshot, index: index))
    }

    func testQuarantinedPullChangeIsPersistedWithoutApplyingEntity() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceAppQuarantine-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let scope = LocalStoreScope(viewerUserId: "user-a")
        let store = FileBackedFinanceLocalStore(rootURL: root)
        let foreignAccountId = UUID().uuidString
        let foreignChange = syncChange(
            entityType: .accounts,
            entityId: foreignAccountId,
            changeType: "create",
            payload: [
                "id": .string(foreignAccountId), "name": .string("Foreign"),
                "accountType": .string("card"), "ownershipType": .string("personal"),
                "ownerUserId": .string("user-b"), "householdId": .null,
                "currency": .string("RUB"), "initialBalance": .string("0"),
                "currentBalance": .string("0"), "isPaymentAccount": .bool(true),
                "status": .string("active"),
            ]
        )

        try await store.quarantinePullChanges(
            scope: scope,
            deviceId: "device",
            changes: [foreignChange]
        )
        let snapshot = try await store.loadSnapshot(scope: scope, deviceId: "device")

        XCTAssertTrue(snapshot.accounts.isEmpty)
        XCTAssertEqual(snapshot.issues.count, 1)
        XCTAssertEqual(snapshot.issues.first?.entityId, foreignAccountId)
        XCTAssertEqual(snapshot.issues.first?.errorCode, "PERSONAL_ONLY_PULL_QUARANTINED")
    }

    func testLocalStoreUsesFileProtectionAndBackupExclusion() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceAppProtection-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let scope = LocalStoreScope(viewerUserId: "user-a")
        let store = FileBackedFinanceLocalStore(rootURL: root)
        try await store.saveSnapshot(.empty(scope: scope, deviceId: "device"))

        let fileURL = root.appendingPathComponent("\(scope.storageKey).json")
        XCTAssertEqual(try root.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup, true)
        XCTAssertEqual(try fileURL.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup, true)
#if os(iOS) && !targetEnvironment(simulator)
        let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
        XCTAssertEqual(attributes[.protectionKey] as? FileProtectionType, .completeUntilFirstUserAuthentication)
#endif
        XCTAssertEqual(
            FileBackedFinanceLocalStore.snapshotFileProtection,
            .completeUntilFirstUserAuthentication
        )
        XCTAssertTrue(FileBackedFinanceLocalStore.snapshotWritingOptions.contains(.atomic))
        XCTAssertTrue(FileBackedFinanceLocalStore.snapshotWritingOptions.contains(
            .completeFileProtectionUntilFirstUserAuthentication
        ))
    }

    func testLoadingExistingSnapshotMigratesProtectionAndBackupExclusion() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FinanceAppProtectionMigration-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let scope = LocalStoreScope(viewerUserId: "user-a")
        let fileURL = root.appendingPathComponent("\(scope.storageKey).json")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        var snapshot = FinanceLocalSnapshot.empty(scope: scope, deviceId: "device")
        snapshot.syncState.cursor = 42
        try JSONEncoder().encode(snapshot).write(to: fileURL, options: .atomic)

        var rootForValues = root
        var rootValues = URLResourceValues()
        rootValues.isExcludedFromBackup = false
        try rootForValues.setResourceValues(rootValues)
        var fileForValues = fileURL
        var fileValues = URLResourceValues()
        fileValues.isExcludedFromBackup = false
        try fileForValues.setResourceValues(fileValues)
#if os(iOS) && !targetEnvironment(simulator)
        try FileManager.default.setAttributes(
            [.protectionKey: FileProtectionType.none],
            ofItemAtPath: fileURL.path
        )
#endif

        let loaded = try await FileBackedFinanceLocalStore(rootURL: root).loadSnapshot(
            scope: scope,
            deviceId: "device"
        )

        XCTAssertEqual(loaded.syncState.cursor, 42)
        XCTAssertEqual(try root.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup, true)
        XCTAssertEqual(try fileURL.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup, true)
#if os(iOS) && !targetEnvironment(simulator)
        let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
        XCTAssertEqual(attributes[.protectionKey] as? FileProtectionType, .completeUntilFirstUserAuthentication)
#endif
        XCTAssertEqual(
            FileBackedFinanceLocalStore.snapshotFileProtection,
            .completeUntilFirstUserAuthentication
        )
    }

    func testOCRRemainsOnlineOnlyAndOutsideSyncEntityTypes() {
        XCTAssertFalse(SyncEntityType.allCases.map(\.rawValue).contains("capture_draft"))
        XCTAssertFalse(SyncEntityType.allCases.map(\.rawValue).contains("screenshot_ocr"))
        XCTAssertTrue(SyncQueuePolicy.onlineOnlyReason(.screenshotOCR).contains("только онлайн"))
        XCTAssertTrue(SyncQueuePolicy.onlineOnlyReason(.screenshotOCR).contains("нельзя сохранять локально"))
    }

    private func localRecord<Entity: Identifiable & Codable & Sendable>(
        _ entity: Entity,
        entityType: SyncEntityType
    ) -> LocalRecord<Entity> where Entity.ID == String {
        LocalRecord(
            entity: entity,
            metadata: LocalRecordMetadata(
                entityType: entityType,
                entityId: entity.id,
                serverVersion: 1,
                syncStatus: .synced,
                pendingMutationId: nil,
                updatedAt: Date().ISO8601Format(),
                lastSyncedAt: Date().ISO8601Format()
            )
        )
    }

    private func syncChange(
        entityType: SyncEntityType,
        entityId: String,
        changeType: String,
        payload: [String: SyncJSONValue]?,
        tombstonePayload: [String: SyncJSONValue]? = nil
    ) -> SyncChange {
        SyncChange(
            seq: 1,
            entityType: entityType,
            entityId: entityId,
            changeType: changeType,
            entityVersion: 1,
            entityUpdatedAt: Date().ISO8601Format(),
            changedByUserId: "user-a",
            clientMutationId: nil,
            payload: payload,
            tombstonePayload: tombstonePayload,
            createdAt: Date().ISO8601Format()
        )
    }
}
