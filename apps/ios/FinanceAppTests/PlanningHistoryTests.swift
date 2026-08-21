import XCTest
@testable import FinanceApp

final class PlanningHistoryTests: XCTestCase {
    func testSummaryDTODecodesAndMapsPlanningHistoryContract() throws {
        let data = Data(#"""
        {
          "items": [{
            "id": "11111111-1111-1111-1111-111111111111",
            "scope": "personal",
            "ownerUserId": "user-a",
            "householdId": null,
            "month": "2026-07",
            "currency": "RUB",
            "summary": {
              "totalPlannedIncome": "100000.0000",
              "totalConfirmedIncome": "90000.0000",
              "totalAllocatedAmount": "75000.0000",
              "unallocatedAmount": "25000.0000",
              "previousMonthSurplus": "5000.0000",
              "underallocated": true,
              "overallocated": false
            },
            "createdAt": "2026-07-01T00:00:00.000Z",
            "updatedAt": "2026-07-20T00:00:00.000Z",
            "version": 4
          }]
        }
        """#.utf8)

        let dto = try XCTUnwrap(ResponseParser.unwrapItemsOnly(PlanningPlanSummaryDTO.self, from: data).first)
        let item = dto.historyItem

        XCTAssertEqual(item.id, "11111111-1111-1111-1111-111111111111")
        XCTAssertEqual(item.month, "2026-07")
        XCTAssertEqual(item.summary.totalPlannedIncome, "100000.0000")
        XCTAssertEqual(item.summary.unallocatedAmount, "25000.0000")
        XCTAssertTrue(item.summary.underallocated)
        XCTAssertNil(item.detail)
    }

    func testHistoryCopyFetchesSummaryDetailOnlyWhenNeeded() async throws {
        let data = Data(#"""
        {
          "id": "11111111-1111-1111-1111-111111111111",
          "scope": "personal",
          "ownerUserId": "user-a",
          "householdId": null,
          "month": "2026-07",
          "currency": "RUB",
          "summary": {
            "totalPlannedIncome": "100.0000",
            "totalConfirmedIncome": "100.0000",
            "totalAllocatedAmount": "80.0000",
            "unallocatedAmount": "20.0000",
            "previousMonthSurplus": "0.0000",
            "underallocated": true,
            "overallocated": false
          },
          "createdAt": "2026-07-01T00:00:00.000Z",
          "updatedAt": "2026-07-20T00:00:00.000Z",
          "version": 4
        }
        """#.utf8)
        let summaryItem = try ResponseParser.decode(PlanningPlanSummaryDTO.self, from: data).historyItem
        let detail = planningPlan(id: summaryItem.id)
        var fetchedId: String?

        let fetched = try await summaryItem.resolvedDetail { id in
            fetchedId = id
            return detail
        }
        XCTAssertEqual(fetchedId, summaryItem.id)
        XCTAssertEqual(fetched.id, detail.id)

        fetchedId = nil
        let localItem = PlanningPlanHistoryItem(plan: detail)
        let embedded = try await localItem.resolvedDetail { id in
            fetchedId = id
            return detail
        }
        XCTAssertNil(fetchedId)
        XCTAssertEqual(embedded.id, detail.id)
    }

    private func planningPlan(id: String) -> PlanningPlan {
        PlanningPlan(
            id: id,
            scope: .personal,
            ownerUserId: "user-a",
            month: "2026-07",
            currency: .RUB,
            householdId: nil,
            summary: PlanningSummary(
                totalPlannedIncome: "100.0000",
                totalConfirmedIncome: "100.0000",
                totalAllocatedAmount: "80.0000",
                unallocatedAmount: "20.0000",
                previousMonthSurplus: "0.0000",
                underallocated: true,
                overallocated: false
            ),
            incomeSources: [],
            allocations: [],
            version: 4
        )
    }
}
