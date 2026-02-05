<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import FamilyMemberManager from "@/components/people/FamilyMemberManager.vue";
import OwnershipManager from "@/components/people/OwnershipManager.vue";

const router = useRouter();
type Tab = "members" | "ownerships";
const tab = ref<Tab>("members");
</script>

<template>
  <div class="container">
    <div style="display:flex; align-items:center; justify-content: space-between; gap: 12px;">
      <h1 class="h1" style="margin: 0;">Personas</h1>

      <div style="display:flex; align-items:center; gap: 10px;">
        <button class="btn" type="button" @click="router.push('/')">
          Volver a Patrimonio
        </button>
      </div>
    </div>

    <div class="card" style="margin-top: 14px;">
      <div style="display:flex; gap: 10px; margin-bottom: 14px;">
        <button
          class="btn"
          type="button"
          :style="tab === 'members' ? 'opacity:1' : 'opacity:.6'"
          @click="tab = 'members'"
        >
          Miembros
        </button>

        <button
          class="btn"
          type="button"
          :style="tab === 'ownerships' ? 'opacity:1' : 'opacity:.6'"
          @click="tab = 'ownerships'"
        >
          Titularidades
        </button>
      </div>

      <div v-if="tab === 'members'">
        <FamilyMemberManager />
      </div>

      <div v-else>
        <OwnershipManager />
      </div>
    </div>
  </div>
</template>
