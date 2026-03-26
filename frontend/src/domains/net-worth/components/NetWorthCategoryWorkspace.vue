<script setup lang="ts">
type CategoryType = 'asset' | 'liability';
type PositionType = 'asset' | 'liability';

type PositionRow = {
  id: number;
  type: PositionType;
  name: string;
  subtitle: string;
  value: number;
  currency: string;
  ownershipFraction: number;
  category: string;
};

defineProps<{
  showCategoryWorkspace: boolean;
  timelineSidebarPanelStyle?: Record<string, string>;
  selectedTimelineCategoryType: CategoryType;
  selectedTimelineCategory: string | null;
  categoryWorkspaceLabel: string;
  categoryWorkspaceMeta: string;
  openCreateModal: (type: CategoryType, category: string | null) => void;
  showPositionSelector: boolean;
  selectedPositionId: number | null;
  onPositionSelection: (event: Event) => void;
  availablePositionRows: PositionRow[];
  categoryWorkspaceRows: PositionRow[];
  selectedPositionType: PositionType | null;
  formatNumber: (value: number, decimals?: number) => string;
  formatPct: (value: number | null, decimals?: number) => string;
  displayCurrencyUnit: (currency: string | null | undefined) => string;
  ownershipBadgeForRow: (row: PositionRow) => string | null;
  selectPosition: (row: PositionRow) => void | Promise<void>;
  editRow: (row: PositionRow) => void | Promise<void>;
  deleteRow: (row: PositionRow) => void | Promise<void>;
}>();
</script>

<template>
  <div
    v-if="!showCategoryWorkspace"
    class="ui-nw-category-workspace ui-nw-category-workspace-empty"
    :style="timelineSidebarPanelStyle"
  >
    <p class="ui-nw-category-workspace-copy">
      Selecciona una categoría de Activos o Pasivos para ver los detalles.
    </p>
  </div>

  <div
    v-else
    class="ui-nw-category-workspace ui-nw-category-workspace-embedded"
    :style="timelineSidebarPanelStyle"
  >
    <div class="ui-nw-category-workspace-head">
      <div class="ui-nw-category-workspace-heading">
        <div class="ui-nw-category-workspace-kicker">
          {{ selectedTimelineCategoryType === 'liability' ? 'Pasivos' : 'Activos' }}
        </div>
        <div class="ui-nw-category-workspace-title-row">
          <h3 class="ui-nw-category-workspace-title">{{ categoryWorkspaceLabel }}</h3>
          <button
            class="icon-btn ui-nw-category-add-btn"
            type="button"
            :aria-label="
              selectedTimelineCategoryType === 'liability' ? 'Nuevo pasivo' : 'Nuevo activo'
            "
            :title="selectedTimelineCategoryType === 'liability' ? 'Nuevo pasivo' : 'Nuevo activo'"
            @click="openCreateModal(selectedTimelineCategoryType, selectedTimelineCategory)"
          >
            <span class="icon" aria-hidden="true">+</span>
          </button>
        </div>
        <p class="ui-nw-category-workspace-copy">{{ categoryWorkspaceMeta }}</p>
      </div>
    </div>

    <label v-if="showPositionSelector" class="ui-nw-position-select">
      <span class="ui-nw-position-select-label">
        {{ selectedTimelineCategoryType === 'liability' ? 'Pasivo concreto' : 'Activo concreto' }}
      </span>
      <select
        class="input ui-nw-position-select-input"
        :value="selectedPositionId ?? ''"
        @change="onPositionSelection"
      >
        <option value="">Categoría completa</option>
        <option v-for="row in availablePositionRows" :key="row.id" :value="row.id">
          {{ row.name }}
        </option>
      </select>
    </label>

    <div v-if="categoryWorkspaceRows.length === 0" class="subtle">
      No hay posiciones para esta categoría con el filtro actual.
    </div>
    <div v-else class="ui-nw-category-workspace-list">
      <article
        v-for="row in categoryWorkspaceRows"
        :key="`${row.type}-${row.id}`"
        class="ui-nw-category-item"
        :class="{
          'ui-nw-category-item-active':
            selectedPositionType === row.type && selectedPositionId === row.id,
        }"
      >
        <button class="ui-nw-category-item-main" type="button" @click="selectPosition(row)">
          <div class="ui-nw-category-selection-label">
            {{ row.type === 'liability' ? 'Pasivo concreto' : 'Activo concreto' }}
          </div>
          <div class="ui-nw-category-item-head">
            <strong>{{ row.name }}</strong>
            <span>{{ formatNumber(row.value, 2) }} {{ displayCurrencyUnit(row.currency) }}</span>
          </div>
          <div class="ui-nw-category-item-meta">
            <span>{{ row.subtitle }}</span>
            <span v-if="row.ownershipFraction < 1">
              {{ formatPct(row.ownershipFraction, 0) }} titularidad aplicada
            </span>
            <span v-if="ownershipBadgeForRow(row)">{{ ownershipBadgeForRow(row) }}</span>
          </div>
        </button>
        <div class="ui-nw-category-item-actions">
          <button
            class="icon-btn ui-nw-category-item-action"
            type="button"
            aria-label="Editar"
            title="Editar"
            @click="editRow(row)"
          >
            <span class="icon" aria-hidden="true">&#9998;</span>
          </button>
          <button
            class="icon-btn ui-nw-category-item-action"
            type="button"
            :aria-label="row.type === 'asset' ? 'Eliminar activo' : 'Eliminar pasivo'"
            title="Eliminar"
            @click="deleteRow(row)"
          >
            <span class="icon" aria-hidden="true">&#128465;</span>
          </button>
        </div>
      </article>
    </div>
  </div>
</template>
