<script setup lang="ts">
type Props = {
  label: string;
  count: number;
  totalsLine: string;
  baseLabel: string | null;
  percent: string | null;
  showBaseTotal: boolean;
  showToggle: boolean;
  expanded: boolean;
};

defineProps<Props>();

const emit = defineEmits<{
  (e: 'toggle'): void;
}>();
</script>

<template>
  <div class="nw-cat-header">
    <div class="nw-cat-left">
      <div class="text-base">{{ label }}</div>
      <span class="badge">{{ count }}</span>
    </div>
    <div class="nw-cat-right">
      <div class="nw-cat-total">
        <div v-if="showBaseTotal && baseLabel" class="nw-cat-total-primary">
          {{ baseLabel }}
          <span v-if="percent" class="nw-cat-percent">. {{ percent }}%</span>
        </div>
        <div :class="showBaseTotal && baseLabel ? 'nw-cat-total-details' : 'nw-cat-total-primary'">
          {{ totalsLine }}
          <span v-if="!showBaseTotal && percent" class="nw-cat-percent">. {{ percent }}%</span>
        </div>
      </div>
      <button
        v-if="showToggle"
        class="icon-btn nw-cat-toggle"
        type="button"
        :aria-label="expanded ? 'Ocultar desglose' : 'Mostrar desglose'"
        :title="expanded ? 'Ocultar desglose' : 'Mostrar desglose'"
        @click="emit('toggle')"
      >
        <span v-if="expanded" class="icon" aria-hidden="true">&#9662;</span>
        <span v-else class="icon" aria-hidden="true">&#9656;</span>
      </button>
    </div>
  </div>
</template>
