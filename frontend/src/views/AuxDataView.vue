<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { useAuxDataPage } from '@/domains/aux-data';
import { FamilyMemberManager, OwnershipManager } from '@/domains/people';

const {
  loading,
  error,
  fxRates,
  inflation,
  fxStates,
  inflationStates,
  supportedInflationRegions,
  formatInflationIndex,
  formatFxRate,
} = useAuxDataPage();

const regionLabelMap = computed(
  () => new Map(supportedInflationRegions.value.map((region) => [region.code, region.label])),
);

const sections = reactive({
  family: true,
  ipc: true,
  fx: true,
});
type FamilyTab = 'members' | 'ownerships';
const familyTab = ref<FamilyTab>('members');

function toggleSection(section: 'family' | 'ipc' | 'fx'): void {
  sections[section] = !sections[section];
}

function formatTimestamp(value: string | null): string {
  if (!value) return '-';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('es-ES');
}
</script>

<template>
  <div class="container ui-pro-page">
    <h1 class="h1 ui-settings-page-title">Settings</h1>

    <div v-if="error" class="alert mt-3">{{ error }}</div>

    <section class="card ui-pro-panel ui-settings-accordion-item">
      <button
        class="ui-settings-toggle"
        type="button"
        :aria-expanded="sections.family"
        @click="toggleSection('family')"
      >
        <span class="ui-settings-toggle-title">Miembros de la familia</span>
        <span class="ui-settings-toggle-icon" aria-hidden="true">
          {{ sections.family ? '-' : '+' }}
        </span>
      </button>
      <div v-if="sections.family" class="ui-settings-content">
        <div class="ui-settings-family-tabs">
          <button
            class="btn opacity-60"
            type="button"
            :class="{ '!opacity-100': familyTab === 'members' }"
            @click="familyTab = 'members'"
          >
            Miembros
          </button>
          <button
            class="btn opacity-60"
            type="button"
            :class="{ '!opacity-100': familyTab === 'ownerships' }"
            @click="familyTab = 'ownerships'"
          >
            Titularidades
          </button>
        </div>

        <FamilyMemberManager v-if="familyTab === 'members'" />
        <OwnershipManager v-else />
      </div>
    </section>

    <section class="card ui-pro-panel ui-settings-accordion-item">
      <button
        class="ui-settings-toggle"
        type="button"
        :aria-expanded="sections.ipc"
        @click="toggleSection('ipc')"
      >
        <span class="ui-settings-toggle-title">Datos IPC</span>
        <span class="ui-settings-toggle-icon" aria-hidden="true">
          {{ sections.ipc ? '-' : '+' }}
        </span>
      </button>
      <div v-if="sections.ipc" class="ui-settings-content">
        <div class="ui-data-status-grid">
          <article v-for="state in inflationStates" :key="state.scope" class="ui-data-status-card">
            <div class="ui-data-status-card-head">
              <strong>{{ regionLabelMap.get(state.scope) ?? state.scope }}</strong>
              <span>{{ state.scope }}</span>
            </div>
            <div>Requerido desde: {{ state.required_start_date ?? '-' }}</div>
            <div>Cubierto hasta: {{ state.covered_until ?? '-' }}</div>
            <div>Ultimo exito: {{ formatTimestamp(state.last_success_at) }}</div>
            <div v-if="state.last_error" class="ui-form-help ui-form-help-error">
              {{ state.last_error }}
            </div>
          </article>
        </div>

        <table class="ui-data-table">
          <thead>
            <tr>
              <th>Periodo</th>
              <th>Region</th>
              <th>Indice</th>
              <th>Sync</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in inflation" :key="r.id">
              <td>{{ r.period }}</td>
              <td>{{ regionLabelMap.get(r.region) ?? r.region }}</td>
              <td>{{ formatInflationIndex(r.index) }}</td>
              <td>{{ r.last_synced_at ? formatTimestamp(r.last_synced_at) : '-' }}</td>
            </tr>
            <tr v-if="!inflation.length && !loading">
              <td colspan="4" class="ui-table-empty">No hay indices IPC sincronizados todavia.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card ui-pro-panel ui-settings-accordion-item">
      <button
        class="ui-settings-toggle"
        type="button"
        :aria-expanded="sections.fx"
        @click="toggleSection('fx')"
      >
        <span class="ui-settings-toggle-title">Tasas de conversion</span>
        <span class="ui-settings-toggle-icon" aria-hidden="true">
          {{ sections.fx ? '-' : '+' }}
        </span>
      </button>
      <div v-if="sections.fx" class="ui-settings-content">
        <div class="ui-data-status-grid">
          <article v-for="state in fxStates" :key="state.scope" class="ui-data-status-card">
            <div class="ui-data-status-card-head">
              <strong>{{ state.scope }}</strong>
              <span>FX</span>
            </div>
            <div>Requerido desde: {{ state.required_start_date ?? '-' }}</div>
            <div>Cubierto hasta: {{ state.covered_until ?? '-' }}</div>
            <div>Ultimo exito: {{ formatTimestamp(state.last_success_at) }}</div>
            <div v-if="state.last_error" class="ui-form-help ui-form-help-error">
              {{ state.last_error }}
            </div>
          </article>
        </div>

        <table class="ui-data-table">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Par</th>
              <th>Rate</th>
              <th>Sync</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in fxRates" :key="r.id">
              <td>{{ r.rate_date }}</td>
              <td>{{ r.from_currency }} -> {{ r.to_currency }}</td>
              <td>{{ formatFxRate(r.rate, r.from_currency, r.to_currency) }}</td>
              <td>{{ r.last_synced_at ? formatTimestamp(r.last_synced_at) : '-' }}</td>
            </tr>
            <tr v-if="!fxRates.length && !loading">
              <td colspan="4" class="ui-table-empty">No hay FX rates sincronizados todavia.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="loading" class="ui-status-line">Cargando datos auxiliares...</div>
  </div>
</template>
