<script setup lang="ts">
import { computed } from 'vue';
import { gradeFromScore, scoreColor } from '@/domains/guide/scoreVisuals';

const props = defineProps<{
  score: number;
}>();

const badgeStyle = computed<Record<string, string>>(() => ({
  color: scoreColor(props.score),
  borderColor: 'rgba(255, 255, 255, 0.22)',
}));

const grade = computed(() => gradeFromScore(props.score));
</script>

<template>
  <span class="badge ui-score-grade-badge" :style="badgeStyle">
    {{ grade }}
  </span>
</template>
