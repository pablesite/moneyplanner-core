import { computed, nextTick, ref } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Asset, Ownership, PositionTimelineRow, Summary } from '@/domains/net-worth/models';
import { useNetWorthOwnership } from '@/domains/net-worth/useNetWorthOwnership';
import { useNetWorthPageMetrics } from '@/domains/net-worth/useNetWorthPageMetrics';
import { useNetWorthTimeline } from '@/domains/net-worth/useNetWorthTimeline';

const mocks = vi.hoisted(() => ({
  coreNetWorthApi: {
    getAssetTimeline: vi.fn(),
    getLiabilityTimeline: vi.fn(),
  },
}));

vi.mock('@/domains/net-worth', () => ({
  coreNetWorthApi: mocks.coreNetWorthApi,
}));

function makeSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    base_currency: 'EUR',
    total_assets: '1500',
    total_liabilities: '400',
    net_worth: '1100',
    assets_by_category: {},
    assets_by_subcategory: {},
    liabilities_by_category: {},
    inflation_region: 'ES',
    inflation_base_period: '2025-01',
    inflation_available: true,
    inflation_status: 'available',
    total_assets_real: '1400',
    total_liabilities_real: '350',
    net_worth_real: '1050',
    assets_by_category_real: {},
    liabilities_by_category_real: {},
    ...overrides,
  };
}

function makeAsset(overrides: Partial<Asset> = {}): Asset {
  return {
    id: 1,
    name: 'Cuenta',
    category: 'cash',
    subcategory: 'bank',
    tracking_mode: 'manual',
    accounting_account_id: null,
    currency: 'EUR',
    amount: '1000',
    is_active: true,
    notes: '',
    ...overrides,
  };
}

function makeOwnerships(): Ownership[] {
  return [
    {
      id: 1,
      kind: 'individual',
      member: { id: 7, name: 'Ana', role: 'adult' },
      splits: [],
      notes: '',
    },
    {
      id: 2,
      kind: 'shared',
      member: null,
      splits: [
        { member: { id: 7, name: 'Ana', role: 'adult' }, percent: '75' },
        { member: { id: 9, name: 'Luis', role: 'adult' }, percent: '25' },
      ],
      notes: '',
    },
  ];
}

describe('net-worth page refactor composables', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.coreNetWorthApi.getAssetTimeline.mockResolvedValue({
      data: {
        rows: [
          { date: '2025-01-01', value: '100', value_base: '100' },
          { date: '2025-02-01', value: '120', value_base: '120' },
        ],
      },
    });
    mocks.coreNetWorthApi.getLiabilityTimeline.mockResolvedValue({
      data: {
        rows: [
          { date: '2025-01-01', value: '40', value_base: '40' },
          { date: '2025-02-01', value: '30', value_base: '30' },
        ],
      },
    });
  });

  it('computes ownership options, fractions and resets filter in real mode', async () => {
    const valueMode = ref<'nominal' | 'real'>('nominal');
    const ownerships = ref(makeOwnerships());
    const ownership = useNetWorthOwnership({ ownerships, valueMode });

    expect(ownership.ownershipOptions.value.map((row) => row.label)).toEqual(['Ana', 'Luis']);
    expect(ownership.allocationFractionForNetWorthOwner(2, 7)).toBe(0.75);
    expect(ownership.matchesOwnershipFilter(1)).toBe(true);
    expect(ownership.ownershipBadge(2)).toBe('Ana + Luis');

    ownership.setOwnershipFilter(7);
    ownership.setValueMode('real');
    await nextTick();

    expect(ownership.ownershipFilter.value).toBe('all');
    expect(ownership.ownershipFilterDisabled.value).toBe(true);
  });

  it('derives page metrics and workspace rows from ownership-filtered data', () => {
    const ownershipFilter = ref<'all' | number>(7);
    const selectedTimelineCategory = ref<string | null>('cash');
    const selectedTimelineCategoryType = ref<'asset' | 'liability'>('asset');
    const selectedPositionType = ref<'asset' | 'liability' | null>(null);
    const selectedPositionId = ref<number | null>(null);

    const metrics = useNetWorthPageMetrics({
      assets: ref([
        makeAsset({ id: 1, name: 'Cuenta comun', ownership_ref: 2, amount_base: '800' }),
        makeAsset({ id: 2, name: 'Cuenta Ana', ownership_ref: 1, amount_base: '200' }),
      ]),
      liabilities: ref([
        makeAsset({
          id: 3,
          name: 'Hipoteca',
          category: 'mortgage',
          subcategory: '',
          ownership_ref: 2,
          amount_base: '400',
          financed_asset_ref: 1,
        }),
      ]),
      baseCurrency: ref('EUR'),
      summary: ref(makeSummary()),
      positionTimelineRowsSource: ref<PositionTimelineRow[]>([
        { date: '2025-01-01', value: '100', value_base: '100' },
      ]),
      assetCategories: [{ value: 'cash', label: 'Liquidez' }],
      liabilityCategories: [{ value: 'mortgage', label: 'Hipoteca' }],
      byCategoryKeys: ref(['cash', 'mortgage']),
      byCategoryAssets: ref([1000, 0]),
      byCategoryLiabilities: ref([0, 400]),
      summaryAssets: ref('1000'),
      summaryLiabilities: ref('400'),
      summaryNetWorth: ref('600'),
      summaryAssetBackedLiabilities: ref('400'),
      summaryUnbackedLiabilities: ref('0'),
      ownershipFilter,
      selectedTimelineCategory,
      selectedTimelineCategoryType,
      selectedPositionType,
      selectedPositionId,
      matchesOwnershipFilter: (ownershipRef) => ownershipRef === 1 || ownershipRef === 2,
      allocationFractionForNetWorthOwner: (ownershipRef, selectedOwner) => {
        if (selectedOwner === 'all') return 1;
        if (ownershipRef === 1 && selectedOwner === 7) return 1;
        if (ownershipRef === 2 && selectedOwner === 7) return 0.75;
        return 0;
      },
    });

    expect(metrics.assetsValue.value).toBe(800);
    expect(metrics.liabilitiesValue.value).toBe(300);
    expect(metrics.analysis.value.netWorth).toBe(500);
    expect(metrics.selectedCategoryLabel.value).toBe('Liquidez');
    expect(metrics.availablePositionRows.value).toHaveLength(2);
    expect(metrics.categoryWorkspaceRows.value).toHaveLength(2);
    expect(metrics.activeAssets.value).toEqual([
      { id: 1, name: 'Cuenta comun', category: 'cash' },
      { id: 2, name: 'Cuenta Ana', category: 'cash' },
    ]);
  });

  it('builds ownership-scoped timeline rows and chart metadata', async () => {
    const ownershipFilter = ref<'all' | number>(7);
    const selectedPositionType = ref<'asset' | 'liability' | null>(null);
    const selectedPositionId = ref<number | null>(null);
    const selectedTimelineCategory = ref<string | null>(null);
    const selectedTimelineCategoryType = ref<'asset' | 'liability'>('asset');
    const selectedTimelinePreset = ref<'1m' | '3m' | '6m' | '1a' | 'all'>('all');
    const customTimelineWindow = ref<{ start: number; end: number } | null>(null);
    const resetPositionSelection = vi.fn();
    const setStoreError = vi.fn();

    const timeline = useNetWorthTimeline({
      ownershipFilter,
      selectedPosition: computed(() => null),
      selectedPositionType,
      selectedPositionId,
      selectedTimelineCategory,
      selectedTimelineCategoryType,
      selectedTimelinePreset,
      customTimelineWindow,
      timelineRows: computed(() => [
        { date: '2025-01-01', label: 'ene 25', netWorth: 60, assets: 100, liabilities: 40 },
      ]),
      availablePositionRows: computed(() => []),
      allAssetPositionRows: computed(() => [
        {
          id: 1,
          type: 'asset' as const,
          category: 'cash',
          name: 'Cuenta',
          subtitle: 'cash / bank',
          value: 80,
          currency: 'EUR',
          ownershipFraction: 0.75,
        },
      ]),
      allLiabilityPositionRows: computed(() => [
        {
          id: 3,
          type: 'liability' as const,
          category: 'mortgage',
          name: 'Hipoteca',
          subtitle: 'mortgage',
          value: 30,
          currency: 'EUR',
          ownershipFraction: 0.75,
        },
      ]),
      positionTimelineRows: computed(() => []),
      storeTimelineLoading: ref(false),
      storePositionTimelineLoading: ref(false),
      setStoreError,
      resetPositionSelection,
      getTimelineMetricValue: (row) => row.netWorth,
    });

    await nextTick();
    await flushPromises();
    await nextTick();

    expect(mocks.coreNetWorthApi.getAssetTimeline).toHaveBeenCalledWith(1);
    expect(mocks.coreNetWorthApi.getLiabilityTimeline).toHaveBeenCalledWith(3);
    expect(timeline.visibleTimelineRows.value.map((row) => row.value)).toEqual([45, 67.5]);
    expect(
      timeline.timelineChartPoints.value[timeline.timelineChartPoints.value.length - 1]?.fullLabel,
    ).toBe('febrero de 2025');
    expect(timeline.timelineRangeCaption.value).toBe('enero de 2025 - febrero de 2025');
    expect(timeline.timelineSummaryLabel.value).toBe('Último patrimonio neto');
    expect(timeline.displayedTimelineSeriesColor.value).toBe('#4cc3ff');
    expect(setStoreError).not.toHaveBeenCalled();
    expect(resetPositionSelection).not.toHaveBeenCalled();
  });
});
