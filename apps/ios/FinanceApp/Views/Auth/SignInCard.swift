import SwiftUI

struct SignInCard: View {
    let isLoading: Bool
    let message: String
    let onLogin: (String, String) -> Void
    let onRegister: (String, String, String, String) -> Void

    @State private var authMode: AuthMode = .login
    @State private var email = ""
    @State private var password = ""
    @State private var confirmPassword = ""
    @State private var displayName = ""

    enum AuthMode {
        case login, register
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                IconBubble(systemName: "wallet.pass", color: FinanceColors.primary, size: 36)
                VStack(alignment: .leading, spacing: 2) {
                    Text(message)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    Text("Личный кабинет")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            HStack(spacing: 8) {
                authChip("Вход", isSelected: authMode == .login) {
                    authMode = .login
                }
                authChip("Регистрация", isSelected: authMode == .register) {
                    authMode = .register
                }
            }

            field("Электронная почта", text: $email, keyboardType: .emailAddress)
                .textInputAutocapitalization(.never)

            SecureField("Пароль", text: $password)
                .textFieldStyle(.roundedBorder)
                .font(.body)

            if authMode == .register {
                SecureField("Повторите пароль", text: $confirmPassword)
                    .textFieldStyle(.roundedBorder)
                    .font(.body)

                TextField("Имя (необязательно)", text: $displayName)
                    .textFieldStyle(.roundedBorder)
                    .font(.body)
            }

            HStack {
                Spacer()
                Button {
                    if authMode == .login {
                        onLogin(email.trimmingCharacters(in: .whitespacesAndNewlines), password)
                    } else {
                        onRegister(
                            email.trimmingCharacters(in: .whitespacesAndNewlines),
                            password,
                            confirmPassword,
                            displayName
                        )
                    }
                } label: {
                    Text(authMode == .login ? "Войти" : "Создать аккаунт")
                        .font(.body.bold())
                }
                .buttonStyle(.borderedProminent)
                .tint(FinanceColors.primary)
                .disabled(isLoading || !canSubmit)
            }
        }
        .padding(16)
        .background(FinanceColors.primaryContainer)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var canSubmit: Bool {
        let e = email.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !e.isEmpty, !password.isEmpty else { return false }
        if authMode == .register {
            guard password.count >= FinanceConstants.passwordMinLength,
                  password == confirmPassword,
                  !confirmPassword.isEmpty else { return false }
        }
        return true
    }

    private func authChip(_ title: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(isSelected ? FinanceColors.primary : Color.clear)
                .foregroundColor(isSelected ? .white : FinanceColors.primary)
                .clipShape(Capsule())
                .overlay(
                    Capsule()
                        .stroke(FinanceColors.primary, lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .disabled(isLoading)
    }

    private func field(_ label: String, text: Binding<String>, keyboardType: UIKeyboardType = .default) -> some View {
        TextField(label, text: text)
            .textFieldStyle(.roundedBorder)
            .font(.body)
            .keyboardType(keyboardType)
    }
}
