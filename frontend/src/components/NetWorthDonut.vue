<script setup lang="ts">
import { computed } from "vue";
import { Doughnut } from "vue-chartjs";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
  type Plugin,
} from "chart.js";

ChartJS.register(ArcElement, Tooltip, Legend);

type Props = {
  totalAssets: string | number | null | undefined;
  totalLiabilities: string | number | null | undefined;
  netWorth: string | number | null | undefined;
  unit: string; // "EUR" o "EUR (IPC)" etc.
};

const props = defineProps<Props>();

function normalizeNumberInput(raw: unknown) {
  return String(raw ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
}

function toNumber(v: unknown) {
  const n = Number(normalizeNumberInput(v));
  return Number.isFinite(n) ? n : 0;
}

function formatMoney(n: number, decimals = 2) {
  return new Intl.NumberFormat("es-ES", {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatPercent(n: number, decimals = 0) {
  return new Intl.NumberFormat("es-ES", {
    style: "percent",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

const assets = computed(() => Math.max(0, toNumber(props.totalAssets)));
const liabilities = computed(() => Math.max(0, toNumber(props.totalLiabilities)));
const net = computed(() => toNumber(props.netWorth));

// Donut de balance:
// - el círculo representa los activos
// - parte financiada con deuda dentro de activos = min(pasivos, activos)
// - capital propio dentro de activos = max(activos - pasivos, 0)
// - si pasivos > activos, la deuda excedente se muestra fuera (no cabe en el 100% del donut)
const debtInsideAssets = computed(() => Math.min(liabilities.value, assets.value));
const equityInsideAssets = computed(() => Math.max(assets.value - liabilities.value, 0));
const debtOverflow = computed(() => Math.max(liabilities.value - assets.value, 0));

const debtRatio = computed(() => {
  if (assets.value <= 0) return null;
  return liabilities.value / assets.value;
});

const data = computed<ChartData<"doughnut">>(() => ({
  labels: ["Capital propio (en activos)", "Activos financiados con deuda"],
  datasets: [
    {
      data: [equityInsideAssets.value, debtInsideAssets.value],
      backgroundColor: [
        "rgba(90, 200, 250, 0.85)",  // equity
        "rgba(255, 99, 132, 0.80)",  // deuda
      ],
      borderColor: ["rgba(0,0,0,0)", "rgba(0,0,0,0)"],
      borderWidth: 0,
      hoverOffset: 6,
      spacing: 2,
      cutout: "72%",
    },
  ],
}));

const options = computed<ChartOptions<"doughnut">>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => {
          const label = ctx.label ?? "";
          const v = typeof ctx.raw === "number" ? ctx.raw : 0;
          const pct =
            assets.value > 0 ? ` (${formatPercent(v / assets.value, 0)})` : "";
          return `${label}: ${formatMoney(v, 2)} ${props.unit}${pct}`;
        },
      },
    },
  },
}));

// Texto centrado (Neto) con color por signo
const centerTextPlugin = computed<Plugin<"doughnut">>(() => ({
  id: "centerText",
  afterDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    const cx = (chartArea.left + chartArea.right) / 2;
    const cy = (chartArea.top + chartArea.bottom) / 2;

    const netStr = formatMoney(net.value, 2);

    const isNeg = net.value < 0;
    const netColor = isNeg ? "rgba(255, 120, 140, 0.95)" : "rgba(140, 240, 180, 0.95)";

    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    // Neto
    ctx.font = "700 16px system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    ctx.fillStyle = netColor;
    ctx.fillText(netStr, cx, cy - 10);

    // Etiqueta
    ctx.font = "12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    ctx.fillStyle = "rgba(255,255,255,0.70)";
    ctx.fillText("Patrimonio neto", cx, cy + 8);

    // Unidad
    ctx.font = "12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    ctx.fillStyle = "rgba(255,255,255,0.60)";
    ctx.fillText(props.unit, cx, cy + 26);

    ctx.restore();
  },
}));
</script>

<template>
  <div class="donut-wrap">
    <div class="donut-chart">
      <Doughnut :data="data" :options="options" :plugins="[centerTextPlugin]" />
    </div>

    <div class="donut-legend">
      <div class="legend-title">Estructura del balance</div>

      <div class="legend-row">
        <span class="dot dot-assets"></span>
        <span>Activos</span>
        <span class="legend-val">{{ formatMoney(assets, 2) }} {{ unit }}</span>
      </div>

      <div class="legend-row">
        <span class="dot dot-liab"></span>
        <span>Pasivos</span>
        <span class="legend-val">{{ formatMoney(liabilities, 2) }} {{ unit }}</span>
      </div>

      <div class="legend-row">
        <span class="dot dot-equity"></span>
        <span>Capital propio (en activos)</span>
        <span class="legend-val">{{ formatMoney(equityInsideAssets, 2) }} {{ unit }}</span>
      </div>

      <div class="legend-row subtle-row">
        <span class="dot dot-debt"></span>
        <span>Activos financiados con deuda</span>
        <span class="legend-val">{{ formatMoney(debtInsideAssets, 2) }} {{ unit }}</span>
      </div>

      <div v-if="debtOverflow > 0" class="overflow">
        La deuda excede a los activos en {{ formatMoney(debtOverflow, 2) }} {{ unit }}.
      </div>

      <div v-if="debtRatio !== null" class="ratio">
        Ratio deuda / activos: {{ formatPercent(debtRatio, 0) }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.donut-wrap {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 16px;
  align-items: center;
}

.donut-chart {
  height: 190px;
}

.donut-legend {
  display: grid;
  gap: 10px;
}

.legend-title {
  font-size: 14px;
  opacity: 0.85;
  margin-bottom: 2px;
}

.legend-row {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  gap: 10px;
  align-items: center;
  font-size: 14px;
}

.legend-val {
  opacity: 0.9;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.dot-assets {
  background: rgba(255, 255, 255, 0.35);
}

.dot-liab {
  background: rgba(255, 99, 132, 0.85);
}

.dot-equity {
  background: rgba(90, 200, 250, 0.9);
}

.dot-debt {
  background: rgba(255, 99, 132, 0.65);
}

.overflow {
  margin-top: 6px;
  font-size: 13px;
  color: rgba(255, 140, 160, 0.95);
}

.ratio {
  margin-top: 2px;
  font-size: 13px;
  opacity: 0.75;
}

@media (max-width: 720px) {
  .donut-wrap {
    grid-template-columns: 1fr;
  }
  .donut-chart {
    height: 230px;
  }
}
</style>
