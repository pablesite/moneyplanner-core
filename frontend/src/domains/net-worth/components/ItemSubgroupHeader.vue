<script setup lang="ts">
type Props = {
  label: string | null;
  totalsLine: string;
  baseLabel: string | null;
  percent: string | null;
  showBaseTotal: boolean;
};

defineProps<Props>();
</script>

<template>
  <div class="subcat-header">
    <div class="subcat-title">{{ label }}</div>
    <div class="subcat-total">
      <div v-if="showBaseTotal && baseLabel" class="subcat-total-primary">
        {{ baseLabel }}
        <span v-if="percent" class="subcat-percent">. {{ percent }}%</span>
      </div>
      <div :class="showBaseTotal && baseLabel ? 'subcat-total-details' : 'subcat-total-primary'">
        {{ totalsLine }}
      </div>
    </div>
    <div class="subcat-actions-spacer" aria-hidden="true"></div>
  </div>
</template>

<style scoped>
.subcat-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: baseline;
  gap: 12px;
  margin-top: 12px;
  padding-top: 6px;
}

.subcat-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.75);
}

.subcat-total {
  display: grid;
  justify-items: end;
  text-align: right;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.1;
  white-space: nowrap;
}

.subcat-total-primary {
  color: rgba(255, 255, 255, 0.9);
  font-size: 11px;
  font-weight: 700;
}

.subcat-total-details {
  color: rgba(255, 255, 255, 0.55);
  font-size: 10px;
  font-weight: 500;
}

.subcat-percent {
  color: rgba(255, 255, 255, 0.55);
}

.subcat-actions-spacer {
  width: var(--item-actions-width, 72px);
}
</style>
