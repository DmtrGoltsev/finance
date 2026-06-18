import SwiftUI

struct MonthExpenseCard: View {
    let view: FinanceDashboard.DashboardViewData

    var body: some View {
        HStack(spacing: 12) {
            IconBubble(systemName: "receipt", color: FinanceColors.expense)
            VStack(alignment: .leading, spacing: 2) {
                Text("Расходы месяца \u{2022} \(view.scopeTitle)")
                    .font(.caption)
                Text(MoneyHelpers.format(view.monthExpenses, currency: view.primaryCurrency))
                    .font(.title2)
                    .fontWeight(.semibold)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("Доходы")
                    .font(.caption2)
                Text(MoneyHelpers.format(view.monthIncome, currency: view.primaryCurrency))
                    .font(.body)
                    .fontWeight(.medium)
            }
        }
        .padding(16)
        .background(FinanceColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.04), radius: 4, y: 2)
    }
}
