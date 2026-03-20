<script setup lang="ts">
import DataInputAnnualSections from '@/views/data-input/DataInputAnnualSections.vue';
import { useDataInputPage } from '@/views/data-input/useDataInputPage';

const page = useDataInputPage();
</script>

<template>
  <DataInputAnnualSections :page="page" />
</template>
