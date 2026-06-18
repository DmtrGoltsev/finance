import SwiftUI

struct PlanningAllocationEditor: View {
    @Binding var draft: PlanningAllocationDraft
    let currency: CurrencyCode
    let targetOptions: [PlanningTargetOption]
    let usedTargetIds: Set<String>

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach([AllocationTargetType.expense_category, .investment_asset_category], id: \.self) { targetType in
                        Button {
                            let savingsEnabled = draft.isSavingsGoal && targetType == .investment_asset_category
                            draft = PlanningAllocationDraft(
                                targetType: targetType,
                                targetId: "",
                                allocationMode: draft.allocationMode,
                                allocationValue: draft.allocationValue,
                                recurrenceType: draft.recurrenceType,
                                isSavingsGoal: savingsEnabled,
                                goalTargetAmount: savingsEnabled ? draft.goalTargetAmount : "",
                                goalDueMonth: savingsEnabled ? draft.goalDueMonth : nextPlanningMonth(),
                                comment: draft.comment
                            )
                        } label: {
                            Text(localizedTargetType(targetType))
                                .font(.caption)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(draft.targetType == targetType ? FinanceColors.planningPrimary : Color(UIColor.tertiarySystemBackground))
                                .foregroundColor(draft.targetType == targetType ? .white : .primary)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            if targetOptions.isEmpty {
                Text("Целей этого типа пока нет. Создайте категорию перед сохранением распределения.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                Text(draft.targetType == .expense_category ? "Категория расходов" : "Категория инвестиций")
                    .font(.caption)
                    .fontWeight(.semibold)

                ScrollView(.vertical, showsIndicators: false) {
                    LazyVStack(spacing: 6) {
                        ForEach(targetOptions) { option in
                            Button {
                                draft.targetId = option.id
                            } label: {
                                HStack {
                                    Text(option.title)
                                        .font(.subheadline)
                                        .lineLimit(1)
                                        .foregroundColor(draft.targetId == option.id ? .white : .primary)
                                    Spacer()
                                    if draft.targetId == option.id {
                                        Image(systemName: "checkmark")
                                            .font(.caption)
                                            .foregroundColor(.white)
                                    }
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(draft.targetId == option.id ? FinanceColors.planningPrimary : Color(UIColor.tertiarySystemBackground))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .frame(maxHeight: 144)
                }
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach([AllocationRecurrenceType.regular, .one_off], id: \.self) { recurrence in
                        Button {
                            draft.recurrenceType = recurrence
                        } label: {
                            Text(localizedRecurrenceType(recurrence))
                                .font(.caption)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(draft.recurrenceType == recurrence ? FinanceColors.planningPrimary : Color(UIColor.tertiarySystemBackground))
                                .foregroundColor(draft.recurrenceType == recurrence ? .white : .primary)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach([AllocationMode.amount, .percent], id: \.self) { mode in
                        Button {
                            draft.allocationMode = mode
                        } label: {
                            Text(localizedAllocationMode(mode))
                                .font(.caption)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(draft.allocationMode == mode ? FinanceColors.planningPrimary : Color(UIColor.tertiarySystemBackground))
                                .foregroundColor(draft.allocationMode == mode ? .white : .primary)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            TextField(draft.allocationMode == .percent ? "Процент" : "Сумма", text: $draft.allocationValue)
                .textFieldStyle(.roundedBorder)
                .keyboardType(.decimalPad)
                .onChange(of: draft.allocationValue) { _, new in draft.allocationValue = planningDecimalInput(new) }

            if draft.targetType == .investment_asset_category {
                Button {
                    let enabled = !draft.isSavingsGoal
                    draft.isSavingsGoal = enabled
                    if enabled {
                        if draft.goalTargetAmount.isEmpty { draft.goalTargetAmount = "" }
                        if draft.goalDueMonth.isEmpty { draft.goalDueMonth = nextPlanningMonth() }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: draft.isSavingsGoal ? "checkmark.circle.fill" : "circle")
                            .font(.system(size: 16))
                        Text("Цель накопления")
                            .font(.subheadline)
                    }
                    .foregroundColor(draft.isSavingsGoal ? FinanceColors.planningPrimary : .secondary)
                }
                .buttonStyle(.plain)
            } else {
                Text("Накопительная цель доступна только для инвестиционных категорий.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if draft.isSavingsGoal && draft.targetType == .investment_asset_category {
                TextField("Целевая сумма", text: $draft.goalTargetAmount)
                    .textFieldStyle(.roundedBorder)
                    .keyboardType(.decimalPad)
                    .onChange(of: draft.goalTargetAmount) { _, new in draft.goalTargetAmount = planningDecimalInput(new) }

                Text("Срок цели")
                    .font(.caption)
                    .fontWeight(.semibold)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(planningGoalMonthChoices()) { choice in
                            Button {
                                draft.goalDueMonth = choice.month
                            } label: {
                                Text(choice.title)
                                    .font(.caption)
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 6)
                                    .background(draft.goalDueMonth == choice.month ? FinanceColors.planningPrimary : Color(UIColor.tertiarySystemBackground))
                                    .foregroundColor(draft.goalDueMonth == choice.month ? .white : .primary)
                                    .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }

                if let monthly = estimatedMonthlyAmount() {
                    Text("Ориентир в месяц: \(MoneyHelpers.format(monthly, currency: currency))")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            TextField("Комментарий", text: $draft.comment)
                .textFieldStyle(.roundedBorder)
        }
    }

    private func estimatedMonthlyAmount() -> String? {
        guard let target = normalizePlanningAmount(draft.goalTargetAmount) else { return nil }
        let targetDec = Decimal(string: target) ?? .zero
        guard targetDec > .zero else { return nil }
        let cal = Calendar.current
        let now = Date()
        let currentYM = DateHelpers.currentYearMonth()
        let currentParts = currentYM.split(separator: "-").compactMap { Int($0) }
        guard currentParts.count == 2 else { return nil }
        let dueParts = draft.goalDueMonth.split(separator: "-").compactMap { Int($0) }
        guard dueParts.count == 2 else { return nil }
        let monthsDiff = (dueParts[0] - currentParts[0]) * 12 + (dueParts[1] - currentParts[1]) + 1
        let months = max(monthsDiff, 1)
        let monthly = targetDec / Decimal(months)
        return MoneyHelpers.decimalToString(monthly)
    }
}
