import Foundation

struct AppEnvironment: Sendable {
    static let apiBaseURLInfoKey = "FINANCE_API_BASE_URL"
    static let apiBaseURLEnvironmentKey = "FINANCE_API_BASE_URL"

    let apiBaseURL: URL
    let configurationError: String?

    var isValid: Bool { configurationError == nil }

    static var current: AppEnvironment {
        configured()
    }

    static func configured(
        bundle: Bundle = .main,
        processInfo: ProcessInfo = .processInfo
    ) -> AppEnvironment {
        if let envURL = normalizedURL(processInfo.environment[apiBaseURLEnvironmentKey]) {
            return validated(url: envURL)
        }

        if let bundleValue = bundle.object(forInfoDictionaryKey: apiBaseURLInfoKey) as? String,
           let bundleURL = normalizedURL(bundleValue) {
            return validated(url: bundleURL)
        }

        #if DEBUG
        return AppEnvironment(apiBaseURL: normalizedURL("http://127.0.0.1:8000/finance-api")!, configurationError: nil)
        #else
        return AppEnvironment(
            apiBaseURL: invalidFallbackURL,
            configurationError: "Не задан FINANCE_RELEASE_API_BASE_URL для Release-сборки. Укажите HTTPS API URL в конфигурации сборки."
        )
        #endif
    }

    static func configuredAPIBaseURL(
        bundle: Bundle = .main,
        processInfo: ProcessInfo = .processInfo
    ) -> URL {
        configured(bundle: bundle, processInfo: processInfo).apiBaseURL
    }

    private static func normalizedURL(_ rawValue: String?) -> URL? {
        guard let value = rawValue?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty,
              !value.contains("$("),
              !value.contains(")") else {
            return nil
        }
        return URL(string: value.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
    }

    private static func validated(url: URL) -> AppEnvironment {
        #if DEBUG
        return AppEnvironment(apiBaseURL: url, configurationError: nil)
        #else
        guard url.scheme == "https" else {
            return AppEnvironment(
                apiBaseURL: invalidFallbackURL,
                configurationError: "Release API URL должен использовать HTTPS. Проверьте FINANCE_RELEASE_API_BASE_URL."
            )
        }
        if let host = url.host?.lowercased(),
           host == "localhost" || host == "127.0.0.1" || host == "::1" {
            return AppEnvironment(
                apiBaseURL: invalidFallbackURL,
                configurationError: "Release API URL не должен указывать на локальный backend. Проверьте FINANCE_RELEASE_API_BASE_URL."
            )
        }
        return AppEnvironment(apiBaseURL: url, configurationError: nil)
        #endif
    }

    private static var invalidFallbackURL: URL {
        URL(string: "https://finance-api.invalid/finance-api")!
    }
}
