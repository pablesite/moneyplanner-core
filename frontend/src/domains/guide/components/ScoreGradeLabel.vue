<script setup lang="ts">
import { computed } from 'vue';
import { gradeFromScore, scoreColor } from '@/domains/guide/scoreVisuals';

const props = withDefaults(
  defineProps<{
    score: number;
    large?: boolean;
  }>(),
  {
    large: false,
  },
);

const colorStyle = computed<Record<string, string>>(() => ({
  color: scoreColor(props.score),
}));

const grade = computed(() => gradeFromScore(props.score));
</script>

<template>
  <span
    class="ui-score-grade-label"
    :class="{ 'ui-score-grade-label-lg': large }"
    :style="colorStyle"
  >
    {{ grade }}
  </span>
</template>
