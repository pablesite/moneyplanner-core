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
  <div class="cat-header">
    <div class="cat-left">
      <div class="text-base">{{ label }}</div>
      <span class="badge">{{ count }}</span>
    </div>
    <div class="cat-right">
      <div class="cat-total">
        <div v-if="showBaseTotal && baseLabel" class="cat-total-primary">
          {{ baseLabel }}
          <span v-if="percent" class="cat-percent">. {{ percent }}%</span>
        </div>
        <div :class="showBaseTotal && baseLabel ? 'cat-total-details' : 'cat-total-primary'">
          {{ totalsLine }}
          <span v-if="!showBaseTotal && percent" class="cat-percent">. {{ percent }}%</span>
        </div>
      </div>
      <button
        v-if="showToggle"
        class="icon-btn cat-toggle"
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

<style scoped>
.cat-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.cat-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  position: relative;
}

.cat-left > div {
  color: var(--cat-accent-text, rgba(255, 255, 255, 0.92));
}

.cat-left .badge {
  border: 1px solid var(--cat-accent, rgba(255, 255, 255, 0.2));
  color: var(--cat-accent-text, rgba(255, 255, 255, 0.85));
}

.cat-right {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.cat-toggle {
  margin-left: 0;
}

.cat-total {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  text-align: right;
  line-height: 1.15;
  max-width: 280px;
}

.cat-total > div {
  word-break: break-word;
}

.cat-total-primary {
  color: rgba(255, 255, 255, 0.92);
  font-size: 13px;
  font-weight: 700;
}

.cat-total-details {
  color: rgba(255, 255, 255, 0.55);
  font-size: 11px;
  font-weight: 500;
}

.cat-percent {
  color: rgba(255, 255, 255, 0.55);
}
</style>
