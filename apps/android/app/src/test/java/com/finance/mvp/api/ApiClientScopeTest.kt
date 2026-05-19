package com.finance.mvp.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ApiClientScopeTest {
    @Test
    fun sharedQuickAddAccountKeepsSharedOwnershipAndHousehold() {
        assertEquals("shared", normalizeAccountOwnershipType("shared"))
        assertEquals("household-1", accountHouseholdIdForOwnership("household-1", "shared"))
    }

    @Test
    fun personalQuickAddAccountStaysPrivateEvenWhenSessionHasHousehold() {
        assertEquals("personal", normalizeAccountOwnershipType("personal"))
        assertNull(accountHouseholdIdForOwnership("household-1", "personal"))
        assertNull(accountHouseholdIdForOwnership(null, "shared"))
    }

    @Test
    fun categoryScopeUsesHouseholdOnlyWhenRequested() {
        assertEquals("personal", categoryScopeForHousehold(null))
        assertEquals("personal", categoryScopeForHousehold(""))
        assertEquals("household", categoryScopeForHousehold("household-1"))
    }

    @Test
    fun transactionCategoryTypeIsLimitedToBackendSupportedValues() {
        assertEquals("income", normalizeTransactionCategoryType("income"))
        assertEquals("expense", normalizeTransactionCategoryType("expense"))
        assertEquals("expense", normalizeTransactionCategoryType("transfer"))
    }

    @Test
    fun devSeedDisplayTextIsUserFacingWithoutChangingIds() {
        assertEquals("Дом", userFacingSeedText("Dev Home"))
        assertEquals("Проценты по вкладу", userFacingSeedText("Dev deposit interest"))
        assertEquals("Custom label", userFacingSeedText("Dev Custom label"))
        assertEquals("Семейная карта", userFacingSeedText(" Dev Household Card "))
    }
}
