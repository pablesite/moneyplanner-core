<script setup lang="ts">
import { computed } from 'vue';
import { scoreColor } from '@/domains/guide/scoreVisuals';
import ScoreGradeLabel from './ScoreGradeLabel.vue';

const props = withDefaults(
  defineProps<{
    score: number;
    largeGrade?: boolean;
    rowClass?: string;
    trackClass?: string;
    fillClass?: string;
    gradeClass?: string;
  }>(),
  {
    largeGrade: false,
    rowClass: '',
    trackClass: '',
    fillClass: '',
    gradeClass: '',
  },
);

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

const fillStyle = computed<Record<string, string>>(() => ({
  width: `${clamp(props.score, 0, 100)}%`,
  backgroundColor: scoreColor(props.score),
}));
</script>

<template>
  <div class="ui-score-meter-row" :class="rowClass">
    <ScoreGradeLabel :score="score" :large="largeGrade" :class="gradeClass" />
    <div class="ui-score-meter-track" :class="trackClass">
      <span class="ui-score-meter-fill" :class="fillClass" :style="fillStyle"></span>
    </div>
  </div>
</template>
