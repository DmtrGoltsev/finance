import SwiftUI

struct IconBubble: View {
    let systemName: String
    let color: Color
    let size: CGFloat

    init(systemName: String, color: Color, size: CGFloat = 40) {
        self.systemName = systemName
        self.color = color
        self.size = size
    }

    var body: some View {
        Circle()
            .fill(color.opacity(0.14))
            .frame(width: size, height: size)
            .overlay(
                Image(systemName: systemName)
                    .font(.system(size: size * 0.45))
                    .foregroundColor(color)
            )
    }
}
