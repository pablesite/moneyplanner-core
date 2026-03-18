import { computed, ref, watch, type ComputedRef, type Ref } from 'vue';
import { coreNetWorthApi } from '@/domains/net-worth';
import type {
  DisplayedTimelinePoint,
  PositionRow,
  PositionTimelinePoint,
} from '@/domains/net-worth/useNetWorthPageMetrics';

type TimelinePoint = {
  date: string;
  label: string;
  netWorth: number;
  assets: number;
  liabilities: number;
};

type TimelineChartPoint = {
  date: string;
  shortLabel: string;
  fullLabel: string;
  value: number;
};

type CachedTimelineRows = {
  positionType: 'asset' | 'liability';
  rows: PositionTimelinePoint[];
};

type TimelinePreset = '1m' | '3m' | '6m' | '1a' | 'all';

function formatMonthYearLabel(date: string): string {
  return new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit' }).format(
    new Date(date),
  );
}

export function useNetWorthTimeline(params: {
  ownershipFilter: Ref<'all' | number>;
  selectedPosition: ComputedRef<PositionRow | null>;
  selectedPositionType: Ref<'asset' | 'liability' | null>;
  selectedPositionId: Ref<number | null>;
  selectedTimelineCategory: Ref<string | null>;
  selectedTimelineCategoryType: Ref<'asset' | 'liability'>;
  selectedTimelinePreset: Ref<TimelinePreset>;
  customTimelineWindow: Ref<{ start: number; end: number } | null>;
  timelineRows: ComputedRef<TimelinePoint[]>;
  availablePositionRows: ComputedRef<PositionRow[]>;
  allAssetPositionRows: ComputedRef<PositionRow[]>;
  allLiabilityPositionRows: ComputedRef<PositionRow[]>;
  positionTimelineRows: ComputedRef<PositionTimelinePoint[]>;
  storeTimelineLoading: Ref<boolean>;
  storePositionTimelineLoading: Ref<boolean>;
  setStoreError: (message: string) => void;
  resetPositionSelection: () => void;
  getTimelineMetricValue: (row: TimelinePoint) => number;
}) {
  const ownershipTimelineCache = ref<Record<string, CachedTimelineRows>>({});
  const ownershipTimelineLoading = ref(false);
  const cachedDisplayedTimelineRows = ref<DisplayedTimelinePoint[]>([]);
  const cachedDisplayedTimelineSeriesColor = ref('#4cc3ff');

  function positionCacheKey(type: 'asset' | 'liability', id: number): string {
    return `${type}:${id}`;
  }

  const ownershipScopedRows = computed<PositionRow[]>(() => {
    if (params.ownershipFilter.value === 'all' || params.selectedPosition.value) return [];
    if (params.selectedTimelineCategory.value) return params.availablePositionRows.value;
    return [...params.allAssetPositionRows.value, ...params.allLiabilityPositionRows.value];
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
              label: formatMonthYearLabel(timelineRow.date),
              value: Number(timelineRow.value_base || timelineRow.value || 0),
            })),
          };
          return cache;
        },
        { ...ownershipTimelineCache.value },
      );
    } catch (error: unknown) {
      params.setStoreError(
        error instanceof Error ? error.message : 'No se pudo cargar la timeline filtrada',
      );
    } finally {
      ownershipTimelineLoading.value = false;
    }
  }

  watch(
    () => ownershipScopedRows.value.map((row) => positionCacheKey(row.type, row.id)).join('|'),
    async () => {
      if (params.ownershipFilter.value === 'all' || params.selectedPosition.value) return;
      await ensureOwnershipTimelineCache(ownershipScopedRows.value);
    },
    { immediate: true },
  );

  watch(params.availablePositionRows, (rows) => {
    if (!params.selectedPositionId.value || !params.selectedPositionType.value) return;
    if (
      !rows.some(
        (row) =>
          row.id === params.selectedPositionId.value &&
          row.type === params.selectedPositionType.value,
      )
    ) {
      params.resetPositionSelection();
    }
  });

  const ownershipTimelineRows = computed<TimelinePoint[]>(() => {
    if (params.ownershipFilter.value === 'all') return [];

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
    params.ownershipFilter.value === 'all'
      ? params.timelineRows.value
      : ownershipTimelineRows.value,
  );

  const displayedTimelineRows = computed<DisplayedTimelinePoint[]>(() => {
    if (params.selectedPosition.value) {
      return params.positionTimelineRows.value.map((row) => ({
        date: row.date,
        label: row.label,
        value: row.value,
      }));
    }
    return activeTimelineRows.value.map((row) => ({
      date: row.date,
      label: row.label,
      value: params.getTimelineMetricValue(row),
    }));
  });

  const displayedTimelineLoading = computed(() =>
    params.selectedPosition.value
      ? params.storePositionTimelineLoading.value
      : params.ownershipFilter.value === 'all'
        ? params.storeTimelineLoading.value
        : ownershipTimelineLoading.value,
  );

  const currentTimelineSeriesColor = computed(() => {
    if (params.selectedPosition.value?.type === 'liability') return '#ff4d73';
    if (params.selectedTimelineCategoryType.value === 'liability') return '#ff4d73';
    if (params.selectedPosition.value?.type === 'asset') return '#2dd4bf';
    return '#4cc3ff';
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

  const visibleTimelineRows = computed<DisplayedTimelinePoint[]>(() => {
    if (displayedTimelineLoading.value && cachedDisplayedTimelineRows.value.length > 0) {
      return cachedDisplayedTimelineRows.value;
    }
    return displayedTimelineRows.value.length > 0
      ? displayedTimelineRows.value
      : cachedDisplayedTimelineRows.value;
  });

  const timelinePresetPointCount: Record<TimelinePreset, number> = {
    '1m': 1,
    '3m': 3,
    '6m': 6,
    '1a': 12,
    all: Number.POSITIVE_INFINITY,
  };

  const timelineDefaultWindow = computed(() => {
    const end = Math.max(0, visibleTimelineRows.value.length - 1);
    const count = timelinePresetPointCount[params.selectedTimelinePreset.value];
    if (!Number.isFinite(count)) return { start: 0, end };
    return { start: Math.max(0, end - count + 1), end };
  });

  const timelineWindow = computed(() => {
    const length = visibleTimelineRows.value.length;
    if (length === 0) return { start: 0, end: 0 };
    const source = params.customTimelineWindow.value ?? timelineDefaultWindow.value;
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

  const displayedTimelineSummaryLabel = computed(() => {
    if (params.selectedPosition.value) {
      return params.selectedPosition.value.type === 'liability'
        ? 'Ultimo valor del pasivo'
        : 'Ultimo valor del activo';
    }
    if (!params.selectedTimelineCategory.value) return 'Ultimo patrimonio neto';
    return 'Ultimo valor de la categoria';
  });

  const displayedTimelineSeriesColor = computed(() => {
    if (displayedTimelineLoading.value && cachedDisplayedTimelineRows.value.length > 0) {
      return cachedDisplayedTimelineSeriesColor.value;
    }
    return currentTimelineSeriesColor.value;
  });

  return {
    displayedTimelineLoading,
    visibleTimelineRows,
    timelineWindow,
    timelineChartRows,
    timelineChartPoints,
    timelineRangeCaption,
    latestTimelineChartPoint,
    timelineSummaryLabel: displayedTimelineSummaryLabel,
    displayedTimelineSeriesColor,
  };
}
