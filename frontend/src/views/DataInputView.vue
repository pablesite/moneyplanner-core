<script setup lang="ts">
import DataInputIntroCard from './data-input/DataInputIntroCard.vue';
import DataInputAnnualSections from './data-input/DataInputAnnualSections.vue';
import DataInputPatrimonySection from './data-input/DataInputPatrimonySection.vue';
import { useDataInputPage } from './data-input/useDataInputPage';

const page = useDataInputPage();
</script>

<template>
  <div class="container ui-pro-page">
    <DataInputIntroCard :page="page" />
    <DataInputAnnualSections :page="page" />
    <DataInputPatrimonySection :page="page" />
  </div>
</template>
