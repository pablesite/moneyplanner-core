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
  labels: string[];
  assets: number[];
  liabilities: number[];
  unit: string;
};

const props = defineProps<Props>();

const ASSET_COLOR = "rgba(92, 192, 255, 0.9)";
const LIABILITY_COLOR = "rgba(255, 99, 132, 0.85)";

function formatMoney(n: number, decimals = 2) {
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
      backgroundColor: ASSET_COLOR,
      borderRadius: 8,
      barThickness: 28,
    },
    {
      label: "Pasivos",
      data: props.liabilities.map(v => -Math.abs(v)),
      backgroundColor: LIABILITY_COLOR,
      borderRadius: 8,
      barThickness: 28,
    },
  ],
}));

const options = computed<ChartOptions<"bar">>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      labels: { color: "rgba(255,255,255,0.75)" },
    },
    tooltip: {
      callbacks: {
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
    x: {
      stacked: true,
      ticks: { color: "rgba(255,255,255,0.65)" },
      grid: { display: false },
    },
    y: {
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
    <div class="chart">
      <Bar :data="data" :options="options" />
    </div>
  </div>
</template>

<style scoped>
.wrap {
  display: grid;
  gap: 10px;
}
.chart {
  height: 260px;
}
</style>
