import SwiftUI

struct ModeChips: View {
    let selectedMode: FinanceMode
    let onModeSelected: (FinanceMode) -> Void

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(FinanceMode.allCases, id: \.self) { mode in
                    Button {
                        onModeSelected(mode)
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: mode.sfSymbol)
                                .font(.system(size: 12))
                            Text(mode.title)
                                .font(.subheadline)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(
                            selectedMode == mode
                                ? FinanceColors.primary
                                : FinanceColors.primaryContainer
                        )
                        .foregroundColor(
                            selectedMode == mode
                                ? FinanceColors.onPrimary
                                : FinanceColors.primary
                        )
                        .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

extension FinanceMode {
    var sfSymbol: String {
        switch self {
        case .personal: return "person"
        case .shared: return "person.2"
        case .overview: return "eye"
        }
    }
}
