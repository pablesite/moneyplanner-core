<script setup lang="ts">
import { computed, watch } from 'vue';
import {
  BudgetAnnualSection,
  BudgetHeroSection,
  BudgetMonthlyCloseExpenseSection,
  BudgetMonthlyCloseIncomeSection,
  BudgetMonthlyCloseLiquiditySection,
  BudgetMonthlyCloseResultSection,
} from '@/domains/budget';
import { useDataInputPage } from './data-input/useDataInputPage';

import '@/domains/budget/styles/dashboard.css';
import { type BudgetDashboardMode, useBudgetDashboardPage } from './budget/useBudgetDashboardPage';

const props = withDefaults(defineProps<{ mode?: BudgetDashboardMode }>(), {
  mode: 'budget',
});

const {
  fiscalYear,
  ownershipFilter,
  incomeViewMode,
  expenseViewMode,
  monthLabels,
  selectedExecutionMonth,
  expenseMonthlySummary,
  expenseExecutionLoading,
  expenseExecutionBusyEntryId,
  expenseExecutionError,
  expenseAdjustAmounts,
  incomeExecutionLoading,
  incomeExecutionBusyEntryId,
  incomeExecutionError,
  incomeAdjustAmounts,
  budgetSuggestionsLoading,
  budgetSuggestionsError,
  budgetSuggestions,
  liquidityMonthlySummary,
  liquidityExecutionLoading,
  liquidityExecutionBusyAssetId,
  liquidityExecutionError,
  liquidityAdjustAmounts,
  activeMonthlyCloseStep,
  monthlyCloseError,
  monthlyCloseActionBusy,
  isMonthlyCloseView,
  monthlyCloseFlowSteps,
  previousMonthlyCloseStep,
  fiscalYearOptions,
  selectedOwnershipFilterLabel,
  selectedFiscalYearLabel,
  isLoading,
  firstError,
  ownershipOptions,
  setActiveMonthlyCloseStep,
  goToPreviousMonthlyCloseStep,
  goToNextMonthlyCloseStep,
  selectOwnershipFilterOption,
  selectFiscalYearOption,
  updateSelectedExecutionMonth,
  setIncomeAdjustAmount,
  setExpenseAdjustAmount,
  setLiquidityAdjustAmount,
  updateIncomeViewMode,
  updateExpenseViewMode,
  plannedIncomeTotal,
  plannedExpenseTotal,
  plannedBalanceTotal,
  selectedExpenseMonthPlanned,
  selectedExpenseMonthDeviation,
  monthlyIncomeExecutionEntries,
  selectedIncomeMonthPlanned,
  selectedIncomeMonthExecuted,
  selectedIncomeMonthDeviation,
  selectedIncomeMonthCompletionRatio,
  groupedMonthlyIncomeExecutionEntries,
  incomeEvolutionMonths,
  incomeEvolutionBaseMonthly,
  expenseEvolutionMonths,
  expenseEvolutionBaseMonthly,
  selectedLiquidityMonthPlanned,
  selectedLiquidityMonthExecuted,
  selectedLiquidityMonthDeviation,
  selectedLiquidityStartBase,
  selectedMonthlyCloseExpected,
  selectedMonthlyCloseResidual,
  selectedMonthlyCloseCompletionRatio,
  monthlyLiquidityExecutionRows,
  monthlyExpenseExecutionEntries,
  selectedExpenseMonthExecuted,
  groupedMonthlyExpenseExecutionEntries,
  monthlyIncomeResultBreakdown,
  monthlyExpenseResultBreakdown,
  selectedExecutionMonthLabel,
  budgetDetailMonth,
  budgetDetailMonthLabel,
  updateBudgetDetailMonth,
  budgetSectionActualExecution,
  budgetCategoryActualExecution,
  budgetSubcategoryActualExecution,
  incomeInvestmentRotationCategoryAdjustment,
  incomeInvestmentRotationSubcategoryAdjustment,
  selectedMonthlyExecutedVolume,
  selectedMonthlyResidualVolumeRatio,
  selectedMonthlyResidualIncomeRatio,
  selectedMonthlyResidualExpenseRatio,
  selectedMonthlyResidualExpectedCloseRatio,
  selectedMonthlyResidualSeverity,
  selectedMonthlyResidualSeverityLabel,
  resultReconciliationFlowRows,
  resultReconciliationCompositionRows,
  executionStatusLabel,
  executionStatusDetail,
  monthlyIncomeCoverageSummary,
  monthlyExpenseCoverageSummary,
  monthlyIncomePendingClassification,
  monthlyExpensePendingClassification,
  isLockedExecutionRow,
  executionSourceLabel,
  monthlyExpenseCoverageLabel,
  monthlyExpenseCoverageDetail,
  monthlyIncomeCoverageLabel,
  monthlyIncomeCoverageDetail,
  refreshAccountingExecutionData,
  refreshBudgetData,
  refreshBudgetSuggestionData,
  refreshExpenseExecutionData,
  refreshIncomeExecutionData,
  formatMoney,
  formatSignedMoney,
  formatPercent,
  formatCompactMoney,
  executionPreview,
  viewModeLabel,
  isSectionExpanded,
  toggleSectionExpanded,
  sections,
  filteredIncomeEntries,
  filteredExpenseEntries,
  incomeBudgetSuggestions,
  expenseBudgetSuggestions,
  incomeExecutionYtdTotals,
  expenseExecutionYtdTotals,
  hasAnyPlannedData,
  closeStatus,
  isCloseLocked,
  hasDistributionSuggestion,
  activeViewSummary,
  ensureExpenseAdjustAmountPrefilled,
  ensureExpenseGroupAdjustAmountPrefilled,
  checkinStatusLabel,
  isExpenseGroupUnlocked,
  isIncomeGroupUnlocked,
  ensureIncomeGroupAdjustAmountPrefilled,
  saveIncomeGroupCheckinFromInput,
  onIncomeGroupReviewedToggle,
  resetIncomeGroupCheckinDraftValue,
  unlockIncomeGroupManualAdjustment,
  relockIncomeGroupManualAdjustment,
  expenseCheckinRowSummary,
  resetExpenseCheckinDraftValue,
  resetExpenseGroupCheckinDraftValue,
  saveExpenseCheckinFromInput,
  saveExpenseGroupCheckinFromInput,
  onExpenseGroupReviewedToggle,
  unlockExpenseGroupManualAdjustment,
  relockExpenseGroupManualAdjustment,
  onExpenseCheckinCheckboxToggle,
  onExpenseAdjustAmountBlur,
  liquidityCheckinRowSummary,
  ensureLiquidityAdjustAmountPrefilled,
  isLiquidityLedgerRowUnlocked,
  handleFinalizeClose,
  handleReopenClose,
  handleLockClose,
  handleApplyDistribution,
  resetLiquidityCheckinDraftValue,
  saveLiquidityCheckinFromInput,
  unlockLiquidityLedgerRow,
  relockLiquidityLedgerRow,
  onLiquidityCheckinCheckboxToggle,
  onLiquidityAdjustAmountBlur,
} = useBudgetDashboardPage(computed(() => props.mode));

const annualEntriesPage = props.mode === 'budget' ? useDataInputPage() : null;

if (annualEntriesPage) {
  watch(
    fiscalYear,
    (year) => {
      annualEntriesPage.fiscalYear.value = year;
    },
    { immediate: true },
  );
}

async function submitAnnualIncomeAndRefresh(): Promise<void> {
  if (!annualEntriesPage) return;
  await annualEntriesPage.submitAnnualIncome();
  await Promise.all([
    refreshBudgetData(fiscalYear.value),
    refreshBudgetSuggestionData(),
    refreshAccountingExecutionData(),
    refreshIncomeExecutionData(),
    refreshExpenseExecutionData(),
  ]);
}

async function submitAnnualExpenseAndRefresh(): Promise<void> {
  if (!annualEntriesPage) return;
  await annualEntriesPage.submitAnnualExpense();
  await Promise.all([
    refreshBudgetData(fiscalYear.value),
    refreshBudgetSuggestionData(),
    refreshAccountingExecutionData(),
    refreshIncomeExecutionData(),
    refreshExpenseExecutionData(),
  ]);
}

async function removeAnnualIncomeAndRefresh(entryId: number): Promise<void> {
  if (!annualEntriesPage) return;
  await annualEntriesPage.removeAnnualIncome(entryId);
  await Promise.all([
    refreshBudgetData(fiscalYear.value),
    refreshBudgetSuggestionData(),
    refreshAccountingExecutionData(),
    refreshIncomeExecutionData(),
    refreshExpenseExecutionData(),
  ]);
}

async function removeAnnualExpenseAndRefresh(entryId: number): Promise<void> {
  if (!annualEntriesPage) return;
  await annualEntriesPage.removeAnnualExpense(entryId);
  await Promise.all([
    refreshBudgetData(fiscalYear.value),
    refreshBudgetSuggestionData(),
    refreshAccountingExecutionData(),
    refreshIncomeExecutionData(),
    refreshExpenseExecutionData(),
  ]);
}
</script>

<template>
  <div class="container ui-pro-page relative">
    <BudgetHeroSection
      :is-monthly-close-view="isMonthlyCloseView"
      :month-labels="monthLabels"
      :selected-execution-month="selectedExecutionMonth"
      :selected-ownership-filter-label="selectedOwnershipFilterLabel"
      :ownership-filter="ownershipFilter"
      :ownership-options="ownershipOptions"
      :selected-fiscal-year-label="selectedFiscalYearLabel"
      :fiscal-year="fiscalYear"
      :fiscal-year-options="fiscalYearOptions"
      :is-loading="isLoading"
      :monthly-close-flow-steps="monthlyCloseFlowSteps"
      :active-monthly-close-step="activeMonthlyCloseStep"
      :budget-suggestions-loading="budgetSuggestionsLoading"
      :budget-suggestions-error="budgetSuggestionsError"
      :budget-suggestions="budgetSuggestions"
      :income-budget-suggestions="incomeBudgetSuggestions"
      :expense-budget-suggestions="expenseBudgetSuggestions"
      :planned-income-total="plannedIncomeTotal"
      :planned-expense-total="plannedExpenseTotal"
      :planned-balance-total="plannedBalanceTotal"
      :execution-status-label="executionStatusLabel"
      :execution-status-detail="executionStatusDetail"
      :active-view-summary="activeViewSummary"
      :income-view-mode="incomeViewMode"
      :expense-view-mode="expenseViewMode"
      :format-money="formatMoney"
      :format-percent="formatPercent"
      :view-mode-label="viewModeLabel"
      :update-income-view-mode="updateIncomeViewMode"
      :update-expense-view-mode="updateExpenseViewMode"
      :close-status="closeStatus ?? undefined"
      :set-active-monthly-close-step="setActiveMonthlyCloseStep"
      :update-selected-execution-month="updateSelectedExecutionMonth"
      :select-ownership-filter-option="selectOwnershipFilterOption"
      :select-fiscal-year-option="selectFiscalYearOption"
    />
    <div v-if="!isMonthlyCloseView && firstError" class="alert mt-3">
      {{ firstError }}
    </div>
    <div v-if="!isMonthlyCloseView && expenseExecutionError" class="alert mt-3">
      {{ expenseExecutionError }}
    </div>
    <div v-if="liquidityExecutionError" class="alert mt-3">
      {{ liquidityExecutionError }}
    </div>
    <div v-if="isMonthlyCloseView && monthlyCloseError" class="alert mt-3">
      {{ monthlyCloseError }}
    </div>
    <BudgetMonthlyCloseExpenseSection
      :is-monthly-close-view="isMonthlyCloseView"
      :active-monthly-close-step="activeMonthlyCloseStep"
      :is-close-locked="isCloseLocked"
      :expense-monthly-summary="expenseMonthlySummary"
      :expense-execution-loading="expenseExecutionLoading"
      :expense-execution-busy-entry-id="expenseExecutionBusyEntryId"
      :grouped-monthly-expense-execution-entries="groupedMonthlyExpenseExecutionEntries"
      :monthly-expense-coverage-summary="monthlyExpenseCoverageSummary"
      :monthly-expense-coverage-detail="monthlyExpenseCoverageDetail"
      :monthly-expense-coverage-label="monthlyExpenseCoverageLabel"
      :monthly-expense-pending-classification="monthlyExpensePendingClassification"
      :expense-adjust-amounts="expenseAdjustAmounts"
      :set-expense-adjust-amount="setExpenseAdjustAmount"
      :selected-expense-month-planned="selectedExpenseMonthPlanned"
      :selected-expense-month-executed="selectedExpenseMonthExecuted"
      :selected-expense-month-deviation="selectedExpenseMonthDeviation"
      :format-money="formatMoney"
      :format-percent="formatPercent"
      :execution-source-label="executionSourceLabel"
      :expense-checkin-row-summary="expenseCheckinRowSummary"
      :checkin-status-label="checkinStatusLabel"
      :is-locked-execution-row="isLockedExecutionRow"
      :is-expense-group-unlocked="isExpenseGroupUnlocked"
      :go-to-previous-monthly-close-step="goToPreviousMonthlyCloseStep"
      :go-to-next-monthly-close-step="goToNextMonthlyCloseStep"
      :reset-expense-checkin-draft-value="resetExpenseCheckinDraftValue"
      :reset-expense-group-checkin-draft-value="resetExpenseGroupCheckinDraftValue"
      :ensure-expense-adjust-amount-prefilled="ensureExpenseAdjustAmountPrefilled"
      :ensure-expense-group-adjust-amount-prefilled="ensureExpenseGroupAdjustAmountPrefilled"
      :on-expense-adjust-amount-blur="onExpenseAdjustAmountBlur"
      :save-expense-checkin-from-input="saveExpenseCheckinFromInput"
      :save-expense-group-checkin-from-input="saveExpenseGroupCheckinFromInput"
      :on-expense-checkin-checkbox-toggle="onExpenseCheckinCheckboxToggle"
      :on-expense-group-reviewed-toggle="onExpenseGroupReviewedToggle"
      :unlock-expense-group-manual-adjustment="unlockExpenseGroupManualAdjustment"
      :relock-expense-group-manual-adjustment="relockExpenseGroupManualAdjustment"
    />

    <BudgetMonthlyCloseLiquiditySection
      :is-monthly-close-view="isMonthlyCloseView"
      :active-monthly-close-step="activeMonthlyCloseStep"
      :is-close-locked="isCloseLocked"
      :previous-monthly-close-step="previousMonthlyCloseStep"
      :month-labels="monthLabels"
      :selected-execution-month="selectedExecutionMonth"
      :liquidity-monthly-summary="liquidityMonthlySummary"
      :liquidity-execution-loading="liquidityExecutionLoading"
      :liquidity-execution-busy-asset-id="liquidityExecutionBusyAssetId"
      :monthly-liquidity-execution-rows="monthlyLiquidityExecutionRows"
      :selected-liquidity-month-planned="selectedLiquidityMonthPlanned"
      :selected-liquidity-month-executed="selectedLiquidityMonthExecuted"
      :selected-liquidity-month-deviation="selectedLiquidityMonthDeviation"
      :liquidity-adjust-amounts="liquidityAdjustAmounts"
      :set-liquidity-adjust-amount="setLiquidityAdjustAmount"
      :is-liquidity-ledger-row-unlocked="isLiquidityLedgerRowUnlocked"
      :format-money="formatMoney"
      :format-percent="formatPercent"
      :checkin-status-label="checkinStatusLabel"
      :liquidity-checkin-row-summary="liquidityCheckinRowSummary"
      :go-to-previous-monthly-close-step="goToPreviousMonthlyCloseStep"
      :go-to-next-monthly-close-step="goToNextMonthlyCloseStep"
      :update-selected-execution-month="updateSelectedExecutionMonth"
      :reset-liquidity-checkin-draft-value="resetLiquidityCheckinDraftValue"
      :ensure-liquidity-adjust-amount-prefilled="ensureLiquidityAdjustAmountPrefilled"
      :on-liquidity-adjust-amount-blur="onLiquidityAdjustAmountBlur"
      :save-liquidity-checkin-from-input="saveLiquidityCheckinFromInput"
      :unlock-liquidity-ledger-row="unlockLiquidityLedgerRow"
      :relock-liquidity-ledger-row="relockLiquidityLedgerRow"
      :on-liquidity-checkin-checkbox-toggle="onLiquidityCheckinCheckboxToggle"
    />
    <BudgetMonthlyCloseIncomeSection
      :is-monthly-close-view="isMonthlyCloseView"
      :active-monthly-close-step="activeMonthlyCloseStep"
      :is-close-locked="isCloseLocked"
      :grouped-monthly-income-execution-entries="groupedMonthlyIncomeExecutionEntries"
      :income-execution-loading="incomeExecutionLoading"
      :income-execution-error="incomeExecutionError"
      :income-execution-busy-entry-id="incomeExecutionBusyEntryId"
      :income-adjust-amounts="incomeAdjustAmounts"
      :set-income-adjust-amount="setIncomeAdjustAmount"
      :selected-income-month-planned="selectedIncomeMonthPlanned"
      :selected-income-month-executed="selectedIncomeMonthExecuted"
      :selected-income-month-deviation="selectedIncomeMonthDeviation"
      :selected-income-month-completion-ratio="selectedIncomeMonthCompletionRatio"
      :monthly-income-coverage-summary="monthlyIncomeCoverageSummary"
      :monthly-income-coverage-detail="monthlyIncomeCoverageDetail"
      :monthly-income-coverage-label="monthlyIncomeCoverageLabel"
      :monthly-income-pending-classification="monthlyIncomePendingClassification"
      :format-money="formatMoney"
      :format-percent="formatPercent"
      :checkin-status-label="checkinStatusLabel"
      :is-income-group-unlocked="isIncomeGroupUnlocked"
      :go-to-previous-monthly-close-step="goToPreviousMonthlyCloseStep"
      :go-to-next-monthly-close-step="goToNextMonthlyCloseStep"
      :reset-income-group-checkin-draft-value="resetIncomeGroupCheckinDraftValue"
      :ensure-income-group-adjust-amount-prefilled="ensureIncomeGroupAdjustAmountPrefilled"
      :save-income-group-checkin-from-input="saveIncomeGroupCheckinFromInput"
      :on-income-group-reviewed-toggle="onIncomeGroupReviewedToggle"
      :unlock-income-group-manual-adjustment="unlockIncomeGroupManualAdjustment"
      :relock-income-group-manual-adjustment="relockIncomeGroupManualAdjustment"
    />
    <BudgetMonthlyCloseResultSection
      :is-monthly-close-view="isMonthlyCloseView"
      :active-monthly-close-step="activeMonthlyCloseStep"
      :selected-liquidity-start-base="selectedLiquidityStartBase"
      :selected-monthly-close-expected="selectedMonthlyCloseExpected"
      :selected-liquidity-month-executed="selectedLiquidityMonthExecuted"
      :selected-monthly-close-residual="selectedMonthlyCloseResidual"
      :selected-income-month-executed="selectedIncomeMonthExecuted"
      :selected-expense-month-executed="selectedExpenseMonthExecuted"
      :selected-monthly-close-completion-ratio="selectedMonthlyCloseCompletionRatio"
      :selected-liquidity-month-deviation="selectedLiquidityMonthDeviation"
      :selected-monthly-executed-volume="selectedMonthlyExecutedVolume"
      :selected-monthly-residual-severity="selectedMonthlyResidualSeverity"
      :selected-monthly-residual-severity-label="selectedMonthlyResidualSeverityLabel"
      :selected-monthly-residual-volume-ratio="selectedMonthlyResidualVolumeRatio"
      :selected-monthly-residual-income-ratio="selectedMonthlyResidualIncomeRatio"
      :selected-monthly-residual-expense-ratio="selectedMonthlyResidualExpenseRatio"
      :selected-monthly-residual-expected-close-ratio="selectedMonthlyResidualExpectedCloseRatio"
      :result-reconciliation-flow-rows="resultReconciliationFlowRows"
      :result-reconciliation-composition-rows="resultReconciliationCompositionRows"
      :monthly-income-execution-entries="monthlyIncomeExecutionEntries"
      :monthly-expense-execution-entries="monthlyExpenseExecutionEntries"
      :monthly-income-result-breakdown="monthlyIncomeResultBreakdown"
      :monthly-expense-result-breakdown="monthlyExpenseResultBreakdown"
      :format-money="formatMoney"
      :format-percent="formatPercent"
      :format-signed-money="formatSignedMoney"
      :go-to-previous-monthly-close-step="goToPreviousMonthlyCloseStep"
      :close-status="closeStatus ?? undefined"
      :is-close-locked="isCloseLocked"
      :monthly-close-action-busy="monthlyCloseActionBusy"
      :has-distribution-suggestion="hasDistributionSuggestion"
      :on-finalize-close="handleFinalizeClose"
      :on-reopen-close="handleReopenClose"
      :on-lock-close="handleLockClose"
      :on-apply-distribution="handleApplyDistribution"
    />
    <BudgetAnnualSection
      :is-monthly-close-view="isMonthlyCloseView"
      :has-any-planned-data="hasAnyPlannedData"
      :is-loading="isLoading"
      :fiscal-year="fiscalYear"
      :sections="sections"
      :month-labels="monthLabels"
      :income-evolution-months="incomeEvolutionMonths"
      :income-evolution-base-monthly="incomeEvolutionBaseMonthly"
      :expense-evolution-months="expenseEvolutionMonths"
      :expense-evolution-base-monthly="expenseEvolutionBaseMonthly"
      :selected-execution-month-label="selectedExecutionMonthLabel"
      :budget-detail-month="budgetDetailMonth"
      :budget-detail-month-label="budgetDetailMonthLabel"
      :update-budget-detail-month="updateBudgetDetailMonth"
      :budget-section-actual-execution="budgetSectionActualExecution"
      :format-money="formatMoney"
      :format-compact-money="formatCompactMoney"
      :format-percent="formatPercent"
      :format-signed-money="formatSignedMoney"
      :is-section-expanded="isSectionExpanded"
      :toggle-section-expanded="toggleSectionExpanded"
      :budget-category-actual-execution="budgetCategoryActualExecution"
      :budget-subcategory-actual-execution="budgetSubcategoryActualExecution"
      :income-investment-rotation-category-adjustment="incomeInvestmentRotationCategoryAdjustment"
      :income-investment-rotation-subcategory-adjustment="
        incomeInvestmentRotationSubcategoryAdjustment
      "
      :income-execution-ytd-totals="incomeExecutionYtdTotals"
      :expense-execution-ytd-totals="expenseExecutionYtdTotals"
      :execution-preview="executionPreview"
      :update-income-view-mode="updateIncomeViewMode"
      :update-expense-view-mode="updateExpenseViewMode"
      :annual-entries-page="annualEntriesPage"
      :on-submit-annual-income="submitAnnualIncomeAndRefresh"
      :on-submit-annual-expense="submitAnnualExpenseAndRefresh"
      :on-remove-annual-income="removeAnnualIncomeAndRefresh"
      :on-remove-annual-expense="removeAnnualExpenseAndRefresh"
      :filtered-income-entries="filteredIncomeEntries"
      :filtered-expense-entries="filteredExpenseEntries"
      :ownership-filter="ownershipFilter"
      :selected-ownership-filter-label="selectedOwnershipFilterLabel"
    />
  </div>
</template>
