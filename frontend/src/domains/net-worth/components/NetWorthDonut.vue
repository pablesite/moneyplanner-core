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
  unit: string; // "EUR" o "EUR (IPC)" etc.
  assetBackedLiabilities?: string | number | null | undefined;
  unbackedLiabilities?: string | number | null | undefined;
};

const props = defineProps<Props>();

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

/**
 * Donut representa el total de activos (100% = activos).
 * Se descompone en:
 * - Capital propio (neto): activos - pasivos (puede ser 0 si neto negativo)
 * - Deuda con activo (financia): pasivos asignados a activos
 * - Deuda sin activo: pasivos no asignados (reduce el equity, aunque no financie un activo)
 *
 * Así: equitySlice + backedSlice + unbackedSlice = assets (si net>=0).
 * Si pasivos > activos -> overflow.
 */
const backedSlice = computed(() => Math.min(backedRaw.value, assets.value));

const unbackedSlice = computed(() => {
  // No dejamos que la suma de slices supere assets (lo demás va a overflow)
  const room = Math.max(assets.value - backedSlice.value, 0);
  return Math.min(unbackedRaw.value, room);
});

const equitySlice = computed(() => {
  // Capital propio dentro de activos, restando todo tipo de deuda
  return Math.max(assets.value - backedSlice.value - unbackedSlice.value, 0);
});

const liabilityOverflow = computed(() => {
  // Si la deuda total supera activos, el neto sería negativo.
  const totalDebt = backedRaw.value + unbackedRaw.value;
  return Math.max(totalDebt - assets.value, 0);
});

const debtRatio = computed(() => {
  if (assets.value <= 0) return null;
  return liabilities.value / assets.value;
});

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
    <div class="nw-donut-chart">
      <Doughnut :data="data" :options="options" :plugins="[centerTextPlugin]" />
    </div>

    <div class="nw-donut-legend">
      <div class="nw-donut-legend-title">Estructura del balance</div>

      <div class="nw-donut-legend-row">
        <span class="nw-donut-dot nw-donut-dot-equity"></span>
        <span>Activos</span>
        <span class="nw-donut-legend-val">{{ formatMoney(assets, 2) }} {{ unit }}</span>
      </div>

      <div class="nw-donut-legend-row">
        <span class="nw-donut-dot nw-donut-dot-liability"></span>
        <span>Pasivos</span>
        <span class="nw-donut-legend-val">{{ formatMoney(liabilities, 2) }} {{ unit }}</span>
      </div>

      <div class="nw-donut-legend-row">
        <span class="nw-donut-dot nw-donut-dot-equity"></span>
        <span>Capital propio (neto)</span>
        <span class="nw-donut-legend-val">{{ formatMoney(net, 2) }} {{ unit }}</span>
      </div>

      <div class="nw-donut-legend-row">
        <span class="nw-donut-dot nw-donut-dot-liability"></span>
        <span>Activos financiados con deuda</span>
        <span class="nw-donut-legend-val">{{ formatMoney(backedSlice, 2) }} {{ unit }}</span>
      </div>

      <div class="nw-donut-legend-row">
        <span class="nw-donut-dot nw-donut-dot-unbacked"></span>
        <span>Deuda sin activo</span>
        <span class="nw-donut-legend-val">{{ formatMoney(unbackedRaw, 2) }} {{ unit }}</span>
      </div>

      <div v-if="liabilityOverflow > 0" class="nw-donut-overflow">
        Aviso: la deuda total excede a los activos en {{ formatMoney(liabilityOverflow, 2) }}
        {{ unit }}.
      </div>

      <div v-if="debtRatio !== null" class="nw-donut-ratio">
        Ratio deuda / activos: {{ formatPercent(debtRatio, 0) }}
      </div>
    </div>
  </div>
</template>

