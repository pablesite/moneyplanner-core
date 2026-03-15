<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  ItemForm,
  NetWorthDonut,
  NetWorthTimelineChart,
  SettingsPopover,
  coreNetWorthApi,
  useNetWorthViewExtensions,
  useNetWorthViewState,
} from '@/domains/net-worth';
import { BaseModal } from '@/domains/ui';

const {
  store,
  valueMode,
  currencies,
  assetCategories,
  liabilityCategories,
  prettyError,
  canShowReal,
  confirmDeleteSnapshot,
  showAssetModal,
  showLiabilityModal,
  showEditModal,
  editKind,
  formatMoney,
  unitLabel,
  modeLabel,
  realBaseLabel,
  assetSubcategories,
  summaryAssets,
  summaryLiabilities,
  summaryNetWorth,
  byCategoryKeys,
  byCategoryAssets,
  byCategoryLiabilities,
  summaryAssetBackedLiabilities,
  summaryUnbackedLiabilities,
  submitAsset,
  submitLiability,
  openEdit,
  closeEdit,
  editTitle,
  editCategories,
  editInitial,
  submitEdit,
} = useNetWorthViewState();

const { itemFormProps } = useNetWorthViewExtensions(store);

type OwnershipFilterValue = 'all' | number;

type OwnershipOption = {
  value: OwnershipFilterValue;
  label: string;
};

function toNumber(raw: unknown): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const value = Number(normalized);
  return Number.isFinite(value) ? value : 0;
}

function formatNumber(n: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatPct(n: number | null, decimals = 0): string {
  if (n == null || !Number.isFinite(n)) return '-';
  return new Intl.NumberFormat('es-ES', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function displayCurrencyUnit(currency: string | null | undefined): string {
  return currency === 'EUR' ? '€' : String(currency ?? '').trim();
}

const ownershipFilter = ref<OwnershipFilterValue>('all');

const ownershipById = computed(() => {
  const map = new Map<number, (typeof store.ownerships)[number]>();
  for (const ownership of store.ownerships ?? []) {
    map.set(ownership.id, ownership);
  }
  return map;
});

function normalizeOwnershipSharePercent(raw: unknown): number {
  const value = toNumber(raw);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return value <= 1 ? value * 100 : value;
}

function allocationFractionForNetWorthOwner(
  ownershipRef: number | null | undefined,
  selectedOwner: OwnershipFilterValue,
): number {
  if (selectedOwner === 'all') return 1;
  if (ownershipRef == null) return 0;

  const ownership = ownershipById.value.get(ownershipRef);
  if (!ownership) return 0;

  if (ownership.kind === 'individual') {
    return ownership.member?.id === selectedOwner ? 1 : 0;
  }

  const split = (ownership.splits ?? []).find((row) => row.member?.id === selectedOwner);
  if (!split) return 0;
  return normalizeOwnershipSharePercent(split.percent) / 100;
}

const ownershipOptions = computed<OwnershipOption[]>(() => {
  const options = new Map<number, OwnershipOption>();
  for (const ownership of store.ownerships ?? []) {
    if (ownership.kind === 'individual' && ownership.member?.id && ownership.member.name?.trim()) {
      options.set(ownership.member.id, {
        value: ownership.member.id,
        label: ownership.member.name.trim(),
      });
      continue;
    }

    for (const split of ownership.splits ?? []) {
      if (!split.member?.id || !split.member.name?.trim()) continue;
      options.set(split.member.id, {
        value: split.member.id,
        label: split.member.name.trim(),
      });
    }
  }

  return Array.from(options.values()).sort((a, b) => a.label.localeCompare(b.label, 'es'));
});

const selectedOwnershipFilterLabel = computed(() => {
  if (ownershipFilter.value === 'all') return 'Todos';
  return (
    ownershipOptions.value.find((option) => option.value === ownershipFilter.value)?.label ??
    'Todos'
  );
});
const ownershipFilterDisabled = computed(() => valueMode.value !== 'nominal');
const heroUnitLabel = computed(() => displayCurrencyUnit(unitLabel()));

watch(ownershipOptions, (options) => {
  if (ownershipFilter.value === 'all') return;
  if (!options.some((option) => option.value === ownershipFilter.value)) {
    ownershipFilter.value = 'all';
  }
});

watch(valueMode, (mode) => {
  if (mode !== 'nominal') ownershipFilter.value = 'all';
});

watch(ownershipFilter, async () => {
  resetPositionSelection();
  if (
    selectedTimelineCategory.value &&
    !effectiveCategoryKeys.value.includes(selectedTimelineCategory.value)
  ) {
    selectedTimelineCategory.value = null;
    selectedTimelineCategoryType.value = 'asset';
    await store.fetchTimeline(null, 'asset');
  }
});

function matchesOwnershipFilter(ownershipRef: number | null | undefined): boolean {
  return allocationFractionForNetWorthOwner(ownershipRef, ownershipFilter.value) > 0;
}

function closePopoverFromClick(event: Event): void {
  const target = event.currentTarget as HTMLElement | null;
  const details = target?.closest('details') as HTMLDetailsElement | null;
  if (details) details.open = false;
}

function selectOwnershipFilterOption(value: OwnershipFilterValue, event: Event): void {
  ownershipFilter.value = value;
  closePopoverFromClick(event);
}

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

const selectedTimelineCategory = ref<string | null>(null);
const selectedTimelineCategoryType = ref<'asset' | 'liability'>('asset');
const selectedPositionType = ref<'asset' | 'liability' | null>(null);
const selectedPositionId = ref<number | null>(null);
const createAssetCategory = ref<string | null>(null);
const createLiabilityCategory = ref<string | null>(null);
const timelineExpanded = ref(false);
const selectedTimelinePreset = ref<'1m' | '3m' | '6m' | '1a' | 'all'>('all');
const customTimelineWindow = ref<{ start: number; end: number } | null>(null);
const timelinePresetOptions = ['1m', '3m', '6m', '1a', 'all'] as const;

type TimelinePoint = {
  date: string;
  label: string;
  netWorth: number;
  assets: number;
  liabilities: number;
};

const timelineRows = computed<TimelinePoint[]>(() =>
  (store.timeline?.rows ?? []).map((row) => ({
    date: row.date,
    label: new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit' }).format(
      new Date(row.date),
    ),
    netWorth: toNumber(row.net_worth),
    assets: toNumber(row.total_assets),
    liabilities: toNumber(row.total_liabilities),
  })),
);

const timelineMetric = computed<'net_worth' | 'assets' | 'liabilities'>(() => {
  if (!selectedTimelineCategory.value) return 'net_worth';
  return selectedTimelineCategoryType.value === 'liability' ? 'liabilities' : 'assets';
});

function getTimelineMetricValue(row: TimelinePoint): number {
  if (timelineMetric.value === 'assets') return row.assets;
  if (timelineMetric.value === 'liabilities') return row.liabilities;
  return row.netWorth;
}

const currentSummaryTimelinePoint = computed<DisplayedTimelinePoint>(() => ({
  date: 'current',
  label: 'Actual',
  value: netWorthValue.value,
}));

const categoryLabelMap = computed(() => {
  const entries = new Map<string, string>();
  assetCategories.forEach((category) => entries.set(`asset:${category.value}`, category.label));
  liabilityCategories.forEach((category) =>
    entries.set(`liability:${category.value}`, category.label),
  );
  return entries;
});

const selectedCategoryLabel = computed(() => {
  if (!selectedTimelineCategory.value) return 'Todo patrimonio';
  return (
    categoryLabelMap.value.get(
      `${selectedTimelineCategoryType.value}:${selectedTimelineCategory.value}`,
    ) ?? selectedTimelineCategory.value
  );
});

type PositionRow = {
  id: number;
  type: 'asset' | 'liability';
  category: string;
  name: string;
  subtitle: string;
  value: number;
  currency: string;
  ownershipFraction: number;
};

type PositionTimelinePoint = {
  date: string;
  label: string;
  value: number;
};

type DisplayedTimelinePoint = {
  date: string;
  label: string;
  value: number;
};

type TimelineChartPoint = {
  date: string;
  shortLabel: string;
  fullLabel: string;
  value: number;
};

type PositionActivityRow = {
  id: string;
  date: string;
  label: string;
  kind: 'valuation' | 'event';
  amount: number;
  meta: string;
  note: string;
};

function resolvePositionValue(item: {
  amount?: string | null;
  amount_base?: string | null;
  effective_amount?: string | null;
  estimated_outstanding_amount?: string | null;
  currency?: string | null;
}): { value: number; currency: string } {
  const baseCurrency = store.baseCurrency ?? store.summary?.base_currency ?? 'EUR';
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

const ownershipFilteredAssets = computed(() =>
  store.assets
    .filter((asset) => asset.is_active !== false)
    .filter((asset) => matchesOwnershipFilter(asset.ownership_ref)),
);

const ownershipFilteredLiabilities = computed(() =>
  store.liabilities
    .filter((liability) => liability.is_active !== false)
    .filter((liability) => matchesOwnershipFilter(liability.ownership_ref)),
);

const allAssetPositionRows = computed<PositionRow[]>(() =>
  ownershipFilteredAssets.value
    .map((asset) => {
      const resolved = resolvePositionValue(asset);
      const ownershipFraction = allocationFractionForNetWorthOwner(
        asset.ownership_ref,
        ownershipFilter.value,
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
    selectedTimelineCategory.value && selectedTimelineCategoryType.value === 'asset'
      ? asset.category === selectedTimelineCategory.value
      : true,
  ),
);

const allLiabilityPositionRows = computed<PositionRow[]>(() =>
  ownershipFilteredLiabilities.value
    .map((liability) => {
      const resolved = resolvePositionValue(liability);
      const ownershipFraction = allocationFractionForNetWorthOwner(
        liability.ownership_ref,
        ownershipFilter.value,
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
    selectedTimelineCategory.value && selectedTimelineCategoryType.value === 'liability'
      ? liability.category === selectedTimelineCategory.value
      : true,
  ),
);

function buildCategoryTotals(rows: PositionRow[]): Map<string, number> {
  const totals = new Map<string, number>();
  for (const row of rows) {
    totals.set(row.category, (totals.get(row.category) ?? 0) + row.value);
  }
  return totals;
}

const filteredAssetCategoryTotals = computed(() => buildCategoryTotals(allAssetPositionRows.value));
const filteredLiabilityCategoryTotals = computed(() =>
  buildCategoryTotals(allLiabilityPositionRows.value),
);

const effectiveCategoryKeys = computed(() => {
  if (ownershipFilter.value === 'all') return byCategoryKeys.value;
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
  if (ownershipFilter.value === 'all') return byCategoryAssets.value;
  return effectiveCategoryKeys.value.map((key) => filteredAssetCategoryTotals.value.get(key) ?? 0);
});

const effectiveCategoryLiabilities = computed(() => {
  if (ownershipFilter.value === 'all') return byCategoryLiabilities.value;
  return effectiveCategoryKeys.value.map(
    (key) => filteredLiabilityCategoryTotals.value.get(key) ?? 0,
  );
});

function buildCategoryCounts(rows: PositionRow[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of rows) {
    counts.set(row.category, (counts.get(row.category) ?? 0) + 1);
  }
  return counts;
}

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
    const resolved = resolvePositionValue(liability);
    const fraction = allocationFractionForNetWorthOwner(
      liability.ownership_ref,
      ownershipFilter.value,
    );
    return total + (liability.financed_asset_ref != null ? resolved.value * fraction : 0);
  }, 0),
);
const filteredUnbackedDebtValue = computed(() =>
  ownershipFilteredLiabilities.value.reduce((total, liability) => {
    const resolved = resolvePositionValue(liability);
    const fraction = allocationFractionForNetWorthOwner(
      liability.ownership_ref,
      ownershipFilter.value,
    );
    return total + (liability.financed_asset_ref == null ? resolved.value * fraction : 0);
  }, 0),
);

const assetsValue = computed(() =>
  ownershipFilter.value === 'all'
    ? Math.max(0, toNumber(summaryAssets.value))
    : Math.max(0, filteredAssetsValue.value),
);
const liabilitiesValue = computed(() =>
  ownershipFilter.value === 'all'
    ? Math.max(0, toNumber(summaryLiabilities.value))
    : Math.max(0, filteredLiabilitiesValue.value),
);
const netWorthValue = computed(() =>
  ownershipFilter.value === 'all'
    ? toNumber(summaryNetWorth.value)
    : filteredAssetsValue.value - filteredLiabilitiesValue.value,
);
const backedDebtValue = computed(() =>
  ownershipFilter.value === 'all'
    ? Math.max(0, toNumber(summaryAssetBackedLiabilities.value))
    : Math.max(0, filteredBackedDebtValue.value),
);
const unbackedDebtValue = computed(() =>
  ownershipFilter.value === 'all'
    ? Math.max(0, toNumber(summaryUnbackedLiabilities.value))
    : Math.max(0, filteredUnbackedDebtValue.value),
);

const availablePositionRows = computed<PositionRow[]>(() => {
  if (!selectedTimelineCategory.value) return [];
  return selectedTimelineCategoryType.value === 'liability'
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
  selectedTimelineCategoryType.value === 'liability'
    ? liabilityPositionRows.value
    : assetPositionRows.value,
);

const categoryWorkspaceCount = computed(() => categoryWorkspaceRows.value.length);
const categoryWorkspaceTotal = computed(() =>
  categoryWorkspaceRows.value.reduce((total, row) => total + row.value, 0),
);

const showCategoryWorkspace = computed(() => !!selectedTimelineCategory.value);

function ownershipBadge(ownershipRef: number | null | undefined): string | null {
  if (ownershipRef == null) return null;
  const ownership = ownershipById.value.get(ownershipRef);
  if (!ownership) return null;
  if (ownership.kind === 'individual') return ownership.member?.name?.trim() ?? null;
  const names = (ownership.splits ?? [])
    .map((split) => split.member?.name?.trim())
    .filter((name): name is string => !!name);
  return names.length ? names.join(' + ') : 'Compartido';
}

function sourceItemForRow(row: PositionRow) {
  return row.type === 'asset'
    ? (ownershipFilteredAssets.value.find((item) => item.id === row.id) ?? null)
    : (ownershipFilteredLiabilities.value.find((item) => item.id === row.id) ?? null);
}

function ownershipBadgeForRow(row: PositionRow): string | null {
  return ownershipBadge(sourceItemForRow(row)?.ownership_ref);
}

function editRow(row: PositionRow): void {
  const item = sourceItemForRow(row);
  if (!item) return;
  openEdit(item, row.type);
}

async function deleteRow(row: PositionRow): Promise<void> {
  const label = row.type === 'asset' ? 'activo' : 'pasivo';
  if (!confirm(`Eliminar este ${label}? Esta accion no se puede deshacer.`)) return;
  if (row.type === 'asset') {
    await store.deleteAsset(row.id);
  } else {
    await store.deleteLiability(row.id);
  }
}

const categoryWorkspaceLabel = computed(() => {
  if (!selectedTimelineCategory.value) return '';
  const scope = selectedTimelineCategoryType.value === 'liability' ? 'pasivos' : 'activos';
  return `${selectedCategoryLabel.value} dentro de ${scope}`;
});

const categoryWorkspaceMeta = computed(() => {
  if (!selectedTimelineCategory.value) return '';
  return `${categoryWorkspaceCount.value} posiciones - ${formatNumber(categoryWorkspaceTotal.value, 2)} ${heroUnitLabel.value}`;
});

const showPositionSelector = computed(
  () => !!selectedTimelineCategory.value && availablePositionRows.value.length > 0,
);

const selectedPosition = computed(() => {
  const rows =
    selectedPositionType.value === 'liability'
      ? liabilityPositionRows.value
      : assetPositionRows.value;
  return rows.find((row) => row.id === selectedPositionId.value) ?? null;
});

const positionTimelineRows = computed<PositionTimelinePoint[]>(() =>
  (store.positionTimeline?.rows ?? []).map((row) => ({
    date: row.date,
    label: new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit' }).format(
      new Date(row.date),
    ),
    value: toNumber(row.value_base || row.value) * (selectedPosition.value?.ownershipFraction ?? 1),
  })),
);

const positionTimelineRange = computed(() => {
  const values = positionTimelineRows.value.map((row) => row.value);
  if (!values.length) return { min: 0, max: 1 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return { min: min - 1, max: max + 1 };
  return { min, max };
});

const positionTimelinePath = computed(() => {
  const rows = positionTimelineRows.value;
  if (rows.length < 2) return '';
  const { min, max } = positionTimelineRange.value;
  return rows
    .map((row, index) => {
      const x = (index / (rows.length - 1)) * 100;
      const normalized = (row.value - min) / (max - min);
      const y = 100 - normalized * 100;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
});

const latestPositionTimelinePoint = computed(
  () => positionTimelineRows.value[positionTimelineRows.value.length - 1] ?? null,
);

type CachedTimelineRows = {
  positionType: 'asset' | 'liability';
  rows: PositionTimelinePoint[];
};

const ownershipTimelineCache = ref<Record<string, CachedTimelineRows>>({});
const ownershipTimelineLoading = ref(false);

function positionCacheKey(type: 'asset' | 'liability', id: number): string {
  return `${type}:${id}`;
}

const ownershipScopedRows = computed<PositionRow[]>(() => {
  if (ownershipFilter.value === 'all' || selectedPosition.value) return [];
  if (selectedTimelineCategory.value) return availablePositionRows.value;
  return [...allAssetPositionRows.value, ...allLiabilityPositionRows.value];
});

async function ensureOwnershipTimelineCache(rows: PositionRow[]): Promise<void> {
  const missingRows = rows.filter(
    (row) => !ownershipTimelineCache.value[positionCacheKey(row.type, row.id)],
  );
  if (!missingRows.length) return;

  ownershipTimelineLoading.value = true;
  try {
    const results = await Promise.all(
      missingRows.map(async (row) => {
        const response =
          row.type === 'asset'
            ? await coreNetWorthApi.getAssetTimeline(row.id)
            : await coreNetWorthApi.getLiabilityTimeline(row.id);
        return { row, timeline: response.data };
      }),
    );

    ownershipTimelineCache.value = results.reduce<Record<string, CachedTimelineRows>>(
      (cache, entry) => {
        cache[positionCacheKey(entry.row.type, entry.row.id)] = {
          positionType: entry.row.type,
          rows: (entry.timeline.rows ?? []).map((timelineRow) => ({
            date: timelineRow.date,
            label: new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit' }).format(
              new Date(timelineRow.date),
            ),
            value: toNumber(timelineRow.value_base || timelineRow.value),
          })),
        };
        return cache;
      },
      { ...ownershipTimelineCache.value },
    );
  } catch (error: unknown) {
    store.error = error instanceof Error ? error.message : 'No se pudo cargar la timeline filtrada';
  } finally {
    ownershipTimelineLoading.value = false;
  }
}

watch(
  () => ownershipScopedRows.value.map((row) => positionCacheKey(row.type, row.id)).join('|'),
  async () => {
    if (ownershipFilter.value === 'all' || selectedPosition.value) return;
    await ensureOwnershipTimelineCache(ownershipScopedRows.value);
  },
  { immediate: true },
);

watch(availablePositionRows, (rows) => {
  if (!selectedPositionId.value || !selectedPositionType.value) return;
  if (
    !rows.some(
      (row) => row.id === selectedPositionId.value && row.type === selectedPositionType.value,
    )
  ) {
    resetPositionSelection();
  }
});

const ownershipTimelineRows = computed<TimelinePoint[]>(() => {
  if (ownershipFilter.value === 'all') return [];

  const byDate = new Map<string, TimelinePoint>();
  for (const row of ownershipScopedRows.value) {
    const cached = ownershipTimelineCache.value[positionCacheKey(row.type, row.id)];
    if (!cached) continue;

    for (const point of cached.rows) {
      const current = byDate.get(point.date) ?? {
        date: point.date,
        label: point.label,
        netWorth: 0,
        assets: 0,
        liabilities: 0,
      };
      if (row.type === 'asset') {
        current.assets += point.value * row.ownershipFraction;
      } else {
        current.liabilities += point.value * row.ownershipFraction;
      }
      current.netWorth = current.assets - current.liabilities;
      byDate.set(point.date, current);
    }
  }

  return Array.from(byDate.values()).sort((a, b) => a.date.localeCompare(b.date));
});

const activeTimelineRows = computed(() =>
  ownershipFilter.value === 'all' ? timelineRows.value : ownershipTimelineRows.value,
);

const latestTimelinePoint = computed(
  () => activeTimelineRows.value[activeTimelineRows.value.length - 1] ?? null,
);

const displayedTimelineRows = computed<DisplayedTimelinePoint[]>(() => {
  if (selectedPosition.value) {
    return positionTimelineRows.value.map((row) => ({
      date: row.date,
      label: row.label,
      value: row.value,
    }));
  }
  return activeTimelineRows.value.map((row) => ({
    date: row.date,
    label: row.label,
    value: getTimelineMetricValue(row),
  }));
});

const cachedDisplayedTimelineRows = ref<DisplayedTimelinePoint[]>([]);
const cachedDisplayedTimelineSeriesColor = ref('#4cc3ff');
const timelineColumnRef = ref<HTMLElement | null>(null);
const timelineSidebarHeight = ref<number | null>(null);
const isDesktopTimelineLayout = ref(false);
let timelineColumnResizeObserver: ResizeObserver | null = null;

function syncTimelineLayoutViewport(): void {
  if (typeof window === 'undefined') return;
  isDesktopTimelineLayout.value = window.innerWidth > 1024;
}

function syncTimelineSidebarHeight(): void {
  if (!isDesktopTimelineLayout.value) {
    timelineSidebarHeight.value = null;
    return;
  }

  const nextHeight = timelineColumnRef.value?.offsetHeight ?? null;
  timelineSidebarHeight.value = nextHeight && nextHeight > 0 ? nextHeight : null;
}

const timelineSidebarPanelStyle = computed<Record<string, string> | undefined>(() => {
  if (!isDesktopTimelineLayout.value || timelineSidebarHeight.value == null) return undefined;
  const height = `${timelineSidebarHeight.value}px`;
  return {
    height,
    maxHeight: height,
  };
});

onMounted(() => {
  syncTimelineLayoutViewport();
  void nextTick(syncTimelineSidebarHeight);

  if (typeof window !== 'undefined') {
    window.addEventListener('resize', syncTimelineLayoutViewport);
    window.addEventListener('resize', syncTimelineSidebarHeight);
  }

  if (typeof ResizeObserver !== 'undefined') {
    timelineColumnResizeObserver = new ResizeObserver(() => {
      syncTimelineSidebarHeight();
    });
    if (timelineColumnRef.value) {
      timelineColumnResizeObserver.observe(timelineColumnRef.value);
    }
  }
});

onBeforeUnmount(() => {
  timelineColumnResizeObserver?.disconnect();
  timelineColumnResizeObserver = null;

  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', syncTimelineLayoutViewport);
    window.removeEventListener('resize', syncTimelineSidebarHeight);
  }
});

const displayedTimelineLoading = computed(() =>
  selectedPosition.value
    ? store.positionTimelineLoading
    : ownershipFilter.value === 'all'
      ? store.timelineLoading
      : ownershipTimelineLoading.value,
);

const visibleTimelineRows = computed<DisplayedTimelinePoint[]>(() => {
  if (displayedTimelineLoading.value && cachedDisplayedTimelineRows.value.length > 0) {
    return cachedDisplayedTimelineRows.value;
  }
  return displayedTimelineRows.value.length > 0
    ? displayedTimelineRows.value
    : cachedDisplayedTimelineRows.value;
});

const timelinePresetPointCount: Record<(typeof timelinePresetOptions)[number], number> = {
  '1m': 1,
  '3m': 3,
  '6m': 6,
  '1a': 12,
  all: Number.POSITIVE_INFINITY,
};

const timelineDefaultWindow = computed(() => {
  const end = Math.max(0, visibleTimelineRows.value.length - 1);
  const count = timelinePresetPointCount[selectedTimelinePreset.value];
  if (!Number.isFinite(count)) return { start: 0, end };
  return { start: Math.max(0, end - count + 1), end };
});

const timelineWindow = computed(() => {
  const length = visibleTimelineRows.value.length;
  if (length === 0) return { start: 0, end: 0 };
  const source = customTimelineWindow.value ?? timelineDefaultWindow.value;
  const start = Math.min(Math.max(0, source.start), length - 1);
  const end = Math.min(Math.max(start, source.end), length - 1);
  return { start, end };
});

const timelineChartRows = computed(() =>
  visibleTimelineRows.value.slice(timelineWindow.value.start, timelineWindow.value.end + 1),
);

const timelineChartPoints = computed<TimelineChartPoint[]>(() =>
  timelineChartRows.value.map((row) => ({
    date: row.date,
    shortLabel: row.label,
    fullLabel:
      row.date === 'current'
        ? row.label
        : new Intl.DateTimeFormat('es-ES', { month: 'long', year: 'numeric' }).format(
            new Date(row.date),
          ),
    value: row.value,
  })),
);

const timelineRangeCaption = computed(() => {
  if (timelineChartPoints.value.length === 0) return '-';
  const first = timelineChartPoints.value[0];
  const last = timelineChartPoints.value[timelineChartPoints.value.length - 1];
  if (!first || !last) return '-';
  return `${first.fullLabel} - ${last.fullLabel}`;
});

const latestTimelineChartPoint = computed(
  () => timelineChartPoints.value[timelineChartPoints.value.length - 1] ?? null,
);

watch(
  [showCategoryWorkspace, displayedTimelineRows, visibleTimelineRows, selectedPosition],
  async () => {
    await nextTick();
    syncTimelineSidebarHeight();
  },
  { deep: true },
);

const displayedTimelineLatestPoint = computed(() => {
  if (!selectedPosition.value && !selectedTimelineCategory.value) {
    return currentSummaryTimelinePoint.value;
  }
  return visibleTimelineRows.value[visibleTimelineRows.value.length - 1] ?? null;
});

const displayedTimelineSummaryLabel = computed(() => {
  if (selectedPosition.value) {
    return selectedPosition.value.type === 'liability'
      ? 'Ultimo valor del pasivo'
      : 'Ultimo valor del activo';
  }
  if (!selectedTimelineCategory.value) return 'Ultimo patrimonio neto';
  return 'Ultimo valor de la categoria';
});

const displayedTimelineSummaryMeta = computed(() => {
  const point = displayedTimelineLatestPoint.value;
  if (!point) return '-';
  if (selectedPosition.value) {
    return `${point.label} | ${selectedPosition.value.subtitle}`;
  }
  if (!selectedTimelineCategory.value) {
    return `${point.label} | Activos ${formatNumber(assetsValue.value, 0)} ${heroUnitLabel.value} | Pasivos ${formatNumber(
      liabilitiesValue.value,
      0,
    )} ${heroUnitLabel.value}`;
  }
  return `${point.label} | ${selectedCategoryLabel.value}`;
});

const currentTimelineSeriesColor = computed(() => {
  if (selectedPosition.value?.type === 'liability') return '#ff4d73';
  if (selectedTimelineCategoryType.value === 'liability') return '#ff4d73';
  if (selectedPosition.value?.type === 'asset') return '#2dd4bf';
  return '#4cc3ff';
});

const displayedTimelineSeriesColor = computed(() => {
  if (displayedTimelineLoading.value && cachedDisplayedTimelineRows.value.length > 0) {
    return cachedDisplayedTimelineSeriesColor.value;
  }
  return currentTimelineSeriesColor.value;
});

watch(
  [displayedTimelineRows, displayedTimelineLoading],
  ([rows, loading]) => {
    if (!loading && rows.length > 0) {
      cachedDisplayedTimelineRows.value = rows;
      cachedDisplayedTimelineSeriesColor.value = currentTimelineSeriesColor.value;
    }
  },
  { immediate: true },
);

const displayedTimelineRange = computed(() => {
  const values = timelineChartRows.value.map((row) => row.value);
  if (!values.length) return { min: 0, max: 1 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return { min: min - 1, max: max + 1 };
  return { min, max };
});

const displayedTimelinePath = computed(() => {
  const rows = timelineChartRows.value;
  if (rows.length < 2) return '';
  const { min, max } = displayedTimelineRange.value;
  return rows
    .map((row, index) => {
      const x = (index / (rows.length - 1)) * 100;
      const normalized = (row.value - min) / (max - min);
      const y = 100 - normalized * 100;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');
});

const displayedTimelineYAxisLabels = computed(() => {
  const { min, max } = displayedTimelineRange.value;
  const mid = min + (max - min) / 2;
  return [max, mid, min].map((value) => formatNumber(value, 0));
});

const displayedTimelineXAxisLabels = computed(() => {
  const rows = timelineChartRows.value;
  if (rows.length <= 6) return rows;
  const indexes = Array.from(
    new Set([
      0,
      Math.floor(rows.length / 4),
      Math.floor(rows.length / 2),
      Math.floor((rows.length * 3) / 4),
      rows.length - 1,
    ]),
  );
  return indexes
    .map((index) => rows[index])
    .filter((row): row is DisplayedTimelinePoint => row !== undefined);
});

type TimelineCategoryOption = {
  value: string | null;
  label: string;
  type: 'asset' | 'liability';
  count: number;
  total: number;
};

const timelineAssetCategoryOptions = computed<TimelineCategoryOption[]>(() =>
  effectiveCategoryKeys.value
    .map((key, index) => ({
      value: key,
      label: categoryLabelMap.value.get(`asset:${key}`) ?? key,
      type: 'asset' as const,
      count: effectiveCategoryAssetCounts.value[index] ?? 0,
      total: effectiveCategoryAssets.value[index] ?? 0,
    }))
    .filter((option) => option.count > 0 || option.total > 0),
);

const timelineLiabilityCategoryOptions = computed<TimelineCategoryOption[]>(() =>
  effectiveCategoryKeys.value
    .map((key, index) => ({
      value: key,
      label: categoryLabelMap.value.get(`liability:${key}`) ?? key,
      type: 'liability' as const,
      count: effectiveCategoryLiabilityCounts.value[index] ?? 0,
      total: effectiveCategoryLiabilities.value[index] ?? 0,
    }))
    .filter((option) => option.count > 0 || option.total > 0),
);

const timelineCategoryOptions = computed(() => [
  ...timelineAssetCategoryOptions.value,
  ...timelineLiabilityCategoryOptions.value,
]);

const timelineSummaryLabel = displayedTimelineSummaryLabel;
const timelineSummaryMeta = displayedTimelineSummaryMeta;
const timelineSeriesColor = displayedTimelineSeriesColor;
const timelinePath = displayedTimelinePath;
const timelineYAxisLabels = displayedTimelineYAxisLabels;
const timelineXAxisLabels = displayedTimelineXAxisLabels;
const legacyTimelineSummaryValue = computed(() =>
  latestTimelinePoint.value ? getTimelineMetricValue(latestTimelinePoint.value) : 0,
);

const positionActivityRows = computed<PositionActivityRow[]>(() => {
  if (selectedPositionType.value === 'asset') {
    const valuations = store.assetValuations.map((row) => ({
      id: `valuation-${row.id}`,
      date: row.valuation_date,
      label: 'Checkpoint',
      kind: 'valuation' as const,
      amount: toNumber(row.value),
      meta: row.source,
      note: row.note ?? '',
    }));
    const investmentEvents = store.investmentEvents.map((row) => ({
      id: `investment-${row.id}`,
      date: row.event_date,
      label: row.event_type,
      kind: 'event' as const,
      amount: toNumber(row.amount),
      meta:
        row.event_type === 'passive_income' && row.is_reinvested === false
          ? 'passive_income · no reinvertido'
          : row.event_type,
      note: row.note ?? '',
    }));
    const liquidityEvents = store.liquidityEvents.map((row) => ({
      id: `liquidity-${row.id}`,
      date: row.event_date,
      label: row.event_type,
      kind: 'event' as const,
      amount: toNumber(row.amount),
      meta: row.event_type,
      note: row.note ?? '',
    }));
    return [...valuations, ...investmentEvents, ...liquidityEvents].sort((a, b) =>
      b.date.localeCompare(a.date),
    );
  }

  const valuations = store.liabilityValuations.map((row) => ({
    id: `valuation-${row.id}`,
    date: row.valuation_date,
    label: 'Checkpoint',
    kind: 'valuation' as const,
    amount: toNumber(row.value),
    meta: row.source,
    note: row.note ?? '',
  }));
  const events = store.liabilityEvents.map((row) => ({
    id: `liability-event-${row.id}`,
    date: row.event_date,
    label: row.event_type,
    kind: 'event' as const,
    amount: toNumber(row.amount),
    meta: row.event_type,
    note: row.note ?? '',
  }));
  return [...valuations, ...events].sort((a, b) => b.date.localeCompare(a.date));
});

function resetPositionSelection(): void {
  selectedPositionType.value = null;
  selectedPositionId.value = null;
  store.positionTimeline = null;
  store.assetValuations = [];
  store.liabilityValuations = [];
  store.investmentEvents = [];
  store.liquidityEvents = [];
  store.liabilityEvents = [];
}

function openCreateModal(type: 'asset' | 'liability', category: string | null = null): void {
  resetPositionSelection();
  if (type === 'asset') {
    createAssetCategory.value = category;
    showAssetModal.value = true;
    return;
  }
  createLiabilityCategory.value = category;
  showLiabilityModal.value = true;
}

async function submitAssetFromView(payload: Parameters<typeof submitAsset>[0]): Promise<void> {
  await submitAsset(payload);
  createAssetCategory.value = null;
}

async function submitLiabilityFromView(
  payload: Parameters<typeof submitLiability>[0],
): Promise<void> {
  await submitLiability(payload);
  createLiabilityCategory.value = null;
}

async function applyTimelineCategoryFilter(
  category: string | null,
  categoryType: 'asset' | 'liability' = 'asset',
): Promise<void> {
  selectedTimelineCategory.value = category;
  selectedTimelineCategoryType.value = categoryType;
  selectedTimelinePreset.value = 'all';
  customTimelineWindow.value = null;
  resetPositionSelection();
  await store.fetchTimeline(category, categoryType);
}

async function resetTimelineSelection(): Promise<void> {
  await applyTimelineCategoryFilter(null, 'asset');
}

async function applyCompositionCategoryFilter(payload: {
  key: string;
  type: 'asset' | 'liability';
}): Promise<void> {
  const isSelectedCategory =
    selectedTimelineCategory.value === payload.key &&
    selectedTimelineCategoryType.value === payload.type;

  if (isSelectedCategory) {
    await applyTimelineCategoryFilter(null, 'asset');
    return;
  }

  await applyTimelineCategoryFilter(payload.key, payload.type);
}

async function handleCompositionAddType(payload: { type: 'asset' | 'liability' }): Promise<void> {
  openCreateModal(payload.type, null);
}

async function selectPosition(row: PositionRow): Promise<void> {
  selectedPositionType.value = row.type;
  selectedPositionId.value = row.id;
  selectedTimelinePreset.value = 'all';
  customTimelineWindow.value = null;
  await Promise.all([
    store.fetchPositionTimeline(row.type, row.id),
    store.fetchPositionActivity(row.type, row.id, row.type === 'asset' ? row.category : null),
  ]);
}

function setTimelinePreset(preset: (typeof timelinePresetOptions)[number]): void {
  selectedTimelinePreset.value = preset;
  customTimelineWindow.value = null;
}

function updateTimelineWindowStart(rawValue: string): void {
  const nextStart = Number(rawValue);
  const currentEnd = timelineWindow.value.end;
  customTimelineWindow.value = {
    start: Math.min(nextStart, currentEnd),
    end: currentEnd,
  };
}

function updateTimelineWindowEnd(rawValue: string): void {
  const nextEnd = Number(rawValue);
  const currentStart = timelineWindow.value.start;
  customTimelineWindow.value = {
    start: currentStart,
    end: Math.max(currentStart, nextEnd),
  };
}

function onPositionSelection(event: Event): void {
  const target = event.target as HTMLSelectElement | null;
  const rawValue = target?.value ?? '';
  if (!rawValue) {
    resetPositionSelection();
    return;
  }

  const selectedId = Number(rawValue);
  const row = availablePositionRows.value.find((item) => item.id === selectedId);
  if (!row) {
    resetPositionSelection();
    return;
  }

  void selectPosition(row);
}

const assetCreateInitial = computed(() =>
  createAssetCategory.value ? { category: createAssetCategory.value } : undefined,
);

const liabilityCreateInitial = computed(() =>
  createLiabilityCategory.value ? { category: createLiabilityCategory.value } : undefined,
);
</script>

<template>
  <div class="container ui-pro-page relative">
    <section class="card ui-pro-panel ui-nw-hero-shell grid gap-2.5 mb-2">
      <p class="ui-pro-kicker">Patrimonio</p>
      <div class="ui-nw-topbar mt-1">
        <div class="ui-nw-topbar-actions">
          <button
            class="icon-btn ui-nw-topbar-action disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            :disabled="store.loading"
            aria-label="Refrescar"
            @click="store.refreshAll()"
          >
            <span class="icon" aria-hidden="true">&#8635;</span>
          </button>
          <button
            class="icon-btn ui-nw-topbar-action disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            :disabled="store.loading"
            aria-label="Guardar snapshot"
            title="Guardar snapshot"
            @click="store.createTodaySnapshot()"
          >
            <span class="icon" aria-hidden="true">&#128190;</span>
          </button>
        </div>

        <div class="ui-pro-toolbar ui-nw-toolbar">
          <SettingsPopover
            :loading="store.loading"
            :base-currency="store.baseCurrency ?? 'EUR'"
            :currencies="currencies"
            :value-mode="valueMode"
            :can-show-real="canShowReal()"
            :mode-help="modeLabel()"
            :real-base-label="realBaseLabel"
            :show-refresh="false"
            :show-snapshot="false"
            :icon-only="true"
            @update:base-currency="store.updateBaseCurrency"
            @update:value-mode="(v) => (valueMode = v)"
            @snapshot="store.createTodaySnapshot()"
            @refresh="store.refreshAll()"
          />
        </div>
      </div>

      <div class="ui-nw-hero mt-2">
        <div class="ui-nw-hero-main">
          <div class="ui-nw-hero-donut">
            <div class="ui-nw-hero-donut-frame">
              <NetWorthDonut
                :total-assets="analysis.assets"
                :total-liabilities="analysis.liabilities"
                :asset-backed-liabilities="analysis.backedDebt"
                :unbacked-liabilities="analysis.unbackedDebt"
                :net-worth="analysis.netWorth"
                :unit="heroUnitLabel"
                :show-composition="false"
              />
            </div>
          </div>
          <article class="ui-nw-hero-summary">
            <div class="ui-nw-hero-summary-head">
              <div class="ui-nw-hero-badge">Balance actual</div>
              <label class="ui-nw-hero-context" data-test="ownership-filter">
                <span class="ui-nw-hero-context-label">Titularidad</span>
                <details
                  class="ui-select-popover ui-nw-hero-context-popover"
                  :class="{ 'opacity-60': ownershipFilterDisabled }"
                >
                  <summary
                    class="ui-select-popover-trigger ui-nw-hero-context-trigger"
                    :aria-disabled="ownershipFilterDisabled"
                    @click="ownershipFilterDisabled ? $event.preventDefault() : undefined"
                  >
                    <span class="ui-select-popover-text">{{ selectedOwnershipFilterLabel }}</span>
                    <span class="ui-select-popover-caret" aria-hidden="true">⌄</span>
                  </summary>
                  <div class="ui-select-popover-menu" role="listbox" aria-label="Titularidad">
                    <button
                      type="button"
                      class="ui-select-popover-option"
                      :class="{ 'ui-select-popover-option-active': ownershipFilter === 'all' }"
                      data-test="ownership-filter-option-all"
                      :disabled="ownershipFilterDisabled"
                      @click="selectOwnershipFilterOption('all', $event)"
                    >
                      Todos
                    </button>
                    <button
                      v-for="option in ownershipOptions"
                      :key="String(option.value)"
                      type="button"
                      class="ui-select-popover-option"
                      :class="{
                        'ui-select-popover-option-active': ownershipFilter === option.value,
                      }"
                      :data-test="`ownership-filter-option-${String(option.value)}`"
                      :disabled="ownershipFilterDisabled"
                      @click="selectOwnershipFilterOption(option.value, $event)"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                </details>
              </label>
            </div>
            <div class="ui-nw-hero-summary-body">
              <div class="ui-nw-hero-primary">
                <div class="ui-nw-hero-title">Patrimonio neto</div>
                <button
                  class="ui-nw-hero-value-button"
                  type="button"
                  @click="resetTimelineSelection"
                >
                  <div class="ui-nw-hero-value">
                    {{ formatNumber(analysis.netWorth, 2) }} {{ heroUnitLabel }}
                  </div>
                </button>
                <div class="ui-nw-hero-metrics">
                  <div class="ui-nw-hero-metric">
                    <span class="ui-nw-hero-metric-label">Cobertura liquida</span>
                    <strong class="ui-nw-hero-metric-value">
                      {{ formatPct(analysis.liquidityToDebtRatio, 0) }}
                    </strong>
                  </div>
                  <div class="ui-nw-hero-metric">
                    <span class="ui-nw-hero-metric-label">Capital propio</span>
                    <strong class="ui-nw-hero-metric-value">
                      {{ formatPct(analysis.equityRatio, 0) }}
                    </strong>
                  </div>
                </div>
              </div>

              <div class="ui-nw-hero-side">
                <div class="ui-nw-hero-stats">
                  <div class="ui-nw-hero-stat ui-nw-hero-stat-assets">
                    <span class="ui-nw-hero-stat-label">Activos</span>
                    <strong class="ui-nw-hero-stat-value">
                      {{ formatNumber(analysis.assets, 2) }} {{ heroUnitLabel }}
                    </strong>
                  </div>
                  <div class="ui-nw-hero-stat ui-nw-hero-stat-liabilities">
                    <span class="ui-nw-hero-stat-label">Pasivos</span>
                    <strong class="ui-nw-hero-stat-value">
                      {{ formatNumber(analysis.liabilities, 2) }} {{ heroUnitLabel }}
                    </strong>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </div>

      <div class="ui-nw-hero-timeline">
        <div class="ui-nw-timeline-layout">
          <div ref="timelineColumnRef" class="ui-nw-timeline-column">
            <div class="ui-pro-panel ui-nw-balance-panel ui-nw-balance-panel-integrated">
              <NetWorthDonut
                :total-assets="analysis.assets"
                :total-liabilities="analysis.liabilities"
                :asset-backed-liabilities="analysis.backedDebt"
                :unbacked-liabilities="analysis.unbackedDebt"
                :net-worth="analysis.netWorth"
                :unit="heroUnitLabel"
                :category-keys="effectiveCategoryKeys"
                :category-labels="effectiveCategoryLabels"
                :category-assets="effectiveCategoryAssets"
                :category-liabilities="effectiveCategoryLiabilities"
                :category-asset-counts="effectiveCategoryAssetCounts"
                :category-liability-counts="effectiveCategoryLiabilityCounts"
                :selected-category-key="selectedTimelineCategory"
                :selected-category-type="selectedTimelineCategoryType"
                :show-chart="false"
                @select-category="applyCompositionCategoryFilter"
                @add-type="handleCompositionAddType"
              />
            </div>

            <div v-if="displayedTimelineLoading && visibleTimelineRows.length === 0" class="subtle">
              Cargando evolucion...
            </div>
            <div v-else-if="visibleTimelineRows.length === 0" class="subtle">
              {{
                selectedPosition
                  ? 'Esta posicion aun no tiene suficientes puntos para construir una serie mensual.'
                  : 'Aun no hay datos suficientes para construir la serie temporal.'
              }}
            </div>
            <div v-else class="ui-nw-timeline-main">
              <div class="ui-nw-timeline-body">
                <div class="ui-nw-timeline-toolbar">
                  <div class="ui-nw-timeline-range-group" role="group" aria-label="Rango temporal">
                    <button
                      v-for="preset in timelinePresetOptions"
                      :key="preset"
                      class="ui-nw-timeline-range-button"
                      :class="{
                        'ui-nw-timeline-range-button-active':
                          customTimelineWindow === null && selectedTimelinePreset === preset,
                      }"
                      type="button"
                      @click="setTimelinePreset(preset)"
                    >
                      {{ preset }}
                    </button>
                  </div>

                  <div class="ui-nw-timeline-toolbar-actions">
                    <span class="ui-nw-timeline-range-caption">{{ timelineRangeCaption }}</span>
                    <button
                      class="ui-nw-timeline-expand-button"
                      type="button"
                      @click="timelineExpanded = true"
                    >
                      Expandir
                    </button>
                  </div>
                </div>

                <div class="ui-nw-timeline-chart-shell">
                  <div v-if="displayedTimelineLoading" class="ui-nw-timeline-loading-overlay">
                    <span class="ui-nw-timeline-loading-pill">Actualizando serie...</span>
                  </div>
                  <NetWorthTimelineChart
                    :points="timelineChartPoints"
                    :unit="displayCurrencyUnit(store.timeline?.base_currency ?? unitLabel())"
                    :series-label="timelineSummaryLabel"
                    :series-color="displayedTimelineSeriesColor"
                  />
                </div>

                <div class="ui-nw-timeline-points">
                  <div
                    v-for="row in timelineChartRows.slice(-6)"
                    :key="row.date"
                    class="ui-nw-timeline-point"
                  >
                    <span>{{ row.label }}</span>
                    <strong>{{ formatNumber(row.value, 0) }}</strong>
                  </div>
                </div>
              </div>

              <div v-if="selectedPosition" class="ui-nw-position-activity">
                <div class="ui-nw-position-activity-head">
                  <h3 class="ui-nw-position-activity-title">Eventos y checkpoints</h3>
                  <span v-if="store.positionActivityLoading" class="subtle">Cargando...</span>
                </div>
                <div v-if="positionActivityRows.length === 0" class="subtle">
                  No hay eventos ni valoraciones manuales registrados para esta posicion.
                </div>
                <div v-else class="ui-nw-position-activity-list">
                  <div
                    v-for="row in positionActivityRows"
                    :key="row.id"
                    class="ui-nw-position-activity-row"
                    :class="{
                      'ui-nw-position-activity-row-valuation': row.kind === 'valuation',
                    }"
                  >
                    <div class="ui-nw-position-activity-main">
                      <strong>{{ row.date }}</strong>
                      <span>{{ row.label }} | {{ row.meta }}</span>
                      <span v-if="row.note">{{ row.note }}</span>
                    </div>
                    <div class="ui-nw-position-activity-amount">
                      {{ formatNumber(row.amount, 2) }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <BaseModal
            :open="timelineExpanded"
            title="Evolucion temporal"
            panel-class="max-w-[1080px]"
            @close="timelineExpanded = false"
          >
            <div class="ui-nw-timeline-modal">
              <div class="ui-nw-timeline-modal-head">
                <div>
                  <div class="ui-nw-timeline-modal-title">{{ timelineSummaryLabel }}</div>
                  <div class="ui-nw-timeline-modal-copy">{{ timelineRangeCaption }}</div>
                </div>
                <div class="ui-nw-timeline-modal-value">
                  {{ formatNumber(latestTimelineChartPoint?.value ?? 0, 2) }}
                  {{ displayCurrencyUnit(store.timeline?.base_currency ?? unitLabel()) }}
                </div>
              </div>

              <div class="ui-nw-timeline-modal-ranges">
                <label class="ui-nw-timeline-slider-group">
                  <span>Inicio</span>
                  <input
                    class="ui-nw-timeline-slider"
                    type="range"
                    min="0"
                    :max="Math.max(0, visibleTimelineRows.length - 1)"
                    :value="timelineWindow.start"
                    @input="updateTimelineWindowStart(($event.target as HTMLInputElement).value)"
                  />
                  <strong>{{ timelineChartPoints[0]?.fullLabel ?? '-' }}</strong>
                </label>

                <label class="ui-nw-timeline-slider-group">
                  <span>Fin</span>
                  <input
                    class="ui-nw-timeline-slider"
                    type="range"
                    min="0"
                    :max="Math.max(0, visibleTimelineRows.length - 1)"
                    :value="timelineWindow.end"
                    @input="updateTimelineWindowEnd(($event.target as HTMLInputElement).value)"
                  />
                  <strong>{{ latestTimelineChartPoint?.fullLabel ?? '-' }}</strong>
                </label>
              </div>

              <NetWorthTimelineChart
                :points="timelineChartPoints"
                :unit="displayCurrencyUnit(store.timeline?.base_currency ?? unitLabel())"
                :series-label="timelineSummaryLabel"
                :series-color="displayedTimelineSeriesColor"
                expanded
              />
            </div>
          </BaseModal>

          <aside class="ui-nw-timeline-sidebar">
            <div
              v-if="!showCategoryWorkspace"
              class="ui-nw-category-workspace ui-nw-category-workspace-empty"
              :style="timelineSidebarPanelStyle"
            >
              <h3 class="ui-nw-category-workspace-title">Selecciona una categoria arriba</h3>
              <p class="ui-nw-category-workspace-copy">
                El grafico se actualiza en primera plana y aqui veras las posiciones concretas de
                esa categoria.
              </p>
            </div>

            <div
              v-else
              class="ui-nw-category-workspace ui-nw-category-workspace-embedded"
              :style="timelineSidebarPanelStyle"
            >
              <div class="ui-nw-category-workspace-head">
                <div class="ui-nw-category-workspace-heading">
                  <div class="ui-nw-category-workspace-kicker">
                    {{ selectedTimelineCategoryType === 'liability' ? 'Pasivos' : 'Activos' }}
                  </div>
                  <div class="ui-nw-category-workspace-title-row">
                    <h3 class="ui-nw-category-workspace-title">{{ categoryWorkspaceLabel }}</h3>
                    <button
                      class="icon-btn ui-nw-category-add-btn"
                      type="button"
                      :aria-label="
                        selectedTimelineCategoryType === 'liability'
                          ? 'Nuevo pasivo'
                          : 'Nuevo activo'
                      "
                      :title="
                        selectedTimelineCategoryType === 'liability'
                          ? 'Nuevo pasivo'
                          : 'Nuevo activo'
                      "
                      @click="
                        openCreateModal(selectedTimelineCategoryType, selectedTimelineCategory)
                      "
                    >
                      <span class="icon" aria-hidden="true">+</span>
                    </button>
                  </div>
                  <p class="ui-nw-category-workspace-copy">{{ categoryWorkspaceMeta }}</p>
                </div>
              </div>

              <label v-if="showPositionSelector" class="ui-nw-position-select">
                <span class="ui-nw-position-select-label">
                  {{
                    selectedTimelineCategoryType === 'liability'
                      ? 'Pasivo concreto'
                      : 'Activo concreto'
                  }}
                </span>
                <select
                  class="input ui-nw-position-select-input"
                  :value="selectedPositionId ?? ''"
                  @change="onPositionSelection"
                >
                  <option value="">Categoria completa</option>
                  <option v-for="row in availablePositionRows" :key="row.id" :value="row.id">
                    {{ row.name }}
                  </option>
                </select>
              </label>

              <div v-if="categoryWorkspaceRows.length === 0" class="subtle">
                No hay posiciones para esta categoria con el filtro actual.
              </div>
              <div v-else class="ui-nw-category-workspace-list">
                <article
                  v-for="row in categoryWorkspaceRows"
                  :key="`${row.type}-${row.id}`"
                  class="ui-nw-category-item"
                  :class="{
                    'ui-nw-category-item-active':
                      selectedPositionType === row.type && selectedPositionId === row.id,
                  }"
                >
                  <button
                    class="ui-nw-category-item-main"
                    type="button"
                    @click="selectPosition(row)"
                  >
                    <div class="ui-nw-category-selection-label">
                      {{ row.type === 'liability' ? 'Pasivo concreto' : 'Activo concreto' }}
                    </div>
                    <div class="ui-nw-category-item-head">
                      <strong>{{ row.name }}</strong>
                      <span
                        >{{ formatNumber(row.value, 2) }}
                        {{ displayCurrencyUnit(row.currency) }}</span
                      >
                    </div>
                    <div class="ui-nw-category-item-meta">
                      <span>{{ row.subtitle }}</span>
                      <span v-if="row.ownershipFraction < 1">
                        {{ formatPct(row.ownershipFraction, 0) }} titularidad aplicada
                      </span>
                      <span v-if="ownershipBadgeForRow(row)">{{ ownershipBadgeForRow(row) }}</span>
                    </div>
                  </button>
                  <div class="ui-nw-category-item-actions">
                    <button
                      class="icon-btn ui-nw-category-item-action"
                      type="button"
                      aria-label="Editar"
                      title="Editar"
                      @click="editRow(row)"
                    >
                      <span class="icon" aria-hidden="true">&#9998;</span>
                    </button>
                    <button
                      class="icon-btn ui-nw-category-item-action"
                      type="button"
                      :aria-label="row.type === 'asset' ? 'Eliminar activo' : 'Eliminar pasivo'"
                      title="Eliminar"
                      @click="deleteRow(row)"
                    >
                      <span class="icon" aria-hidden="true">&#128465;</span>
                    </button>
                  </div>
                </article>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </section>

    <div v-if="store.error" class="alert mt-3">
      {{ prettyError() }}
    </div>

    <section v-if="false" class="section card ui-pro-panel ui-nw-timeline-panel">
      <div class="ui-nw-timeline-head">
        <div>
          <h2 class="mt-0 text-base ui-nw-timeline-title">Evolucion temporal</h2>
        </div>
        <div class="ui-nw-timeline-filters">
          <button
            v-for="option in timelineCategoryOptions"
            :key="`${option.type}-${option.value ?? 'all'}`"
            class="ui-nw-timeline-filter"
            :class="{
              'ui-nw-timeline-filter-active':
                selectedTimelineCategory === option.value &&
                (option.value === null || selectedTimelineCategoryType === option.type),
            }"
            type="button"
            @click="applyTimelineCategoryFilter(option.value, option.type)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <div v-if="store.timelineLoading" class="subtle">Cargando evolucion...</div>
      <div v-else-if="timelineRows.length === 0" class="subtle">
        Aun no hay datos suficientes para construir la serie temporal.
      </div>
      <div v-else class="ui-nw-timeline-body">
        <div class="ui-nw-timeline-summary">
          <div class="ui-nw-timeline-summary-label">{{ timelineSummaryLabel }}</div>
          <div class="ui-nw-timeline-summary-value">
            {{ formatNumber(legacyTimelineSummaryValue, 2) }}
            {{ store.timeline?.base_currency }}
          </div>
          <div v-if="false" class="ui-nw-timeline-summary-meta">
            {{ latestTimelinePoint?.label ?? '-' }} · Activos
            {{ formatNumber(latestTimelinePoint?.assets ?? 0, 0) }} · Pasivos
            {{ formatNumber(latestTimelinePoint?.liabilities ?? 0, 0) }}
          </div>
          <div class="ui-nw-timeline-summary-meta">{{ timelineSummaryMeta }}</div>
        </div>

        <div class="ui-nw-timeline-chart-shell">
          <div class="ui-nw-timeline-chart-layout">
            <div class="ui-nw-timeline-y-axis" aria-hidden="true">
              <span v-for="label in timelineYAxisLabels" :key="label">{{ label }}</span>
            </div>
            <div class="ui-nw-timeline-chart-stage">
              <svg
                class="ui-nw-timeline-chart"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                aria-label="Grafico de evolucion patrimonial"
              >
                <path
                  class="ui-nw-timeline-grid"
                  d="M 0 20 L 100 20 M 0 50 L 100 50 M 0 80 L 100 80"
                />
                <path
                  v-if="timelinePath"
                  class="ui-nw-timeline-line"
                  :d="timelinePath"
                  :style="{ stroke: timelineSeriesColor }"
                />
              </svg>
            </div>
          </div>
          <div v-if="false">
            <svg
              class="ui-nw-timeline-chart"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-label="Grafico de evolucion patrimonial"
            >
              <path
                class="ui-nw-timeline-grid"
                d="M 0 20 L 100 20 M 0 50 L 100 50 M 0 80 L 100 80"
              />
              <path v-if="timelinePath" class="ui-nw-timeline-line" :d="timelinePath" />
            </svg>
          </div>
        </div>

        <div class="ui-nw-timeline-x-axis" aria-hidden="true">
          <span v-for="row in timelineXAxisLabels" :key="`axis-${row.date}`">{{ row.label }}</span>
        </div>

        <div class="ui-nw-timeline-points">
          <div v-for="row in timelineRows.slice(-6)" :key="row.date" class="ui-nw-timeline-point">
            <span>{{ row.label }}</span>
            <strong>{{ formatNumber(getTimelineMetricValue(row), 0) }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section v-if="false" class="section card ui-pro-panel ui-nw-drilldown-panel">
      <div class="ui-nw-drilldown-head">
        <div>
          <h2 class="mt-0 text-base">Detalle por posicion</h2>
          <p class="ui-nw-drilldown-copy">
            Selecciona un activo o pasivo para ver su evolucion mensual por separado.
          </p>
        </div>
      </div>

      <div class="ui-nw-drilldown-grid">
        <div class="ui-nw-position-column">
          <div class="ui-nw-position-column-head">
            <h3 class="ui-nw-position-column-title">Activos</h3>
            <span class="ui-nw-position-column-meta"
              >{{ assetPositionRows.length }} posiciones</span
            >
          </div>
          <div v-if="assetPositionRows.length === 0" class="subtle">
            No hay activos para este filtro.
          </div>
          <div v-else class="ui-nw-position-list">
            <button
              v-for="row in assetPositionRows.slice(0, 8)"
              :key="`asset-${row.id}`"
              class="ui-nw-position-button"
              :class="{
                'ui-nw-position-button-active':
                  selectedPositionType === 'asset' && selectedPositionId === row.id,
              }"
              type="button"
              @click="selectPosition(row)"
            >
              <span class="ui-nw-position-button-main">
                <strong>{{ row.name }}</strong>
                <span>{{ row.subtitle }}</span>
              </span>
              <span class="ui-nw-position-button-value">
                {{ formatNumber(row.value, 2) }} {{ row.currency }}
              </span>
            </button>
          </div>
        </div>

        <div class="ui-nw-position-column">
          <div class="ui-nw-position-column-head">
            <h3 class="ui-nw-position-column-title">Pasivos</h3>
            <span class="ui-nw-position-column-meta"
              >{{ liabilityPositionRows.length }} posiciones</span
            >
          </div>
          <div v-if="liabilityPositionRows.length === 0" class="subtle">
            No hay pasivos activos.
          </div>
          <div v-else class="ui-nw-position-list">
            <button
              v-for="row in liabilityPositionRows.slice(0, 8)"
              :key="`liability-${row.id}`"
              class="ui-nw-position-button"
              :class="{
                'ui-nw-position-button-active':
                  selectedPositionType === 'liability' && selectedPositionId === row.id,
              }"
              type="button"
              @click="selectPosition(row)"
            >
              <span class="ui-nw-position-button-main">
                <strong>{{ row.name }}</strong>
                <span>{{ row.subtitle }}</span>
              </span>
              <span class="ui-nw-position-button-value">
                {{ formatNumber(row.value, 2) }} {{ row.currency }}
              </span>
            </button>
          </div>
        </div>
      </div>

      <div class="ui-nw-position-detail">
        <div v-if="store.positionTimelineLoading" class="subtle">
          Cargando evolucion de la posicion...
        </div>
        <div v-else-if="!selectedPosition" class="subtle">
          Elige una posicion para inspeccionar su curva temporal.
        </div>
        <div v-else-if="positionTimelineRows.length === 0" class="subtle">
          Esta posicion aun no tiene suficientes puntos para construir una serie mensual.
        </div>
        <div v-else class="ui-nw-position-detail-body">
          <div class="ui-nw-position-detail-summary">
            <div class="ui-nw-position-detail-label">
              {{
                selectedPosition?.type === 'asset' ? 'Activo seleccionado' : 'Pasivo seleccionado'
              }}
            </div>
            <div class="ui-nw-position-detail-title">{{ selectedPosition?.name }}</div>
            <div class="ui-nw-position-detail-meta">
              {{ selectedPosition?.subtitle }} | Ultimo valor
              {{ formatNumber(latestPositionTimelinePoint?.value ?? 0, 2) }}
              {{ store.positionTimeline?.base_currency ?? selectedPosition?.currency }}
            </div>
          </div>

          <div class="ui-nw-position-detail-chart-shell">
            <svg
              class="ui-nw-position-detail-chart"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-label="Grafico de evolucion de la posicion"
            >
              <path
                class="ui-nw-position-detail-grid"
                d="M 0 20 L 100 20 M 0 50 L 100 50 M 0 80 L 100 80"
              />
              <path
                v-if="positionTimelinePath"
                class="ui-nw-position-detail-line"
                :d="positionTimelinePath"
              />
            </svg>
          </div>

          <div class="ui-nw-position-detail-points">
            <div
              v-for="row in positionTimelineRows.slice(-6)"
              :key="`${selectedPosition?.type}-${selectedPosition?.id}-${row.date}`"
              class="ui-nw-position-detail-point"
            >
              <span>{{ row.label }}</span>
              <strong>{{ formatNumber(row.value, 0) }}</strong>
            </div>
          </div>

          <div class="ui-nw-position-activity">
            <div class="ui-nw-position-activity-head">
              <h3 class="ui-nw-position-activity-title">Eventos y checkpoints</h3>
              <span v-if="store.positionActivityLoading" class="subtle">Cargando...</span>
            </div>
            <div v-if="positionActivityRows.length === 0" class="subtle">
              No hay eventos ni valoraciones manuales registrados para esta posicion.
            </div>
            <div v-else class="ui-nw-position-activity-list">
              <div
                v-for="row in positionActivityRows"
                :key="row.id"
                class="ui-nw-position-activity-row"
                :class="{
                  'ui-nw-position-activity-row-valuation': row.kind === 'valuation',
                }"
              >
                <div class="ui-nw-position-activity-main">
                  <strong>{{ row.date }}</strong>
                  <span>{{ row.label }} · {{ row.meta }}</span>
                  <span v-if="row.note">{{ row.note }}</span>
                </div>
                <div class="ui-nw-position-activity-amount">
                  {{ formatNumber(row.amount, 2) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="section card ui-pro-panel">
      <h2 class="mt-0 text-base">Snapshots</h2>

      <ul v-if="store.snapshots.length" class="m-0 grid list-none gap-2 pl-0">
        <li v-for="s in store.snapshots" :key="s.id" class="ui-nw-snapshot-row">
          <div class="min-w-0">
            {{ s.snapshot_date }} - neto: {{ formatMoney(s.net_worth, 2) }}
            {{ displayCurrencyUnit(s.base_currency) }}
            <span class="subtle">
              (activos {{ formatMoney(s.total_assets, 2) }}
              {{ displayCurrencyUnit(s.base_currency) }}, pasivos
              {{ formatMoney(s.total_liabilities, 2) }} {{ displayCurrencyUnit(s.base_currency) }})
            </span>
          </div>
          <button
            class="icon-btn disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            :disabled="store.loading"
            aria-label="Eliminar snapshot"
            title="Eliminar snapshot"
            @click="confirmDeleteSnapshot(s.id)"
          >
            <span class="icon" aria-hidden="true">&#128465;</span>
          </button>
        </li>
      </ul>

      <div v-else class="subtle">No hay snapshots todavia.</div>
    </div>

    <BaseModal
      :open="showAssetModal"
      title="Nuevo activo"
      @close="
        showAssetModal = false;
        createAssetCategory = null;
      "
    >
      <ItemForm
        title="Nuevo activo"
        :categories="assetCategories"
        :subcategories="assetSubcategories"
        :initial="assetCreateInitial"
        v-bind="itemFormProps"
        :allow-negative="true"
        :on-submit="submitAssetFromView"
        :on-cancel="
          () => {
            showAssetModal = false;
            createAssetCategory = null;
          }
        "
      />
    </BaseModal>

    <BaseModal
      :open="showLiabilityModal"
      title="Nuevo pasivo"
      @close="
        showLiabilityModal = false;
        createLiabilityCategory = null;
      "
    >
      <ItemForm
        title="Nuevo pasivo"
        :categories="liabilityCategories"
        :initial="liabilityCreateInitial"
        v-bind="itemFormProps"
        :assets="activeAssets"
        :show-financed-asset="true"
        :on-submit="submitLiabilityFromView"
        :on-cancel="
          () => {
            showLiabilityModal = false;
            createLiabilityCategory = null;
          }
        "
      />
    </BaseModal>

    <BaseModal :open="showEditModal" :title="editTitle" @close="closeEdit">
      <ItemForm
        v-if="editInitial"
        :title="editTitle"
        :categories="editCategories"
        :subcategories="editKind === 'asset' ? assetSubcategories : undefined"
        v-bind="itemFormProps"
        :assets="editKind === 'liability' ? activeAssets : []"
        :show-financed-asset="editKind === 'liability'"
        :allow-negative="editKind === 'asset'"
        mode="edit"
        :initial="editInitial"
        :on-submit="submitEdit"
        :on-cancel="closeEdit"
      />
    </BaseModal>

    <div v-if="store.loading" class="ui-status-line">Cargando...</div>
  </div>
</template>

<style scoped>
.ui-nw-hero-shell {
  position: relative;
  overflow: visible;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background:
    radial-gradient(circle at top left, rgba(76, 195, 255, 0.12), transparent 30%),
    radial-gradient(circle at right, rgba(45, 212, 191, 0.08), transparent 34%),
    linear-gradient(180deg, rgba(10, 16, 28, 0.96), rgba(7, 12, 22, 0.98));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 18px 40px rgba(0, 0, 0, 0.22);
}

.ui-nw-topbar {
  position: relative;
  z-index: 12;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.ui-nw-topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ui-nw-topbar-action {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.ui-nw-balance-panel {
  padding: 14px;
}

.ui-nw-balance-panel-integrated {
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.ui-nw-inline-analytics {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: grid;
  gap: 16px;
}

.ui-nw-hero-timeline {
  margin-top: 0;
  padding-top: 6px;
  border-top: 0;
}

.ui-nw-timeline-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.9fr);
  gap: 14px 16px;
  align-items: stretch;
}

.ui-nw-timeline-column {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.ui-nw-hero {
  position: relative;
  z-index: 1;
}

.ui-nw-hero-main {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}

.ui-nw-hero-donut {
  position: relative;
  min-height: 0;
}

.ui-nw-hero-donut-frame {
  height: 184px;
  border-radius: 20px;
  border: 1px solid rgba(92, 192, 255, 0.14);
  background:
    radial-gradient(circle at 50% 0%, rgba(92, 192, 255, 0.18), transparent 54%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.015));
  padding: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    inset 0 -24px 60px rgba(0, 0, 0, 0.16);
}

.ui-nw-hero-summary {
  height: 184px;
  border-radius: 20px;
  border: 1px solid rgba(45, 212, 191, 0.18);
  background:
    radial-gradient(circle at top right, rgba(45, 212, 191, 0.14), transparent 32%),
    linear-gradient(135deg, rgba(6, 28, 39, 0.94), rgba(7, 23, 34, 0.98)), rgba(7, 14, 26, 0.94);
  padding: 14px 18px;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 12px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 20px 50px rgba(0, 0, 0, 0.18);
}

.ui-nw-hero-summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.ui-nw-hero-summary-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 360px);
  gap: 16px;
  align-items: start;
  min-height: 0;
}

.ui-nw-hero-primary {
  display: grid;
  align-content: start;
  gap: 6px;
  min-width: 0;
}

.ui-nw-hero-side {
  display: grid;
  align-content: center;
  height: 100%;
  min-width: 0;
}

.ui-nw-hero-badge {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  border: 1px solid rgba(45, 212, 191, 0.22);
  background: rgba(45, 212, 191, 0.08);
  color: rgba(185, 255, 242, 0.9);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ui-nw-hero-context {
  display: grid;
  gap: 3px;
  justify-items: stretch;
  text-align: right;
  min-width: 220px;
}

.ui-nw-hero-context-label {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.52);
}

.ui-nw-hero-context-popover {
  min-width: 0;
  width: 100%;
}

.ui-nw-hero-context-trigger {
  min-height: 34px;
  width: 100%;
  justify-content: space-between;
  border-radius: 12px;
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.92);
}

.ui-nw-hero-title {
  font-size: 0.76rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.72);
}

.ui-nw-hero-value {
  font-size: clamp(1.55rem, 2.35vw, 2.45rem);
  line-height: 0.92;
  font-weight: 800;
  color: #f5fbff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ui-nw-hero-value-button {
  width: fit-content;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.ui-nw-hero-copy {
  margin: 0;
  max-width: 44ch;
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.95rem;
  line-height: 1.6;
}

.ui-nw-hero-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  align-content: start;
  min-height: 0;
}

.ui-nw-hero-stat {
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  min-height: 50px;
  padding: 6px 10px;
  display: grid;
  align-content: center;
  gap: 2px;
  background: rgba(255, 255, 255, 0.03);
}

.ui-nw-hero-stat-assets {
  border-color: rgba(92, 192, 255, 0.2);
  background: rgba(92, 192, 255, 0.08);
}

.ui-nw-hero-stat-liabilities {
  border-color: rgba(255, 99, 132, 0.18);
  background: rgba(255, 99, 132, 0.06);
}

.ui-nw-hero-stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.64);
}

.ui-nw-hero-stat-value {
  font-size: 0.92rem;
  line-height: 1.12;
  color: #fff;
}

.ui-nw-hero-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-self: auto;
}

.ui-nw-hero-metric {
  display: grid;
  gap: 2px;
  padding-top: 0;
  border-top: 0;
}

.ui-nw-hero-metric-label {
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-hero-metric-value {
  font-size: 0.84rem;
  line-height: 1.1;
  color: rgba(245, 251, 255, 0.96);
}

.ui-nw-category-workspace {
  margin-top: 0;
  padding: 18px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  display: grid;
  gap: 14px;
}

.ui-nw-category-workspace-empty {
  min-height: 100%;
  align-content: start;
  background:
    radial-gradient(circle at top right, rgba(76, 195, 255, 0.12), transparent 38%),
    rgba(255, 255, 255, 0.03);
}

.ui-nw-category-workspace-embedded {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-height: 0;
  overflow: hidden;
  align-content: start;
}

.ui-nw-category-workspace-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.ui-nw-category-workspace-heading {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.ui-nw-category-workspace-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.ui-nw-category-workspace-kicker {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-category-workspace-title {
  margin: 4px 0 0;
  font-size: 1.1rem;
}

.ui-nw-category-add-btn {
  width: 36px;
  min-width: 36px;
  height: 36px;
  border-radius: 12px;
  border-color: rgba(45, 212, 191, 0.26);
  background: rgba(45, 212, 191, 0.08);
  color: rgba(230, 255, 250, 0.96);
  flex-shrink: 0;
}

.ui-nw-category-workspace-copy {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.68);
}

.ui-nw-category-selection-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-category-workspace-list {
  display: grid;
  flex: 1;
  align-content: start;
  grid-auto-rows: max-content;
  gap: 10px;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.ui-nw-category-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  border: 1px solid rgba(76, 195, 255, 0.18);
  border-radius: 14px;
  background:
    radial-gradient(circle at top left, rgba(76, 195, 255, 0.12), transparent 42%),
    rgba(76, 195, 255, 0.07);
  padding: 12px;
}

.ui-nw-category-item-active {
  border-color: rgba(76, 195, 255, 0.68);
  background:
    linear-gradient(180deg, rgba(18, 53, 73, 0.88), rgba(13, 38, 54, 0.94)),
    radial-gradient(circle at top left, rgba(76, 195, 255, 0.2), transparent 42%);
  box-shadow:
    inset 0 0 0 1px rgba(76, 195, 255, 0.22),
    0 0 0 1px rgba(76, 195, 255, 0.08),
    0 12px 28px rgba(2, 15, 26, 0.28);
}

.ui-nw-category-item-main {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 4px;
}

.ui-nw-category-item-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
}

.ui-nw-category-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.62);
}

.ui-nw-category-item-actions {
  display: flex;
  align-items: center;
  align-self: center;
  gap: 6px;
}

.ui-nw-category-item-action {
  width: 30px;
  min-width: 30px;
  height: 30px;
  border-radius: 10px;
  padding: 0;
}

.ui-nw-category-item-action .icon {
  font-size: 13px;
  line-height: 1;
}

.ui-nw-category-item-active .ui-nw-category-selection-label {
  color: rgba(183, 230, 255, 0.92);
}

.ui-nw-category-item-head strong {
  min-width: 0;
}

.ui-nw-category-item-head span {
  white-space: nowrap;
  align-self: start;
}

.ui-nw-category-item-active .ui-nw-category-item-head strong,
.ui-nw-category-item-active .ui-nw-category-item-head span {
  color: #f6fbff;
}

.ui-nw-toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  gap: 0;
  flex-wrap: nowrap;
  padding: 0;
  border: 0;
  background: transparent;
  backdrop-filter: none;
}

.ui-nw-toolbar :deep(.nw-settings-root) {
  position: relative;
  z-index: 40;
  display: flex;
  align-items: flex-end;
}

.ui-nw-toolbar :deep(.nw-settings-icon-only) {
  width: 42px;
  min-width: 42px;
  height: 42px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.ui-nw-toolbar :deep(.nw-settings-btn-icon) {
  width: 18px;
  height: 18px;
}

.ui-nw-balance-kpi-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(12, minmax(0, 1fr));
}

.ui-nw-balance-kpi {
  grid-column: span 4;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
}

.ui-nw-balance-kpi-main {
  grid-column: span 12;
  text-align: center;
  background:
    linear-gradient(90deg, rgba(45, 212, 191, 0.12), rgba(56, 189, 248, 0.08)),
    rgba(7, 14, 26, 0.92);
  border-color: rgba(45, 212, 191, 0.3);
}

.ui-nw-kpi-inline-grid {
  margin-top: 12px;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(12, minmax(0, 1fr));
}

.ui-nw-kpi-inline-grid-compact {
  max-width: 720px;
  margin-inline: auto;
}

.ui-nw-kpi-inline {
  grid-column: span 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 8px 6px;
  min-height: 96px;
}

.ui-nw-kpi-inline-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.72);
}

.ui-nw-kpi-inline-value {
  margin-top: 3px;
  font-size: 20px;
  line-height: 1.2;
  font-weight: 700;
}

.ui-nw-kpi-inline-meta {
  margin-top: 3px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.75);
}

.ui-nw-kpi-label {
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--muted);
}

.ui-nw-kpi-value {
  margin-top: 6px;
  font-size: 26px;
  line-height: 1.15;
  font-weight: 700;
}

.ui-nw-kpi-sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
}

.ui-nw-timeline-panel {
  display: grid;
  gap: 1rem;
}

.ui-nw-timeline-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.ui-nw-timeline-title {
  margin: 0;
}

.ui-nw-timeline-copy {
  margin: 0;
  color: var(--muted);
}

.ui-nw-position-select {
  display: grid;
  gap: 6px;
  min-width: min(320px, 100%);
}

.ui-nw-position-select-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-position-select-input {
  min-width: 0;
}

.ui-nw-timeline-filters {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.ui-nw-timeline-filter-groups {
  display: grid;
  gap: 0.85rem;
}

.ui-nw-timeline-filter-group {
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  align-items: center;
}

.ui-nw-timeline-filter-group-label {
  min-width: 58px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.52);
}

.ui-nw-timeline-filter {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: rgba(255, 255, 255, 0.8);
  border-radius: 999px;
  padding: 0.45rem 0.8rem;
  font-size: 0.85rem;
}

.ui-nw-timeline-filter small {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-timeline-filter-active {
  border-color: rgba(45, 212, 191, 0.4);
  background: rgba(45, 212, 191, 0.14);
  color: #fff;
}

.ui-nw-timeline-filter-active small {
  color: rgba(255, 255, 255, 0.78);
}

.ui-nw-timeline-filter-liability.ui-nw-timeline-filter-active {
  border-color: rgba(255, 77, 115, 0.42);
  background: rgba(255, 77, 115, 0.12);
}

.ui-nw-timeline-main {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.ui-nw-timeline-sidebar {
  display: flex;
  min-width: 0;
  min-height: 0;
  align-self: stretch;
}

.ui-nw-timeline-body {
  display: grid;
  gap: 1rem;
}

.ui-nw-timeline-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.9rem;
}

.ui-nw-timeline-range-group {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.ui-nw-timeline-range-button,
.ui-nw-timeline-expand-button {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.03);
  color: rgba(255, 255, 255, 0.82);
  border-radius: 999px;
  padding: 0.45rem 0.8rem;
  font-size: 0.82rem;
  font-weight: 600;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    color 0.18s ease;
}

.ui-nw-timeline-range-button:hover,
.ui-nw-timeline-expand-button:hover {
  border-color: rgba(76, 195, 255, 0.28);
  background: rgba(76, 195, 255, 0.12);
  color: #fff;
}

.ui-nw-timeline-range-button-active {
  border-color: rgba(76, 195, 255, 0.42);
  background: rgba(76, 195, 255, 0.18);
  color: #fff;
}

.ui-nw-timeline-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.ui-nw-timeline-range-caption {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.6);
}

.ui-nw-timeline-chart-shell {
  position: relative;
  border-radius: 14px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
}

.ui-nw-timeline-loading-overlay {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 1;
  pointer-events: none;
}

.ui-nw-timeline-loading-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(76, 195, 255, 0.24);
  background: rgba(8, 18, 31, 0.82);
  color: rgba(240, 248, 255, 0.9);
  font-size: 0.76rem;
  letter-spacing: 0.02em;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.16);
}

.ui-nw-timeline-points {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: 0.75rem;
}

.ui-nw-timeline-point {
  display: grid;
  gap: 0.2rem;
  border-radius: 12px;
  padding: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
}

.ui-nw-timeline-point span {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-timeline-point strong {
  font-size: 1rem;
  color: #fff;
}

.ui-nw-timeline-modal {
  display: grid;
  gap: 1rem;
}

.ui-nw-timeline-modal-head {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  justify-content: space-between;
  gap: 0.9rem;
}

.ui-nw-timeline-modal-title {
  font-size: 0.92rem;
  font-weight: 600;
  color: #fff;
}

.ui-nw-timeline-modal-copy {
  margin-top: 0.2rem;
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.64);
}

.ui-nw-timeline-modal-value {
  font-size: 1.05rem;
  font-weight: 700;
  color: #fff;
}

.ui-nw-timeline-modal-ranges {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.ui-nw-timeline-slider-group {
  display: grid;
  gap: 0.45rem;
  padding: 0.9rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
}

.ui-nw-timeline-slider-group span {
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
}

.ui-nw-timeline-slider-group strong {
  font-size: 0.84rem;
  color: #fff;
}

.ui-nw-timeline-slider {
  width: 100%;
}

.ui-nw-drilldown-panel {
  display: grid;
  gap: 1rem;
}

.ui-nw-drilldown-copy {
  margin: 0;
  color: var(--muted);
}

.ui-nw-drilldown-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.ui-nw-position-column {
  display: grid;
  gap: 0.85rem;
}

.ui-nw-position-column-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.75rem;
}

.ui-nw-position-column-title {
  margin: 0;
  font-size: 0.95rem;
}

.ui-nw-position-column-meta {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.56);
}

.ui-nw-position-list {
  display: grid;
  gap: 0.65rem;
}

.ui-nw-position-button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  text-align: left;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  padding: 0.8rem 0.9rem;
  color: inherit;
}

.ui-nw-position-button-active {
  border-color: rgba(45, 212, 191, 0.42);
  background: rgba(45, 212, 191, 0.1);
}

.ui-nw-position-button-main {
  display: grid;
  gap: 0.18rem;
}

.ui-nw-position-button-main span {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-position-button-value {
  font-size: 0.92rem;
  font-weight: 700;
  white-space: nowrap;
}

.ui-nw-position-detail {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 1rem;
}

.ui-nw-position-detail-body {
  display: grid;
  gap: 1rem;
}

.ui-nw-position-detail-summary {
  border-radius: 14px;
  border: 1px solid rgba(76, 195, 255, 0.22);
  padding: 14px;
  background:
    radial-gradient(circle at top left, rgba(76, 195, 255, 0.14), transparent 38%),
    rgba(255, 255, 255, 0.02);
}

.ui-nw-position-detail-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-position-detail-title {
  margin-top: 0.3rem;
  font-size: 1.2rem;
  font-weight: 700;
}

.ui-nw-position-detail-meta {
  margin-top: 0.35rem;
  font-size: 0.92rem;
  color: rgba(255, 255, 255, 0.68);
}

.ui-nw-position-detail-chart-shell {
  border-radius: 14px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
}

.ui-nw-position-detail-chart {
  display: block;
  width: 100%;
  height: 180px;
}

.ui-nw-position-detail-grid {
  fill: none;
  stroke: rgba(255, 255, 255, 0.12);
  stroke-width: 0.4;
  vector-effect: non-scaling-stroke;
}

.ui-nw-position-detail-line {
  fill: none;
  stroke: #2dd4bf;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
}

.ui-nw-position-detail-points {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
  gap: 0.75rem;
}

.ui-nw-position-detail-point {
  display: grid;
  gap: 0.2rem;
  border-radius: 12px;
  padding: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
}

.ui-nw-position-detail-point span {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.58);
}

.ui-nw-position-detail-point strong {
  font-size: 1rem;
  color: #fff;
}

.ui-nw-position-activity {
  display: grid;
  gap: 0.85rem;
}

.ui-nw-position-activity-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.75rem;
}

.ui-nw-position-activity-title {
  margin: 0;
  font-size: 0.95rem;
}

.ui-nw-position-activity-list {
  display: grid;
  gap: 0.65rem;
}

.ui-nw-position-activity-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.8rem 0.9rem;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
}

.ui-nw-position-activity-row-valuation {
  border-color: rgba(76, 195, 255, 0.22);
  background: rgba(76, 195, 255, 0.08);
}

.ui-nw-position-activity-main {
  display: grid;
  gap: 0.2rem;
}

.ui-nw-position-activity-main strong {
  font-size: 0.9rem;
}

.ui-nw-position-activity-main span {
  font-size: 0.82rem;
  color: rgba(255, 255, 255, 0.62);
}

.ui-nw-position-activity-amount {
  font-size: 0.92rem;
  font-weight: 700;
  white-space: nowrap;
}

@media (max-width: 1024px) {
  .ui-nw-hero-main {
    grid-template-columns: 1fr;
  }

  .ui-nw-hero-summary-body {
    grid-template-columns: 1fr;
  }

  .ui-nw-hero-summary {
    height: auto;
    padding: 18px;
  }

  .ui-nw-hero-value {
    white-space: normal;
  }

  .ui-nw-hero-side {
    grid-template-rows: auto auto;
  }

  .ui-nw-hero-donut-frame {
    height: 200px;
  }

  .ui-nw-hero-timeline {
    margin-top: 8px;
  }

  .ui-nw-timeline-layout {
    grid-template-columns: 1fr;
  }

  .ui-nw-category-workspace-embedded {
    position: static;
    height: auto;
    overflow: visible;
  }

  .ui-nw-balance-kpi-main {
    grid-column: span 12;
    grid-row: auto;
  }

  .ui-nw-kpi-inline {
    grid-column: span 4;
  }

  .ui-nw-drilldown-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .ui-nw-topbar {
    align-items: stretch;
  }

  .ui-nw-topbar-actions,
  .ui-nw-toolbar {
    width: 100%;
    max-width: none;
  }

  .ui-nw-toolbar {
    justify-content: space-between;
  }

  .ui-nw-balance-kpi,
  .ui-nw-balance-kpi-main {
    grid-column: span 12;
    grid-row: auto;
  }

  .ui-nw-kpi-inline {
    grid-column: span 12;
  }

  .ui-nw-kpi-value {
    font-size: 22px;
  }

  .ui-nw-timeline-filter-group {
    align-items: flex-start;
  }

  .ui-nw-timeline-filter-group-label {
    min-width: auto;
    width: 100%;
  }

  .ui-nw-timeline-toolbar-actions {
    width: 100%;
    justify-content: space-between;
  }

  .ui-nw-timeline-modal-ranges {
    grid-template-columns: 1fr;
  }

  .ui-nw-category-item {
    grid-template-columns: 1fr;
  }

  .ui-nw-category-item-head {
    flex-direction: column;
    gap: 4px;
  }

  .ui-nw-hero-stats {
    grid-template-columns: 1fr;
  }

  .ui-nw-hero-summary-head,
  .ui-nw-hero-context {
    text-align: left;
  }

  .ui-nw-hero-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ui-nw-hero-value {
    font-size: 1.8rem;
    white-space: normal;
  }

  .ui-nw-category-workspace-list {
    max-height: none;
  }
}
</style>
