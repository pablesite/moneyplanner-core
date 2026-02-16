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
  <div class="nw-subcat-header">
    <div class="nw-subcat-title">{{ label }}</div>
    <div class="nw-subcat-total">
      <div v-if="showBaseTotal && baseLabel" class="nw-subcat-total-primary">
        {{ baseLabel }}
        <span v-if="percent" class="nw-subcat-percent">. {{ percent }}%</span>
      </div>
      <div :class="showBaseTotal && baseLabel ? 'nw-subcat-total-details' : 'nw-subcat-total-primary'">
        {{ totalsLine }}
      </div>
    </div>
    <div class="nw-subcat-actions-spacer" aria-hidden="true"></div>
  </div>
</template>
