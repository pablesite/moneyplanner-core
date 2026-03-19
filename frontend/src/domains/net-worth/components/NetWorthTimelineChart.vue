<script setup lang="ts">
import { computed } from 'vue';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

export type NetWorthTimelineChartPoint = {
  date: string;
  shortLabel: string;
  fullLabel: string;
  value: number;
};

type Props = {
  points: NetWorthTimelineChartPoint[];
  unit: string;
  seriesLabel: string;
  ariaLabel?: string;
  seriesColor?: string;
  expanded?: boolean;
};

const props = withDefaults(defineProps<Props>(), {
  ariaLabel: 'Grafico de evolucion patrimonial',
  seriesColor: '#4cc3ff',
  expanded: false,
});

function formatNumber(n: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${formatNumber(value / 1_000_000_000, 1)}B`;
  if (abs >= 1_000_000) return `${formatNumber(value / 1_000_000, 1)}M`;
  if (abs >= 1_000) return `${formatNumber(value / 1_000, 1)}k`;
  return formatNumber(value, 0);
}

const xTickStep = computed(() => {
  if (props.points.length <= 6) return 1;
  return Math.ceil(props.points.length / 6);
});

const chartData = computed<ChartData<'line'>>(() => ({
  labels: props.points.map((point) => point.shortLabel),
  datasets: [
    {
      label: props.seriesLabel,
      data: props.points.map((point) => point.value),
      borderColor: props.seriesColor,
      backgroundColor: 'rgba(76, 195, 255, 0.12)',
      borderWidth: props.expanded ? 3 : 2.5,
      tension: 0.32,
      fill: true,
      pointRadius: props.points.length > 1 ? 2 : 4,
      pointHoverRadius: 7,
      pointHitRadius: 20,
      pointBorderWidth: 2,
      pointHoverBorderWidth: 3,
      pointBackgroundColor: '#f6fbff',
      pointHoverBackgroundColor: '#ffffff',
      pointBorderColor: props.seriesColor,
      pointHoverBorderColor: props.seriesColor,
    },
  ],
}));

const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: {
    mode: 'nearest',
    axis: 'x',
    intersect: false,
  },
  plugins: {
    legend: {
      display: false,
    },
    tooltip: {
      displayColors: false,
      backgroundColor: 'rgba(10, 17, 26, 0.96)',
      borderColor: 'rgba(255, 255, 255, 0.12)',
      borderWidth: 1,
      padding: 12,
      titleFont: {
        size: 12,
        weight: 600,
      },
      bodyFont: {
        size: 12,
      },
      callbacks: {
        title: (items) => {
          const index = items[0]?.dataIndex ?? 0;
          return props.points[index]?.fullLabel ?? '';
        },
        label: (ctx) =>
          `${props.seriesLabel}: ${formatNumber(Number(ctx.raw ?? 0), 2)} ${props.unit}`,
      },
    },
  },
  scales: {
    x: {
      grid: {
        display: false,
      },
      border: {
        display: false,
      },
      ticks: {
        color: 'rgba(226, 232, 240, 0.72)',
        maxRotation: 0,
        autoSkip: false,
        callback: (_value, index) => {
          if (index === 0 || index === props.points.length - 1) {
            return props.points[index]?.shortLabel ?? '';
          }
          return index % xTickStep.value === 0 ? (props.points[index]?.shortLabel ?? '') : '';
        },
      },
    },
    y: {
      grid: {
        color: 'rgba(148, 163, 184, 0.12)',
      },
      border: {
        display: false,
      },
      ticks: {
        color: 'rgba(226, 232, 240, 0.72)',
        callback: (value) => formatCompact(Number(value)),
      },
    },
  },
}));
</script>

<template>
  <div
    class="ui-nw-timeline-chart-card"
    :class="{ 'ui-nw-timeline-chart-card-expanded': expanded }"
  >
    <div
      class="ui-nw-timeline-chart-canvas"
      :class="{ 'ui-nw-timeline-chart-canvas-expanded': expanded }"
    >
      <Line :aria-label="ariaLabel" :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>
