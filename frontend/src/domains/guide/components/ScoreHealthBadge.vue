<script setup lang="ts">
import { computed } from 'vue';
import { scoreBadgeStyle } from '@/domains/guide/scoreVisuals';

type ScoreTone = 'solid' | 'medium' | 'watch' | 'risk';

const props = defineProps<{
  label: string;
  score: number;
  tone: ScoreTone;
  formattedScore?: string;
}>();

const badgeStyle = computed(() => scoreBadgeStyle(props.score));
</script>

<template>
  <div class="ui-guide-health-score-badge" :class="`ui-guide-health-${tone}`" :style="badgeStyle">
    <span class="ui-guide-health-score-text">{{ label }}</span>
    <strong class="ui-guide-health-score-value">{{
      formattedScore ?? `${Math.round(score)}%`
    }}</strong>
  </div>
</template>
