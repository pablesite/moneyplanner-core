<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const hasToken = computed(() => !!localStorage.getItem("access_token"));

function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  router.push("/login");
}
</script>

<template>
  <header class="app-header">
    <div class="container app-header-inner">
      <div class="app-header-title">moneyplanner</div>

      <div v-if="hasToken" class="app-header-actions">
        <button class="app-header-logout" @click="logout">
          Logout
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header-inner{
  display:flex;
  justify-content:space-between;
  align-items:center;
  padding: 16px 0;
  border-bottom: 1px solid #333;
}

.app-header-title{
  font-size: 18px;
}

.app-header-actions{
  display:flex;
  gap: 10px;
  align-items:center;
}

.app-header-logout{
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #999;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
</style>
