import { computed, reactive, ref, watch } from 'vue';
import {
  type ItemFormPayload,
  type ItemFormProps,
  type PrimaryHomeImprovementDraft,
  type ContributionIntervalDraft,
  decimalsByCurrency,
  ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE,
  LIABILITY_CATEGORY_DEFAULTS,
  ASSET_AMORTIZATION_METHODS,
  todayIsoDate,
  ownershipLabel,
  buildIntervalKey,
  scoreAssetNameMatch,
  sanitizeAmount,
  formatAmountForEdit,
  normalizePercentWithMaxDecimals,
  canCapitalizeImprovementInterest,
  improvementRemoveLabel,
  formatImprovementSummaryDate,
  formatImprovementSummaryAmount,
  currencySymbol,
} from './itemFormUtils';
import { useLiabilitySchedule } from './useLiabilitySchedule';
import { usePrimaryHomeValuation } from './usePrimaryHomeValuation';

export type {
  ItemFormPayload,
  ItemFormProps,
  PrimaryHomeImprovementDraft,
  ContributionIntervalDraft,
};
export {
  currencies,
  DEPOSIT_TERM_MONTH_OPTIONS,
  LIABILITY_PAYMENT_FREQUENCIES,
  LIABILITY_EXPENSE_SUBCATEGORY_OPTIONS,
  TRACKING_MODE_OPTIONS,
  REAL_ESTATE_USAGE_OPTIONS,
  PRIMARY_HOME_VALUATION_MODE_OPTIONS,
  PRIMARY_HOME_VALUATION_PROFILES,
  PRIMARY_HOME_CUSTOM_PROFILE_VALUE,
  PRIMARY_HOME_IMPROVEMENT_AMORTIZATION_OPTIONS,
} from './itemFormUtils';

export function useItemForm(props: ItemFormProps) {
  const saving = ref(false);

  const form = reactive({
    name: '',
    category: '',
    subcategory: '',
    amount: '',
    annual_interest_tae: props.showFinancedAsset ? '0' : '',
    estimated_average_balance_for_interest: '',
    deposit_term_months: '',
    monthly_payment_amount: '',
    start_date: todayIsoDate(),
    payment_start_date: '',
    expected_end_date: '',
    market_value_override: '',
    market_value_override_date: '',
    term_months: '',
    rate_type: 'fixed',
    payment_frequency: 'monthly',
    amortization_system: 'french',
    opening_fees_amount: '',
    early_repayment_fee_percent: '',
    novation_subrogation_fee_amount: '',
    linked_products_monthly_cost: '',
    cancellation_forecast_enabled: false,
    cancellation_date: '',
    cancellation_include_payment_month: true,
    cancellation_fee_amount: '',
    expense_subcategory_override: '',
    amortization_method: 'none',
    amortization_term_years: '',
    valuation_model: 'manual',
    land_value_share_percent: '30',
    land_annual_appreciation_percent: '3',
    building_annual_depreciation_percent: '1',
    notes: '',
    currency: '',
    tracking_mode: 'manual',
    is_active: true,
    ownership_id: null as number | null,
    financed_asset_id: null as number | null,
  });

  const isEdit = computed(() => props.mode === 'edit');
  const contributionIntervals = ref<ContributionIntervalDraft[]>([]);

  const financedAssetOptions = computed(() => {
    const list = Array.isArray(props.assets) ? props.assets : [];
    return [
      { value: null, label: 'No financia ningún activo' },
      ...list
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((a) => ({ value: a.id, label: a.name })),
    ];
  });

  const showFinancedAsset = computed(() => !!props.showFinancedAsset);
  const isLiabilityForm = computed(() => showFinancedAsset.value);
  const isAssetForm = computed(() => !showFinancedAsset.value);
  const requiresAssetTae = computed(
    () =>
      !!props.subcategories &&
      form.category === 'cash' &&
      ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE.includes(form.subcategory),
  );
  const showAnnualInterestInput = computed(() => isLiabilityForm.value || requiresAssetTae.value);
  const showAssetAnnualInterestInput = computed(
    () => isAssetForm.value && showAnnualInterestInput.value,
  );
  const isShortTermDepositAsset = computed(
    () =>
      isAssetForm.value && form.category === 'cash' && form.subcategory === 'short_term_deposit',
  );
  const showEstimatedAverageBalanceForInterestInput = computed(() => {
    if (!showAssetAnnualInterestInput.value) return false;
    if (isShortTermDepositAsset.value) return false;
    const taeRaw = String(form.annual_interest_tae ?? '')
      .trim()
      .replace(',', '.');
    const taeValue = Number(taeRaw);
    return Number.isFinite(taeValue) && taeValue > 0;
  });
  const isInvestmentCategory = computed(
    () => isAssetForm.value && String(form.category ?? '').trim() === 'investments',
  );
  const showInvestmentMarketValueFields = computed(
    () => isAssetForm.value && String(form.category ?? '').trim() === 'investments',
  );
  const showDepositTermMonthsInput = computed(() => isShortTermDepositAsset.value);
  const showMonthlyPaymentInput = computed(() => false);
  const isCreditCardLiability = computed(
    () => isLiabilityForm.value && String(form.category ?? '').trim() === 'credit_card',
  );
  const showLiabilityAdvancedFields = computed(
    () => isLiabilityForm.value && !isCreditCardLiability.value,
  );
  const showLiabilityExpenseSubcategoryField = computed(
    () => isLiabilityForm.value && form.category !== 'mortgage' && form.financed_asset_id == null,
  );
  const showLiabilityTaeOnlyField = computed(
    () => isLiabilityForm.value && !showLiabilityAdvancedFields.value,
  );
  const showMortgageFeeFields = computed(
    () => isLiabilityForm.value && form.category === 'mortgage',
  );
  const showMortgageCancellationForecastFields = computed(
    () => isLiabilityForm.value && form.category === 'mortgage',
  );
  const showAssetAmortizationFields = computed(
    () => isAssetForm.value && String(form.category ?? '').trim() === 'furnishings',
  );
  const isJewelryFurnishings = computed(
    () => showAssetAmortizationFields.value && String(form.subcategory ?? '').trim() === 'jewelry',
  );
  const showPrimaryHomeValuationFields = computed(
    () =>
      isAssetForm.value &&
      String(form.category ?? '').trim() === 'real_estate' &&
      ['primary_home', 'second_home', 'rental'].includes(String(form.subcategory ?? '').trim()),
  );
  const showPrimaryHomeAutoValuationFields = computed(
    () => showPrimaryHomeValuationFields.value && form.valuation_model === 'real_estate_auto',
  );
  const requiresAssetAmortizationInputs = computed(
    () =>
      showAssetAmortizationFields.value &&
      String(form.amortization_method ?? '').trim() === 'straight_line',
  );
  const useDegressiveResidualProfileForFurnishings = computed(() => {
    if (!showAssetAmortizationFields.value) return false;
    const subcategory = String(form.subcategory ?? '').trim();
    return subcategory === 'vehicles' || subcategory === 'sports_equipment';
  });
  const assetAmortizationMethodOptions = computed(() => {
    if (isJewelryFurnishings.value) {
      return [{ value: 'none', label: 'Sin amortización (joyería)' }];
    }
    if (!useDegressiveResidualProfileForFurnishings.value) return ASSET_AMORTIZATION_METHODS;
    return ASSET_AMORTIZATION_METHODS.map((option) =>
      option.value === 'straight_line'
        ? { ...option, label: 'Lineal (decreciente + residual por subcategoría)' }
        : option,
    );
  });
  const assetAmortizationModelHint = computed(() => {
    if (isJewelryFurnishings.value) {
      return "En 'Joyería' no se aplica amortización automática.";
    }
    if (!useDegressiveResidualProfileForFurnishings.value) return '';
    const subcategory = String(form.subcategory ?? '').trim();
    if (subcategory === 'vehicles') {
      return "En 'Vehículos', este método aplica curva decreciente con suelo residual del 15%.";
    }
    if (subcategory === 'sports_equipment') {
      return "En 'Equipamiento deportivo', este método aplica curva decreciente con suelo residual del 20%.";
    }
    return '';
  });
  const defaultDegressiveTermYearsForFurnishings = computed(() => {
    if (!useDegressiveResidualProfileForFurnishings.value) return null;
    const subcategory = String(form.subcategory ?? '').trim();
    if (subcategory === 'vehicles') return 20;
    if (subcategory === 'sports_equipment') return 15;
    return null;
  });
  const requiresAssetAmortizationTermInput = computed(
    () =>
      requiresAssetAmortizationInputs.value && !useDegressiveResidualProfileForFurnishings.value,
  );
  const financedAssetSuggestion = computed(() => {
    if (!showFinancedAsset.value) return null;
    const assets = Array.isArray(props.assets) ? props.assets : [];
    if (!assets.length) return null;
    const defaults = LIABILITY_CATEGORY_DEFAULTS[String(form.category ?? '').trim()] ?? {};
    const preferredCategories = new Set(defaults.preferredAssetCategories ?? []);
    const hasPreferredFilter = preferredCategories.size > 0;

    const candidates = assets
      .map((asset) => {
        let score = scoreAssetNameMatch(form.name, asset.name);
        if (hasPreferredFilter && preferredCategories.has(asset.category)) score += 15;
        return { asset, score };
      })
      .sort((a, b) => b.score - a.score || a.asset.name.localeCompare(b.asset.name));

    if (!candidates.length) return null;
    const best = candidates[0];
    const second = candidates[1];
    if (!best) return null;
    if (best.score >= 70) return best.asset;
    if (best.score >= 20 && (!second || best.score - second.score >= 15)) return best.asset;
    if (!String(form.name ?? '').trim() && hasPreferredFilter) {
      const preferredOnly = assets.filter((asset) => preferredCategories.has(asset.category));
      if (preferredOnly.length === 1) return preferredOnly[0];
    }
    return null;
  });
  const financedAssetSuggestionHelp = computed(() => {
    if (!showFinancedAsset.value || !financedAssetAutoMatched.value) return null;
    const suggestion = financedAssetSuggestion.value;
    if (!suggestion || form.financed_asset_id !== suggestion.id) return null;
    return 'Activo financiado sugerido automáticamente (editable).';
  });
  const subcategoriesForCategory = computed(() => {
    if (!props.subcategories || !form.category) return [];
    const options = props.subcategories.filter((s) => s.category === form.category);
    if (form.category !== 'real_estate') return options;
    return options.filter((option) => option.value !== 'rental');
  });
  const showRealEstateUsageField = computed(
    () =>
      isAssetForm.value &&
      String(form.category ?? '').trim() === 'real_estate' &&
      String(form.subcategory ?? '').trim() === 'second_home',
  );

  const maxDecimals = computed(() => decimalsByCurrency[form.currency] ?? 2);
  const estimatedAverageBalanceCurrencyLabel = computed(() => {
    const currency = String(form.currency ?? '').trim();
    return currency || 'EUR';
  });
  const normalizedDefaultCurrency = computed(() =>
    String(props.defaultCurrency ?? '')
      .trim()
      .toUpperCase(),
  );
  const financedAssetManuallySelected = ref(false);
  const financedAssetAutoMatched = ref(false);
  const realEstateUsage = ref<'self_use' | 'rental'>('self_use');

  const ownershipOptions = computed(() => {
    return [
      { value: null, label: 'Selecciona titularidad' },
      ...(props.ownerships || []).map((o) => ({ value: o.id, label: ownershipLabel(o) })),
    ];
  });

  const {
    liabilityDatesError,
    liabilityScheduleError,
    cancellationForecastError,
    estimatedMonthlyPaymentPreviewText,
    estimatedPaymentPreviewLabel,
    liabilityTermFieldLabel,
    liabilityTermFieldPlaceholder,
    liabilityTermFieldHint,
    onLiabilityTermInput,
    onLiabilityEndDateInput,
    onLiabilityPaymentStartDateInput,
  } = useLiabilitySchedule(
    form,
    showLiabilityAdvancedFields,
    showMortgageCancellationForecastFields,
    maxDecimals,
  );

  const {
    primaryHomeValuationProfile,
    primaryHomeImprovements,
    expandedPrimaryHomeImprovementIndex,
    primaryHomeImprovementsError,
    primaryHomeValuationError,
    addPrimaryHomeImprovement,
    removePrimaryHomeImprovement,
    buildImprovementPayload,
    detectPrimaryHomeValuationProfile,
    resetPrimaryHomeState,
    isImprovementExpanded,
    toggleImprovementExpanded,
  } = usePrimaryHomeValuation(form, showPrimaryHomeAutoValuationFields, maxDecimals);

  watch(
    () => form.category,
    () => {
      if (!props.subcategories) return;
      const valid = subcategoriesForCategory.value.some((s) => s.value === form.subcategory);
      if (!valid) form.subcategory = '';
    },
  );
  watch(
    () => form.subcategory,
    () => {
      if (!showRealEstateUsageField.value) {
        realEstateUsage.value = 'self_use';
      }
      if (showAssetAmortizationFields.value) {
        const valid = new Set(assetAmortizationMethodOptions.value.map((opt) => opt.value));
        if (!valid.has(String(form.amortization_method ?? '').trim())) {
          form.amortization_method = 'none';
        }
      }
      if (!isJewelryFurnishings.value) return;
      form.amortization_method = 'none';
      form.amortization_term_years = '';
    },
  );

  function addContributionInterval(): void {
    contributionIntervals.value.push({
      _key: buildIntervalKey(),
      start_date: '',
      end_date: '',
      amount: '',
      frequency: 'monthly',
      currency: String(form.currency ?? '').trim() || 'EUR',
    });
  }

  function removeContributionInterval(key: string): void {
    contributionIntervals.value = contributionIntervals.value.filter((row) => row._key !== key);
  }

  const amountError = computed(() => {
    const { error } = sanitizeAmount(form.amount, maxDecimals.value, props.allowNegative);
    return error;
  });
  const annualInterestError = computed(() => {
    if (!showAnnualInterestInput.value) return '';
    const raw = String(form.annual_interest_tae ?? '')
      .trim()
      .replace(',', '.');
    if (!raw) return 'La TAE es obligatoria para este indicador';
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 0) return 'TAE inválida';
    return '';
  });
  const estimatedAverageBalanceForInterestError = computed(() => {
    if (!showEstimatedAverageBalanceForInterestInput.value) return '';
    const { value, error } = sanitizeAmount(form.estimated_average_balance_for_interest, 0);
    if (error) return error;
    if (!value) return 'Indica el importe anual medio previsto para estimar intereses.';
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return 'El importe anual medio previsto debe ser mayor que 0.';
    }
    return '';
  });
  const depositTermMonthsError = computed(() => {
    if (!showDepositTermMonthsInput.value) return '';
    const raw = String(form.deposit_term_months ?? '').trim();
    if (!raw) return 'Indica la duración del depósito (1-12 meses).';
    const months = Number(raw);
    if (!Number.isInteger(months) || months < 1 || months > 12) {
      return 'La duración del depósito debe estar entre 1 y 12 meses.';
    }
    return '';
  });
  const monthlyPaymentError = computed(() => {
    if (!showMonthlyPaymentInput.value) return '';
    const raw = String(form.monthly_payment_amount ?? '').trim();
    if (!raw) return '';
    const { error } = sanitizeAmount(raw, maxDecimals.value);
    return error;
  });
  const investmentContributionError = computed(() => {
    if (!isInvestmentCategory.value) return '';
    for (const interval of contributionIntervals.value) {
      const hasAnyValue = Boolean(
        String(interval.start_date ?? '').trim() ||
        String(interval.end_date ?? '').trim() ||
        String(interval.amount ?? '').trim(),
      );
      if (!hasAnyValue) continue;
      if (!String(interval.start_date ?? '').trim()) return 'Cada intervalo requiere fecha inicio.';
      const amount = sanitizeAmount(interval.amount, maxDecimals.value);
      if (amount.error) return amount.error;
      if (!amount.value || Number(amount.value) <= 0) {
        return 'Cada intervalo requiere cuota mayor que 0.';
      }
      if (
        String(interval.end_date ?? '').trim() &&
        String(interval.end_date).trim() < String(interval.start_date).trim()
      ) {
        return 'En cada intervalo, la fecha fin debe ser >= fecha inicio.';
      }
    }
    return '';
  });
  const requiredFieldsError = computed(() => {
    if (!String(form.name ?? '').trim()) return 'Nombre obligatorio';
    if (!String(form.category ?? '').trim()) return 'Categoría obligatoria';
    if (props.subcategories && !String(form.subcategory ?? '').trim()) {
      return 'Subcategoría obligatoria';
    }
    if (!String(form.start_date ?? '').trim()) return 'Fecha inicio obligatoria';
    if (!String(form.amount ?? '').trim()) return 'Importe obligatorio';
    if (!String(form.currency ?? '').trim()) return 'Moneda obligatoria';
    return '';
  });
  const assetAmortizationError = computed(() => {
    if (!requiresAssetAmortizationInputs.value) return '';
    const amount = String(form.amount ?? '').trim();
    if (!amount) return 'Importe obligatorio para modelar amortización';
    if (requiresAssetAmortizationTermInput.value) {
      const term = String(form.amortization_term_years ?? '').trim();
      if (!term) return 'Plazo de amortización (años) obligatorio';
      const years = Number(term);
      if (!Number.isInteger(years) || years <= 0) return 'Plazo de amortización inválido';
    }
    const normalizedPurchase = sanitizeAmount(amount, maxDecimals.value);
    if (!normalizedPurchase.value || normalizedPurchase.error) return 'Valor de compra inválido';
    return '';
  });
  function getFirstSubmitBlockingError(): string {
    const validations = [
      requiredFieldsError.value,
      annualInterestError.value,
      estimatedAverageBalanceForInterestError.value,
      depositTermMonthsError.value,
      monthlyPaymentError.value,
      assetAmortizationError.value,
      investmentContributionError.value,
      primaryHomeValuationError.value,
      primaryHomeImprovementsError.value,
      liabilityDatesError.value,
      liabilityScheduleError.value,
      cancellationForecastError.value,
    ];
    return validations.find((message) => !!message) ?? '';
  }

  function buildBaseItemPayload(normalizedAmount: string): ItemFormPayload {
    return {
      name: form.name,
      category: form.category,
      subcategory:
        form.subcategory === 'second_home' && realEstateUsage.value === 'rental'
          ? 'rental'
          : form.subcategory || undefined,
      amount: normalizedAmount,
      start_date: form.start_date,
      notes: form.notes,
      currency: form.currency,
      tracking_mode: form.tracking_mode,
      is_active: form.is_active,
      ownership_id: form.ownership_id,
    };
  }

  function buildInterestPayload(): Partial<ItemFormPayload> {
    return {
      annual_interest_tae: showAnnualInterestInput.value
        ? String(form.annual_interest_tae).trim().replace(',', '.')
        : undefined,
      estimated_average_balance_for_interest:
        showEstimatedAverageBalanceForInterestInput.value &&
        String(form.estimated_average_balance_for_interest ?? '').trim()
          ? sanitizeAmount(form.estimated_average_balance_for_interest, 0).value
          : undefined,
      deposit_term_months:
        showDepositTermMonthsInput.value && String(form.deposit_term_months ?? '').trim()
          ? Number(String(form.deposit_term_months).trim())
          : undefined,
      monthly_payment_amount:
        showMonthlyPaymentInput.value && String(form.monthly_payment_amount ?? '').trim()
          ? sanitizeAmount(form.monthly_payment_amount, maxDecimals.value).value
          : undefined,
    };
  }

  // eslint-disable-next-line complexity
  function buildInvestmentPayload(normalizedAmount: string): Partial<ItemFormPayload> {
    const hasMarketValueOverride = !!String(form.market_value_override ?? '').trim();
    const effectiveMarketValueOverrideDate = hasMarketValueOverride
      ? String(form.market_value_override_date ?? '').trim() || todayIsoDate()
      : null;
    return {
      expected_end_date:
        showLiabilityAdvancedFields.value && String(form.expected_end_date ?? '').trim()
          ? String(form.expected_end_date).trim()
          : undefined,
      contribution_intervals: isInvestmentCategory.value
        ? contributionIntervals.value
            .filter((row) => String(row.start_date ?? '').trim() && String(row.amount ?? '').trim())
            .map((row) => ({
              ...(row.id ? { id: row.id } : {}),
              start_date: String(row.start_date).trim(),
              end_date: String(row.end_date ?? '').trim() ? String(row.end_date).trim() : null,
              amount:
                sanitizeAmount(row.amount, maxDecimals.value).value ?? String(row.amount).trim(),
              frequency: row.frequency === 'weekly' ? 'weekly' : 'monthly',
              currency: String(row.currency ?? '').trim() || null,
            }))
        : undefined,
      initial_purchase_value:
        isInvestmentCategory.value && contributionIntervals.value.length > 0
          ? normalizedAmount
          : undefined,
      market_value_override: showInvestmentMarketValueFields.value
        ? hasMarketValueOverride
          ? sanitizeAmount(form.market_value_override, maxDecimals.value).value
          : null
        : undefined,
      market_value_override_date: showInvestmentMarketValueFields.value
        ? hasMarketValueOverride
          ? effectiveMarketValueOverrideDate
          : null
        : undefined,
    };
  }

  // eslint-disable-next-line complexity
  function buildLiabilityPayload(): Partial<ItemFormPayload> {
    const paymentStartDate = String(form.payment_start_date ?? '').trim();
    return {
      payment_start_date: isLiabilityForm.value && paymentStartDate ? paymentStartDate : undefined,
      term_months:
        showLiabilityAdvancedFields.value && String(form.term_months ?? '').trim()
          ? Number(String(form.term_months).trim())
          : undefined,
      rate_type: showLiabilityAdvancedFields.value ? 'fixed' : undefined,
      payment_frequency: showLiabilityAdvancedFields.value ? form.payment_frequency : undefined,
      expense_subcategory_override: showLiabilityExpenseSubcategoryField.value
        ? String(form.expense_subcategory_override ?? '').trim() || undefined
        : undefined,
      amortization_system:
        showLiabilityAdvancedFields.value && String(form.amortization_system ?? '').trim()
          ? String(form.amortization_system).trim()
          : undefined,
      opening_fees_amount:
        showMortgageFeeFields.value && String(form.opening_fees_amount ?? '').trim()
          ? sanitizeAmount(form.opening_fees_amount, maxDecimals.value).value
          : undefined,
      early_repayment_fee_percent:
        showMortgageFeeFields.value && String(form.early_repayment_fee_percent ?? '').trim()
          ? String(form.early_repayment_fee_percent).trim().replace(',', '.')
          : undefined,
      novation_subrogation_fee_amount:
        showMortgageFeeFields.value && String(form.novation_subrogation_fee_amount ?? '').trim()
          ? sanitizeAmount(form.novation_subrogation_fee_amount, maxDecimals.value).value
          : undefined,
      linked_products_monthly_cost:
        showMortgageFeeFields.value && String(form.linked_products_monthly_cost ?? '').trim()
          ? sanitizeAmount(form.linked_products_monthly_cost, maxDecimals.value).value
          : undefined,
      cancellation_forecast_enabled: showMortgageCancellationForecastFields.value
        ? !!form.cancellation_forecast_enabled
        : undefined,
      cancellation_date:
        showMortgageCancellationForecastFields.value &&
        form.cancellation_forecast_enabled &&
        String(form.cancellation_date ?? '').trim()
          ? String(form.cancellation_date).trim()
          : null,
      cancellation_include_payment_month:
        showMortgageCancellationForecastFields.value && form.cancellation_forecast_enabled
          ? !!form.cancellation_include_payment_month
          : undefined,
      cancellation_fee_amount:
        showMortgageCancellationForecastFields.value &&
        form.cancellation_forecast_enabled &&
        String(form.cancellation_fee_amount ?? '').trim()
          ? sanitizeAmount(form.cancellation_fee_amount, maxDecimals.value).value
          : null,
    };
  }

  function buildAssetValuationPayload(): Partial<ItemFormPayload> {
    return {
      amortization_method: showAssetAmortizationFields.value ? form.amortization_method : undefined,
      amortization_term_years:
        requiresAssetAmortizationTermInput.value &&
        String(form.amortization_term_years ?? '').trim()
          ? Number(String(form.amortization_term_years).trim())
          : undefined,
      valuation_model: showPrimaryHomeValuationFields.value ? form.valuation_model : undefined,
      land_value_share_percent:
        showPrimaryHomeAutoValuationFields.value &&
        String(form.land_value_share_percent ?? '').trim()
          ? normalizePercentWithMaxDecimals(form.land_value_share_percent, 1)
          : undefined,
      land_annual_appreciation_percent:
        showPrimaryHomeAutoValuationFields.value &&
        String(form.land_annual_appreciation_percent ?? '').trim()
          ? normalizePercentWithMaxDecimals(form.land_annual_appreciation_percent, 1)
          : undefined,
      building_annual_depreciation_percent:
        showPrimaryHomeAutoValuationFields.value &&
        String(form.building_annual_depreciation_percent ?? '').trim()
          ? String(form.building_annual_depreciation_percent).trim().replace(',', '.')
          : undefined,
      improvements: showPrimaryHomeAutoValuationFields.value
        ? primaryHomeImprovements.value.map((item) => buildImprovementPayload(item))
        : undefined,
    };
  }

  function buildItemFormPayload(normalizedAmount: string): ItemFormPayload {
    const payload: ItemFormPayload = {
      ...buildBaseItemPayload(normalizedAmount),
      ...buildInterestPayload(),
      ...buildInvestmentPayload(normalizedAmount),
      ...buildLiabilityPayload(),
      ...buildAssetValuationPayload(),
    };
    if (showFinancedAsset.value) payload.financed_asset_id = form.financed_asset_id;
    return payload;
  }

  function resetFormAfterSubmit(): void {
    form.name = '';
    form.category = '';
    form.subcategory = '';
    realEstateUsage.value = 'self_use';
    form.amount = '';
    form.annual_interest_tae = props.showFinancedAsset ? '0' : '';
    form.estimated_average_balance_for_interest = '';
    form.deposit_term_months = '';
    form.monthly_payment_amount = '';
    form.start_date = todayIsoDate();
    form.payment_start_date = '';
    form.expected_end_date = '';
    contributionIntervals.value = [];
    form.market_value_override = '';
    form.market_value_override_date = '';
    form.term_months = '';
    form.rate_type = 'fixed';
    form.payment_frequency = 'monthly';
    form.amortization_system = 'french';
    form.opening_fees_amount = '';
    form.early_repayment_fee_percent = '';
    form.novation_subrogation_fee_amount = '';
    form.linked_products_monthly_cost = '';
    form.cancellation_forecast_enabled = false;
    form.cancellation_date = '';
    form.cancellation_include_payment_month = true;
    form.cancellation_fee_amount = '';
    form.expense_subcategory_override = 'financial_commitments';
    form.amortization_method = 'none';
    form.amortization_term_years = '';
    resetPrimaryHomeState();
    form.notes = '';
    form.currency = normalizedDefaultCurrency.value || '';
    form.ownership_id = null;
    form.financed_asset_id = null;
    financedAssetManuallySelected.value = false;
    financedAssetAutoMatched.value = false;
  }

  function applyLiabilityCategoryDefaults(category: string): void {
    if (!isLiabilityForm.value || isEdit.value) return;
    const defaults = LIABILITY_CATEGORY_DEFAULTS[String(category ?? '').trim()];
    if (defaults?.paymentFrequency) form.payment_frequency = defaults.paymentFrequency;
    form.rate_type = 'fixed';
    form.amortization_system = 'french';
    if (!String(form.annual_interest_tae ?? '').trim()) form.annual_interest_tae = '0';
    if (category !== 'mortgage') {
      form.opening_fees_amount = '';
      form.early_repayment_fee_percent = '';
      form.novation_subrogation_fee_amount = '';
      form.linked_products_monthly_cost = '';
      form.cancellation_forecast_enabled = false;
      form.cancellation_date = '';
      form.cancellation_include_payment_month = true;
      form.cancellation_fee_amount = '';
    }
    if (category === 'mortgage') {
      form.expense_subcategory_override = '';
    } else if (!String(form.expense_subcategory_override ?? '').trim()) {
      form.expense_subcategory_override = 'financial_commitments';
    }
  }

  // eslint-disable-next-line complexity
  function populateFormFromInitial(initial: NonNullable<ItemFormProps['initial']>): void {
    form.name = initial.name ?? '';
    form.category = initial.category ?? '';
    if (
      String(initial.category ?? '').trim() === 'real_estate' &&
      String(initial.subcategory ?? '').trim() === 'rental'
    ) {
      form.subcategory = 'second_home';
      realEstateUsage.value = 'rental';
    } else {
      form.subcategory = initial.subcategory ?? '';
      realEstateUsage.value = 'self_use';
    }
    form.amount = initial.amount ?? '';
    form.annual_interest_tae = initial.annual_interest_tae ?? (props.showFinancedAsset ? '0' : '');
    form.estimated_average_balance_for_interest = String(
      sanitizeAmount(initial.estimated_average_balance_for_interest ?? '', 0).value ?? '',
    );
    form.deposit_term_months =
      initial.deposit_term_months == null ? '' : String(initial.deposit_term_months);
    form.monthly_payment_amount = initial.monthly_payment_amount ?? '';
    form.start_date = initial.start_date ?? todayIsoDate();
    form.payment_start_date = initial.payment_start_date ?? '';
    form.expected_end_date = initial.expected_end_date ?? '';
    contributionIntervals.value = (initial.contribution_intervals ?? []).map((row) => ({
      _key: String(row.id ?? buildIntervalKey()),
      id: row.id,
      start_date: row.start_date,
      end_date: row.end_date ?? '',
      amount: formatAmountForEdit(row.amount ?? '', initial.currency ?? 'EUR'),
      frequency: row.frequency === 'weekly' ? 'weekly' : 'monthly',
      currency: (row.currency ?? String(initial.currency ?? '').trim()) || 'EUR',
    }));
    form.market_value_override = formatAmountForEdit(
      initial.market_value_override ?? '',
      initial.currency ?? 'EUR',
    );
    form.market_value_override_date = initial.market_value_override_date ?? '';
    form.term_months = initial.term_months == null ? '' : String(initial.term_months);
    form.rate_type = props.showFinancedAsset ? 'fixed' : (initial.rate_type ?? 'fixed');
    form.payment_frequency = initial.payment_frequency ?? 'monthly';
    form.expense_subcategory_override =
      initial.expense_subcategory_override ?? 'financial_commitments';
    form.amortization_system = initial.amortization_system ?? '';
    form.opening_fees_amount = initial.opening_fees_amount ?? '';
    form.early_repayment_fee_percent = initial.early_repayment_fee_percent ?? '';
    form.novation_subrogation_fee_amount = initial.novation_subrogation_fee_amount ?? '';
    form.linked_products_monthly_cost = initial.linked_products_monthly_cost ?? '';
    form.cancellation_forecast_enabled = !!initial.cancellation_forecast_enabled;
    form.cancellation_date = initial.cancellation_date ?? '';
    form.cancellation_include_payment_month = initial.cancellation_include_payment_month ?? true;
    form.cancellation_fee_amount = initial.cancellation_fee_amount ?? '';
    form.amortization_method = initial.amortization_method ?? 'none';
    form.amortization_term_years =
      initial.amortization_term_years == null ? '' : String(initial.amortization_term_years);
    form.valuation_model = initial.valuation_model ?? 'manual';
    form.land_value_share_percent = normalizePercentWithMaxDecimals(
      initial.land_value_share_percent ?? '30',
      1,
      false,
      'comma',
    );
    form.land_annual_appreciation_percent = normalizePercentWithMaxDecimals(
      initial.land_annual_appreciation_percent ?? '3',
      1,
      false,
      'comma',
    );
    form.building_annual_depreciation_percent = initial.building_annual_depreciation_percent ?? '1';
    primaryHomeValuationProfile.value = detectPrimaryHomeValuationProfile();
    primaryHomeImprovements.value = Array.isArray(initial.improvements)
      ? initial.improvements.map((row) => ({
          id: row.id,
          name: row.name ?? '',
          reform_date: row.reform_date ?? todayIsoDate(),
          amount: formatAmountForEdit(row.amount ?? '', initial.currency ?? 'EUR'),
          amortization_method: row.amortization_method ?? 'none',
          amortization_term_years:
            row.amortization_term_years == null ? '' : String(row.amortization_term_years),
          annual_interest_tae: row.annual_interest_tae ?? '',
          capitalize_interest: !!row.capitalize_interest,
          manual_current_value: formatAmountForEdit(
            row.manual_current_value ?? '',
            initial.currency ?? 'EUR',
          ),
          notes: row.notes ?? '',
        }))
      : [];
    expandedPrimaryHomeImprovementIndex.value = primaryHomeImprovements.value.length
      ? primaryHomeImprovements.value.length - 1
      : null;
    form.notes = initial.notes ?? '';
    form.currency = initial.currency ?? '';
    form.tracking_mode = initial.tracking_mode ?? 'manual';
    form.is_active = initial.is_active ?? true;
    form.ownership_id = initial.ownership_id ?? null;
    form.financed_asset_id = initial.financed_asset_id ?? null;
    financedAssetManuallySelected.value = form.financed_asset_id != null;
    financedAssetAutoMatched.value = false;
  }

  async function submit() {
    if (getFirstSubmitBlockingError()) return;

    const { value: normalizedAmount, error } = sanitizeAmount(
      form.amount,
      maxDecimals.value,
      props.allowNegative,
    );
    if (!normalizedAmount || error) return;
    const payload = buildItemFormPayload(normalizedAmount);

    saving.value = true;
    try {
      await props.onSubmit(payload);
      resetFormAfterSubmit();
    } finally {
      saving.value = false;
    }
  }

  watch(
    () => props.initial,
    (initial) => {
      if (!initial) return;
      populateFormFromInitial(initial);
    },
    { immediate: true, deep: true },
  );

  watch(
    [() => props.defaultCurrency, () => props.initial],
    () => {
      if (props.initial) return;
      if (!String(form.currency ?? '').trim() && normalizedDefaultCurrency.value) {
        form.currency = normalizedDefaultCurrency.value;
      }
    },
    { immediate: true },
  );
  watch(
    () => form.currency,
    (currency) => {
      const fallbackCurrency = String(currency ?? '').trim() || 'EUR';
      for (const interval of contributionIntervals.value) {
        if (!String(interval.currency ?? '').trim()) {
          interval.currency = fallbackCurrency;
        }
      }
    },
  );

  watch(
    () => form.category,
    (category) => {
      applyLiabilityCategoryDefaults(category);
    },
  );

  watch([() => form.category, () => form.subcategory], () => {
    if (!isInvestmentCategory.value) {
      contributionIntervals.value = [];
    }
    if (!showInvestmentMarketValueFields.value) {
      form.market_value_override = '';
      form.market_value_override_date = '';
    } else if (!String(form.market_value_override_date ?? '').trim()) {
      form.market_value_override_date = todayIsoDate();
    }
    if (!showDepositTermMonthsInput.value) {
      form.deposit_term_months = '';
    }
    if (!showPrimaryHomeValuationFields.value) {
      resetPrimaryHomeState();
    }
    if (!showLiabilityExpenseSubcategoryField.value) {
      form.expense_subcategory_override = '';
    } else if (!String(form.expense_subcategory_override ?? '').trim()) {
      form.expense_subcategory_override = 'financial_commitments';
    }
  });

  watch(
    [() => form.category, () => form.name, () => props.assets],
    () => {
      if (!showFinancedAsset.value || isEdit.value || financedAssetManuallySelected.value) return;
      financedAssetAutoMatched.value = false;
      const suggestion = financedAssetSuggestion.value;
      if (!suggestion) {
        form.financed_asset_id = null;
        return;
      }
      if (form.financed_asset_id !== suggestion.id) form.financed_asset_id = suggestion.id;
      financedAssetAutoMatched.value = true;
    },
    { deep: true },
  );

  function onFinancedAssetChange(): void {
    financedAssetManuallySelected.value = true;
    financedAssetAutoMatched.value = false;
  }

  return {
    form,
    saving,
    isEdit,
    contributionIntervals,
    primaryHomeImprovements,
    primaryHomeValuationProfile,
    realEstateUsage,
    ownershipOptions,
    financedAssetOptions,
    subcategoriesForCategory,
    showFinancedAsset,
    isLiabilityForm,
    isAssetForm,
    isInvestmentCategory,
    isShortTermDepositAsset,
    isCreditCardLiability,
    showAnnualInterestInput,
    showAssetAnnualInterestInput,
    showEstimatedAverageBalanceForInterestInput,
    showInvestmentMarketValueFields,
    showDepositTermMonthsInput,
    showMonthlyPaymentInput,
    showLiabilityAdvancedFields,
    showLiabilityExpenseSubcategoryField,
    showLiabilityTaeOnlyField,
    showMortgageFeeFields,
    showMortgageCancellationForecastFields,
    showAssetAmortizationFields,
    showPrimaryHomeValuationFields,
    showPrimaryHomeAutoValuationFields,
    showRealEstateUsageField,
    requiresAssetAmortizationInputs,
    requiresAssetAmortizationTermInput,
    assetAmortizationMethodOptions,
    assetAmortizationModelHint,
    defaultDegressiveTermYearsForFurnishings,
    estimatedAverageBalanceCurrencyLabel,
    liabilityTermFieldLabel,
    liabilityTermFieldPlaceholder,
    liabilityTermFieldHint,
    estimatedMonthlyPaymentPreviewText,
    estimatedPaymentPreviewLabel,
    financedAssetSuggestionHelp,
    amountError,
    annualInterestError,
    estimatedAverageBalanceForInterestError,
    depositTermMonthsError,
    monthlyPaymentError,
    investmentContributionError,
    requiredFieldsError,
    assetAmortizationError,
    primaryHomeValuationError,
    primaryHomeImprovementsError,
    liabilityDatesError,
    liabilityScheduleError,
    cancellationForecastError,
    addContributionInterval,
    removeContributionInterval,
    addPrimaryHomeImprovement,
    removePrimaryHomeImprovement,
    canCapitalizeImprovementInterest,
    improvementRemoveLabel,
    formatImprovementSummaryDate,
    formatImprovementSummaryAmount,
    currencySymbol,
    isImprovementExpanded,
    toggleImprovementExpanded,
    onLiabilityTermInput,
    onLiabilityEndDateInput,
    onLiabilityPaymentStartDateInput,
    onFinancedAssetChange,
    submit,
  };
}
