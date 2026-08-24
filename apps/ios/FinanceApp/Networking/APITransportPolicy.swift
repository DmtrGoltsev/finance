import Foundation

enum APITransportPolicyError: Error, Equatable {
    case missingURL
    case disallowedURL
}

enum APITransportPolicy: Sendable, Equatable {
    static let personalSideloadBaseURL = URL(string: "http://45.10.110.42/finance-api")!

    case standard
    case personalSideloadHTTP

    func validateRequest(_ request: URLRequest) throws {
        guard let url = request.url else {
            throw APITransportPolicyError.missingURL
        }
        try validate(url)
    }

    func validateResponse(_ response: URLResponse) throws {
        guard let url = response.url else {
            throw APITransportPolicyError.missingURL
        }
        try validate(url)
    }

    func validate(_ url: URL) throws {
        guard self == .personalSideloadHTTP else { return }

        guard url.scheme?.lowercased() == "http",
              url.host?.lowercased() == "45.10.110.42",
              url.port == nil,
              url.user == nil,
              url.password == nil,
              url.fragment == nil else {
            throw APITransportPolicyError.disallowedURL
        }

        let encodedPath = url.path(percentEncoded: true)
        let lowercasedPath = encodedPath.lowercased()
        let forbiddenEncodings = ["%2e", "%2f", "%5c", "%25"]
        guard !encodedPath.contains("\\"),
              !forbiddenEncodings.contains(where: { lowercasedPath.contains($0) }),
              let decodedPath = encodedPath.removingPercentEncoding,
              !decodedPath.contains("\\") else {
            throw APITransportPolicyError.disallowedURL
        }

        let pathSegments = decodedPath.split(separator: "/", omittingEmptySubsequences: false)
        guard !pathSegments.contains(where: { $0 == "." || $0 == ".." }),
              decodedPath == "/finance-api" || decodedPath.hasPrefix("/finance-api/") else {
            throw APITransportPolicyError.disallowedURL
        }
    }

    func makeTaskDelegate() -> (any URLSessionTaskDelegate)? {
        switch self {
        case .standard:
            return nil
        case .personalSideloadHTTP:
            return PersonalHTTPRedirectBlocker()
        }
    }
}

final class PersonalHTTPRedirectBlocker: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        completionHandler(nil)
    }
}
