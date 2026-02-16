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
      @click.self="emit('close')"
    >
      <div
        class="w-full max-w-[720px] overflow-hidden rounded-lg border border-white/10 bg-[#121212fa] shadow-2xl"
      >
        <div class="flex items-center gap-3 border-b border-white/10 px-4 py-3.5">
          <div class="text-base font-semibold">{{ title }}</div>
        </div>

        <div class="px-4 py-3.5">
          <slot />
        </div>
      </div>
    </div>
  </teleport>
</template>
