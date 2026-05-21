<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { useAuxDataPage } from '@/domains/aux-data';
import { FamilyMemberManager, OwnershipManager } from '@/domains/people';

const {
  loading,
  error,
  syncError,
  syncSuccess,
  syncingInflation,
  syncingFx,
  fxRates,
  fxHasMore,
  fxLoadingMore,
  inflation,
  inflationHasMore,
  inflationLoadingMore,
  fxStates,
  inflationStates,
  supportedInflationRegions,
  formatInflationIndex,
  formatFxRate,
  loadMoreInflation,
  loadMoreFx,
  syncInflationNow,
  syncFxHistoryNow,
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

// Infinite scroll via IntersectionObserver
const inflationSentinel = ref<HTMLElement | null>(null);
const fxSentinel = ref<HTMLElement | null>(null);

let inflationObserver: IntersectionObserver | null = null;
let fxObserver: IntersectionObserver | null = null;

function setupObserver(
  el: HTMLElement,
  hasMore: { value: boolean },
  loadMore: () => void,
): IntersectionObserver {
  const obs = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting && hasMore.value) loadMore();
    },
    { threshold: 0.1 },
  );
  obs.observe(el);
  return obs;
}

watch(inflationSentinel, (el) => {
  inflationObserver?.disconnect();
  if (el) inflationObserver = setupObserver(el, inflationHasMore, loadMoreInflation);
});

watch(fxSentinel, (el) => {
  fxObserver?.disconnect();
  if (el) fxObserver = setupObserver(el, fxHasMore, loadMoreFx);
});

onBeforeUnmount(() => {
  inflationObserver?.disconnect();
  fxObserver?.disconnect();
});
</script>

<template>
  <div class="container ui-page-shell">
    <header class="ui-page-head">
      <div>
        <p class="ui-page-eyebrow">Datos auxiliares</p>
        <h1 class="ui-page-title ui-settings-page-title">Settings</h1>
      </div>
    </header>

    <div v-if="error" class="ui-state-block ui-state-error" role="alert">{{ error }}</div>

    <section class="ui-section-card ui-settings-accordion-item">
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

    <section class="ui-section-card ui-settings-accordion-item">
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
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <button class="btn" type="button" :disabled="syncingInflation" @click="syncInflationNow">
            {{ syncingInflation ? 'Sincronizando IPC...' : 'Actualizar IPC ahora' }}
          </button>
          <span v-if="syncSuccess" class="ui-form-help ui-form-help-success">{{ syncSuccess }}</span>
          <span v-if="syncError" class="ui-form-help ui-form-help-error">{{ syncError }}</span>
        </div>

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

        <div class="ui-data-table-wrap">
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
                <td colspan="4" class="ui-table-empty">
                  No hay indices IPC sincronizados todavia.
                </td>
              </tr>
            </tbody>
          </table>
          <div ref="inflationSentinel" class="ui-data-table-sentinel">
            <span v-if="inflationLoadingMore" class="ui-data-table-sentinel-label"
              >Cargando...</span
            >
          </div>
        </div>
      </div>
    </section>

    <section class="ui-section-card ui-settings-accordion-item">
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
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <button class="btn" type="button" :disabled="syncingFx" @click="syncFxHistoryNow">
            {{ syncingFx ? 'Sincronizando FX...' : 'Actualizar FX histórico' }}
          </button>
        </div>

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

        <div class="ui-data-table-wrap">
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
          <div ref="fxSentinel" class="ui-data-table-sentinel">
            <span v-if="fxLoadingMore" class="ui-data-table-sentinel-label">Cargando...</span>
          </div>
        </div>
      </div>
    </section>

    <div v-if="loading" class="ui-state-block ui-state-loading">Cargando datos auxiliares...</div>
  </div>
</template>
