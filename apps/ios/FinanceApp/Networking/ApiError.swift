import Foundation

enum FinanceApiError: Error, LocalizedError, Sendable {
    case httpError(statusCode: Int, message: String)
    case networkError(Error)
    case decodingError(Error)
    case unauthorized
    case notFound
    case serverError(String)
    case unknown(Error)

    var errorDescription: String? {
        switch self {
        case .httpError(let code, let msg):
            if code == 401 {
                return "Сессия истекла. Войдите снова."
            }
            if code == 403 {
                return "Операция запрещена или CSRF-токен устарел. Локальные данные сохранены."
            }
            if msg.contains("ACCOUNT_CURRENCY_IMMUTABLE_AFTER_TRANSACTIONS") {
                return "Валюту счёта нельзя изменить после создания операций."
            }
            return msg
        case .networkError:
            return "Не удалось подключиться к серверу."
        case .decodingError:
            return "Ошибка обработки данных."
        case .unauthorized:
            return "Сессия истекла. Войдите снова."
        case .notFound:
            return "Данные не найдены."
        case .serverError(let msg):
            return msg
        case .unknown:
            return "Неизвестная ошибка."
        }
    }

    var isAuthError: Bool {
        if case .httpError(let code, _) = self { return code == 401 }
        if case .unauthorized = self { return true }
        return false
    }
}
