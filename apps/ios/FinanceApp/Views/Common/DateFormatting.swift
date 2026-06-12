import SwiftUI

struct DateText: View {
    let dateString: String
    let font: Font

    init(dateString: String, font: Font = .caption) {
        self.dateString = dateString
        self.font = font
    }

    var body: some View {
        Text(DateHelpers.displayDate(dateString))
            .font(font)
            .foregroundColor(.secondary)
    }
}
