import SwiftUI

struct ReportMonthSwitcher: View {
    @Binding var yearMonth: String

    var body: some View {
        HStack(spacing: 12) {
            Button {
                yearMonth = shiftMonth(yearMonth, by: -1)
            } label: {
                Image(systemName: "chevron.left")
                    .font(.body)
                    .foregroundColor(FinanceColors.primary)
            }

            Text(DateHelpers.displayMonth(yearMonth))
                .font(.headline)
                .foregroundColor(.primary)
                .frame(minWidth: 132)

            Button {
                yearMonth = shiftMonth(yearMonth, by: 1)
            } label: {
                Image(systemName: "chevron.right")
                    .font(.body)
                    .foregroundColor(FinanceColors.primary)
            }
            .disabled(yearMonth >= DateHelpers.currentYearMonth())

            if Self.showsCurrentMonthButton(yearMonth) {
                Button {
                    yearMonth = DateHelpers.currentYearMonth()
                } label: {
                    Image(systemName: "calendar.badge.clock")
                        .font(.body)
                        .foregroundColor(FinanceColors.primary)
                }
                .accessibilityLabel("Текущий месяц")
                .accessibilityIdentifier("analytics.currentMonth")
            }
        }
    }

    static func showsCurrentMonthButton(_ yearMonth: String) -> Bool {
        yearMonth != DateHelpers.currentYearMonth()
    }

    func shiftMonth(_ ym: String, by delta: Int) -> String {
        let parts = ym.split(separator: "-")
        guard parts.count == 2,
              let year = Int(parts[0]),
              let month = Int(parts[1]) else { return ym }
        let total = (year * 12 + month - 1) + delta
        let newYear = total / 12
        let newMonth = total % 12 + 1
        return String(format: "%04d-%02d", newYear, newMonth)
    }
}
