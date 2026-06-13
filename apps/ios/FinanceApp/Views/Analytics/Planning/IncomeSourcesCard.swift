import SwiftUI

struct IncomeSourcesCard: View {
    let plan: PlanningPlan
    let currency: CurrencyCode
    let isLoading: Bool
    let onCreate: (PlanningIncomeSourceCreateRequest) async -> Void
    let onUpdate: (PlanningIncomeSource, PlanningIncomeSourceUpdateRequest) async -> Void
    let onConfirm: (PlanningIncomeSource) async -> Void
    let onDelete: (PlanningIncomeSource) async -> Void

    @State private var source = ""
    @State private var amount = ""
    @State private var day = ""
    @State private var showAddForm = false

    private var normalizedAmount: String? { normalizePlanningAmount(amount) }
    private var planningDay: Int? { toPlanningDay(day) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Источники дохода")
                .font(.headline)

            if !showAddForm {
                Button {
                    showAddForm = true
                } label: {
                    Text("Добавить источник")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .tint(FinanceColors.planningPrimary)
                .disabled(isLoading)
            } else {
                TextField("Источник", text: $source)
                    .textFieldStyle(.roundedBorder)

                HStack(spacing: 8) {
                    TextField("Сумма", text: $amount)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.decimalPad)
                        .onChange(of: amount) { _, new in amount = planningDecimalInput(new) }
                    TextField("День месяца", text: $day)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                        .onChange(of: day) { _, new in day = String(new.filter(\.isNumber).prefix(2)) }
                }

                Button {
                    guard let normAmt = normalizedAmount, let pDay = planningDay else { return }
                    let request = PlanningIncomeSourceCreateRequest(
                        amount: normAmt,
                        source: source.trimmingCharacters(in: .whitespaces),
                        description: nil,
                        dayOfMonth: pDay,
                        effectiveDate: nil
                    )
                    Task { await onCreate(request) }
                    source = ""
                    amount = ""
                    day = ""
                    showAddForm = false
                } label: {
                    Text("Добавить источник")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(FinanceColors.planningPrimary)
                .disabled(isLoading || source.trimmingCharacters(in: .whitespaces).isEmpty || normalizedAmount == nil || planningDay == nil)
            }

            if plan.incomeSources.isEmpty {
                Text("Источников дохода пока нет")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            } else {
                ForEach(plan.incomeSources) { item in
                    IncomeSourceRow(
                        source: item,
                        currency: currency,
                        isLoading: isLoading,
                        onUpdate: onUpdate,
                        onConfirm: onConfirm,
                        onDelete: onDelete
                    )
                }
            }
        }
        .padding(16)
        .background(Color(UIColor.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

private struct IncomeSourceRow: View {
    let source: PlanningIncomeSource
    let currency: CurrencyCode
    let isLoading: Bool
    let onUpdate: (PlanningIncomeSource, PlanningIncomeSourceUpdateRequest) async -> Void
    let onConfirm: (PlanningIncomeSource) async -> Void
    let onDelete: (PlanningIncomeSource) async -> Void

    @State private var isEditing = false
    @State private var editSource = ""
    @State private var editAmount = ""
    @State private var editDay = ""

    private var normalizedEditAmount: String? { normalizePlanningAmount(editAmount) }
    private var editPlanningDay: Int? { toPlanningDay(editDay) }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(source.source)
                        .font(.subheadline)
                        .fontWeight(.medium)
                    Text("\(MoneyHelpers.format(source.amount, currency: currency)) • день \(source.dayOfMonth) • \(source.confirmationState == .confirmed ? "подтверждён" : "ожидает")")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
                Button(isEditing ? "Закрыть" : "Править") {
                    if !isEditing {
                        editSource = source.source
                        editAmount = source.amount
                        editDay = "\(source.dayOfMonth)"
                    }
                    isEditing.toggle()
                }
                .font(.caption)
                .foregroundColor(FinanceColors.planningPrimary)
            }

            if isEditing {
                TextField("Источник", text: $editSource)
                    .textFieldStyle(.roundedBorder)

                HStack(spacing: 8) {
                    TextField("Сумма", text: $editAmount)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.decimalPad)
                        .onChange(of: editAmount) { _, new in editAmount = planningDecimalInput(new) }
                    TextField("День месяца", text: $editDay)
                        .textFieldStyle(.roundedBorder)
                        .keyboardType(.numberPad)
                        .onChange(of: editDay) { _, new in editDay = String(new.filter(\.isNumber).prefix(2)) }
                }

                HStack(spacing: 8) {
                    Button("Удалить", role: .destructive) {
                        Task { await onDelete(source) }
                    }
                    .buttonStyle(.bordered)
                    .disabled(isLoading)
                    .frame(maxWidth: .infinity)

                    Button("Сохранить") {
                        guard let normAmt = normalizedEditAmount, let pDay = editPlanningDay else { return }
                        let request = PlanningIncomeSourceUpdateRequest(
                            source: editSource.trimmingCharacters(in: .whitespaces),
                            amount: normAmt,
                            description: nil,
                            dayOfMonth: pDay,
                            effectiveDate: nil,
                            version: source.version
                        )
                        Task { await onUpdate(source, request) }
                        isEditing = false
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(FinanceColors.planningPrimary)
                    .disabled(isLoading || editSource.trimmingCharacters(in: .whitespaces).isEmpty || normalizedEditAmount == nil || editPlanningDay == nil)
                    .frame(maxWidth: .infinity)
                }
            }

            if source.confirmationState != .confirmed {
                Button("Подтвердить доход") {
                    Task { await onConfirm(source) }
                }
                .buttonStyle(.bordered)
                .tint(FinanceColors.income)
                .frame(maxWidth: .infinity)
                .disabled(isLoading)
            }
        }
        .padding(10)
        .background(Color(UIColor.tertiarySystemBackground).opacity(0.35))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
