<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue';

let modalIdCounter = 0;

const props = withDefaults(
  defineProps<{
    open: boolean;
    title?: string;
    panelClass?: string;
    closeOnBackdrop?: boolean;
  }>(),
  {
    closeOnBackdrop: false,
  },
);

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const titleId = `base-modal-title-${++modalIdCounter}`;

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close');
}

function onBackdropClick() {
  if (!props.closeOnBackdrop) return;
  emit('close');
}

onMounted(() => window.addEventListener('keydown', onKeydown));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));
</script>

<template>
  <teleport to="body">
    <div v-if="open" class="ui-modal-backdrop" @click.self="onBackdropClick">
      <div
        class="ui-modal-panel"
        :class="panelClass"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="title ? titleId : undefined"
      >
        <div class="ui-modal-head">
          <div :id="titleId" class="ui-modal-title">{{ title }}</div>
          <button
            class="btn btn-ghost btn-sm ui-modal-close"
            type="button"
            aria-label="Cerrar modal"
            @click="emit('close')"
          >
            Cerrar
          </button>
        </div>

        <div class="ui-modal-body">
          <slot />
        </div>
      </div>
    </div>
  </teleport>
</template>
