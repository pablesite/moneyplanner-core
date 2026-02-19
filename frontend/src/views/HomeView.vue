<script setup lang="ts">
type Phase = {
  id: number;
  title: string;
  focus: string;
  progress: number;
};

const phases: Phase[] = [
  { id: 1, title: 'Estado inicial', focus: 'Foto real y deudas base', progress: 100 },
  { id: 2, title: 'Flujo de caja positivo', focus: 'Superavit mensual estable', progress: 68 },
  { id: 3, title: 'Fondo de emergencia', focus: 'Colchon de seguridad', progress: 35 },
  { id: 4, title: 'Mejorar patrimonio', focus: 'Balancear activo y pasivo', progress: 18 },
  {
    id: 5,
    title: 'Independencia financiera',
    focus: 'Ingresos cubren tu estilo de vida',
    progress: 6,
  },
];

const fallbackPhase: Phase = phases[phases.length - 1] ?? {
  id: 5,
  title: 'Independencia financiera',
  focus: 'Ingresos cubren tu estilo de vida',
  progress: 0,
};

const activePhase = phases.find((phase) => phase.progress < 100) ?? fallbackPhase;

function phaseState(phase: Phase): 'done' | 'active' | 'next' {
  if (phase.progress >= 100) return 'done';
  if (phase.id === activePhase.id) return 'active';
  return 'next';
}

function phaseStateLabel(phase: Phase): string {
  const state = phaseState(phase);
  if (state === 'done') return 'Completada';
  if (state === 'active') return 'Actual';
  return 'Siguiente';
}
</script>

<template>
  <div class="container ui-pro-page">
    <section class="card ui-pro-panel ui-home-intro">
      <div class="ui-home-intro-text">
        <p class="ui-pro-kicker">Inicio</p>
        <h1 class="h1 ui-home-title">Vas por buen camino: Fase {{ activePhase.id }} en progreso</h1>
        <p class="subtle ui-home-copy">
          Estas consolidando habitos de flujo positivo. El siguiente salto es construir un fondo de
          emergencia que te de tranquilidad.
        </p>
      </div>
    </section>

    <article class="section card ui-pro-panel">
      <h2 class="h2">Ruta por fases</h2>
      <p class="subtle ui-home-block-copy">
        Recorrido de izquierda a derecha para visualizar tu avance total.
      </p>

      <ol class="ui-home-phase-row">
        <li
          v-for="phase in phases"
          :key="phase.id"
          class="ui-home-phase-card"
          :class="{
            'ui-home-phase-done': phaseState(phase) === 'done',
            'ui-home-phase-active': phaseState(phase) === 'active',
          }"
        >
          <div class="ui-home-phase-head">
            <span class="ui-home-phase-id">F{{ phase.id }}</span>
            <span class="badge">{{ phaseStateLabel(phase) }}</span>
          </div>

          <div class="ui-home-phase-title">{{ phase.title }}</div>
          <div class="ui-home-phase-focus">{{ phase.focus }}</div>

          <div class="ui-home-phase-donut" :style="{ '--phase-progress': `${phase.progress}%` }">
            <div class="ui-home-phase-donut-inner">{{ phase.progress }}%</div>
          </div>
        </li>
      </ol>
    </article>

    <article class="card ui-pro-panel">
      <h2 class="h2">Siguiente mejor accion</h2>
      <p class="subtle ui-home-block-copy">
        Dedica 20 minutos hoy para revisar estos puntos y seguir avanzando sin saturarte.
      </p>
      <ul class="list">
        <li>Registrar todos los gastos variables de la semana.</li>
        <li>Confirmar que no hay nuevos pasivos sin categorizar.</li>
        <li>Definir objetivo de ahorro automatico para este mes.</li>
      </ul>
    </article>
  </div>
</template>

<style scoped>
.ui-home-intro {
  display: block;
}

.ui-home-kicker {
  margin: 0 0 6px;
  color: rgba(74, 222, 128, 0.9);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}

.ui-home-title {
  margin-bottom: 8px;
}

.ui-home-copy {
  margin: 0;
}

.ui-home-block-copy {
  margin-top: 0;
}

.ui-home-phase-row {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  gap: 10px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
}

.ui-home-phase-card {
  min-width: 220px;
  max-width: 220px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.02);
  display: grid;
  gap: 8px;
  scroll-snap-align: start;
}

.ui-home-phase-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ui-home-phase-id {
  font-size: 12px;
  color: var(--muted);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  padding: 2px 8px;
}

.ui-home-phase-title {
  font-weight: 600;
  font-size: 14px;
}

.ui-home-phase-focus {
  font-size: 12px;
  color: var(--muted);
  min-height: 34px;
}

.ui-home-phase-done {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.07);
}

.ui-home-phase-active {
  border-color: rgba(45, 212, 191, 0.72);
  background: rgba(45, 212, 191, 0.12);
  box-shadow: inset 0 0 0 1px rgba(45, 212, 191, 0.2);
}

.ui-home-phase-donut {
  --phase-progress: 0%;
  width: 66px;
  height: 66px;
  border-radius: 999px;
  background: conic-gradient(
    rgba(45, 212, 191, 0.9) var(--phase-progress),
    rgba(255, 255, 255, 0.16) 0
  );
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
}

.ui-home-phase-donut-inner {
  width: 48px;
  height: 48px;
  border-radius: 999px;
  background: rgba(11, 13, 18, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 900px) {
  .ui-home-intro {
    display: block;
  }
}
</style>
