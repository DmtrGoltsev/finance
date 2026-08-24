import SwiftUI
import PhotosUI

struct OperationsTab: View {
    let dashboard: FinanceDashboard?
    let onDeleteTransaction: (String) -> Void
    let apiClient: FinanceApiClient
    let onRefreshDashboard: @Sendable () async -> Void
    // Integration hook for a root-owned online-or-queue update path.
    let onUpdateTransaction: ((String, TransactionUpdateRequest) async throws -> Void)?

    @State private var captureDrafts: [CaptureDraft] = []
    @State private var screenshotAggregateDrafts: [ScreenshotAggregateDraftUi] = []
    @State private var captureIsLoading = false
    @State private var captureMessage: String?
    @State private var screenshotOcrStatus: String?
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var showPhotoPicker = false
    @State private var editingTransaction: Transaction?

    init(
        dashboard: FinanceDashboard?,
        onDeleteTransaction: @escaping (String) -> Void,
        apiClient: FinanceApiClient,
        onRefreshDashboard: @escaping @Sendable () async -> Void,
        onUpdateTransaction: ((String, TransactionUpdateRequest) async throws -> Void)? = nil
    ) {
        self.dashboard = dashboard
        self.onDeleteTransaction = onDeleteTransaction
        self.apiClient = apiClient
        self.onRefreshDashboard = onRefreshDashboard
        self.onUpdateTransaction = onUpdateTransaction
    }

    var body: some View {
        let items = (dashboard?.personalTransactions ?? [])
            .sorted(by: Transaction.newestFirst)

        ScrollView {
            VStack(spacing: 12) {
                CaptureDraftReviewCard(
                    isAuthenticated: dashboard?.session.isAuthenticated == true,
                    drafts: captureDrafts,
                    screenshotAggregateDrafts: screenshotAggregateDrafts,
                    accounts: reviewAccounts,
                    categories: reviewCategories,
                    isLoading: captureIsLoading,
                    message: captureMessage,
                    screenshotOcrStatus: screenshotOcrStatus,
                    onRefresh: { Task { await loadCaptureDrafts() } },
                    onPickScreenshot: { showPhotoPicker = true },
                    onAggregateCategorySelected: { key, id in updateAggregateCategory(key: key, categoryId: id) },
                    onAggregateIncludedChanged: { key, val in updateAggregateIncluded(key: key, include: val) },
                    onAggregateCreateCategory: { key, name in Task { await createCategoryForAggregate(key: key, categoryName: name) } },
                    onConfirmAggregateDrafts: { Task { await createAggregateDrafts() } },
                    onClearAggregateDrafts: clearAggregateDrafts,
                    onConfirm: { draft, accId, catId, amt, date in Task { await confirmDraft(draft, accountId: accId, categoryId: catId, amount: amt, occurredDate: date) } },
                    onDiscard: { draft in Task { await discardDraft(draft) } }
                )

                if items.isEmpty {
                    EmptyState(text: "Операций пока нет. Добавьте расход, доход, перевод или инвестицию.")
                } else {
                    Text("Операции")
                        .font(.headline)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    ForEach(items) { transaction in
                        TransactionRow(
                            transaction: transaction,
                            categories: dashboard?.categories ?? [],
                            onDelete: { onDeleteTransaction(transaction.id) },
                            onEdit: { editingTransaction = transaction }
                        )
                    }
                }
            }
            .padding(16)
        }
        .photosPicker(isPresented: $showPhotoPicker, selection: $selectedPhotoItem, matching: .images)
        .onChange(of: selectedPhotoItem) { _, newItem in
            if let newItem {
                Task { await processScreenshot(newItem) }
                selectedPhotoItem = nil
            }
        }
        .task {
            if dashboard?.session.isAuthenticated == true {
                await loadCaptureDrafts()
            }
        }
        .refreshable {
            await loadCaptureDrafts()
        }
        .sheet(item: $editingTransaction) { transaction in
            TransactionEditSheet(
                transaction: transaction,
                dashboard: dashboard,
                onSave: { request in
                    if let onUpdateTransaction {
                        try await onUpdateTransaction(transaction.id, request)
                    } else {
                        _ = try await apiClient.updateTransaction(transactionId: transaction.id, request)
                    }
                    await onRefreshDashboard()
                },
                onDismiss: { editingTransaction = nil }
            )
        }
    }

    private var reviewAccounts: [Account] {
        (dashboard?.accounts ?? [])
            .filter { $0.status == .active && !$0.id.isEmpty && $0.ownershipType == .personal && $0.isPaymentAccount }
    }

    private var reviewCategories: [Category] {
        (dashboard?.categories ?? [])
            .filter { $0.status == .active && !$0.id.isEmpty && $0.scope == .personal && $0.type == .expense }
    }
}

extension OperationsTab {
    private func loadCaptureDrafts() async {
        captureIsLoading = true
        do {
            let (drafts, _) = try await apiClient.listCaptureDrafts(limit: nil, status: .pending)
            captureDrafts = drafts
            captureMessage = "Черновики обновлены"
        } catch {
            captureMessage = error.localizedDescription
        }
        captureIsLoading = false
    }

    private func processScreenshot(_ item: PhotosPickerItem) async {
        captureIsLoading = true
        screenshotOcrStatus = "Отправляем скриншот в backend OCR. Операции не создаются автоматически."
        screenshotAggregateDrafts = []

        guard let data = try? await item.loadTransferable(type: Data.self) else {
            screenshotOcrStatus = "Не удалось загрузить изображение"
            captureIsLoading = false
            return
        }

        let capturedAt = DateHelpers.nowISO()

        do {
            let response = try await apiClient.screenshotOcr(
                imageData: data,
                contentType: "image/jpeg",
                capturedAt: capturedAt,
                householdId: nil
            )

            if response.items.isEmpty {
                screenshotOcrStatus = "Backend OCR не нашёл расходов на скриншоте"
                captureMessage = "Выберите другой скриншот или добавьте расход вручную."
                captureIsLoading = false
                return
            }

            let activeIds = Set(reviewCategories.filter { $0.type == .expense }.map(\.id))
            let drafts = response.items.map { candidate -> ScreenshotAggregateDraftUi in
                let mappedId = CategoryAggregateMappingStore.shared.get(label: candidate.externalLabel)
                let validId = mappedId.flatMap { activeIds.contains($0) ? $0 : nil }
                return ScreenshotAggregateDraftUi(
                    candidate: candidate,
                    selectedCategoryId: validId ?? "",
                    include: validId != nil
                )
            }
            screenshotAggregateDrafts = drafts
            screenshotOcrStatus = "Backend OCR сформировал \(drafts.count) кандидатов. Проверьте их перед созданием черновиков."
            captureMessage = "Выберите категории и создайте черновики для ручной проверки."
        } catch {
            screenshotOcrStatus = "Backend OCR не вернул кандидатов для проверки"
            captureMessage = "\(error.localizedDescription). Выберите другой скриншот или добавьте расход вручную."
        }
        captureIsLoading = false
    }

    private func updateAggregateCategory(key: String, categoryId: String) {
        screenshotAggregateDrafts = screenshotAggregateDrafts.map { draft in
            if draft.candidate.idempotencyKey == key {
                var updated = draft
                updated.selectedCategoryId = categoryId
                updated.include = !categoryId.isEmpty
                return updated
            }
            return draft
        }
    }

    private func updateAggregateIncluded(key: String, include: Bool) {
        screenshotAggregateDrafts = screenshotAggregateDrafts.map { draft in
            if draft.candidate.idempotencyKey == key {
                var updated = draft
                updated.include = include
                return updated
            }
            return draft
        }
    }

    private func createCategoryForAggregate(key: String, categoryName: String) async {
        captureIsLoading = true
        captureMessage = "Создаём категорию"
        do {
            let request = CategoryCreateRequest(
                name: categoryName,
                type: .expense,
                scope: .personal,
                householdId: nil,
                iconKey: nil,
                color: nil
            )
            let category = try await apiClient.createCategory(request)
            updateAggregateCategory(key: key, categoryId: category.id)
            updateAggregateIncluded(key: key, include: true)
            await onRefreshDashboard()
            captureMessage = "Категория «\(categoryName)» создана"
        } catch {
            captureMessage = error.localizedDescription
        }
        captureIsLoading = false
    }

    private func createAggregateDrafts() async {
        let selected = screenshotAggregateDrafts.filter { $0.include && !$0.selectedCategoryId.isEmpty }
        if selected.isEmpty {
            captureMessage = "Выберите хотя бы одну категорию."
            return
        }
        captureIsLoading = true
        screenshotOcrStatus = "Создаём \(selected.count) черновиков для проверки"

        do {
            for draft in selected {
                let request = draft.candidate.toCreateRequest(categoryId: draft.selectedCategoryId)
                _ = try await apiClient.createCaptureDraft(request)
                CategoryAggregateMappingStore.shared.save(
                    label: draft.candidate.externalLabel,
                    categoryId: draft.selectedCategoryId
                )
            }
            await loadCaptureDrafts()
            screenshotAggregateDrafts = []
            screenshotOcrStatus = "Черновики для проверки созданы: \(selected.count)"
            captureMessage = "Проверьте каждый черновик и только потом подтвердите операцию."
        } catch {
            screenshotOcrStatus = "Не удалось создать черновики"
            captureMessage = error.localizedDescription
            captureIsLoading = false
        }
    }

    private func clearAggregateDrafts() {
        screenshotAggregateDrafts = []
        screenshotOcrStatus = nil
    }

    @MainActor
    private func confirmDraft(
        _ draft: CaptureDraft,
        accountId: String,
        categoryId: String,
        amount: String,
        occurredDate: String
    ) async {
        guard !accountId.isEmpty, !categoryId.isEmpty else {
            captureMessage = "Выберите счёт и категорию перед подтверждением"
            return
        }
        guard Decimal(string: amount) != nil, !occurredDate.isEmpty else {
            captureMessage = "Проверьте сумму и дату операции"
            return
        }
        captureIsLoading = true
        do {
            let needsUpdate = draft.accountId != accountId
                || draft.categoryId != categoryId
                || draft.amount != amount
                || draft.occurredDate != occurredDate
            if needsUpdate {
                let updateRequest = CaptureDraftUpdateRequest(
                    occurredAt: nil,
                    occurredDate: occurredDate,
                    amount: amount,
                    currency: nil,
                    description: nil,
                    merchantName: nil,
                    accountId: accountId,
                    categoryId: categoryId,
                    confidence: nil
                )
                let updated = try await apiClient.updateCaptureDraft(draftId: draft.id, updateRequest)
                _ = try await apiClient.confirmCaptureDraft(draftId: updated.id)
            } else {
                _ = try await apiClient.confirmCaptureDraft(draftId: draft.id)
            }
            captureMessage = "Черновик подтверждён"
            await onRefreshDashboard()
            await loadCaptureDrafts()
        } catch {
            captureMessage = error.localizedDescription
            captureIsLoading = false
        }
    }

    @MainActor
    private func discardDraft(_ draft: CaptureDraft) async {
        captureIsLoading = true
        do {
            try await apiClient.discardCaptureDraft(draftId: draft.id)
            captureMessage = "Черновик отклонён"
            await loadCaptureDrafts()
        } catch {
            captureMessage = error.localizedDescription
            captureIsLoading = false
        }
    }
}
