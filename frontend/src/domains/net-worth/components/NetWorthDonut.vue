<script setup lang="ts">
import { computed } from 'vue';
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

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'select-category', payload: { key: string; type: 'asset' | 'liability' }): void;
  (e: 'add-type', payload: { type: 'asset' | 'liability' }): void;
}>();

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
const liabilities = computed(() => Math.max(0, toNumber(props.totalLiabilities)));
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
  total: number,
) {
  if (!keys?.length || !labels?.length || !values?.length || total <= 0)
    return [] as CategoryShare[];
  return labels
    .map((label, index) => {
      const value = Math.max(0, values[index] ?? 0);
      return {
        key: keys[index] ?? label,
        label,
        value,
        share: total > 0 ? value / total : 0,
        count: Math.max(0, counts?.[index] ?? 0),
      };
    })
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 5);
}

const assetComposition = computed(() =>
  buildCategoryShares(
    props.categoryKeys,
    props.categoryLabels,
    props.categoryAssets,
    props.categoryAssetCounts,
    assets.value,
  ),
);
const liabilityComposition = computed(() =>
  buildCategoryShares(
    props.categoryKeys,
    props.categoryLabels,
    props.categoryLiabilities,
    props.categoryLiabilityCounts,
    liabilities.value,
  ),
);

const data = computed<ChartData<'doughnut'>>(() => ({
  labels: ['Capital propio (neto)', 'Activos financiados con deuda', 'Deuda sin activo'],
  datasets: [
    {
      data: [equitySlice.value, backedSlice.value, unbackedSlice.value],
      backgroundColor: [
        'rgba(92, 192, 255, 0.9)',
        'rgba(255, 99, 132, 0.85)',
        'rgba(255, 140, 110, 0.85)',
      ],
      borderColor: ['rgba(0,0,0,0)', 'rgba(0,0,0,0)', 'rgba(0,0,0,0)'],
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
          return `${label}: ${formatMoney(v, 2)} ${props.unit}${pct}`;
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
    ctx.fillText(props.unit, cx, cy + 26);

    ctx.restore();
  },
}));
</script>

<template>
  <div class="nw-donut-wrap">
    <div v-if="props.showChart !== false" class="nw-donut-chart">
      <Doughnut :data="data" :options="options" :plugins="[centerTextPlugin]" />
    </div>

    <div v-if="props.showComposition !== false || $slots['side-top']" class="nw-donut-side">
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
                  <span>{{ formatMoney(row.value, 2) }} {{ props.unit }}</span>
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
                  <span>{{ formatMoney(row.value, 2) }} {{ props.unit }}</span>
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

<style scoped>
.nw-donut-comp-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.nw-donut-comp-title {
  font-size: 0.95rem;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.8);
}

.nw-donut-comp-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  border-radius: 12px;
  border: 1px solid transparent;
  padding: 8px 10px;
  transition:
    border-color 0.16s ease,
    background-color 0.16s ease;
}

.nw-donut-comp-main {
  width: 100%;
  text-align: left;
  background: transparent;
  border: 0;
  padding: 0;
  color: inherit;
  cursor: pointer;
}

.nw-donut-comp-row-active {
  border-color: rgba(45, 212, 191, 0.35);
  background: rgba(45, 212, 191, 0.08);
}

.nw-donut-comp-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.nw-donut-comp-meta {
  margin-top: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.62);
}

.nw-donut-comp-bar {
  margin-top: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.nw-donut-comp-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.nw-donut-comp-fill-asset {
  background: linear-gradient(90deg, #38bdf8, #4cc3ff);
}

.nw-donut-comp-fill-liability {
  background: linear-gradient(90deg, #fb7185, #f43f5e);
}

.nw-donut-comp-action {
  width: 36px;
  min-width: 36px;
  height: 36px;
  border-radius: 12px;
  border: 1px solid rgba(45, 212, 191, 0.4);
  background: rgba(45, 212, 191, 0.08);
  color: rgba(255, 255, 255, 0.92);
  cursor: pointer;
  font-size: 1.15rem;
  line-height: 1;
}

.nw-donut-comp-empty {
  color: rgba(255, 255, 255, 0.58);
  font-size: 0.85rem;
}

.nw-donut-side-top {
  margin-bottom: 16px;
}
</style>
