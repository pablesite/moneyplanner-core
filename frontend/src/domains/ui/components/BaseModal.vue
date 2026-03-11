<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue';

defineProps<{
  open: boolean;
  title?: string;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close');
}

onMounted(() => window.addEventListener('keydown', onKeydown));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));
</script>

<template>
  <teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/55 p-4 sm:p-5"
    >
      <div
        class="flex max-h-[calc(100vh-2rem)] w-full max-w-[720px] flex-col overflow-hidden rounded-lg border border-white/10 bg-[#121212fa] shadow-2xl sm:max-h-[calc(100vh-2.5rem)]"
      >
        <div class="flex items-center gap-3 border-b border-white/10 px-4 py-3.5">
          <div class="text-base font-semibold">{{ title }}</div>
        </div>

        <div class="overflow-y-auto px-4 py-3.5">
          <slot />
        </div>
      </div>
    </div>
  </teleport>
</template>
