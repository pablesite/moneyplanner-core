<script setup lang="ts">
type BudgetSection = {
  id: 'income' | 'expense';
  title: string;
  subtitle: string;
  emptyMessage: string;
  toneClass: string;
  totalAnnual: number;
  filterMode: 'all' | 'recurrent' | 'one_off';
  categoryCount: number;
  subcategoryCount: number;
  groups: any[];
};

defineProps<{
  isMonthlyCloseView: boolean;
  hasAnyPlannedData: boolean;
  isLoading: boolean;
  fiscalYear: number;
  sections: BudgetSection[];
  monthLabels: string[];
  incomeEvolutionMonths: any[];
  incomeEvolutionBaseMonthly: number;
  selectedExecutionMonthLabel: string;
  formatMoney: (value: number, decimals?: number) => string;
  formatCompactMoney: (value: number, decimals?: number) => string;
  formatPercent: (value: number | null, decimals?: number) => string;
  formatSignedMoney: (value: number, decimals?: number) => string;
  isSectionExpanded: (sectionId: 'income' | 'expense') => boolean;
  toggleSectionExpanded: (sectionId: 'income' | 'expense') => void;
  budgetCategoryActualExecution: (...args: any[]) => any;
  budgetSubcategoryActualExecution: (...args: any[]) => any;
  executionPreview: (...args: any[]) => any;
  updateIncomeViewMode: (mode: 'all' | 'recurrent' | 'one_off') => void;
  updateExpenseViewMode: (mode: 'all' | 'recurrent' | 'one_off') => void;
}>();
</script>

<template>
  <section
    v-if="!isMonthlyCloseView && !hasAnyPlannedData && !isLoading"
    class="card ui-pro-panel ui-budget-empty mt-3"
  >
    <h2 class="mt-0">Sin presupuesto anual para {{ fiscalYear }}</h2>
    <p class="subtle mb-0">
      Carga primero `Ingresos anuales` y `Gastos anuales` en `Introduccion de datos` para ver el
      dashboard.
    </p>
    <RouterLink class="ui-budget-empty-link" to="/introduccion-datos">
      Ir a Introduccion de datos
    </RouterLink>
  </section>

  <section
    v-for="section in sections"
    v-show="!isMonthlyCloseView"
    :key="section.id"
    class="card ui-pro-panel ui-budget-section mt-3"
    :class="section.toneClass"
  >
    <div class="ui-budget-section-header">
      <div>
        <h2 class="ui-budget-section-title">{{ section.title }}</h2>
        <p class="ui-budget-section-subtitle">{{ section.subtitle }}</p>
      </div>
      <div class="ui-budget-section-header-side">
        <div class="ui-budget-section-controls">
          <button
            v-if="section.groups.length"
            type="button"
            class="ui-budget-detail-toggle"
            :aria-expanded="isSectionExpanded(section.id)"
            @click="toggleSectionExpanded(section.id)"
          >
            <span class="ui-budget-detail-toggle-icon" aria-hidden="true">
              {{ isSectionExpanded(section.id) ? '-' : '+' }}
            </span>
            <span>
              {{
                isSectionExpanded(section.id)
                  ? 'Ocultar detalle'
                  : `Ver detalle (${section.categoryCount} categorias · ${section.subcategoryCount} subcategorias)`
              }}
            </span>
          </button>

          <div
            class="ui-budget-filter-segment"
            role="tablist"
            :aria-label="`Filtro de ${section.title}`"
          >
            <button
              type="button"
              class="ui-budget-filter-btn"
              :class="{ 'ui-budget-filter-btn-active': section.filterMode === 'all' }"
              @click="
                section.id === 'income' ? updateIncomeViewMode('all') : updateExpenseViewMode('all')
              "
            >
              Todos
            </button>
            <button
              type="button"
              class="ui-budget-filter-btn"
              :class="{ 'ui-budget-filter-btn-active': section.filterMode === 'recurrent' }"
              @click="
                section.id === 'income'
                  ? updateIncomeViewMode('recurrent')
                  : updateExpenseViewMode('recurrent')
              "
            >
              Recurrentes
            </button>
            <button
              type="button"
              class="ui-budget-filter-btn"
              :class="{ 'ui-budget-filter-btn-active': section.filterMode === 'one_off' }"
              @click="
                section.id === 'income'
                  ? updateIncomeViewMode('one_off')
                  : updateExpenseViewMode('one_off')
              "
            >
              Puntuales
            </button>
          </div>
        </div>

        <div class="ui-budget-section-total">
          <strong>{{ formatMoney(section.totalAnnual) }} EUR</strong>
          <small>{{ formatMoney(section.totalAnnual / 12) }} EUR/mes</small>
        </div>
      </div>
    </div>

    <div class="ui-budget-evolution-card">
      <div class="ui-budget-evolution-head">
        <div>
          <h3>Evolucion ejecutada (barras)</h3>
          <p v-if="section.id === 'income'">
            Compara `Previsto` vs `Ejecutado` por mes usando los check-ins del cierre mensual
            (ingresos recurrentes).
          </p>
          <p v-else>
            Preparado para comparar `Previsto` vs `Ejecutado` por mes. Actualmente en modo
            placeholder hasta implementar contabilidad.
          </p>
        </div>
        <span class="ui-budget-pill">
          {{ section.id === 'income' ? 'Cierre mensual activo' : 'Pendiente contabilidad' }}
        </span>
      </div>

      <div
        class="ui-budget-evolution-bars"
        :aria-label="
          section.id === 'income'
            ? 'Barras de evolucion de ingresos previsto vs ejecutado por mes'
            : 'Placeholder de barras de evolucion'
        "
      >
        <div
          v-for="point in section.id === 'income'
            ? incomeEvolutionMonths
            : monthLabels.map((label) => ({ label }))"
          :key="`${section.id}-${point.label}`"
          class="ui-budget-month-col"
        >
          <div class="ui-budget-month-rail">
            <div
              class="ui-budget-month-plan"
              :style="
                section.id === 'income' && 'planHeightPct' in point
                  ? { height: `${point.planHeightPct}%` }
                  : undefined
              "
              :title="
                section.id === 'income' && 'planned' in point
                  ? `Previsto ${point.label}: ${formatMoney(Number(point.planned))} EUR`
                  : undefined
              "
            />
            <div
              :class="
                section.id === 'income' && 'hasExecuted' in point && point.hasExecuted
                  ? 'ui-budget-month-exec'
                  : 'ui-budget-month-exec-pending'
              "
              :style="
                section.id === 'income' && 'execHeightPct' in point
                  ? { height: `${point.execHeightPct}%` }
                  : undefined
              "
              :title="
                section.id === 'income' && 'executed' in point
                  ? `Ejecutado ${point.label}: ${formatMoney(Number(point.executed))} EUR`
                  : undefined
              "
            />
          </div>
          <span class="ui-budget-month-label">{{ point.label }}</span>
        </div>
      </div>

      <div class="ui-budget-evolution-legend">
        <span><i class="ui-budget-legend-dot ui-budget-legend-plan" /> Previsto</span>
        <span v-if="section.id === 'income'">
          <i class="ui-budget-legend-dot ui-budget-legend-exec-solid" /> Ejecutado
        </span>
        <span v-else>
          <i class="ui-budget-legend-dot ui-budget-legend-exec" /> Ejecutado (pendiente)
        </span>
        <span>
          {{ section.id === 'income' ? 'Base recurrente mensual:' : 'Base mensual orientativa:' }}
          <strong>
            {{
              formatCompactMoney(
                section.id === 'income' ? incomeEvolutionBaseMonthly : section.totalAnnual / 12,
              )
            }}
            EUR
          </strong>
        </span>
      </div>
    </div>

    <div v-if="section.groups.length && isSectionExpanded(section.id)" class="ui-budget-groups">
      <article
        v-for="group in section.groups"
        :key="`${section.id}-${group.categoryKey}`"
        class="ui-budget-group"
      >
        <header class="ui-budget-group-header">
          <div class="ui-budget-group-title-wrap">
            <div class="ui-budget-group-kicker">Categoria</div>
            <h3>{{ group.categoryLabel }}</h3>
            <p>
              {{ group.rows.length }} subcategorias ·
              {{ formatPercent(group.shareOfSection, 0) }} de {{ section.title.toLowerCase() }}
            </p>

            <div
              v-if="budgetCategoryActualExecution(section.id, group.categoryKey)"
              class="ui-budget-inline-progress"
              :aria-label="`Ejecucion YTD categoria ${group.categoryLabel}`"
            >
              <div class="ui-budget-inline-progress-labels">
                <span
                  >Previsto vs Ejecutado acumulado (YTD hasta
                  {{ selectedExecutionMonthLabel }})</span
                >
                <span>
                  {{
                    formatPercent(
                      budgetCategoryActualExecution(section.id, group.categoryKey)
                        ?.completionRatio ?? null,
                      0,
                    )
                  }}
                  completitud
                  <span
                    class="ui-budget-inline-progress-preview-pill"
                    :class="`ui-budget-inline-progress-preview-pill-${budgetCategoryActualExecution(section.id, group.categoryKey)?.tone}`"
                  >
                    {{
                      formatPercent(
                        budgetCategoryActualExecution(section.id, group.categoryKey)?.ratio ?? null,
                        0,
                      )
                    }}
                  </span>
                </span>
              </div>
              <div class="ui-budget-inline-progress-track ui-budget-inline-progress-track-lg">
                <div
                  class="ui-budget-inline-progress-fill"
                  :class="`ui-budget-inline-progress-fill-${budgetCategoryActualExecution(section.id, group.categoryKey)?.tone}`"
                  :style="{
                    width: `${budgetCategoryActualExecution(section.id, group.categoryKey)?.widthPct ?? 8}%`,
                  }"
                />
                <span
                  v-if="budgetCategoryActualExecution(section.id, group.categoryKey)?.overflow"
                  class="ui-budget-inline-progress-overflow-marker"
                  aria-hidden="true"
                />
              </div>
            </div>

            <div
              v-else
              class="ui-budget-inline-progress"
              aria-label="Placeholder ejecucion categoria"
            >
              <div class="ui-budget-inline-progress-labels">
                <span>Previsto vs Ejecutado</span>
                <span>
                  Pendiente contabilidad
                  <span
                    class="ui-budget-inline-progress-preview-pill"
                    :class="`ui-budget-inline-progress-preview-pill-${executionPreview(section.id, `group:${group.categoryKey}`).tone}`"
                  >
                    {{
                      formatPercent(
                        executionPreview(section.id, `group:${group.categoryKey}`).ratio,
                        0,
                      )
                    }}
                  </span>
                </span>
              </div>
              <div class="ui-budget-inline-progress-track ui-budget-inline-progress-track-lg">
                <div
                  class="ui-budget-inline-progress-fill"
                  :class="`ui-budget-inline-progress-fill-${executionPreview(section.id, `group:${group.categoryKey}`).tone}`"
                  :style="{
                    width: `${executionPreview(section.id, `group:${group.categoryKey}`).widthPct}%`,
                  }"
                />
                <span
                  v-if="executionPreview(section.id, `group:${group.categoryKey}`).overflow"
                  class="ui-budget-inline-progress-overflow-marker"
                  aria-hidden="true"
                />
              </div>
            </div>
          </div>

          <div class="ui-budget-group-amount">{{ formatMoney(group.plannedAnnual) }} EUR</div>
        </header>

        <ul class="ui-budget-rows">
          <li v-for="row in group.rows" :key="row.key" class="ui-budget-row">
            <div class="ui-budget-row-main">
              <div class="ui-budget-row-kicker">Subcategoria</div>
              <div class="ui-budget-row-title">{{ row.subcategoryLabel }}</div>
              <div class="ui-budget-row-meta">
                {{ row.itemsCount }} registro{{ row.itemsCount === 1 ? '' : 's' }} ·
                {{ formatMoney(row.plannedAnnual / 12) }} EUR/mes previsto
              </div>

              <div
                v-if="budgetSubcategoryActualExecution(section.id, row.key)"
                class="ui-budget-inline-progress ui-budget-inline-progress-row"
                :aria-label="`Ejecucion YTD subcategoria ${row.subcategoryLabel}`"
              >
                <div class="ui-budget-inline-progress-track">
                  <div
                    class="ui-budget-inline-progress-fill"
                    :class="`ui-budget-inline-progress-fill-${budgetSubcategoryActualExecution(section.id, row.key)?.tone}`"
                    :style="{
                      width: `${budgetSubcategoryActualExecution(section.id, row.key)?.widthPct ?? 8}%`,
                    }"
                  />
                  <span
                    v-if="budgetSubcategoryActualExecution(section.id, row.key)?.overflow"
                    class="ui-budget-inline-progress-overflow-marker"
                    aria-hidden="true"
                  />
                </div>
                <div class="ui-budget-inline-progress-caption">
                  YTD hasta {{ selectedExecutionMonthLabel }} - completitud
                  {{
                    formatPercent(
                      budgetSubcategoryActualExecution(section.id, row.key)?.completionRatio ??
                        null,
                      0,
                    )
                  }}
                  <span
                    :class="`ui-budget-inline-progress-caption-tone-${budgetSubcategoryActualExecution(section.id, row.key)?.tone}`"
                  >
                    {{
                      formatPercent(
                        budgetSubcategoryActualExecution(section.id, row.key)?.ratio ?? null,
                        0,
                      )
                    }}
                  </span>
                </div>
              </div>

              <div
                v-else
                class="ui-budget-inline-progress ui-budget-inline-progress-row"
                aria-label="Placeholder ejecucion subcategoria"
              >
                <div class="ui-budget-inline-progress-track">
                  <div
                    class="ui-budget-inline-progress-fill"
                    :class="`ui-budget-inline-progress-fill-${executionPreview(section.id, `row:${row.key}`).tone}`"
                    :style="{
                      width: `${executionPreview(section.id, `row:${row.key}`).widthPct}%`,
                    }"
                  />
                  <span
                    v-if="executionPreview(section.id, `row:${row.key}`).overflow"
                    class="ui-budget-inline-progress-overflow-marker"
                    aria-hidden="true"
                  />
                </div>
                <div class="ui-budget-inline-progress-caption">
                  Ejecucion pendiente · preview
                  <span
                    :class="`ui-budget-inline-progress-caption-tone-${executionPreview(section.id, `row:${row.key}`).tone}`"
                  >
                    {{ formatPercent(executionPreview(section.id, `row:${row.key}`).ratio, 0) }}
                  </span>
                </div>
              </div>
            </div>

            <div class="ui-budget-row-metrics">
              <div class="ui-budget-row-metric">
                <span>{{
                  budgetSubcategoryActualExecution(section.id, row.key)
                    ? 'Previsto YTD'
                    : 'Previsto'
                }}</span>
                <strong>
                  {{
                    budgetSubcategoryActualExecution(section.id, row.key)
                      ? `${formatMoney(budgetSubcategoryActualExecution(section.id, row.key)?.planned ?? 0)} EUR`
                      : `${formatMoney(row.plannedAnnual)} EUR`
                  }}
                </strong>
              </div>
              <div class="ui-budget-row-metric">
                <span>{{
                  budgetSubcategoryActualExecution(section.id, row.key)
                    ? 'Ejecutado YTD'
                    : 'Ejecutado'
                }}</span>
                <strong
                  class="ui-budget-pending-text"
                  :class="`ui-budget-pending-text-${budgetSubcategoryActualExecution(section.id, row.key)?.tone ?? executionPreview(section.id, `row:${row.key}`).tone}`"
                >
                  {{
                    budgetSubcategoryActualExecution(section.id, row.key)
                      ? `${formatMoney(budgetSubcategoryActualExecution(section.id, row.key)?.executed ?? 0)} EUR`
                      : 'Pendiente'
                  }}
                </strong>
              </div>
              <div class="ui-budget-row-metric">
                <span>{{
                  budgetSubcategoryActualExecution(section.id, row.key)
                    ? 'Desviacion YTD'
                    : 'Desviacion'
                }}</span>
                <strong
                  class="ui-budget-pending-text"
                  :class="`ui-budget-pending-text-${budgetSubcategoryActualExecution(section.id, row.key)?.tone ?? executionPreview(section.id, `row:${row.key}`).tone}`"
                >
                  {{
                    budgetSubcategoryActualExecution(section.id, row.key)
                      ? `${formatSignedMoney(budgetSubcategoryActualExecution(section.id, row.key)?.deviation ?? 0)} EUR`
                      : 'Pendiente'
                  }}
                </strong>
              </div>
            </div>
          </li>
        </ul>
      </article>
    </div>

    <div
      v-else-if="section.groups.length && !isSectionExpanded(section.id)"
      class="ui-budget-detail-collapsed-note"
    >
      Vista compacta activa. Se muestran resumen y evolucion ejecutada. Pulsa en `Ver detalle` para
      desplegar categorias y subcategorias.
    </div>

    <div v-else class="subtle">
      {{ section.emptyMessage }}
      <template v-if="section.filterMode !== 'all'">
        Prueba con la vista `Todos` si quieres incluir movimientos puntuales.
      </template>
    </div>
  </section>

  <div v-if="isLoading" class="ui-status-line">Cargando presupuesto...</div>
</template>
