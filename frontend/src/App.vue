<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import AppShellLayout from '@/shell/AppShellLayout.vue';

const route = useRoute();
const isLoginRoute = computed(() => route.name === 'login');
</script>

<template>
  <router-view v-if="isLoginRoute" />
  <AppShellLayout v-else />
</template>
