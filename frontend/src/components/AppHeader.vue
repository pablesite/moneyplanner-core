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
  <header style="display:flex; justify-content:space-between; align-items:center; padding: 16px 24px; border-bottom: 1px solid #333;">
    <div style="font-size: 18px;">moneyplanner</div>

    <div v-if="hasToken" style="display:flex; gap: 10px; align-items:center;">
      <button
        @click="logout"
        style="padding: 8px 12px; border-radius: 8px; border: 1px solid #999; background: transparent; color: inherit; cursor: pointer;"
      >
        Logout
      </button>
    </div>
  </header>
</template>
