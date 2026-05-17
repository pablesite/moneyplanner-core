<script setup lang="ts">
import BudgetAnnualEntriesContent from '@/views/budget/BudgetAnnualEntriesContent.vue';
import { useBudgetAnnualEntriesPage } from '@/views/budget/useBudgetAnnualEntriesPage';

const page = useBudgetAnnualEntriesPage();
</script>

<template>
  <BudgetAnnualEntriesContent :page="page" />
</template>
