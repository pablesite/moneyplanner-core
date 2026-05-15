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
    <div
      v-if="open"
      class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/55 p-4 sm:p-5"
      @click.self="onBackdropClick"
    >
      <div
        class="flex max-h-[calc(100vh-2rem)] w-full max-w-[720px] flex-col overflow-hidden rounded-lg border border-white/10 bg-[#121212fa] shadow-2xl sm:max-h-[calc(100vh-2.5rem)]"
        :class="panelClass"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="title ? titleId : undefined"
      >
        <div class="flex items-center gap-3 border-b border-white/10 px-4 py-3.5">
          <div :id="titleId" class="text-base font-semibold">{{ title }}</div>
          <button
            class="ml-auto rounded-md border border-white/10 px-2 py-1 text-sm text-white/70 transition hover:border-white/20 hover:text-white"
            type="button"
            aria-label="Cerrar modal"
            @click="emit('close')"
          >
            Cerrar
          </button>
        </div>

        <div class="overflow-y-auto px-4 py-3.5">
          <slot />
        </div>
      </div>
    </div>
  </teleport>
</template>
