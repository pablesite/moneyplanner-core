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
    <div class="page-header">
      <h1 class="h1 page-title">Personas</h1>

      <div class="page-actions">
        <button class="btn" type="button" @click="router.push('/')">
          Volver a Patrimonio
        </button>
      </div>
    </div>

    <div class="card people-content-card">
      <div class="people-tabs">
        <button
          class="btn"
          type="button"
          :class="['tab-btn', { 'is-active': tab === 'members' }]"
          @click="tab = 'members'"
        >
          Miembros
        </button>

        <button
          class="btn"
          type="button"
          :class="['tab-btn', { 'is-active': tab === 'ownerships' }]"
          @click="tab = 'ownerships'"
        >
          Titularidades
        </button>
      </div>

      <div class="people-panel">
        <FamilyMemberManager v-if="tab === 'members'" />
        <OwnershipManager v-else />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page-title{
  margin: 0;
}

.page-actions{
  display: flex;
  align-items: center;
  gap: 10px;
}

.people-content-card{
  margin-top: 14px;
}

.people-tabs{
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.tab-btn{
  opacity: 0.6;
}

.tab-btn.is-active{
  opacity: 1;
}

.people-panel{
  display: grid;
  gap: 14px;
}
</style>
