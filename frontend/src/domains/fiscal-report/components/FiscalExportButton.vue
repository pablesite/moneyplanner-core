<script setup lang="ts">
const props = defineProps<{
  loading: boolean;
}>();

const emit = defineEmits<{
  export: [format: 'csv' | 'pdf'];
}>();
</script>

<template>
  <div class="ui-action-bar">
    <button
      class="btn btn-sm"
      type="button"
      :disabled="props.loading"
      @click="emit('export', 'csv')"
    >
      {{ props.loading ? 'Descargando...' : 'Exportar CSV' }}
    </button>
    <button
      class="btn btn-sm"
      type="button"
      :disabled="props.loading"
      @click="emit('export', 'pdf')"
    >
      {{ props.loading ? 'Descargando...' : 'Exportar PDF' }}
    </button>
  </div>
</template>
