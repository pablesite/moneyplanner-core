<script setup lang="ts">
/* eslint-disable vue/no-mutating-props */
import { computed, type PropType } from 'vue';
import BaseModal from '@/domains/ui/components/BaseModal.vue';

const props = defineProps({
  page: {
    type: Object as PropType<any>,
    required: true,
  },
  showUnmappedCategories: {
    type: Boolean,
    default: false,
  },
});

const unmappedCategories = computed(
  () => props.page.moneyWizImportPreview?.unmapped_categories ?? [],
);
const accountOptions = computed(() => props.page.operationalAccounts ?? []);
const linkedAccountOptions = computed(() =>
  accountOptions.value
    .filter((account: any) => account.asset_id != null || account.liability_id != null)
    .slice()
    .sort((left: any, right: any) =>
      accountLabel(left).localeCompare(accountLabel(right), 'es', { sensitivity: 'base' }),
    ),
);
const ledgerOnlyAccountOptions = computed(() =>
  accountOptions.value
    .filter((account: any) => account.asset_id == null && account.liability_id == null)
    .slice()
    .sort((left: any, right: any) =>
      accountLabel(left).localeCompare(accountLabel(right), 'es', { sensitivity: 'base' }),
    ),
);

function accountLabel(account: any): string {
  if (typeof props.page.accountDisplayName === 'function') {
    return props.page.accountDisplayName(account);
  }
  return account.display_name || account.name;
}
</script>

<template>
  <BaseModal
    :open="page.showMoneyWizImportModal"
    title="Importar CSV MoneyWiz"
    panel-class="max-w-[920px]"
    @close="page.showMoneyWizImportModal = false"
  >
    <div class="ui-accounting-modal-copy">
      <p class="ui-page-eyebrow">Importacion guiada</p>
      <p class="subtle">
        Sube el CSV exportado desde MoneyWiz, revisa la preview y confirma solo cuando no haya filas
        con errores.
      </p>
    </div>

    <form
      class="ui-accounting-form ui-accounting-modal-form"
      @submit.prevent="page.previewMoneyWizImportFromModal"
    >
      <div class="ui-accounting-import-dropzone">
        <label class="ui-accounting-field">
          <span>Archivo CSV</span>
          <input
            type="file"
            accept=".csv,text/csv"
            class="input"
            @change="page.handleMoneyWizFileChange"
          />
        </label>
        <p class="ui-accounting-inline-note">
          {{
            page.moneyWizImportFile
              ? `Archivo listo: ${page.moneyWizImportFile.name}`
              : 'Acepta el CSV exportado desde MoneyWiz con cabeceras en ingles.'
          }}
        </p>
      </div>

      <div v-if="page.moneyWizImportPreview" class="ui-accounting-import-summary">
        <div class="ui-accounting-import-kpis">
          <div class="ui-accounting-import-kpi">
            <span>Filas</span>
            <strong>{{ page.moneyWizImportPreview.row_count }}</strong>
          </div>
          <div class="ui-accounting-import-kpi">
            <span>Validas</span>
            <strong>{{ page.moneyWizImportPreview.valid_row_count }}</strong>
          </div>
          <div class="ui-accounting-import-kpi">
            <span>Errores</span>
            <strong>{{ page.moneyWizImportPreview.error_row_count }}</strong>
          </div>
          <div class="ui-accounting-import-kpi">
            <span>Ya existentes</span>
            <strong>{{ page.moneyWizImportPreview.existing_row_count }}</strong>
          </div>
        </div>

        <div class="ui-accounting-import-grid">
          <div class="ui-accounting-import-card">
            <h3>Tipos detectados</h3>
            <ul class="ui-accounting-import-list">
              <li>Ingresos: {{ page.moneyWizImportPreview.stats.income }}</li>
              <li>Gastos: {{ page.moneyWizImportPreview.stats.expense }}</li>
              <li>Transferencias: {{ page.moneyWizImportPreview.stats.transfer }}</li>
              <li>Inversion: {{ page.moneyWizImportPreview.stats.investment_purchase }}</li>
              <li>Deuda: {{ page.moneyWizImportPreview.stats.debt_payment }}</li>
            </ul>
          </div>

          <div class="ui-accounting-import-card">
            <h3>Cuentas detectadas</h3>
            <p class="subtle">
              Asocia cada cuenta del CSV a una cuenta existente para evitar duplicados.
            </p>
            <div class="ui-accounting-account-map">
              <div
                v-for="account in page.moneyWizImportPreview.detected_accounts"
                :key="`${account.role}-${account.account_type}-${account.name}`"
                class="ui-accounting-account-map-row"
              >
                <span class="ui-accounting-account-map-csv">{{ account.name }}</span>
                <span class="ui-accounting-account-map-arrow">-></span>
                <select
                  class="ui-accounting-account-map-select"
                  :value="page.moneyWizAccountMap[account.name] ?? ''"
                  @change="
                    (event) =>
                      page.updateMoneyWizAccountMap(
                        account.name,
                        (event.target as HTMLSelectElement).value,
                      )
                  "
                >
                  <option value="">Nueva cuenta</option>
                  <optgroup v-if="linkedAccountOptions.length" label="Activos/Pasivos vinculados">
                    <option
                      v-for="existing in linkedAccountOptions"
                      :key="existing.id"
                      :value="existing.id"
                    >
                      {{ accountLabel(existing) }} / {{ existing.currency }}
                    </option>
                  </optgroup>
                  <optgroup v-if="ledgerOnlyAccountOptions.length" label="Solo contables (legacy)">
                    <option
                      v-for="existing in ledgerOnlyAccountOptions"
                      :key="existing.id"
                      :value="existing.id"
                    >
                      {{ accountLabel(existing) }} / {{ existing.currency }}
                    </option>
                  </optgroup>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="showUnmappedCategories && unmappedCategories.length"
          class="ui-state-block ui-state-empty"
        >
          <strong> Categorias sin mapeo automatico ({{ unmappedCategories.length }}) </strong>
          <p class="subtle">
            Estas categorias de MoneyWiz no tienen equivalencia exacta. Se importaran con la
            clasificacion de fallback indicada. Revisa si es correcta antes de confirmar.
          </p>
          <ul class="ui-accounting-import-list">
            <li v-for="uc in unmappedCategories" :key="`${uc.movement_type}-${uc.category_raw}`">
              <span class="subtle">{{ uc.category_raw }}</span>
              <span class="ui-accounting-inline-note">
                -> {{ uc.fallback_category_key }}/{{ uc.fallback_subcategory_key }} ({{
                  uc.row_count
                }}
                {{ uc.row_count === 1 ? 'fila' : 'filas' }})
              </span>
            </li>
          </ul>
        </div>

        <div v-if="page.moneyWizPreviewWarnings.length" class="ui-state-block ui-state-empty">
          <strong>Warnings de preview</strong>
          <ul class="ui-accounting-import-list">
            <li v-for="warning in page.moneyWizPreviewWarnings.slice(0, 5)" :key="warning">
              {{ warning }}
            </li>
          </ul>
        </div>

        <div class="ui-accounting-import-card">
          <h3>Primeras filas</h3>
          <div class="ui-accounting-import-rows">
            <article
              v-for="row in page.moneyWizPreviewRows"
              :key="row.fingerprint"
              class="ui-accounting-import-row"
            >
              <div class="ui-accounting-import-row-head">
                <strong>#{{ row.row_number }} - {{ row.description }}</strong>
                <span>{{ row.movement_type }} - {{ row.amount }} {{ row.currency }}</span>
              </div>
              <p class="subtle">
                {{ row.account_name }}
                <template v-if="row.counterparty_name">-> {{ row.counterparty_name }}</template>
                <template v-if="row.category">- {{ row.category }}</template>
              </p>
              <p v-if="row.warnings.length" class="ui-accounting-inline-note">
                {{ row.warnings[0] }}
              </p>
              <p v-if="row.errors.length" class="ui-state-block ui-state-error">
                {{ row.errors[0] }}
              </p>
            </article>
          </div>
        </div>
      </div>

      <div class="ui-accounting-submit-row">
        <p class="subtle">
          {{
            page.moneyWizImportPreview
              ? page.moneyWizCanCommit
                ? 'La preview esta lista. Al confirmar se refrescaran movimientos, saldos y resumen mensual.'
                : 'La preview necesita revision: si hay filas con errores no se habilita el commit.'
              : 'Empieza generando la preview para revisar warnings, duplicados y cuentas detectadas.'
          }}
        </p>
        <div class="ui-accounting-inline-actions">
          <button
            class="btn"
            type="submit"
            :disabled="page.importPreviewLoading || page.importCommitLoading"
          >
            {{ page.importPreviewLoading ? 'Preparando preview...' : 'Generar preview' }}
          </button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="
              page.importCommitLoading || page.importPreviewLoading || !page.moneyWizCanCommit
            "
            @click="page.commitMoneyWizImportFromModal"
          >
            {{ page.importCommitLoading ? 'Importando...' : 'Confirmar importacion' }}
          </button>
        </div>
      </div>
    </form>
  </BaseModal>
</template>
