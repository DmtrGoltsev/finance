import Foundation

struct AppEnvironment: Sendable {
    static let apiBaseURLInfoKey = "FINANCE_API_BASE_URL"
    static let apiBaseURLEnvironmentKey = "FINANCE_API_BASE_URL"

    let apiBaseURL: URL
    let configurationError: String?
    let transportPolicy: APITransportPolicy

    var isValid: Bool { configurationError == nil }

    static var current: AppEnvironment {
        configured()
    }

    static func configured(
        bundle: Bundle = .main,
        processInfo: ProcessInfo = .processInfo,
        networkMode: AppNetworkMode = .current
    ) -> AppEnvironment {
        if let envURL = normalizedURL(processInfo.environment[apiBaseURLEnvironmentKey]) {
            return validated(url: envURL, networkMode: networkMode)
        }

        if let bundleValue = bundle.object(forInfoDictionaryKey: apiBaseURLInfoKey) as? String,
           let bundleURL = normalizedURL(bundleValue) {
            return validated(url: bundleURL, networkMode: networkMode)
        }

        switch networkMode {
        case .debug:
            return AppEnvironment(
                apiBaseURL: normalizedURL("http://127.0.0.1:8000/finance-api")!,
                configurationError: nil,
                transportPolicy: .standard
            )
        case .release:
            return invalidEnvironment(
                message: "Не задан FINANCE_RELEASE_API_BASE_URL для Release-сборки. Укажите HTTPS API URL в конфигурации сборки.",
                transportPolicy: .standard
            )
        case .personalSideloadHTTP:
            return invalidEnvironment(
                message: "PersonalSideloadHTTP требует точный production URL.",
                transportPolicy: .personalSideloadHTTP
            )
        }
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

    static func validated(url: URL, networkMode: AppNetworkMode) -> AppEnvironment {
        switch networkMode {
        case .debug:
            return AppEnvironment(apiBaseURL: url, configurationError: nil, transportPolicy: .standard)
        case .personalSideloadHTTP:
            guard url == APITransportPolicy.personalSideloadBaseURL else {
                return invalidEnvironment(
                    message: "PersonalSideloadHTTP разрешает только http://45.10.110.42/finance-api.",
                    transportPolicy: .personalSideloadHTTP
                )
            }
            return AppEnvironment(
                apiBaseURL: url,
                configurationError: nil,
                transportPolicy: .personalSideloadHTTP
            )
        case .release:
            guard url.scheme == "https" else {
                return invalidEnvironment(
                    message: "Release API URL должен использовать HTTPS. Проверьте FINANCE_RELEASE_API_BASE_URL.",
                    transportPolicy: .standard
                )
            }
            if let host = url.host?.lowercased(),
               host == "localhost" || host == "127.0.0.1" || host == "::1" {
                return invalidEnvironment(
                    message: "Release API URL не должен указывать на локальный backend. Проверьте FINANCE_RELEASE_API_BASE_URL.",
                    transportPolicy: .standard
                )
            }
            return AppEnvironment(apiBaseURL: url, configurationError: nil, transportPolicy: .standard)
        }
    }

    private static func invalidEnvironment(
        message: String,
        transportPolicy: APITransportPolicy
    ) -> AppEnvironment {
        AppEnvironment(
            apiBaseURL: invalidFallbackURL,
            configurationError: message,
            transportPolicy: transportPolicy
        )
    }

    private static var invalidFallbackURL: URL {
        URL(string: "https://finance-api.invalid/finance-api")!
    }
}

enum AppNetworkMode: Sendable {
    case debug
    case release
    case personalSideloadHTTP

    static var current: AppNetworkMode {
        #if PERSONAL_SIDELOAD_HTTP
        return .personalSideloadHTTP
        #elseif DEBUG
        return .debug
        #else
        return .release
        #endif
    }
}
