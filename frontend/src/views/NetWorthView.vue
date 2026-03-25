<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  NetWorthTimelineChart,
  useNetWorthViewExtensions,
  useNetWorthViewState,
} from '@/domains/net-worth';
import NetWorthCategoryWorkspace from '@/domains/net-worth/components/NetWorthCategoryWorkspace.vue';
import NetWorthHeroSection from '@/domains/net-worth/components/NetWorthHeroSection.vue';
import NetWorthItemModals from '@/domains/net-worth/components/NetWorthItemModals.vue';
import NetWorthTimelineMain from '@/domains/net-worth/components/NetWorthTimelineMain.vue';
import type { NetWorthWritePayload } from '@/domains/net-worth/models';
import '@/domains/net-worth/net-worth-view.css';
import { useNetWorthAccountingActivity } from '@/domains/net-worth/useNetWorthAccountingActivity';
import { useNetWorthOwnership } from '@/domains/net-worth/useNetWorthOwnership';
import {
  useNetWorthPageMetrics,
  type PositionRow,
} from '@/domains/net-worth/useNetWorthPageMetrics';
import { useNetWorthPositionActivity } from '@/domains/net-worth/useNetWorthPositionActivity';
import { useNetWorthPageActions } from '@/domains/net-worth/useNetWorthPageActions';
import { useNetWorthTimeline } from '@/domains/net-worth/useNetWorthTimeline';
import { useNetWorthTimelineLayout } from '@/domains/net-worth/useNetWorthTimelineLayout';
import { BaseModal } from '@/domains/ui';
import { useAnnualExpenseStore } from '@/domains/data-input';
import { toApiErrorMessage } from '@/lib/errors';

const {
  store,
  valueMode,
  currencies,
  assetCategories,
  liabilityCategories,
  prettyError,
  canShowReal,
  showAssetModal,
  showLiabilityModal,
  showEditModal,
  editItem,
  editKind,
  unitLabel,
  modeLabel,
  realBaseLabel,
  assetSubcategories,
  summaryAssets,
  summaryLiabilities,
  summaryNetWorth,
  byCategoryKeys,
  byCategoryAssets,
  byCategoryLiabilities,
  summaryAssetBackedLiabilities,
  summaryUnbackedLiabilities,
  submitAsset,
  openEdit,
  closeEdit,
  editTitle,
  editCategories,
  editInitial,
  submitEdit,
  editError,
} = useNetWorthViewState();
const annualExpenseStore = useAnnualExpenseStore('core');

const { itemFormProps } = useNetWorthViewExtensions(store);

const inflationRegions = [
  { code: 'ES', label: 'Espana' },
  { code: 'ES-AN', label: 'Andalucia' },
  { code: 'ES-AR', label: 'Aragon' },
  { code: 'ES-AS', label: 'Asturias' },
  { code: 'ES-IB', label: 'Illes Balears' },
  { code: 'ES-CN', label: 'Canarias' },
  { code: 'ES-CB', label: 'Cantabria' },
  { code: 'ES-CL', label: 'Castilla y Leon' },
  { code: 'ES-CM', label: 'Castilla-La Mancha' },
  { code: 'ES-CT', label: 'Cataluna' },
  { code: 'ES-VC', label: 'Comunitat Valenciana' },
  { code: 'ES-EX', label: 'Extremadura' },
  { code: 'ES-GA', label: 'Galicia' },
  { code: 'ES-MD', label: 'Comunidad de Madrid' },
  { code: 'ES-MC', label: 'Region de Murcia' },
  { code: 'ES-NC', label: 'Comunidad Foral de Navarra' },
  { code: 'ES-PV', label: 'Pais Vasco' },
  { code: 'ES-RI', label: 'La Rioja' },
  { code: 'ES-CE', label: 'Ceuta' },
  { code: 'ES-ML', label: 'Melilla' },
];

function toNumber(raw: unknown): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const value = Number(normalized);
  return Number.isFinite(value) ? value : 0;
}

function formatNumber(n: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatPct(n: number | null, decimals = 0): string {
  if (n == null || !Number.isFinite(n)) return '-';
  return new Intl.NumberFormat('es-ES', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function displayCurrencyUnit(currency: string | null | undefined): string {
  return currency === 'EUR' ? '€' : String(currency ?? '').trim();
}

type GeneratedLiabilityExpensePreview = {
  id: number;
  fiscalYear: number;
  name: string;
  category: string;
  subcategory: string;
  amountAnnual: number;
  currency: string;
};

const showGeneratedLiabilityExpenseModal = ref(false);
const generatedLiabilityExpenseReview = ref<{
  liabilityId: number;
  liabilityName: string;
  entries: GeneratedLiabilityExpensePreview[];
} | null>(null);
const generatedLiabilityExpenseReviewChangeMessage = ref<string | null>(null);
const generatedLiabilityExpenseReviewTitle = computed(() =>
  generatedLiabilityExpenseReview.value
    ? `Gasto generado por pasivo: ${generatedLiabilityExpenseReview.value.liabilityName}`
    : 'Gasto generado por pasivo',
);

function setGeneratedLiabilityExpenseReview(
  liabilityId: number,
  liabilityName: string,
  entries: GeneratedLiabilityExpensePreview[],
): void {
  generatedLiabilityExpenseReview.value = {
    liabilityId,
    liabilityName,
    entries: entries.map((entry) => ({ ...entry })),
  };
}

function mapGeneratedExpenseEntries(
  entries: Awaited<ReturnType<typeof annualExpenseStore.listBySourceLiability>>,
): GeneratedLiabilityExpensePreview[] {
  return entries
    .filter((entry) => entry.isSystemGenerated && entry.sourceLiabilityId != null)
    .sort((a, b) => a.fiscalYear - b.fiscalYear)
    .map((entry) => ({
      id: entry.id,
      fiscalYear: entry.fiscalYear,
      name: entry.name,
      category: entry.category,
      subcategory: entry.subcategory,
      amountAnnual: entry.amountAnnual,
      currency: entry.currency,
    }));
}

function summarizeGeneratedLiabilityExpenseChanges(
  beforeEntries: GeneratedLiabilityExpensePreview[],
  afterEntries: GeneratedLiabilityExpensePreview[],
): string | null {
  const toYearTotals = (rows: GeneratedLiabilityExpensePreview[]) => {
    const totals = new Map<number, number>();
    for (const row of rows) {
      totals.set(row.fiscalYear, (totals.get(row.fiscalYear) ?? 0) + Number(row.amountAnnual ?? 0));
    }
    return totals;
  };
  const beforeTotals = toYearTotals(beforeEntries);
  const afterTotals = toYearTotals(afterEntries);
  const years = Array.from(new Set([...beforeTotals.keys(), ...afterTotals.keys()])).sort(
    (a, b) => a - b,
  );
  const changedYears: number[] = [];
  for (const year of years) {
    const before = beforeTotals.get(year) ?? 0;
    const after = afterTotals.get(year) ?? 0;
    if (Math.abs(before - after) > 0.009) changedYears.push(year);
  }
  const addedYears = years.filter(
    (year) => (beforeTotals.get(year) ?? 0) <= 0 && (afterTotals.get(year) ?? 0) > 0,
  );
  const removedYears = years.filter(
    (year) => (beforeTotals.get(year) ?? 0) > 0 && (afterTotals.get(year) ?? 0) <= 0,
  );
  if (!changedYears.length && !addedYears.length && !removedYears.length) return null;
  const chunks: string[] = [];
  if (changedYears.length) chunks.push(`Importes actualizados en: ${changedYears.join(', ')}`);
  if (addedYears.length) chunks.push(`Nuevas anualidades: ${addedYears.join(', ')}`);
  if (removedYears.length) chunks.push(`Anualidades eliminadas: ${removedYears.join(', ')}`);
  return chunks.join(' | ');
}

function closeGeneratedLiabilityExpenseModal(): void {
  showGeneratedLiabilityExpenseModal.value = false;
  generatedLiabilityExpenseReview.value = null;
  generatedLiabilityExpenseReviewChangeMessage.value = null;
}

function openGeneratedExpensesInBudget(): void {
  closeGeneratedLiabilityExpenseModal();
  window.location.assign('/presupuesto');
}

async function submitLiabilityWithExpenseReview(
  payload: NetWorthWritePayload & { ownership_id?: number | null },
): Promise<void> {
  const createdLiability = await store.createLiability(payload);
  if (!createdLiability) return;
  showLiabilityModal.value = false;
  try {
    const generatedEntries = await annualExpenseStore.listBySourceLiability(createdLiability.id);
    const systemGeneratedEntries = mapGeneratedExpenseEntries(generatedEntries);
    if (!systemGeneratedEntries.length) return;
    generatedLiabilityExpenseReviewChangeMessage.value = null;
    setGeneratedLiabilityExpenseReview(
      createdLiability.id,
      createdLiability.name,
      systemGeneratedEntries,
    );
    showGeneratedLiabilityExpenseModal.value = true;
  } catch (e: unknown) {
    store.error = `Pasivo creado, pero no se pudo cargar el gasto generado: ${toApiErrorMessage(e)}`;
  }
}

async function updateLiabilityAndShowExpenseReview(
  id: number,
  payload: NetWorthWritePayload & { ownership_id?: number | null },
): Promise<void> {
  let beforeEntries: GeneratedLiabilityExpensePreview[] = [];
  try {
    beforeEntries = mapGeneratedExpenseEntries(await annualExpenseStore.listBySourceLiability(id));
  } catch {
    beforeEntries = [];
  }
  await store.updateLiability(id, payload);
  if (store.error) return;
  try {
    const refreshedEntries = mapGeneratedExpenseEntries(
      await annualExpenseStore.listBySourceLiability(id),
    );
    if (!refreshedEntries.length) return;
    const liabilityName = store.liabilities.find((item) => item.id === id)?.name ?? 'Pasivo';
    generatedLiabilityExpenseReviewChangeMessage.value = summarizeGeneratedLiabilityExpenseChanges(
      beforeEntries,
      refreshedEntries,
    );
    setGeneratedLiabilityExpenseReview(id, liabilityName, refreshedEntries);
    showGeneratedLiabilityExpenseModal.value = true;
  } catch (e: unknown) {
    store.error = `Pasivo actualizado, pero no se pudo cargar el gasto generado: ${toApiErrorMessage(e)}`;
  }
}

async function submitEditWithExpenseReview(
  payload: NetWorthWritePayload & { ownership_id?: number | null },
): Promise<void> {
  const current = editItem.value;
  if (!current || !editKind.value) return;
  if (editKind.value === 'asset') {
    await submitEdit(payload);
    return;
  }
  await updateLiabilityAndShowExpenseReview(current.id, payload);
  closeEdit();
}

const {
  ownershipFilter,
  ownershipOptions,
  selectedOwnershipFilterLabel,
  ownershipFilterDisabled,
  allocationFractionForNetWorthOwner,
  matchesOwnershipFilter,
  ownershipBadge,
  setOwnershipFilter,
  setValueMode,
} = useNetWorthOwnership({
  ownerships: computed(() => store.ownerships),
  valueMode,
});
const heroUnitLabel = computed(() => displayCurrencyUnit(unitLabel()));

watch(ownershipFilter, async () => {
  clearPositionSelection();
  if (
    selectedTimelineCategory.value &&
    !effectiveCategoryKeys.value.includes(selectedTimelineCategory.value)
  ) {
    selectedTimelineCategory.value = null;
    selectedTimelineCategoryType.value = 'asset';
    await store.fetchTimeline(null, 'asset');
  }
});

const selectedTimelineCategory = ref<string | null>(null);
const selectedTimelineCategoryType = ref<'asset' | 'liability'>('asset');
const selectedPositionType = ref<'asset' | 'liability' | null>(null);
const selectedPositionId = ref<number | null>(null);
const createAssetCategory = ref<string | null>(null);
const createLiabilityCategory = ref<string | null>(null);
const timelineExpanded = ref(false);
const selectedTimelinePreset = ref<'1m' | '3m' | '6m' | '1a' | 'all'>('all');
const customTimelineWindow = ref<{ start: number; end: number } | null>(null);
const timelinePresetOptions = ['1m', '3m', '6m', '1a', 'all'] as const;

type TimelinePoint = {
  date: string;
  label: string;
  netWorth: number;
  assets: number;
  liabilities: number;
};

const timelineMetric = computed<'net_worth' | 'assets' | 'liabilities'>(() => {
  if (!selectedTimelineCategory.value) return 'net_worth';
  return selectedTimelineCategoryType.value === 'liability' ? 'liabilities' : 'assets';
});

function getTimelineMetricValue(row: TimelinePoint): number {
  if (timelineMetric.value === 'assets') return row.assets;
  if (timelineMetric.value === 'liabilities') return row.liabilities;
  return row.netWorth;
}

const timelineRows = computed<TimelinePoint[]>(() =>
  (store.timeline?.rows ?? []).map((row) => ({
    date: row.date,
    label: new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit' }).format(
      new Date(row.date),
    ),
    netWorth: toNumber(row.net_worth),
    assets: toNumber(row.total_assets),
    liabilities: toNumber(row.total_liabilities),
  })),
);

const {
  selectedCategoryLabel,
  allAssetPositionRows,
  allLiabilityPositionRows,
  effectiveCategoryKeys,
  effectiveCategoryLabels,
  effectiveCategoryAssets,
  effectiveCategoryLiabilities,
  effectiveCategoryAssetCounts,
  effectiveCategoryLiabilityCounts,
  analysis,
  availablePositionRows,
  activeAssets,
  categoryWorkspaceRows,
  categoryWorkspaceCount,
  categoryWorkspaceTotal,
  showCategoryWorkspace,
  sourceItemForRow,
  selectedPosition,
  selectedPositionSource,
  positionTimelineRows,
} = useNetWorthPageMetrics({
  assets: computed(() => store.assets),
  liabilities: computed(() => store.liabilities),
  baseCurrency: computed(() => store.baseCurrency),
  summary: computed(() => store.summary),
  positionTimelineRowsSource: computed(() => store.positionTimeline?.rows ?? []),
  assetCategories,
  liabilityCategories,
  byCategoryKeys,
  byCategoryAssets,
  byCategoryLiabilities,
  summaryAssets,
  summaryLiabilities,
  summaryNetWorth,
  summaryAssetBackedLiabilities,
  summaryUnbackedLiabilities,
  ownershipFilter,
  selectedTimelineCategory,
  selectedTimelineCategoryType,
  selectedPositionType,
  selectedPositionId,
  matchesOwnershipFilter,
  allocationFractionForNetWorthOwner,
});

function ownershipBadgeForRow(row: PositionRow): string | null {
  return ownershipBadge(sourceItemForRow(row)?.ownership_ref);
}

function editRow(row: PositionRow): void {
  const item = sourceItemForRow(row);
  if (!item) return;
  openEdit(item, row.type);
}

async function deleteRow(row: PositionRow): Promise<void> {
  const label = row.type === 'asset' ? 'activo' : 'pasivo';
  if (!confirm(`Eliminar este ${label}? Esta accion no se puede deshacer.`)) return;
  if (row.type === 'asset') {
    await store.deleteAsset(row.id);
  } else {
    await store.deleteLiability(row.id);
  }
}

const categoryWorkspaceLabel = computed(() => {
  if (!selectedTimelineCategory.value) return '';
  const scope = selectedTimelineCategoryType.value === 'liability' ? 'pasivos' : 'activos';
  return `${selectedCategoryLabel.value} dentro de ${scope}`;
});

const categoryWorkspaceMeta = computed(() => {
  if (!selectedTimelineCategory.value) return '';
  return `${categoryWorkspaceCount.value} posiciones - ${formatNumber(categoryWorkspaceTotal.value, 2)} ${heroUnitLabel.value}`;
});

const showPositionSelector = computed(
  () => !!selectedTimelineCategory.value && availablePositionRows.value.length > 0,
);
const timelineColumnRef = ref<HTMLElement | null>(null);

const {
  accountingActivityLoading,
  accountingActivityError,
  accountingActivityRows,
  accountingActivityYear,
  showAccountingActivitySetupGap,
  showAccountingActivityNeedsReview,
  showAccountingActivityBlock,
  resetAccountingActivity,
  loadAccountingActivity,
} = useNetWorthAccountingActivity({
  selectedPositionSource,
  sourceItemForRow,
  toNumber,
});

const { positionActivityRows } = useNetWorthPositionActivity({
  selectedPositionType,
  assetValuations: computed(() => store.assetValuations),
  investmentEvents: computed(() => store.investmentEvents),
  liquidityEvents: computed(() => store.liquidityEvents),
  liabilityValuations: computed(() => store.liabilityValuations),
  liabilityEvents: computed(() => store.liabilityEvents),
  toNumber,
});

function clearPositionSelection(): void {
  selectedPositionType.value = null;
  selectedPositionId.value = null;
  store.positionTimeline = null;
  store.assetValuations = [];
  store.liabilityValuations = [];
  store.investmentEvents = [];
  store.liquidityEvents = [];
  store.liabilityEvents = [];
  resetAccountingActivity();
}

function closeAssetModal(): void {
  showAssetModal.value = false;
  createAssetCategory.value = null;
}

function closeLiabilityModal(): void {
  showLiabilityModal.value = false;
  createLiabilityCategory.value = null;
}

const {
  displayedTimelineLoading,
  visibleTimelineRows,
  timelineWindow,
  timelineChartRows,
  timelineChartPoints,
  timelineRangeCaption,
  latestTimelineChartPoint,
  timelineSummaryLabel,
  displayedTimelineSeriesColor,
  timelineYAxisStartsAtZero,
} = useNetWorthTimeline({
  ownershipFilter,
  selectedPosition,
  selectedPositionType,
  selectedPositionId,
  selectedTimelineCategory,
  selectedTimelineCategoryType,
  selectedTimelinePreset,
  customTimelineWindow,
  timelineRows,
  availablePositionRows,
  allAssetPositionRows,
  allLiabilityPositionRows,
  positionTimelineRows,
  storeTimelineLoading: computed(() => store.timelineLoading),
  storePositionTimelineLoading: computed(() => store.positionTimelineLoading),
  setStoreError: (message) => {
    store.error = message;
  },
  resetPositionSelection: clearPositionSelection,
  getTimelineMetricValue,
});
const { timelineSidebarPanelStyle } = useNetWorthTimelineLayout({
  showCategoryWorkspace,
  visibleTimelineRows,
  selectedPosition,
  timelineColumnRef,
});

const {
  openCreateModal,
  submitAssetFromView,
  submitLiabilityFromView,
  resetTimelineSelection,
  applyCompositionCategoryFilter,
  handleCompositionAddType,
  selectPosition,
  setTimelinePreset,
  updateTimelineWindowStart,
  updateTimelineWindowEnd,
  onPositionSelection,
  assetCreateInitial,
  liabilityCreateInitial,
} = useNetWorthPageActions({
  store,
  selectedPositionType,
  selectedPositionId,
  selectedTimelineCategory,
  selectedTimelineCategoryType,
  selectedTimelinePreset,
  customTimelineWindow,
  createAssetCategory,
  createLiabilityCategory,
  showAssetModal,
  showLiabilityModal,
  availablePositionRows,
  timelineWindow,
  submitAsset,
  submitLiability: submitLiabilityWithExpenseReview,
  resetAccountingActivity,
  loadAccountingActivity,
});
</script>

<template>
  <div class="container ui-pro-page relative">
    <NetWorthHeroSection
      :store="store"
      :currencies="currencies"
      :inflation-regions="inflationRegions"
      :value-mode="valueMode"
      :set-value-mode="setValueMode"
      :can-show-real="canShowReal()"
      :mode-label="modeLabel()"
      :real-base-label="realBaseLabel"
      :hero-unit-label="heroUnitLabel"
      :analysis="analysis"
      :ownership-filter="ownershipFilter"
      :set-ownership-filter="setOwnershipFilter"
      :ownership-options="ownershipOptions"
      :ownership-filter-disabled="ownershipFilterDisabled"
      :selected-ownership-filter-label="selectedOwnershipFilterLabel"
      :format-number="formatNumber"
      :format-pct="formatPct"
      :reset-timeline-selection="resetTimelineSelection"
      :category-keys="effectiveCategoryKeys"
      :category-labels="effectiveCategoryLabels"
      :category-assets="effectiveCategoryAssets"
      :category-liabilities="effectiveCategoryLiabilities"
      :category-asset-counts="effectiveCategoryAssetCounts"
      :category-liability-counts="effectiveCategoryLiabilityCounts"
    />

    <section class="card ui-pro-panel ui-nw-hero-shell grid gap-2.5 mb-2">
      <div class="ui-nw-hero-timeline">
        <div class="ui-nw-timeline-layout">
          <div ref="timelineColumnRef" class="ui-nw-timeline-column">
            <NetWorthTimelineMain
              :analysis="analysis"
              :hero-unit-label="heroUnitLabel"
              :effective-category-keys="effectiveCategoryKeys"
              :effective-category-labels="effectiveCategoryLabels"
              :effective-category-assets="effectiveCategoryAssets"
              :effective-category-liabilities="effectiveCategoryLiabilities"
              :effective-category-asset-counts="effectiveCategoryAssetCounts"
              :effective-category-liability-counts="effectiveCategoryLiabilityCounts"
              :selected-timeline-category="selectedTimelineCategory"
              :selected-timeline-category-type="selectedTimelineCategoryType"
              :apply-composition-category-filter="applyCompositionCategoryFilter"
              :handle-composition-add-type="handleCompositionAddType"
              :displayed-timeline-loading="displayedTimelineLoading"
              :visible-timeline-rows="visibleTimelineRows"
              :selected-position="selectedPosition"
              :timeline-preset-options="timelinePresetOptions"
              :custom-timeline-window="customTimelineWindow"
              :selected-timeline-preset="selectedTimelinePreset"
              :set-timeline-preset="setTimelinePreset"
              :timeline-range-caption="timelineRangeCaption"
              :set-timeline-expanded="(value) => (timelineExpanded = value)"
              :timeline-chart-points="timelineChartPoints"
              :displayed-timeline-unit="
                displayCurrencyUnit(store.timeline?.base_currency ?? unitLabel())
              "
              :timeline-summary-label="timelineSummaryLabel"
              :displayed-timeline-series-color="displayedTimelineSeriesColor"
              :timeline-y-axis-starts-at-zero="timelineYAxisStartsAtZero"
              :format-number="formatNumber"
              :timeline-chart-rows="timelineChartRows"
              :show-accounting-activity-block="showAccountingActivityBlock"
              :accounting-activity-loading="accountingActivityLoading"
              :accounting-activity-year="accountingActivityYear"
              :show-accounting-activity-needs-review="showAccountingActivityNeedsReview"
              :show-accounting-activity-setup-gap="showAccountingActivitySetupGap"
              :accounting-activity-error="accountingActivityError"
              :accounting-activity-rows="accountingActivityRows"
              :position-activity-loading="store.positionActivityLoading"
              :position-activity-rows="positionActivityRows"
            />
          </div>

          <BaseModal
            :open="timelineExpanded"
            title="Evolucion temporal"
            panel-class="max-w-[1080px]"
            @close="timelineExpanded = false"
          >
            <div class="ui-nw-timeline-modal">
              <div class="ui-nw-timeline-modal-head">
                <div>
                  <div class="ui-nw-timeline-modal-title">{{ timelineSummaryLabel }}</div>
                  <div class="ui-nw-timeline-modal-copy">{{ timelineRangeCaption }}</div>
                </div>
                <div class="ui-nw-timeline-modal-value">
                  {{ formatNumber(latestTimelineChartPoint?.value ?? 0, 2) }}
                  {{ displayCurrencyUnit(store.timeline?.base_currency ?? unitLabel()) }}
                </div>
              </div>

              <div class="ui-nw-timeline-modal-ranges">
                <label class="ui-nw-timeline-slider-group">
                  <span>Inicio</span>
                  <input
                    class="ui-nw-timeline-slider"
                    type="range"
                    min="0"
                    :max="Math.max(0, visibleTimelineRows.length - 1)"
                    :value="timelineWindow.start"
                    @input="updateTimelineWindowStart(($event.target as HTMLInputElement).value)"
                  />
                  <strong>{{ timelineChartPoints[0]?.fullLabel ?? '-' }}</strong>
                </label>

                <label class="ui-nw-timeline-slider-group">
                  <span>Fin</span>
                  <input
                    class="ui-nw-timeline-slider"
                    type="range"
                    min="0"
                    :max="Math.max(0, visibleTimelineRows.length - 1)"
                    :value="timelineWindow.end"
                    @input="updateTimelineWindowEnd(($event.target as HTMLInputElement).value)"
                  />
                  <strong>{{ latestTimelineChartPoint?.fullLabel ?? '-' }}</strong>
                </label>
              </div>

              <NetWorthTimelineChart
                :points="timelineChartPoints"
                :unit="displayCurrencyUnit(store.timeline?.base_currency ?? unitLabel())"
                :series-label="timelineSummaryLabel"
                :series-color="displayedTimelineSeriesColor"
                :y-axis-min-zero="timelineYAxisStartsAtZero"
                expanded
              />
            </div>
          </BaseModal>

          <aside class="ui-nw-timeline-sidebar">
            <NetWorthCategoryWorkspace
              :show-category-workspace="showCategoryWorkspace"
              :timeline-sidebar-panel-style="timelineSidebarPanelStyle"
              :selected-timeline-category-type="selectedTimelineCategoryType"
              :selected-timeline-category="selectedTimelineCategory"
              :category-workspace-label="categoryWorkspaceLabel"
              :category-workspace-meta="categoryWorkspaceMeta"
              :open-create-modal="openCreateModal"
              :show-position-selector="showPositionSelector"
              :selected-position-id="selectedPositionId"
              :on-position-selection="onPositionSelection"
              :available-position-rows="availablePositionRows"
              :category-workspace-rows="categoryWorkspaceRows"
              :selected-position-type="selectedPositionType"
              :format-number="formatNumber"
              :format-pct="formatPct"
              :display-currency-unit="displayCurrencyUnit"
              :ownership-badge-for-row="ownershipBadgeForRow"
              :select-position="selectPosition"
              :edit-row="editRow"
              :delete-row="deleteRow"
            />
          </aside>
        </div>
      </div>
    </section>

    <div v-if="store.error" class="alert mt-3">
      {{ prettyError() }}
    </div>
    <NetWorthItemModals
      :show-asset-modal="showAssetModal"
      :show-liability-modal="showLiabilityModal"
      :show-edit-modal="showEditModal"
      :edit-title="editTitle"
      :asset-categories="assetCategories"
      :liability-categories="liabilityCategories"
      :asset-subcategories="assetSubcategories"
      :asset-create-initial="assetCreateInitial"
      :liability-create-initial="liabilityCreateInitial"
      :edit-initial="editInitial"
      :edit-categories="editCategories"
      :edit-kind="editKind"
      :active-assets="activeAssets"
      :item-form-props="itemFormProps"
      :submit-asset-from-view="submitAssetFromView"
      :submit-liability-from-view="submitLiabilityFromView"
      :submit-edit="submitEditWithExpenseReview"
      :close-edit="closeEdit"
      :on-close-asset-modal="closeAssetModal"
      :on-close-liability-modal="closeLiabilityModal"
      :edit-error="editError"
    />

    <BaseModal
      :open="showGeneratedLiabilityExpenseModal"
      :title="generatedLiabilityExpenseReviewTitle"
      @close="closeGeneratedLiabilityExpenseModal"
    >
      <div v-if="generatedLiabilityExpenseReview" class="grid gap-3">
        <div
          v-if="generatedLiabilityExpenseReviewChangeMessage"
          class="rounded-xl border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-sm text-white/90"
        >
          {{ generatedLiabilityExpenseReviewChangeMessage }}
        </div>
        <div
          class="rounded-xl border border-teal-300/20 bg-teal-400/10 px-3 py-2 text-sm text-white/90"
        >
          Este pasivo generó gastos recurrentes en
          {{ generatedLiabilityExpenseReview.entries.length }}
          anualidades. Revisa su clasificación desde Presupuesto.
        </div>
        <div class="grid gap-2">
          <div
            v-for="entry in generatedLiabilityExpenseReview.entries"
            :key="entry.id"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="text-sm font-medium">Ejercicio {{ entry.fiscalYear }}</div>
              <div class="text-sm text-white/90">
                {{ formatNumber(entry.amountAnnual, 2) }} {{ entry.currency }}
              </div>
            </div>
            <div class="mt-1 text-xs text-white/70">
              {{ entry.name }} · {{ entry.category }} / {{ entry.subcategory }}
            </div>
          </div>
        </div>
        <div class="actions justify-end">
          <button class="btn btn-ghost" type="button" @click="closeGeneratedLiabilityExpenseModal">
            Cerrar
          </button>
          <button class="btn btn-primary" type="button" @click="openGeneratedExpensesInBudget">
            Revisar en Presupuesto
          </button>
        </div>
      </div>
    </BaseModal>

    <div v-if="store.loading" class="ui-status-line">Cargando...</div>
  </div>
</template>
