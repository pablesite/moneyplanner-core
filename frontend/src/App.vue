<template>
  <div>
    <AppHeader />
    <router-view />
  </div>
</template>

<script setup lang="ts">
import AppHeader from '@/domains/auth/components/AppHeader.vue';
</script>
