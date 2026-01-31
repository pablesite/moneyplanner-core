<script setup lang="ts">
import { computed } from "vue";
import { Bar } from "vue-chartjs";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

type Props = {
  labels: string[];        // etiquetas ya “humanas” (Liquidez, Inversiones, Hipoteca...)
  assets: number[];        // positivos
  liabilities: number[];   // positivos (aquí los convertimos a negativos)
  unit: string;            // "EUR"
};

const props = defineProps<Props>();

function formatMoney(n: number, decimals = 0) {
  return new Intl.NumberFormat("es-ES", {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatTickCompact(value: number) {
  const v = Math.abs(value);
  if (v >= 1_000_000) return `${formatMoney(v / 1_000_000, 1)}M`;
  if (v >= 1_000) return `${formatMoney(v / 1_000, 1)}k`;
  return formatMoney(v, 0);
}

const data = computed<ChartData<"bar">>(() => ({
  labels: props.labels,
  datasets: [
    {
      label: "Activos",
      data: props.assets,
      backgroundColor: "rgba(90, 200, 250, 0.85)",
      borderRadius: 8,
      barThickness: 18,
    },
    {
      label: "Pasivos",
      data: props.liabilities.map((v) => -Math.abs(v)),
      backgroundColor: "rgba(255, 99, 132, 0.80)",
      borderRadius: 8,
      barThickness: 18,
    },
  ],
}));

const options = computed<ChartOptions<"bar">>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: "y",
  plugins: {
    legend: {
      display: true,
      labels: { color: "rgba(255,255,255,0.75)" },
    },
    tooltip: {
      callbacks: {
        title: (items) => items?.[0]?.label ?? "",
        label: (ctx) => {
          const label = ctx.dataset.label ?? "";
          const raw = typeof ctx.raw === "number" ? ctx.raw : 0;
          const v = Math.abs(raw);
          return `${label}: ${formatMoney(v, 2)} ${props.unit}`;
        },
      },
    },
  },
  scales: {
    y: {
      stacked: true,
      ticks: {
        color: "rgba(255,255,255,0.70)",
        font: { size: 12 },
      },
      grid: { display: false },
    },
    x: {
      stacked: true,
      ticks: {
        color: "rgba(255,255,255,0.65)",
        callback: (value) => {
          const v = typeof value === "number" ? value : Number(value);
          return formatTickCompact(v);
        },
      },
      grid: { color: "rgba(255,255,255,0.08)" },
    },
  },
}));
</script>

<template>
  <div class="wrap">
    <div class="title">Por categoría</div>
    <div class="sub">Activos (derecha) vs pasivos (izquierda)</div>

    <div class="chart">
      <Bar :data="data" :options="options" />
    </div>
  </div>
</template>

<style scoped>
.wrap {
  display: grid;
  gap: 6px;
}

.title {
  font-size: 14px;
  opacity: 0.9;
}

.sub {
  font-size: 12px;
  opacity: 0.65;
  margin-bottom: 6px;
}

.chart {
  height: 320px;
}

@media (max-width: 720px) {
  .chart {
    height: 380px;
  }
}
</style>
