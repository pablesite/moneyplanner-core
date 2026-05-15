import { computed, ref, watch } from 'vue';
import { coreAccountingApi } from '@/domains/accounting/api';
import { toApiErrorMessage } from '@/lib/errors';
import type { LedgerDailyBalanceSeriesRow } from '@/domains/accounting/models';

type DailyBalanceOwnershipFilter = 'all' | number | null;
type DailyTimelinePreset = '1m' | '3m' | '6m' | '1a' | '5a' | 'all';

function toNumber(raw: string): number {
  const parsed = Number(raw.replace(',', '.').trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

function toIsoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export function useAccountingDailyTimeline() {
  const today = new Date();
  const dailyBalanceDateTo = ref(toIsoDate(today));
  const dailyBalanceDateFrom = ref('');
  const dailyBalanceSeriesRows = ref<LedgerDailyBalanceSeriesRow[]>([]);
  const dailyBalanceSeriesLoading = ref(false);
  const dailyBalanceSeriesError = ref<string | null>(null);
  const dailyBalanceSeriesUnit = ref('EUR');
  const dailyBalanceOwnershipFilter = ref<DailyBalanceOwnershipFilter>('all');
  const dailyTimelinePresetOptions = ['1m', '3m', '6m', '1a', '5a', 'all'] as const;
  const selectedDailyTimelinePreset = ref<DailyTimelinePreset>('1a');
  const dailyTimelineCustomWindow = ref<{ start: number; end: number } | null>(null);
  const dailyTimelineExpanded = ref(false);

  const dailyTimelinePresetPointCount: Record<DailyTimelinePreset, number> = {
    '1m': 31,
    '3m': 92,
    '6m': 183,
    '1a': 365,
    '5a': 1825,
    all: Number.POSITIVE_INFINITY,
  };

  const dailyBalanceTimelineRows = computed(() => {
    const shortFormatter = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: 'short' });
    return dailyBalanceSeriesRows.value.map((row) => {
      const date = new Date(`${row.date}T00:00:00`);
      return {
        date: row.date,
        label: shortFormatter.format(date),
        value: toNumber(row.net_balance),
      };
    });
  });

  const dailyTimelineDefaultWindow = computed(() => {
    const end = Math.max(0, dailyBalanceTimelineRows.value.length - 1);
    const count = dailyTimelinePresetPointCount[selectedDailyTimelinePreset.value];
    if (!Number.isFinite(count)) return { start: 0, end };
    return { start: Math.max(0, end - count + 1), end };
  });

  const dailyTimelineWindow = computed(() => {
    const length = dailyBalanceTimelineRows.value.length;
    if (length === 0) return { start: 0, end: 0 };
    const source = dailyTimelineCustomWindow.value ?? dailyTimelineDefaultWindow.value;
    const start = Math.min(Math.max(0, source.start), length - 1);
    const end = Math.min(Math.max(start, source.end), length - 1);
    return { start, end };
  });

  const dailyBalanceSeriesChartRows = computed(() =>
    dailyBalanceTimelineRows.value.slice(
      dailyTimelineWindow.value.start,
      dailyTimelineWindow.value.end + 1,
    ),
  );

  const dailyBalanceSeriesMonthlyRows = computed(() => {
    const byMonth = new Map<string, { date: string; label: string; value: number }>();
    const monthFormatter = new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit' });
    for (const row of dailyBalanceSeriesChartRows.value) {
      const monthKey = row.date.slice(0, 7);
      const monthDate = `${monthKey}-01`;
      byMonth.set(monthKey, {
        date: monthDate,
        label: monthFormatter.format(new Date(`${monthDate}T00:00:00`)),
        value: row.value,
      });
    }
    return Array.from(byMonth.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([, value]) => value);
  });

  const dailyBalanceSeriesChartPoints = computed(() => {
    const shortFormatter = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: 'short' });
    const fullFormatter = new Intl.DateTimeFormat('es-ES', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
    return dailyBalanceSeriesChartRows.value.map((row, index, rows) => {
      const date = new Date(`${row.date}T00:00:00`);
      const isBoundary = index === 0 || index === rows.length - 1;
      return {
        date: row.date,
        shortLabel: isBoundary ? fullFormatter.format(date) : shortFormatter.format(date),
        fullLabel: fullFormatter.format(date),
        value: row.value,
        isCurrent: row.date === dailyBalanceDateTo.value,
      };
    });
  });

  const dailyBalanceSeriesRangeLabel = computed(() => {
    if (!dailyBalanceSeriesChartPoints.value.length) return 'Sin datos';
    const first = dailyBalanceSeriesChartPoints.value[0];
    const last =
      dailyBalanceSeriesChartPoints.value[dailyBalanceSeriesChartPoints.value.length - 1];
    if (!first || !last) return 'Sin datos';
    return `${first.fullLabel} - ${last.fullLabel}`;
  });

  const dailyBalanceLatestChartPoint = computed(
    () =>
      dailyBalanceSeriesChartPoints.value[dailyBalanceSeriesChartPoints.value.length - 1] ?? null,
  );

  function setDailyTimelinePreset(preset: DailyTimelinePreset): void {
    selectedDailyTimelinePreset.value = preset;
    dailyTimelineCustomWindow.value = null;
  }

  function updateDailyTimelineWindowStart(rawValue: string): void {
    const parsed = Number(rawValue);
    const currentEnd = dailyTimelineWindow.value.end;
    dailyTimelineCustomWindow.value = {
      start: Number.isFinite(parsed)
        ? Math.min(parsed, currentEnd)
        : dailyTimelineWindow.value.start,
      end: currentEnd,
    };
  }

  function updateDailyTimelineWindowEnd(rawValue: string): void {
    const parsed = Number(rawValue);
    const currentStart = dailyTimelineWindow.value.start;
    dailyTimelineCustomWindow.value = {
      start: currentStart,
      end: Number.isFinite(parsed) ? Math.max(parsed, currentStart) : dailyTimelineWindow.value.end,
    };
  }

  async function reloadDailyBalanceSeries(): Promise<void> {
    dailyBalanceSeriesLoading.value = true;
    dailyBalanceSeriesError.value = null;
    try {
      const ownershipIdParam =
        dailyBalanceOwnershipFilter.value === 'all'
          ? undefined
          : dailyBalanceOwnershipFilter.value === null
            ? ('null' as const)
            : dailyBalanceOwnershipFilter.value;
      const response = await coreAccountingApi.getDailyBalanceSeries({
        date_from: dailyBalanceDateFrom.value,
        date_to: dailyBalanceDateTo.value,
        status: 'posted',
        ownership_id: ownershipIdParam,
      });
      dailyBalanceSeriesUnit.value = String(response.data.base_currency || 'EUR')
        .trim()
        .toUpperCase();
      dailyBalanceSeriesRows.value = response.data.rows ?? [];
    } catch (error: unknown) {
      dailyBalanceSeriesRows.value = [];
      dailyBalanceSeriesError.value = toApiErrorMessage(error);
    } finally {
      dailyBalanceSeriesLoading.value = false;
    }
  }

  watch(dailyBalanceOwnershipFilter, () => {
    void reloadDailyBalanceSeries();
  });

  return {
    dailyBalanceDateFrom,
    dailyBalanceDateTo,
    dailyBalanceOwnershipFilter,
    dailyBalanceSeriesRows,
    dailyBalanceSeriesLoading,
    dailyBalanceSeriesError,
    dailyBalanceSeriesUnit,
    dailyBalanceSeriesChartPoints,
    dailyBalanceSeriesChartRows,
    dailyBalanceSeriesMonthlyRows,
    dailyBalanceSeriesRangeLabel,
    dailyBalanceLatestChartPoint,
    dailyTimelinePresetOptions,
    selectedDailyTimelinePreset,
    dailyTimelineCustomWindow,
    dailyTimelineWindow,
    dailyTimelineExpanded,
    setDailyTimelinePreset,
    updateDailyTimelineWindowStart,
    updateDailyTimelineWindowEnd,
    reloadDailyBalanceSeries,
  };
}
