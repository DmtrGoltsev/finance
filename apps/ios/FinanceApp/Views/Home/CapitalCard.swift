import SwiftUI

struct CapitalCard: View {
    let view: FinanceDashboard.DashboardViewData

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Капитал")
                .font(.caption)
                .foregroundColor(.white.opacity(0.78))

            Text(MoneyHelpers.format(view.capital, currency: view.primaryCurrency))
                .font(.title)
                .fontWeight(.bold)
                .foregroundColor(.white)

            Text("\(view.accountCount) активов \u{2022} \(view.operationCount) операций")
                .font(.caption)
                .foregroundColor(.white.opacity(0.78))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(FinanceColors.primary)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
