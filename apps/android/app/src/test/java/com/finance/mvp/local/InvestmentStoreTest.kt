package com.finance.mvp.local

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.finance.mvp.api.Brokerage
import com.finance.mvp.api.InvestmentInstrumentType
import com.finance.mvp.api.InvestmentRiskBucket
import com.finance.mvp.api.PortfolioPosition
import com.finance.mvp.api.PortfolioSnapshot
import com.finance.mvp.investments.PortfolioDraftState
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class InvestmentStoreTest {
    private lateinit var database: FinanceLocalDatabase

    @Before fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = Room.inMemoryDatabaseBuilder(context, FinanceLocalDatabase::class.java).allowMainThreadQueries().build()
    }

    @After fun tearDown() = database.close()

    @Test fun confirmedSnapshotIsReadableOfflineAndScopedToUser() = runTest {
        val store = InvestmentStore(database, nowEpochMillis = { 42L })
        val snapshot = PortfolioSnapshot(
            id = "snap-1", importId = "import-1", brokerage = Brokerage.Sinara,
            observedAt = "2026-09-20T10:00:00Z", currency = "RUB", freeCash = "100",
            monthlyContribution = "1000", totalValue = "5100",
            positions = listOf(
                PortfolioPosition(
                    instrumentName = "Сбербанк", ticker = "SBER",
                    instrumentType = InvestmentInstrumentType.Stock,
                    riskBucket = InvestmentRiskBucket.Aggressive,
                    quantity = "10", marketValue = "5000",
                ),
            ),
            createdAt = "2026-09-20T10:01:00Z",
        )
        store.cacheSnapshots("owner", listOf(snapshot))

        assertEquals("snap-1", store.snapshots("owner").single().id)
        assertEquals(emptyList<PortfolioSnapshot>(), store.snapshots("other"))
    }

    @Test fun structuredDraftSurvivesStoreRecreationWithoutScreenshotOrOcrPayload() = runTest {
        val draft = PortfolioDraftState(
            importId = "import-draft",
            brokerage = Brokerage.Finam,
            screenshotCount = 3,
            positions = listOf(
                PortfolioPosition(
                    instrumentName = "Лукойл", ticker = "LKOH",
                    instrumentType = InvestmentInstrumentType.Stock,
                    riskBucket = InvestmentRiskBucket.Aggressive,
                    quantity = "2", marketValue = "12000",
                ),
            ),
            freeCash = "3000",
            monthlyContribution = "50000",
            createdAtEpochMillis = 100L,
        )
        InvestmentStore(database, nowEpochMillis = { 101L }).cacheDraft("owner", draft)

        val entity = database.localInvestmentDao().latestDraft("owner")!!
        assertTrue(!entity.payloadJson.contains("content://"))
        assertTrue(!entity.payloadJson.contains("ocrText"))
        assertEquals(draft, InvestmentStore(database).draft("owner"))

        InvestmentStore(database).deleteDraft("owner", draft.importId)
        assertEquals(null, InvestmentStore(database).draft("owner"))
    }
}
