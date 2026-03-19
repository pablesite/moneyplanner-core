<script setup lang="ts">
import { RouterLink } from 'vue-router';
import ScoreGradeBadge from '@/domains/guide/components/ScoreGradeBadge.vue';
import { guidePhases, useGuideHomeState } from '@/domains/guide';

const phases = guidePhases;
const {
  phaseState,
  phaseDetailTo,
  phaseDisplayProgress,
  phaseDonutStyle,
  phaseSummaryStyle,
  phaseCardStyle,
  mostTensePhase,
  strongestPhase,
} = useGuideHomeState('core');
</script>

<template>
  <div class="container ui-pro-page">
    <section class="card ui-pro-panel ui-home-intro">
      <div class="ui-home-intro-text">
        <p class="ui-pro-kicker">Guia financiera</p>
        <h1 class="h1 ui-home-title">Mapa de fases financieras</h1>
        <p class="subtle ui-home-copy">
          Cada fase refleja una dimension distinta de tu situacion. Mejorar una puede afectar
          temporalmente a otra, asi que conviene revisar el equilibrio global.
        </p>
        <p v-if="mostTensePhase" class="ui-home-focus-line">
          <span class="ui-home-focus-label">Foco actual:</span>
          F{{ mostTensePhase.phase.id }} - {{ mostTensePhase.phase.title }}
          <span class="ui-home-focus-meta">
            ({{ mostTensePhase.grade }} · {{ mostTensePhase.score }}%)
          </span>
        </p>
      </div>
      <div class="ui-home-intro-kpis">
        <div class="ui-home-intro-kpi" :style="phaseSummaryStyle(mostTensePhase)">
          <span>Mayor tension</span>
          <strong v-if="mostTensePhase">
            F{{ mostTensePhase.phase.id }} · {{ mostTensePhase.grade }} ·
            {{ mostTensePhase.score }}%
          </strong>
          <strong v-else>-</strong>
        </div>
        <div class="ui-home-intro-kpi" :style="phaseSummaryStyle(strongestPhase)">
          <span>Mejor posicionada</span>
          <strong v-if="strongestPhase">
            F{{ strongestPhase.phase.id }} · {{ strongestPhase.grade }} ·
            {{ strongestPhase.score }}%
          </strong>
          <strong v-else>-</strong>
        </div>
      </div>
    </section>

    <article class="section card ui-pro-panel">
      <h2 class="h2">Ruta por fases</h2>
      <p class="subtle ui-home-block-copy">
        Selecciona una fase para abrir su vista de detalle y revisar el diagnostico asociado.
      </p>

      <ol class="ui-home-phase-row">
        <li
          v-for="phase in phases"
          :key="phase.id"
          class="ui-home-phase-card"
          :style="phaseCardStyle(phase)"
          :class="{
            'ui-home-phase-done': phaseState(phase) === 'done',
            'ui-home-phase-active': phaseState(phase) === 'active',
          }"
        >
          <RouterLink class="ui-home-phase-link" :to="phaseDetailTo(phase.id)">
            <div class="ui-home-phase-head">
              <span class="ui-home-phase-id">F{{ phase.id }}</span>
              <ScoreGradeBadge :score="phaseDisplayProgress(phase)" />
            </div>

            <div class="ui-home-phase-title">{{ phase.title }}</div>
            <div class="ui-home-phase-focus">{{ phase.focus }}</div>

            <div class="ui-home-phase-donut" :style="phaseDonutStyle(phase)">
              <div class="ui-home-phase-donut-inner">{{ phaseDisplayProgress(phase) }}%</div>
            </div>

            <div class="ui-home-phase-cta">Ver detalle de fase</div>
          </RouterLink>
        </li>
      </ol>
    </article>
  </div>
</template>
