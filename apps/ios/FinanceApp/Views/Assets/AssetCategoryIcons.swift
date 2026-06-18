import SwiftUI

struct AssetCategoryIconOption: Identifiable, Hashable {
    let key: String
    let sfSymbol: String
    let title: String
    let tint: Color

    var id: String { key }
}

enum AssetCategoryIcons {
    static let options: [AssetCategoryIconOption] = [
        AssetCategoryIconOption(key: "wallet", sfSymbol: "wallet.pass", title: "Кошелёк", tint: FinanceColors.primary),
        AssetCategoryIconOption(key: "creditcard", sfSymbol: "creditcard", title: "Карта", tint: FinanceColors.planningPrimary),
        AssetCategoryIconOption(key: "centsign", sfSymbol: "centsign.circle", title: "Монеты", tint: FinanceColors.income),
        AssetCategoryIconOption(key: "shield", sfSymbol: "lock.shield", title: "Сейф", tint: FinanceColors.investment),
        AssetCategoryIconOption(key: "chart", sfSymbol: "chart.line.uptrend.xyaxis", title: "Инвестиции", tint: FinanceColors.investment),
        AssetCategoryIconOption(key: "house", sfSymbol: "house", title: "Недвижимость", tint: FinanceColors.primary),
        AssetCategoryIconOption(key: "iphone", sfSymbol: "iphone", title: "Техника", tint: .secondary),
        AssetCategoryIconOption(key: "book", sfSymbol: "book", title: "Книги", tint: .secondary),
    ]

    static func icon(for key: String?, assetType: AccountType) -> AssetCategoryIconOption {
        if let key, let found = options.first(where: { $0.key == key }) {
            return found
        }
        return AssetCategoryIconOption(
            key: assetType.rawValue,
            sfSymbol: assetType.sfSymbol,
            title: assetType.title,
            tint: assetType.color
        )
    }
}
