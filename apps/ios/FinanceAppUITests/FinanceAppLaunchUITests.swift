import XCTest

final class FinanceAppLaunchUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testLaunchShowsPersonalAuthenticationWithoutSharedMode() {
        let app = XCUIApplication()
        app.launchArguments += ["-AppleLanguages", "(ru)", "-AppleLocale", "ru_RU"]
        app.launch()

        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10))
        XCTAssertTrue(app.buttons["Вход"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["Регистрация"].exists)
        XCTAssertFalse(app.staticTexts["Общее"].exists)
        XCTAssertFalse(app.staticTexts["Мой обзор"].exists)
    }
}
