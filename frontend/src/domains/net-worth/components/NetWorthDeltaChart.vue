<script setup lang="ts">
import { computed } from 'vue';
import { Bar } from 'vue-chartjs';
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from 'chart.js';

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

type TimelineRow = {
  date: string;
  label: string;
  value: number;
};

const props = defineProps<{
  rows: TimelineRow[];
  unit: string;
}>();

function formatNumber(n: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${formatNumber(value / 1_000_000, 1)}M`;
  if (abs >= 1_000) return `${formatNumber(value / 1_000, 1)}k`;
  return formatNumber(value, 0);
}

type DeltaPoint = {
  label: string;
  value: number;
};

const deltaPoints = computed<DeltaPoint[]>(() => {
  const result: DeltaPoint[] = [];
  for (let i = 1; i < props.rows.length; i++) {
    result.push({
      label: props.rows[i]!.label,
      value: props.rows[i]!.value - props.rows[i - 1]!.value,
    });
  }
  return result;
});

const xTickStep = computed(() => {
  if (deltaPoints.value.length <= 6) return 1;
  return Math.ceil(deltaPoints.value.length / 6);
});

const chartData = computed<ChartData<'bar'>>(() => ({
  labels: deltaPoints.value.map((p) => p.label),
  datasets: [
    {
      label: 'Variación mensual',
      data: deltaPoints.value.map((p) => p.value),
      backgroundColor: deltaPoints.value.map((p) =>
        p.value >= 0 ? 'rgba(52, 211, 153, 0.7)' : 'rgba(248, 113, 113, 0.7)',
      ),
      borderColor: deltaPoints.value.map((p) =>
        p.value >= 0 ? 'rgba(52, 211, 153, 0.9)' : 'rgba(248, 113, 113, 0.9)',
      ),
      borderWidth: 1,
      borderRadius: 3,
    },
  ],
}));

const chartOptions = computed<ChartOptions<'bar'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: {
    mode: 'nearest',
    axis: 'x',
    intersect: false,
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      displayColors: false,
      backgroundColor: 'rgba(10, 17, 26, 0.96)',
      borderColor: 'rgba(255, 255, 255, 0.12)',
      borderWidth: 1,
      padding: 12,
      titleFont: { size: 12, weight: 600 },
      bodyFont: { size: 12 },
      callbacks: {
        title: (items) => deltaPoints.value[items[0]?.dataIndex ?? 0]?.label ?? '',
        label: (ctx) => {
          const v = Number(ctx.raw ?? 0);
          return `${v >= 0 ? '+' : ''}${formatNumber(v, 0)} ${props.unit}`;
        },
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      border: { display: false },
      ticks: {
        color: 'rgba(226, 232, 240, 0.72)',
        maxRotation: 0,
        autoSkip: false,
        callback: (_value, index) => {
          if (index === 0 || index === deltaPoints.value.length - 1) {
            return deltaPoints.value[index]?.label ?? '';
          }
          return index % xTickStep.value === 0 ? (deltaPoints.value[index]?.label ?? '') : '';
        },
      },
    },
    y: {
      grid: { color: 'rgba(148, 163, 184, 0.1)' },
      border: { display: false },
      ticks: {
        color: 'rgba(226, 232, 240, 0.72)',
        callback: (value) => formatCompact(Number(value)),
      },
    },
  },
}));
</script>

<template>
  <div v-if="deltaPoints.length >= 2" class="ui-nw-delta-chart">
    <div class="ui-nw-delta-chart-label">Variación mensual</div>
    <div class="ui-nw-delta-chart-canvas">
      <Bar
        aria-label="Variación mensual del patrimonio"
        :data="chartData"
        :options="chartOptions"
      />
    </div>
  </div>
</template>
