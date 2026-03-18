import { computed, type Ref } from 'vue';
import type { Asset, Liability, PositionTimelineRow, Summary } from '@/domains/net-worth/models';
import type { OwnershipFilterValue } from '@/domains/net-worth/useNetWorthOwnership';

export type PositionRow = {
  id: number;
  type: 'asset' | 'liability';
  category: string;
  name: string;
  subtitle: string;
  value: number;
  currency: string;
  ownershipFraction: number;
};

export type PositionTimelinePoint = {
  date: string;
  label: string;
  value: number;
};

export type DisplayedTimelinePoint = {
  date: string;
  label: string;
  value: number;
};

function toNumber(raw: unknown): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const value = Number(normalized);
  return Number.isFinite(value) ? value : 0;
}

function formatMonthYearLabel(date: string): string {
  return new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit' }).format(
    new Date(date),
  );
}

function resolvePositionValue(
  item: {
    amount?: string | null;
    amount_base?: string | null;
    effective_amount?: string | null;
    estimated_outstanding_amount?: string | null;
    currency?: string | null;
  },
  baseCurrency: string,
): { value: number; currency: string } {
  if (item.amount_base != null && String(item.amount_base).trim() !== '') {
    return { value: toNumber(item.amount_base), currency: baseCurrency };
  }
  if (item.effective_amount != null && String(item.effective_amount).trim() !== '') {
    return { value: toNumber(item.effective_amount), currency: item.currency ?? baseCurrency };
  }
  if (
    item.estimated_outstanding_amount != null &&
    String(item.estimated_outstanding_amount).trim() !== ''
  ) {
    return {
      value: toNumber(item.estimated_outstanding_amount),
      currency: item.currency ?? baseCurrency,
    };
  }
  return { value: toNumber(item.amount), currency: item.currency ?? baseCurrency };
}

function buildCategoryTotals(rows: PositionRow[]): Map<string, number> {
  const totals = new Map<string, number>();
  for (const row of rows) {
    totals.set(row.category, (totals.get(row.category) ?? 0) + row.value);
  }
  return totals;
}

function buildCategoryCounts(rows: PositionRow[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of rows) {
    counts.set(row.category, (counts.get(row.category) ?? 0) + 1);
  }
  return counts;
}

export function useNetWorthPageMetrics(params: {
  assets: Ref<Asset[]>;
  liabilities: Ref<Liability[]>;
  baseCurrency: Ref<string | null>;
  summary: Ref<Summary | null>;
  positionTimelineRowsSource: Ref<PositionTimelineRow[]>;
  assetCategories: { value: string; label: string }[];
  liabilityCategories: { value: string; label: string }[];
  byCategoryKeys: Ref<string[]>;
  byCategoryAssets: Ref<number[]>;
  byCategoryLiabilities: Ref<number[]>;
  summaryAssets: Ref<unknown>;
  summaryLiabilities: Ref<unknown>;
  summaryNetWorth: Ref<unknown>;
  summaryAssetBackedLiabilities: Ref<unknown>;
  summaryUnbackedLiabilities: Ref<unknown>;
  ownershipFilter: Ref<OwnershipFilterValue>;
  selectedTimelineCategory: Ref<string | null>;
  selectedTimelineCategoryType: Ref<'asset' | 'liability'>;
  selectedPositionType: Ref<'asset' | 'liability' | null>;
  selectedPositionId: Ref<number | null>;
  matchesOwnershipFilter: (ownershipRef: number | null | undefined) => boolean;
  allocationFractionForNetWorthOwner: (
    ownershipRef: number | null | undefined,
    selectedOwner: OwnershipFilterValue,
  ) => number;
}) {
  const categoryLabelMap = computed(() => {
    const entries = new Map<string, string>();
    params.assetCategories.forEach((category) => entries.set(`asset:${category.value}`, category.label));
    params.liabilityCategories.forEach((category) =>
      entries.set(`liability:${category.value}`, category.label),
    );
    return entries;
  });

  const selectedCategoryLabel = computed(() => {
    if (!params.selectedTimelineCategory.value) return 'Todo patrimonio';
    return (
      categoryLabelMap.value.get(
        `${params.selectedTimelineCategoryType.value}:${params.selectedTimelineCategory.value}`,
      ) ?? params.selectedTimelineCategory.value
    );
  });

  const ownershipFilteredAssets = computed(() =>
    params.assets.value
      .filter((asset) => asset.is_active !== false)
      .filter((asset) => params.matchesOwnershipFilter(asset.ownership_ref)),
  );

  const ownershipFilteredLiabilities = computed(() =>
    params.liabilities.value
      .filter((liability) => liability.is_active !== false)
      .filter((liability) => params.matchesOwnershipFilter(liability.ownership_ref)),
  );

  const allAssetPositionRows = computed<PositionRow[]>(() =>
    ownershipFilteredAssets.value
      .map((asset) => {
        const resolved = resolvePositionValue(
          asset,
          params.baseCurrency.value ?? params.summary.value?.base_currency ?? 'EUR',
        );
        const ownershipFraction = params.allocationFractionForNetWorthOwner(
          asset.ownership_ref,
          params.ownershipFilter.value,
        );
        return {
          id: asset.id,
          type: 'asset' as const,
          category: asset.category,
          name: asset.name,
          subtitle: [asset.category, asset.subcategory].filter(Boolean).join(' / '),
          value: resolved.value * ownershipFraction,
          currency: resolved.currency,
          ownershipFraction,
        };
      })
      .filter((asset) => asset.ownershipFraction > 0)
      .sort((a, b) => b.value - a.value),
  );

  const assetPositionRows = computed<PositionRow[]>(() =>
    allAssetPositionRows.value.filter((asset) =>
      params.selectedTimelineCategory.value &&
      params.selectedTimelineCategoryType.value === 'asset'
        ? asset.category === params.selectedTimelineCategory.value
        : true,
    ),
  );

  const allLiabilityPositionRows = computed<PositionRow[]>(() =>
    ownershipFilteredLiabilities.value
      .map((liability) => {
        const resolved = resolvePositionValue(
          liability,
          params.baseCurrency.value ?? params.summary.value?.base_currency ?? 'EUR',
        );
        const ownershipFraction = params.allocationFractionForNetWorthOwner(
          liability.ownership_ref,
          params.ownershipFilter.value,
        );
        return {
          id: liability.id,
          type: 'liability' as const,
          category: liability.category,
          name: liability.name,
          subtitle: liability.category || 'liability',
          value: resolved.value * ownershipFraction,
          currency: resolved.currency,
          ownershipFraction,
        };
      })
      .filter((liability) => liability.ownershipFraction > 0)
      .sort((a, b) => b.value - a.value),
  );

  const liabilityPositionRows = computed<PositionRow[]>(() =>
    allLiabilityPositionRows.value.filter((liability) =>
      params.selectedTimelineCategory.value &&
      params.selectedTimelineCategoryType.value === 'liability'
        ? liability.category === params.selectedTimelineCategory.value
        : true,
    ),
  );

  const filteredAssetCategoryTotals = computed(() => buildCategoryTotals(allAssetPositionRows.value));
  const filteredLiabilityCategoryTotals = computed(() =>
    buildCategoryTotals(allLiabilityPositionRows.value),
  );

  const effectiveCategoryKeys = computed(() => {
    if (params.ownershipFilter.value === 'all') return params.byCategoryKeys.value;
    return Array.from(
      new Set([
        ...filteredAssetCategoryTotals.value.keys(),
        ...filteredLiabilityCategoryTotals.value.keys(),
      ]),
    );
  });

  const effectiveCategoryLabels = computed(() =>
    effectiveCategoryKeys.value.map((key) => categoryLabelMap.value.get(`asset:${key}`) ?? key),
  );

  const effectiveCategoryAssets = computed(() => {
    if (params.ownershipFilter.value === 'all') return params.byCategoryAssets.value;
    return effectiveCategoryKeys.value.map((key) => filteredAssetCategoryTotals.value.get(key) ?? 0);
  });

  const effectiveCategoryLiabilities = computed(() => {
    if (params.ownershipFilter.value === 'all') return params.byCategoryLiabilities.value;
    return effectiveCategoryKeys.value.map(
      (key) => filteredLiabilityCategoryTotals.value.get(key) ?? 0,
    );
  });

  const filteredAssetCategoryCounts = computed(() => buildCategoryCounts(allAssetPositionRows.value));
  const filteredLiabilityCategoryCounts = computed(() =>
    buildCategoryCounts(allLiabilityPositionRows.value),
  );

  const effectiveCategoryAssetCounts = computed(() =>
    effectiveCategoryKeys.value.map((key) => filteredAssetCategoryCounts.value.get(key) ?? 0),
  );

  const effectiveCategoryLiabilityCounts = computed(() =>
    effectiveCategoryKeys.value.map((key) => filteredLiabilityCategoryCounts.value.get(key) ?? 0),
  );

  const filteredAssetsValue = computed(() =>
    allAssetPositionRows.value.reduce((total, row) => total + row.value, 0),
  );
  const filteredLiabilitiesValue = computed(() =>
    allLiabilityPositionRows.value.reduce((total, row) => total + row.value, 0),
  );
  const filteredBackedDebtValue = computed(() =>
    ownershipFilteredLiabilities.value.reduce((total, liability) => {
      const resolved = resolvePositionValue(
        liability,
        params.baseCurrency.value ?? params.summary.value?.base_currency ?? 'EUR',
      );
      const fraction = params.allocationFractionForNetWorthOwner(
        liability.ownership_ref,
        params.ownershipFilter.value,
      );
      return total + (liability.financed_asset_ref != null ? resolved.value * fraction : 0);
    }, 0),
  );
  const filteredUnbackedDebtValue = computed(() =>
    ownershipFilteredLiabilities.value.reduce((total, liability) => {
      const resolved = resolvePositionValue(
        liability,
        params.baseCurrency.value ?? params.summary.value?.base_currency ?? 'EUR',
      );
      const fraction = params.allocationFractionForNetWorthOwner(
        liability.ownership_ref,
        params.ownershipFilter.value,
      );
      return total + (liability.financed_asset_ref == null ? resolved.value * fraction : 0);
    }, 0),
  );

  const assetsValue = computed(() =>
    params.ownershipFilter.value === 'all'
      ? Math.max(0, toNumber(params.summaryAssets.value))
      : Math.max(0, filteredAssetsValue.value),
  );
  const liabilitiesValue = computed(() =>
    params.ownershipFilter.value === 'all'
      ? Math.max(0, toNumber(params.summaryLiabilities.value))
      : Math.max(0, filteredLiabilitiesValue.value),
  );
  const netWorthValue = computed(() =>
    params.ownershipFilter.value === 'all'
      ? toNumber(params.summaryNetWorth.value)
      : filteredAssetsValue.value - filteredLiabilitiesValue.value,
  );
  const backedDebtValue = computed(() =>
    params.ownershipFilter.value === 'all'
      ? Math.max(0, toNumber(params.summaryAssetBackedLiabilities.value))
      : Math.max(0, filteredBackedDebtValue.value),
  );
  const unbackedDebtValue = computed(() =>
    params.ownershipFilter.value === 'all'
      ? Math.max(0, toNumber(params.summaryUnbackedLiabilities.value))
      : Math.max(0, filteredUnbackedDebtValue.value),
  );

  const debtRatioValue = computed(() =>
    assetsValue.value > 0 ? liabilitiesValue.value / assetsValue.value : null,
  );
  const equityRatioValue = computed(() =>
    assetsValue.value > 0 ? netWorthValue.value / assetsValue.value : null,
  );
  const liquidityAssetsValue = computed(() => {
    const liquidityCategoryIndex = effectiveCategoryLabels.value.findIndex(
      (label) => label.toLowerCase() === 'liquidez',
    );
    if (liquidityCategoryIndex < 0) return 0;
    return Math.max(0, effectiveCategoryAssets.value[liquidityCategoryIndex] ?? 0);
  });
  const liquidityToDebtRatioValue = computed(() =>
    liabilitiesValue.value > 0 ? liquidityAssetsValue.value / liabilitiesValue.value : null,
  );

  const analysis = computed(() => ({
    assets: assetsValue.value,
    liabilities: liabilitiesValue.value,
    netWorth: netWorthValue.value,
    backedDebt: backedDebtValue.value,
    unbackedDebt: unbackedDebtValue.value,
    debtRatio: debtRatioValue.value,
    equityRatio: equityRatioValue.value,
    liquidityAssets: liquidityAssetsValue.value,
    liquidityToDebtRatio: liquidityToDebtRatioValue.value,
  }));

  const availablePositionRows = computed<PositionRow[]>(() => {
    if (!params.selectedTimelineCategory.value) return [];
    return params.selectedTimelineCategoryType.value === 'liability'
      ? liabilityPositionRows.value
      : assetPositionRows.value;
  });

  const activeAssets = computed(() =>
    ownershipFilteredAssets.value.map((asset) => ({
      id: asset.id,
      name: asset.name,
      category: asset.category,
    })),
  );

  const categoryWorkspaceRows = computed(() =>
    params.selectedTimelineCategoryType.value === 'liability'
      ? liabilityPositionRows.value
      : assetPositionRows.value,
  );

  const categoryWorkspaceCount = computed(() => categoryWorkspaceRows.value.length);
  const categoryWorkspaceTotal = computed(() =>
    categoryWorkspaceRows.value.reduce((total, row) => total + row.value, 0),
  );
  const showCategoryWorkspace = computed(() => !!params.selectedTimelineCategory.value);

  function sourceItemForRow(row: PositionRow) {
    return row.type === 'asset'
      ? (ownershipFilteredAssets.value.find((item) => item.id === row.id) ?? null)
      : (ownershipFilteredLiabilities.value.find((item) => item.id === row.id) ?? null);
  }

  const selectedPosition = computed(() => {
    const rows =
      params.selectedPositionType.value === 'liability'
        ? liabilityPositionRows.value
        : assetPositionRows.value;
    return rows.find((row) => row.id === params.selectedPositionId.value) ?? null;
  });

  const selectedPositionSource = computed(() => {
    const row = selectedPosition.value;
    return row ? sourceItemForRow(row) : null;
  });

  const positionTimelineRows = computed<PositionTimelinePoint[]>(() =>
    params.positionTimelineRowsSource.value.map((row) => ({
      date: row.date,
      label: formatMonthYearLabel(row.date),
      value: toNumber(row.value_base || row.value) * (selectedPosition.value?.ownershipFraction ?? 1),
    })),
  );

  return {
    selectedCategoryLabel,
    ownershipFilteredAssets,
    ownershipFilteredLiabilities,
    allAssetPositionRows,
    assetPositionRows,
    allLiabilityPositionRows,
    liabilityPositionRows,
    effectiveCategoryKeys,
    effectiveCategoryLabels,
    effectiveCategoryAssets,
    effectiveCategoryLiabilities,
    effectiveCategoryAssetCounts,
    effectiveCategoryLiabilityCounts,
    assetsValue,
    liabilitiesValue,
    netWorthValue,
    analysis,
    availablePositionRows,
    activeAssets,
    categoryWorkspaceRows,
    categoryWorkspaceCount,
    categoryWorkspaceTotal,
    showCategoryWorkspace,
    sourceItemForRow,
    selectedPosition,
    selectedPositionSource,
    positionTimelineRows,
  };
}
