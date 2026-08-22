import Foundation
import XCTest
@testable import FinanceApp

final class PersonalSideloadHTTPTests: XCTestCase {
    override func tearDown() {
        PersonalHTTPURLProtocol.reset()
        super.tearDown()
    }

    func testPersonalPolicyAllowsOnlyProductionBaseAndChildren() throws {
        let policy = APITransportPolicy.personalSideloadHTTP

        try policy.validate(try XCTUnwrap(URL(string: "http://45.10.110.42/finance-api")))
        try policy.validate(try XCTUnwrap(URL(string: "http://45.10.110.42/finance-api/api/v1/accounts")))
        try policy.validate(try XCTUnwrap(URL(string: "http://45.10.110.42/finance-api/api/v1/accounts?q=test")))
    }

    func testPersonalPolicyRejectsEveryAuthorityViolation() throws {
        try assertDenied("https://45.10.110.42/finance-api")
        try assertDenied("http://45.10.110.43/finance-api")
        try assertDenied("http://example.com/finance-api")
        try assertDenied("http://45.10.110.42:80/finance-api")
        try assertDenied("http://user@45.10.110.42/finance-api")
        try assertDenied("http://user:password@45.10.110.42/finance-api")
        try assertDenied("http://45.10.110.42/finance-api#fragment")
    }

    func testPersonalPolicyRejectsPathEscapesAndEncodedTraversal() throws {
        try assertDenied("http://45.10.110.42/")
        try assertDenied("http://45.10.110.42/api/v1/accounts")
        try assertDenied("http://45.10.110.42/finance-api-evil")
        try assertDenied("http://45.10.110.42/finance-api/../admin")
        try assertDenied("http://45.10.110.42/finance-api/%2e%2e/admin")
        try assertDenied("http://45.10.110.42/finance-api/%252e%252e/admin")
        try assertDenied("http://45.10.110.42/finance-api/%2Fadmin")
        try assertDenied("http://45.10.110.42/finance-api/%5Cadmin")

        var components = URLComponents()
        components.scheme = "http"
        components.host = "45.10.110.42"
        components.path = "/finance-api\\admin"
        XCTAssertThrowsError(try APITransportPolicy.personalSideloadHTTP.validate(try XCTUnwrap(components.url)))
    }

    func testPersonalPolicyChecksResponseURL() throws {
        let allowedResponse = try XCTUnwrap(HTTPURLResponse(
            url: XCTUnwrap(URL(string: "http://45.10.110.42/finance-api/api/v1/accounts")),
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        ))
        try APITransportPolicy.personalSideloadHTTP.validateResponse(allowedResponse)

        let escapedResponse = try XCTUnwrap(HTTPURLResponse(
            url: XCTUnwrap(URL(string: "http://example.com/finance-api/api/v1/accounts")),
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        ))
        XCTAssertThrowsError(try APITransportPolicy.personalSideloadHTTP.validateResponse(escapedResponse))
    }

    func testPersonalPolicyBlocksRedirectsAndStandardPolicyKeepsDefaultBehavior() throws {
        XCTAssertNil(APITransportPolicy.standard.makeTaskDelegate())
        let blocker = try XCTUnwrap(
            APITransportPolicy.personalSideloadHTTP.makeTaskDelegate() as? PersonalHTTPRedirectBlocker
        )
        let session = URLSession(configuration: .ephemeral)
        let sourceURL = try XCTUnwrap(URL(string: "http://45.10.110.42/finance-api/api/v1/accounts"))
        let redirectURL = try XCTUnwrap(URL(string: "http://45.10.110.42/finance-api/api/v1/other"))
        let task = session.dataTask(with: sourceURL)
        let response = try XCTUnwrap(HTTPURLResponse(
            url: sourceURL,
            statusCode: 302,
            httpVersion: nil,
            headerFields: ["Location": redirectURL.absoluteString]
        ))
        var redirectedRequest: URLRequest?

        blocker.urlSession(
            session,
            task: task,
            willPerformHTTPRedirection: response,
            newRequest: URLRequest(url: redirectURL)
        ) { redirectedRequest = $0 }

        XCTAssertNil(redirectedRequest)
    }

    func testURLSessionIntegrationBlocks3xxRedirectBeforeDestinationRequest() async throws {
        let sourceURL = try XCTUnwrap(URL(string: "http://45.10.110.42/finance-api/api/v1/sessions"))
        let redirectURL = try XCTUnwrap(URL(string: "http://example.com/finance-api/api/v1/sessions"))
        PersonalHTTPURLProtocol.redirectURL = redirectURL

        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [PersonalHTTPURLProtocol.self]
        let session = URLSession(configuration: configuration)

        do {
            let (_, response) = try await session.data(
                for: URLRequest(url: sourceURL),
                delegate: try XCTUnwrap(APITransportPolicy.personalSideloadHTTP.makeTaskDelegate())
            )
            XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 302)
        } catch let error as URLError {
            XCTAssertEqual(error.code, .cancelled)
        }

        XCTAssertEqual(PersonalHTTPURLProtocol.requestURLs, [sourceURL.absoluteString])
    }

    func testReleaseRemainsHTTPSOnlyAndPersonalBuildRequiresExactURL() throws {
        let releaseHTTPS = AppEnvironment.validated(
            url: try XCTUnwrap(URL(string: "https://finance.example/finance-api")),
            networkMode: .release
        )
        XCTAssertTrue(releaseHTTPS.isValid)
        XCTAssertEqual(releaseHTTPS.transportPolicy, .standard)

        let releaseHTTP = AppEnvironment.validated(
            url: APITransportPolicy.personalSideloadBaseURL,
            networkMode: .release
        )
        XCTAssertFalse(releaseHTTP.isValid)

        let personal = AppEnvironment.validated(
            url: APITransportPolicy.personalSideloadBaseURL,
            networkMode: .personalSideloadHTTP
        )
        XCTAssertTrue(personal.isValid)
        XCTAssertEqual(personal.transportPolicy, .personalSideloadHTTP)

        let personalOverride = AppEnvironment.validated(
            url: try XCTUnwrap(URL(string: "http://45.10.110.43/finance-api")),
            networkMode: .personalSideloadHTTP
        )
        XCTAssertFalse(personalOverride.isValid)
    }

    func testTargetNetworkModeUsesPersonalCompileConfigurationWhenBuiltForSideload() {
        #if PERSONAL_SIDELOAD_HTTP
        guard case .personalSideloadHTTP = AppNetworkMode.current else {
            return XCTFail("Personal target must compile with PERSONAL_SIDELOAD_HTTP")
        }
        #else
        guard case .debug = AppNetworkMode.current else {
            return XCTFail("The standard Debug test target must not inherit the personal HTTP mode")
        }
        #endif
    }

    func testLiveClientRejectsDisallowedRequestBeforeTransport() async throws {
        let client = makeClient(baseURL: "http://example.com/finance-api")

        do {
            _ = try await client.login(email: "owner@example.test", password: "secret")
            XCTFail("Expected disallowed request to fail")
        } catch FinanceApiError.networkError(let error as URLError) {
            XCTAssertEqual(error.code, .unsupportedURL)
            XCTAssertEqual(PersonalHTTPURLProtocol.requestCount, 0)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testLiveClientRejectsUnexpectedFinalResponseURL() async throws {
        PersonalHTTPURLProtocol.responseURL = URL(string: "http://example.com/finance-api/api/v1/sessions")
        let client = makeClient(baseURL: APITransportPolicy.personalSideloadBaseURL.absoluteString)

        do {
            _ = try await client.login(email: "owner@example.test", password: "secret")
            XCTFail("Expected final response URL validation to fail")
        } catch FinanceApiError.networkError(let error as URLError) {
            XCTAssertEqual(error.code, .unsupportedURL)
            XCTAssertEqual(PersonalHTTPURLProtocol.requestCount, 1)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    private func assertDenied(
        _ rawURL: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) throws {
        let url = try XCTUnwrap(URL(string: rawURL), file: file, line: line)
        XCTAssertThrowsError(
            try APITransportPolicy.personalSideloadHTTP.validate(url),
            file: file,
            line: line
        )
    }

    private func makeClient(baseURL: String) -> LiveApiClient {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [PersonalHTTPURLProtocol.self]
        return LiveApiClient(
            baseURL: baseURL,
            session: URLSession(configuration: configuration),
            transportPolicy: .personalSideloadHTTP
        )
    }
}

private final class PersonalHTTPURLProtocol: URLProtocol {
    static var requestCount = 0
    static var responseURL: URL?
    static var redirectURL: URL?
    static var requestURLs: [String] = []

    static func reset() {
        requestCount = 0
        responseURL = nil
        redirectURL = nil
        requestURLs = []
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.requestCount += 1
        Self.requestURLs.append(request.url?.absoluteString ?? "")
        if let redirectURL = Self.redirectURL {
            let response = HTTPURLResponse(
                url: request.url!,
                statusCode: 302,
                httpVersion: nil,
                headerFields: ["Location": redirectURL.absoluteString]
            )!
            client?.urlProtocol(
                self,
                wasRedirectedTo: URLRequest(url: redirectURL),
                redirectResponse: response
            )
            return
        }
        let url = Self.responseURL ?? request.url!
        let response = HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data("{}".utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
