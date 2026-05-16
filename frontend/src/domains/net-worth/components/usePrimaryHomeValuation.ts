import { computed, ref, watch, type Ref } from 'vue';
import {
  type PrimaryHomeImprovementDraft,
  PRIMARY_HOME_VALUATION_PROFILES,
  PRIMARY_HOME_CUSTOM_PROFILE_VALUE,
  PRIMARY_HOME_DEFAULT_PROFILE_VALUE,
  buildEmptyPrimaryHomeImprovement,
  sanitizeAmount,
  sanitizePercent,
  normalizePercentWithMaxDecimals,
  canCapitalizeImprovementInterest,
} from './itemFormUtils';

type PrimaryHomeFormFields = {
  amount: string;
  valuation_model: string;
  land_value_share_percent: string;
  land_annual_appreciation_percent: string;
  building_annual_depreciation_percent: string;
};

export function usePrimaryHomeValuation(
  form: PrimaryHomeFormFields,
  showPrimaryHomeAutoValuationFields: Ref<boolean>,
  maxDecimals: Ref<number>,
) {
  const primaryHomeValuationProfile = ref<string>(PRIMARY_HOME_DEFAULT_PROFILE_VALUE);
  const primaryHomeImprovements = ref<PrimaryHomeImprovementDraft[]>([]);
  const expandedPrimaryHomeImprovementIndex = ref<number | null>(null);
  let syncingPrimaryHomeProfile = false;

  function applyPrimaryHomeValuationProfile(profileValue: string): void {
    const profile = PRIMARY_HOME_VALUATION_PROFILES.find((p) => p.value === profileValue);
    if (!profile) return;
    syncingPrimaryHomeProfile = true;
    form.land_annual_appreciation_percent = profile.landAnnualAppreciationPercent;
    form.building_annual_depreciation_percent = profile.buildingAnnualDepreciationPercent;
    syncingPrimaryHomeProfile = false;
  }

  function detectPrimaryHomeValuationProfile(): string {
    const toComparableNumber = (raw: unknown): number | null => {
      const normalized = String(raw ?? '')
        .trim()
        .replace(',', '.');
      if (!normalized) return null;
      const parsed = Number(normalized);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const landGrowth = toComparableNumber(form.land_annual_appreciation_percent);
    const buildingDep = toComparableNumber(form.building_annual_depreciation_percent);
    if (landGrowth == null || buildingDep == null) return PRIMARY_HOME_CUSTOM_PROFILE_VALUE;
    const profile = PRIMARY_HOME_VALUATION_PROFILES.find(
      (p) =>
        Number(p.landAnnualAppreciationPercent) === landGrowth &&
        Number(p.buildingAnnualDepreciationPercent) === buildingDep,
    );
    return profile?.value ?? PRIMARY_HOME_CUSTOM_PROFILE_VALUE;
  }

  function addPrimaryHomeImprovement(): void {
    primaryHomeImprovements.value.push(buildEmptyPrimaryHomeImprovement());
    expandedPrimaryHomeImprovementIndex.value = primaryHomeImprovements.value.length - 1;
  }

  function removePrimaryHomeImprovement(index: number): void {
    if (index < 0 || index >= primaryHomeImprovements.value.length) return;
    primaryHomeImprovements.value.splice(index, 1);
    if (!primaryHomeImprovements.value.length) {
      expandedPrimaryHomeImprovementIndex.value = null;
      return;
    }
    if (expandedPrimaryHomeImprovementIndex.value == null) return;
    if (expandedPrimaryHomeImprovementIndex.value > index) {
      expandedPrimaryHomeImprovementIndex.value -= 1;
      return;
    }
    if (expandedPrimaryHomeImprovementIndex.value === index) {
      expandedPrimaryHomeImprovementIndex.value = Math.min(
        index,
        primaryHomeImprovements.value.length - 1,
      );
    }
  }

  function validatePrimaryHomeImprovement(
    item: PrimaryHomeImprovementDraft,
    index: number,
  ): string {
    const label = `Reforma ${index + 1}`;
    if (!String(item.name ?? '').trim()) return `${label}: el nombre es obligatorio`;
    if (!String(item.reform_date ?? '').trim()) return `${label}: la fecha es obligatoria`;

    const amountSanitized = sanitizeAmount(item.amount, maxDecimals.value);
    if (!amountSanitized.value || amountSanitized.error) return `${label}: importe inválido`;

    if (item.amortization_method === 'straight_line') {
      const years = Number(String(item.amortization_term_years ?? '').trim());
      if (!Number.isInteger(years) || years <= 0) return `${label}: plazo de amortización inválido`;
    }

    if (item.amortization_method === 'manual') {
      const manualSanitized = sanitizeAmount(item.manual_current_value, maxDecimals.value);
      if (!manualSanitized.value || manualSanitized.error) {
        return `${label}: valor actual manual inválido`;
      }
    }

    if (!item.capitalize_interest) return '';
    const interestRaw = String(item.annual_interest_tae ?? '')
      .trim()
      .replace(',', '.');
    const interest = Number(interestRaw);
    if (!interestRaw || !Number.isFinite(interest) || interest < 0) {
      return `${label}: TAE inválida`;
    }
    return '';
  }

  function buildImprovementPayload(item: PrimaryHomeImprovementDraft) {
    return {
      id: item.id,
      name: String(item.name ?? '').trim(),
      reform_date: String(item.reform_date ?? '').trim(),
      amount: sanitizeAmount(item.amount, maxDecimals.value).value,
      amortization_method: item.amortization_method,
      amortization_term_years:
        item.amortization_method === 'straight_line' &&
        String(item.amortization_term_years ?? '').trim()
          ? Number(String(item.amortization_term_years).trim())
          : null,
      annual_interest_tae: String(item.annual_interest_tae ?? '').trim()
        ? String(item.annual_interest_tae).trim().replace(',', '.')
        : null,
      capitalize_interest: !!item.capitalize_interest,
      manual_current_value:
        item.amortization_method === 'manual' && String(item.manual_current_value ?? '').trim()
          ? sanitizeAmount(item.manual_current_value, maxDecimals.value).value
          : null,
      notes: String(item.notes ?? '').trim(),
    };
  }

  function validatePrimaryHomeValuationFields(): string {
    const purchase = sanitizeAmount(form.amount, maxDecimals.value);
    if (!purchase.value || purchase.error) return 'Valor de compra invalido';

    const landShare = sanitizePercent(form.land_value_share_percent);
    const landGrowth = sanitizePercent(form.land_annual_appreciation_percent);
    const buildingDep = sanitizePercent(form.building_annual_depreciation_percent);
    if (landShare.error || landGrowth.error || buildingDep.error)
      return 'Parametros de vivienda invalidos';

    const landShareN = Number(landShare.value);
    const landGrowthN = Number(landGrowth.value);
    const buildingDepN = Number(buildingDep.value);
    if (landShare.value === '' || landShareN < 0 || landShareN > 100) {
      return 'El porcentaje de suelo debe estar entre 0 y 100';
    }
    if (landGrowth.value === '' || landGrowthN < -100 || landGrowthN > 200) {
      return 'La revalorización del suelo debe estar entre -100 y 200';
    }
    if (buildingDep.value === '' || buildingDepN < 0 || buildingDepN > 100) {
      return 'La depreciación de construcción debe estar entre 0 y 100';
    }
    return '';
  }

  const primaryHomeImprovementsError = computed(() => {
    if (!showPrimaryHomeAutoValuationFields.value) return '';
    for (let i = 0; i < primaryHomeImprovements.value.length; i += 1) {
      const item = primaryHomeImprovements.value[i]!;
      const error = validatePrimaryHomeImprovement(item, i);
      if (error) return error;
    }
    return '';
  });

  const primaryHomeValuationError = computed(() => {
    if (!showPrimaryHomeAutoValuationFields.value) return '';
    return validatePrimaryHomeValuationFields();
  });

  function resetPrimaryHomeState(): void {
    form.valuation_model = 'manual';
    form.land_value_share_percent = '30';
    form.land_annual_appreciation_percent = '3';
    form.building_annual_depreciation_percent = '1';
    primaryHomeValuationProfile.value = PRIMARY_HOME_DEFAULT_PROFILE_VALUE;
    primaryHomeImprovements.value = [];
    expandedPrimaryHomeImprovementIndex.value = null;
  }

  function isImprovementExpanded(index: number): boolean {
    return expandedPrimaryHomeImprovementIndex.value === index;
  }

  function toggleImprovementExpanded(index: number): void {
    expandedPrimaryHomeImprovementIndex.value =
      expandedPrimaryHomeImprovementIndex.value === index ? null : index;
  }

  watch(
    () =>
      primaryHomeImprovements.value.map((item) => ({
        amortization_method: item.amortization_method,
        annual_interest_tae: item.annual_interest_tae,
      })),
    () => {
      for (const item of primaryHomeImprovements.value) {
        if (
          item.amortization_method === 'straight_line' &&
          !String(item.amortization_term_years ?? '').trim()
        ) {
          item.amortization_term_years = '10';
        }
        if (!canCapitalizeImprovementInterest(item) && item.capitalize_interest) {
          item.capitalize_interest = false;
        }
      }
    },
    { deep: true },
  );

  watch(
    () => form.valuation_model,
    (model) => {
      if (model !== 'real_estate_auto') {
        primaryHomeValuationProfile.value = PRIMARY_HOME_DEFAULT_PROFILE_VALUE;
        primaryHomeImprovements.value = [];
        expandedPrimaryHomeImprovementIndex.value = null;
        return;
      }
      if (primaryHomeValuationProfile.value !== PRIMARY_HOME_CUSTOM_PROFILE_VALUE) {
        applyPrimaryHomeValuationProfile(primaryHomeValuationProfile.value);
        return;
      }
      primaryHomeValuationProfile.value = detectPrimaryHomeValuationProfile();
    },
  );

  watch(
    () => primaryHomeValuationProfile.value,
    (profile) => {
      if (!showPrimaryHomeAutoValuationFields.value) return;
      if (profile === PRIMARY_HOME_CUSTOM_PROFILE_VALUE) return;
      applyPrimaryHomeValuationProfile(profile);
    },
  );

  watch(
    [
      () => form.land_value_share_percent,
      () => form.land_annual_appreciation_percent,
      () => form.building_annual_depreciation_percent,
    ],
    () => {
      if (syncingPrimaryHomeProfile || !showPrimaryHomeAutoValuationFields.value) return;
      primaryHomeValuationProfile.value = detectPrimaryHomeValuationProfile();
    },
  );

  watch(
    () => form.land_value_share_percent,
    (value) => {
      const normalized = normalizePercentWithMaxDecimals(value, 1, true, 'comma');
      if (String(value ?? '') !== normalized) form.land_value_share_percent = normalized;
    },
    { immediate: true },
  );

  watch(
    () => form.land_annual_appreciation_percent,
    (value) => {
      const normalized = normalizePercentWithMaxDecimals(value, 1, true, 'comma');
      if (String(value ?? '') !== normalized) form.land_annual_appreciation_percent = normalized;
    },
    { immediate: true },
  );

  return {
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
  };
}
