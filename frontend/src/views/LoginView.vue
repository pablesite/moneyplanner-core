<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/lib/api";

const router = useRouter();

const username = ref("");
const password = ref("");
const error = ref<string | null>(null);
const loading = ref(false);

async function login() {
  loading.value = true;
  error.value = null;
  try {
    const res = await api.post("/api/auth/token/", {
      username: username.value,
      password: password.value,
    });

    localStorage.setItem("access_token", res.data.access);
    if (res.data.refresh) localStorage.setItem("refresh_token", res.data.refresh);

    await router.push("/");
  } catch (e: any) {
    error.value = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div style="max-width: 420px; margin: 80px auto; font-family: system-ui; padding: 24px;">
    <h1>Login</h1>

    <div v-if="error" style="padding: 12px; border: 1px solid #f99; background: #fee; margin: 12px 0;">
      {{ error }}
    </div>

    <form @submit.prevent="login" style="display: grid; gap: 12px;">
      <label>
        Usuario
        <input v-model="username" autocomplete="username" style="width: 100%; padding: 10px; margin-top: 6px;" />
      </label>

      <label>
        Contraseña
        <input v-model="password" type="password" autocomplete="current-password"
               style="width: 100%; padding: 10px; margin-top: 6px;" />
      </label>

      <button :disabled="loading" type="submit"
              style="padding: 12px; border: 1px solid #111; background: #111; color: #fff; border-radius: 8px;">
        Entrar
      </button>
    </form>
  </div>
</template>
