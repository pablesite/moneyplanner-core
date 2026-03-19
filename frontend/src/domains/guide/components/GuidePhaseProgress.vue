<script setup lang="ts">
import { RouterLink } from 'vue-router';
import type { GuidePhase } from '@/domains/guide';

type PhaseQuickAction = {
  id: string;
  label: string;
  to: string;
};

const props = defineProps<{
  guidePhases: GuidePhase[];
  phase: GuidePhase | null;
  phaseQuickActions: PhaseQuickAction[];
  phaseDiagnosticCopy: string;
  phaseDetailTo: (phaseId: number) => string;
}>();

void props;
</script>

<template>
  <section class="card ui-pro-panel ui-guide-phase-head">
    <div class="ui-guide-phase-nav-row">
      <div class="ui-guide-phase-nav-links">
        <RouterLink class="ui-guide-back-link" to="/">Ver ruta completa</RouterLink>
        <div v-if="phaseQuickActions.length" class="ui-guide-phase-inline-actions">
          <RouterLink
            v-for="action in phaseQuickActions"
            :key="action.id"
            class="ui-guide-phase-inline-action-link"
            :to="action.to"
          >
            {{ action.label }}
          </RouterLink>
        </div>
      </div>
      <div class="ui-guide-phase-switch">
        <RouterLink
          v-for="phaseItem in guidePhases"
          :key="phaseItem.id"
          class="ui-guide-phase-switch-link"
          :class="{ 'ui-guide-phase-switch-link-active': phaseItem.id === phase?.id }"
          :to="phaseDetailTo(phaseItem.id)"
        >
          F{{ phaseItem.id }}
        </RouterLink>
      </div>
    </div>

    <template v-if="phase">
      <h1 class="h1 ui-guide-phase-title ui-guide-phase-title-inline">
        <span class="ui-pro-kicker ui-guide-phase-title-inline-kicker">Fase {{ phase.id }}</span>
        <span class="ui-pro-kicker ui-guide-phase-title-inline-name">{{ phase.title }}</span>
      </h1>
      <p class="subtle ui-guide-phase-copy">
        {{ phaseDiagnosticCopy }}
      </p>
    </template>

    <template v-else>
      <h1 class="h1 ui-guide-phase-title">Fase no encontrada</h1>
    </template>
  </section>
</template>
