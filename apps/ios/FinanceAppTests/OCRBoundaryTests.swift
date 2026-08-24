import Foundation
import XCTest
@testable import FinanceApp

final class OCRBoundaryTests: XCTestCase {
    func testOCRCandidateCreatesReviewDraftWithoutImageOrRawOCRPayload() throws {
        let candidate = try JSONDecoder().decode(
            ScreenshotOcrCandidate.self,
            from: Data(
                """
                {
                  "candidateType": "categoryAggregate",
                  "categoryAggregate": { "externalLabel": "Супермаркеты" },
                  "amount": "123.45",
                  "currency": "RUB",
                  "operationCount": 1,
                  "description": "Покупка",
                  "confidence": "0.95",
                  "idempotencyKey": "candidate-1",
                  "evidenceHash": "sha256:abc",
                  "suggestedCategoryId": "food"
                }
                """.utf8
            )
        )

        let request = candidate.toCreateRequest(categoryId: "food")
        let json = try TestFixtures.jsonObject(request)
        let keys = Set(json.keys)

        XCTAssertEqual(json["captureSource"] as? String, "screenshot")
        XCTAssertEqual(json["categoryId"] as? String, "food")
        XCTAssertEqual(json["evidenceHash"] as? String, "sha256:abc")
        XCTAssertFalse(keys.contains("image"))
        XCTAssertFalse(keys.contains("imageData"))
        XCTAssertFalse(keys.contains("ocrText"))
        XCTAssertFalse(keys.contains("rawPayload"))
    }
}
