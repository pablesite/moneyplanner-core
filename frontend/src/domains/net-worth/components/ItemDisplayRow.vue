<script setup lang="ts">
type ItemView = {
  id: number;
  name: string;
  is_active: boolean;
  currency: string;
};

type Props = {
  item: ItemView;
  formattedAmount: string;
  isLiabilitiesList: boolean;
  financedAssetName: string | null;
  ownershipLabel?: string | null;
  sharePercent?: number | null;
};

defineProps<Props>();

const emit = defineEmits<{
  (e: 'edit', id: number): void;
  (e: 'archive', id: number): void;
  (e: 'delete', id: number): void;
}>();
</script>

<template>
  <div class="nw-item-row">
    <div class="nw-item-main">
      <div class="nw-item-name">
        <span class="item-name-text">{{ item.name }}</span>
        <span v-if="!item.is_active" class="badge">archivado</span>
        <span v-if="ownershipLabel" class="badge">{{ ownershipLabel }}</span>
        <span v-if="sharePercent && sharePercent < 100" class="badge">{{ sharePercent }}%</span>
      </div>
      <div v-if="isLiabilitiesList && financedAssetName" class="nw-item-submeta">
        <span>Financia: {{ financedAssetName }}</span>
      </div>
    </div>
    <div class="nw-item-amount">{{ formattedAmount }}</div>
    <div class="nw-item-actions">
      <button class="icon-btn" title="Editar" aria-label="Editar" @click="emit('edit', item.id)">
        &#9998;&#65039;
      </button>
      <button
        class="icon-btn"
        title="Archivar"
        aria-label="Archivar"
        @click="emit('archive', item.id)"
      >
        &#128230;
      </button>
      <button class="icon-btn" title="Eliminar" aria-label="Eliminar" @click="emit('delete', item.id)">
        &#128465;&#65039;
      </button>
    </div>
  </div>
</template>
