<script setup lang="ts">
import { computed, useSlots } from 'vue';
import { Doughnut } from 'vue-chartjs';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
  type Plugin,
} from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

const CATEGORY_COLORS: string[] = [
  'rgba(56, 189, 248, 0.92)',
  'rgba(45, 212, 191, 0.92)',
  'rgba(251, 146, 60, 0.92)',
  'rgba(167, 139, 250, 0.92)',
  'rgba(74, 222, 128, 0.92)',
];
const LIABILITY_SLICE_COLOR = 'rgba(244, 63, 94, 0.88)';

type Props = {
  totalAssets: string | number | null | undefined;
  totalLiabilities: string | number | null | undefined;
  netWorth: string | number | null | undefined;
  unit: string;
  assetBackedLiabilities?: string | number | null | undefined;
  unbackedLiabilities?: string | number | null | undefined;
  categoryKeys?: string[] | null | undefined;
  categoryLabels?: string[] | null | undefined;
  categoryAssets?: number[] | null | undefined;
  categoryLiabilities?: number[] | null | undefined;
  categoryAssetCounts?: number[] | null | undefined;
  categoryLiabilityCounts?: number[] | null | undefined;
  selectedCategoryKey?: string | null | undefined;
  selectedCategoryType?: 'asset' | 'liability' | null | undefined;
  showChart?: boolean | undefined;
  showComposition?: boolean | undefined;
};

const props = withDefaults(defineProps<Props>(), {
  showChart: true,
  showComposition: true,
});
const slots = useSlots();
const emit = defineEmits<{
  (e: 'select-category', payload: { key: string; type: 'asset' | 'liability' }): void;
  (e: 'add-type', payload: { type: 'asset' | 'liability' }): void;
}>();

const hasChart = computed(() => props.showChart !== false);
const hasSide = computed(() => props.showComposition !== false || !!slots['side-top']);
const displayUnit = computed(() => (props.unit === 'EUR' ? '€' : props.unit));

function normalizeNumberInput(raw: unknown) {
  return String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
}

function toNumber(v: unknown) {
  const n = Number(normalizeNumberInput(v));
  return Number.isFinite(n) ? n : 0;
}

function formatMoney(n: number, decimals = 2) {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatPercent(n: number, decimals = 0) {
  return new Intl.NumberFormat('es-ES', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

const assets = computed(() => Math.max(0, toNumber(props.totalAssets)));
const net = computed(() => toNumber(props.netWorth));

const backedRaw = computed(() => Math.max(0, toNumber(props.assetBackedLiabilities)));
const unbackedRaw = computed(() => Math.max(0, toNumber(props.unbackedLiabilities)));

const backedSlice = computed(() => Math.min(backedRaw.value, assets.value));

const unbackedSlice = computed(() => {
  const room = Math.max(assets.value - backedSlice.value, 0);
  return Math.min(unbackedRaw.value, room);
});

const equitySlice = computed(() =>
  Math.max(assets.value - backedSlice.value - unbackedSlice.value, 0),
);

type CategoryShare = { key: string; label: string; value: number; share: number; count: number };

function buildCategoryShares(
  keys: string[] | null | undefined,
  labels: string[] | null | undefined,
  values: number[] | null | undefined,
  counts: number[] | null | undefined,
) {
  if (!keys?.length || !labels?.length || !values?.length) return [] as CategoryShare[];
  const items = labels.map((label, index) => {
    const value = Math.max(0, values[index] ?? 0);
    return {
      key: keys[index] ?? label,
      label,
      value,
      share: 0,
      count: Math.max(0, counts?.[index] ?? 0),
    };
  });
  const positiveTotal = items.reduce((sum, item) => sum + item.value, 0);
  return items
    .map((item) => ({
      ...item,
      share: positiveTotal > 0 ? item.value / positiveTotal : 0,
    }))
    .filter((item) => item.value >= 0 && (item.value > 0 || item.count > 0))
    .sort((a, b) => b.value - a.value)
    .slice(0, 5);
}

const assetComposition = computed(() =>
  buildCategoryShares(
    props.categoryKeys,
    props.categoryLabels,
    props.categoryAssets,
    props.categoryAssetCounts,
  ),
);
const liabilityComposition = computed(() =>
  buildCategoryShares(
    props.categoryKeys,
    props.categoryLabels,
    props.categoryLiabilities,
    props.categoryLiabilityCounts,
  ),
);

type ChartSlice = { label: string; value: number; color: string };

const chartSlices = computed<ChartSlice[]>(() => {
  const categories = assetComposition.value;
  if (categories.length > 0) {
    const slices: ChartSlice[] = categories.slice(0, 5).map((cat, i) => ({
      label: cat.label,
      value: cat.value,
      color: CATEGORY_COLORS[i % CATEGORY_COLORS.length] ?? CATEGORY_COLORS[0] ?? '',
    }));
    const liab = toNumber(props.totalLiabilities);
    if (liab > 0) {
      slices.push({ label: 'Pasivos', value: liab, color: LIABILITY_SLICE_COLOR });
    }
    return slices;
  }
  // Fallback: equity / backed / unbacked
  return [
    { label: 'Capital propio (neto)', value: equitySlice.value, color: 'rgba(92, 192, 255, 0.9)' },
    { label: 'Activos con deuda', value: backedSlice.value, color: 'rgba(255, 99, 132, 0.85)' },
    { label: 'Deuda sin activo', value: unbackedSlice.value, color: 'rgba(255, 140, 110, 0.85)' },
  ].filter((s) => s.value > 0);
});

const data = computed<ChartData<'doughnut'>>(() => ({
  labels: chartSlices.value.map((s) => s.label),
  datasets: [
    {
      data: chartSlices.value.map((s) => s.value),
      backgroundColor: chartSlices.value.map((s) => s.color),
      borderColor: 'rgba(0,0,0,0)',
      borderWidth: 0,
      hoverOffset: 6,
      spacing: 2,
      cutout: '72%',
    },
  ],
}));

const options = computed<ChartOptions<'doughnut'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => {
          const label = ctx.label ?? '';
          const v = typeof ctx.raw === 'number' ? ctx.raw : 0;
          const pct = assets.value > 0 ? ` (${formatPercent(v / assets.value, 0)})` : '';
          return `${label}: ${formatMoney(v, 2)} ${displayUnit.value}${pct}`;
        },
      },
    },
  },
}));

const centerTextPlugin = computed<Plugin<'doughnut'>>(() => ({
  id: 'centerText',
  afterDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    const cx = (chartArea.left + chartArea.right) / 2;
    const cy = (chartArea.top + chartArea.bottom) / 2;

    const netStr = formatMoney(net.value, 2);

    const isNeg = net.value < 0;
    const netColor = isNeg ? 'rgba(255, 120, 140, 0.95)' : 'rgba(140, 240, 180, 0.95)';

    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ctx.font = '700 16px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = netColor;
    ctx.fillText(netStr, cx, cy - 10);

    ctx.font = '12px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.70)';
    ctx.fillText('Patrimonio neto', cx, cy + 8);

    ctx.font = '12px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.60)';
    ctx.fillText(displayUnit.value, cx, cy + 26);

    ctx.restore();
  },
}));
</script>

<template>
  <div
    class="nw-donut-wrap"
    :class="{
      'nw-donut-wrap-chart-only': hasChart && !hasSide,
      'nw-donut-wrap-side-only': !hasChart && hasSide,
    }"
  >
    <div v-if="hasChart" class="nw-donut-chart">
      <Doughnut :data="data" :options="options" :plugins="[centerTextPlugin]" />
    </div>
    <div v-if="hasChart && chartSlices.length" class="nw-donut-legend">
      <span v-for="slice in chartSlices" :key="slice.label" class="nw-donut-legend-item">
        <span class="nw-donut-legend-dot" :style="{ background: slice.color }" />
        <span class="nw-donut-legend-label">{{ slice.label }}</span>
      </span>
    </div>

    <div v-if="hasSide" class="nw-donut-side">
      <div v-if="$slots['side-top']" class="nw-donut-side-top">
        <slot name="side-top" />
      </div>

      <div v-if="props.showComposition !== false" class="nw-donut-composition">
        <div class="nw-donut-comp-block">
          <div class="nw-donut-comp-block-head">
            <div class="nw-donut-comp-title">Composicion de activos</div>
            <button
              class="nw-donut-comp-action"
              type="button"
              aria-label="Nuevo activo"
              @click="emit('add-type', { type: 'asset' })"
            >
              +
            </button>
          </div>
          <div v-if="assetComposition.length" class="nw-donut-comp-list">
            <div
              v-for="row in assetComposition"
              :key="`asset-${row.key}`"
              class="nw-donut-comp-row"
              :class="{
                'nw-donut-comp-row-active':
                  props.selectedCategoryType === 'asset' && props.selectedCategoryKey === row.key,
              }"
            >
              <button
                class="nw-donut-comp-main"
                type="button"
                @click="emit('select-category', { key: row.key, type: 'asset' })"
              >
                <div class="nw-donut-comp-head">
                  <span>{{ row.label }}</span>
                  <strong>{{ formatPercent(row.share, 0) }}</strong>
                </div>
                <div class="nw-donut-comp-meta">
                  <span>{{ formatMoney(row.value, 2) }} {{ displayUnit }}</span>
                  <span>{{ row.count }} posiciones</span>
                </div>
                <div class="nw-donut-comp-bar">
                  <span
                    class="nw-donut-comp-fill nw-donut-comp-fill-asset"
                    :style="{ width: `${row.share * 100}%` }"
                  ></span>
                </div>
              </button>
            </div>
          </div>
          <div v-else class="nw-donut-comp-empty">Sin datos de activos por categoria.</div>
        </div>

        <div class="nw-donut-comp-block">
          <div class="nw-donut-comp-block-head">
            <div class="nw-donut-comp-title">Composicion de pasivos</div>
            <button
              class="nw-donut-comp-action"
              type="button"
              aria-label="Nuevo pasivo"
              @click="emit('add-type', { type: 'liability' })"
            >
              +
            </button>
          </div>
          <div v-if="liabilityComposition.length" class="nw-donut-comp-list">
            <div
              v-for="row in liabilityComposition"
              :key="`liability-${row.key}`"
              class="nw-donut-comp-row"
              :class="{
                'nw-donut-comp-row-active':
                  props.selectedCategoryType === 'liability' &&
                  props.selectedCategoryKey === row.key,
              }"
            >
              <button
                class="nw-donut-comp-main"
                type="button"
                @click="emit('select-category', { key: row.key, type: 'liability' })"
              >
                <div class="nw-donut-comp-head">
                  <span>{{ row.label }}</span>
                  <strong>{{ formatPercent(row.share, 0) }}</strong>
                </div>
                <div class="nw-donut-comp-meta">
                  <span>{{ formatMoney(row.value, 2) }} {{ displayUnit }}</span>
                  <span>{{ row.count }} posiciones</span>
                </div>
                <div class="nw-donut-comp-bar">
                  <span
                    class="nw-donut-comp-fill nw-donut-comp-fill-liability"
                    :style="{ width: `${row.share * 100}%` }"
                  ></span>
                </div>
              </button>
            </div>
          </div>
          <div v-else class="nw-donut-comp-empty">Sin datos de pasivos por categoria.</div>
        </div>
      </div>
    </div>
  </div>
</template>
