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

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export type NetWorthTimelineChartPoint = {
  date: string;
  shortLabel: string;
  fullLabel: string;
  value: number;
  isCurrent?: boolean;
};

type Props = {
  points: NetWorthTimelineChartPoint[];
  unit: string;
  seriesLabel: string;
  ariaLabel?: string;
  seriesColor?: string;
  expanded?: boolean;
  yAxisMinZero?: boolean;
};

const props = withDefaults(defineProps<Props>(), {
  ariaLabel: 'Grafico de evolucion patrimonial',
  seriesColor: () => cssVar('--chart-series-stroke'),
  expanded: false,
  yAxisMinZero: false,
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

const hasNegativePoints = computed(() => props.points.some((point) => point.value < 0));

const chartData = computed<ChartData<'line'>>(() => ({
  labels: props.points.map((point) => point.shortLabel),
  datasets: [
    {
      label: props.seriesLabel,
      data: props.points.map((point) => point.value),
      borderColor: props.seriesColor,
      backgroundColor: cssVar('--chart-series-fill'),
      borderWidth: props.expanded ? 3 : 2.5,
      tension: 0.32,
      fill: true,
      pointRadius: props.points.length > 1 ? 2 : 4,
      pointHoverRadius: 7,
      pointHitRadius: 20,
      pointBorderWidth: 2,
      pointHoverBorderWidth: 3,
      pointBackgroundColor: props.points.map((p) =>
        p.isCurrent ? cssVar('--chart-point-current-bg') : cssVar('--chart-point-bg'),
      ),
      pointHoverBackgroundColor: props.points.map((p) =>
        p.isCurrent ? cssVar('--chart-point-current-hover-bg') : cssVar('--chart-point-hover-bg'),
      ),
      pointBorderColor: props.points.map((p) =>
        p.isCurrent ? cssVar('--chart-point-current-bg') : props.seriesColor,
      ),
      pointHoverBorderColor: props.points.map((p) =>
        p.isCurrent ? cssVar('--chart-point-current-hover-bg') : props.seriesColor,
      ),
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
      backgroundColor: cssVar('--chart-tooltip-bg'),
      borderColor: cssVar('--color-border'),
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
        color: cssVar('--color-text-muted'),
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
      beginAtZero: props.yAxisMinZero && !hasNegativePoints.value,
      min: props.yAxisMinZero && !hasNegativePoints.value ? 0 : undefined,
      grid: {
        color: cssVar('--color-border'),
      },
      border: {
        display: false,
      },
      ticks: {
        color: cssVar('--color-text-muted'),
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
