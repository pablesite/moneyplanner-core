<script setup lang="ts">
import { computed } from 'vue';
import { Bar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

type Props = {
  labels: string[]; // etiquetas ya “humanas” (Liquidez, Inversiones, Hipoteca...)
  assets: number[]; // positivos
  liabilities: number[]; // positivos (aquí los convertimos a negativos)
  unit: string; // "EUR"
};

const props = defineProps<Props>();

const ASSET_COLOR_BY_LABEL: Record<string, string> = {
  liquidez: 'rgba(92, 192, 255, 0.9)',
  inversiones: 'rgba(74, 209, 179, 0.9)',
  inmuebles: 'rgba(111, 211, 122, 0.9)',
  mobiliario: 'rgba(138, 203, 136, 0.85)',
  otros: 'rgba(122, 161, 194, 0.85)',
};

const LIAB_COLOR_BY_LABEL: Record<string, string> = {
  hipoteca: 'rgba(255, 99, 132, 0.85)',
  'préstamo personal': 'rgba(255, 120, 150, 0.85)',
  'prestamo personal': 'rgba(255, 120, 150, 0.85)',
  tarjeta: 'rgba(255, 140, 110, 0.85)',
  otros: 'rgba(255, 130, 130, 0.8)',
};

function labelKey(label: string) {
  return (label || '').trim().toLowerCase();
}

function assetColorFor(label: string) {
  return ASSET_COLOR_BY_LABEL[labelKey(label)] ?? 'rgba(92, 192, 255, 0.9)';
}

function liabilityColorFor(label: string) {
  return LIAB_COLOR_BY_LABEL[labelKey(label)] ?? 'rgba(255, 99, 132, 0.85)';
}

function formatMoney(n: number, decimals = 0) {
  return new Intl.NumberFormat('es-ES', {
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

const data = computed<ChartData<'bar'>>(() => ({
  labels: orderedLabels.value,
  datasets: [
    {
      label: 'Activos',
      data: orderedAssets.value,
      backgroundColor: orderedLabels.value.map((l) => assetColorFor(l)),
      borderRadius: 8,
      barThickness: 18,
    },
    {
      label: 'Pasivos',
      data: orderedLiabilities.value.map((v) => -Math.abs(v)),
      backgroundColor: orderedLabels.value.map((l) => liabilityColorFor(l)),
      borderRadius: 8,
      barThickness: 18,
    },
  ],
}));

const ASSET_ORDER = ['liquidez', 'inversiones', 'inmuebles', 'mobiliario', 'otros'];
const LIAB_ORDER = ['tarjeta', 'préstamo personal', 'prestamo personal', 'hipoteca', 'otros'];

const assetRank = new Map<string, number>(ASSET_ORDER.map((k, i) => [k, i]));
const liabRank = new Map<string, number>(LIAB_ORDER.map((k, i) => [k, i]));

const orderedIndex = computed(() => {
  const indexed = props.labels.map((label, i) => ({ label, i }));
  return indexed.sort((a, b) => {
    const ak = labelKey(a.label);
    const bk = labelKey(b.label);
    const aIsAsset = assetRank.has(ak);
    const bIsAsset = assetRank.has(bk);
    const aIsLiab = liabRank.has(ak);
    const bIsLiab = liabRank.has(bk);

    // 1) Activos primero, luego pasivos, luego resto
    const aGroup = aIsAsset ? 0 : aIsLiab ? 1 : 2;
    const bGroup = bIsAsset ? 0 : bIsLiab ? 1 : 2;
    if (aGroup !== bGroup) return aGroup - bGroup;

    // 2) Dentro de activos/pasivos, usar su orden fijo
    if (aGroup === 0) {
      const ai = assetRank.get(ak) ?? Number.MAX_SAFE_INTEGER;
      const bi = assetRank.get(bk) ?? Number.MAX_SAFE_INTEGER;
      if (ai !== bi) return ai - bi;
    } else if (aGroup === 1) {
      const ai = liabRank.get(ak) ?? Number.MAX_SAFE_INTEGER;
      const bi = liabRank.get(bk) ?? Number.MAX_SAFE_INTEGER;
      if (ai !== bi) return ai - bi;
    }

    return a.label.localeCompare(b.label);
  });
});

const orderedLabels = computed(() => orderedIndex.value.map((x) => x.label));
const orderedAssets = computed(() => orderedIndex.value.map((x) => props.assets[x.i] ?? 0));
const orderedLiabilities = computed(() =>
  orderedIndex.value.map((x) => props.liabilities[x.i] ?? 0),
);

const options = computed<ChartOptions<'bar'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: 'y',
  plugins: {
    legend: {
      display: true,
      labels: { color: 'rgba(255,255,255,0.75)' },
    },
    tooltip: {
      callbacks: {
        title: (items) => items?.[0]?.label ?? '',
        label: (ctx) => {
          const label = ctx.dataset.label ?? '';
          const raw = typeof ctx.raw === 'number' ? ctx.raw : 0;
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
        color: 'rgba(255,255,255,0.70)',
        font: { size: 12 },
      },
      grid: { display: false },
    },
    x: {
      stacked: true,
      ticks: {
        color: 'rgba(255,255,255,0.65)',
        callback: (value) => {
          const v = typeof value === 'number' ? value : Number(value);
          return formatTickCompact(v);
        },
      },
      grid: { color: 'rgba(255,255,255,0.08)' },
    },
  },
}));
</script>

<template>
  <div class="nw-bar-wrap">
    <div class="nw-bar-chart-category">
      <Bar :data="data" :options="options" />
    </div>
  </div>
</template>
