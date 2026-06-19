import Foundation

enum OfflineMutationFallback {
    static func canQueue(after error: Error) -> Bool {
        if let apiError = error as? FinanceApiError {
            if case .networkError = apiError {
                return true
            }
            return false
        }
        if error is URLError {
            return true
        }
        return false
    }
}

enum LocalOptimisticError: Error, LocalizedError {
    case missingLocalScope
    case missingCurrentEntity

    var errorDescription: String? {
        switch self {
        case .missingLocalScope:
            return "Локальная область синхронизации недоступна."
        case .missingCurrentEntity:
            return "Текущая локальная запись недоступна для offline-изменения."
        }
    }
}
