import SwiftUI

struct LoadingOverlay: View {
    let message: String?

    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
                .scaleEffect(1.2)
            if let msg = message {
                Text(msg)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(32)
    }
}
