import SwiftUI

struct CaptureDraftReviewCard: View {
    let isAuthenticated: Bool
    let drafts: [CaptureDraft]
    let screenshotAggregateDrafts: [ScreenshotAggregateDraftUi]
    let accounts: [Account]
    let categories: [Category]
    let isLoading: Bool
    let message: String?
    let screenshotOcrStatus: String?
    let onRefresh: () -> Void
    let onPickScreenshot: () -> Void
    let onAggregateCategorySelected: (String, String) -> Void
    let onAggregateIncludedChanged: (String, Bool) -> Void
    let onAggregateCreateCategory: (String, String) -> Void
    let onConfirmAggregateDrafts: () -> Void
    let onClearAggregateDrafts: () -> Void
    let onConfirm: (CaptureDraft, String, String, String, String) -> Void
    let onDiscard: (CaptureDraft) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                IconBubble(systemName: "doc.text.viewfinder", color: FinanceColors.investment, size: 36)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Черновики операций")
                        .font(.headline)
                    Text("Проверьте распознанные данные перед созданием")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Button {
                onPickScreenshot()
            } label: {
                HStack {
                    Image(systemName: "photo.on.rectangle")
                    Text("Выбрать скриншот")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(!isAuthenticated || isLoading)

            if let status = screenshotOcrStatus, !status.isEmpty {
                Text(status)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Button {
                onRefresh()
            } label: {
                HStack {
                    Image(systemName: "arrow.clockwise")
                    Text("Обновить")
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(!isAuthenticated || isLoading)

            if let msg = message, !msg.isEmpty {
                Text(msg)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if !screenshotAggregateDrafts.isEmpty {
                ScreenshotAggregateDraftList(
                    drafts: screenshotAggregateDrafts,
                    categories: categories,
                    isLoading: isLoading,
                    onCategorySelected: onAggregateCategorySelected,
                    onIncludedChanged: onAggregateIncludedChanged,
                    onCreateCategory: onAggregateCreateCategory,
                    onConfirm: onConfirmAggregateDrafts,
                    onClear: onClearAggregateDrafts
                )
            }

            if !isAuthenticated {
                Text("Войдите, чтобы синхронизировать черновики.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else if !drafts.isEmpty || !screenshotAggregateDrafts.isEmpty {
                if accounts.isEmpty || categories.isEmpty {
                    Text("Войдите, чтобы проверить и подтвердить OCR-черновики.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                } else {
                    ForEach(drafts) { draft in
                        CaptureDraftRow(
                            draft: draft,
                            accounts: accounts,
                            categories: categories,
                            isLoading: isLoading,
                            onConfirm: onConfirm,
                            onDiscard: onDiscard
                        )
                    }
                }
            } else if screenshotAggregateDrafts.isEmpty {
                Text("Нет черновиков на проверку. Отправьте скриншот в OCR или обновите список.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
    }
}
