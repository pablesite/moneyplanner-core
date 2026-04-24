<script setup lang="ts">
defineProps<{
  avisos: string[];
}>();
</script>

<template>
  <section v-if="avisos.length" class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h3 class="ui-section-title">Avisos</h3>
        <p class="ui-section-subtitle">Notas informativas del cálculo fiscal</p>
      </div>
    </header>

    <ul class="list fiscal-warning-list">
      <li v-for="(aviso, index) in avisos" :key="index" class="fiscal-warning-item">
        {{ aviso }}
      </li>
    </ul>
  </section>
</template>
