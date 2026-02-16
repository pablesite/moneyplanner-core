<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { clearAuthTokens, getAccessToken } from '@/domains/auth/session';

const router = useRouter();

const hasToken = computed(() => !!getAccessToken());

function logout() {
  clearAuthTokens();
  router.push('/login');
}
</script>

<template>
  <header class="app-header">
    <div class="container ui-app-header-inner">
      <div class="ui-app-header-title">moneyplanner core</div>

      <div v-if="hasToken" class="ui-app-header-actions">
        <button class="btn" type="button" @click="logout">Logout</button>
      </div>
    </div>
  </header>
</template>
