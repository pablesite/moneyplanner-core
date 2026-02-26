<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { FamilyMemberManager, OwnershipManager } from '@/domains/people';

const router = useRouter();
type Tab = 'members' | 'ownerships';
const tab = ref<Tab>('members');
</script>

<template>
  <div class="container ui-pro-page">
    <div class="ui-page-header">
      <h1 class="h1 ui-page-title">Personas</h1>

      <div class="ui-page-actions">
        <button class="btn" type="button" @click="router.push('/account')">Cuenta</button>
        <button class="btn" type="button" @click="router.push('/patrimonio')">
          Volver a Patrimonio
        </button>
      </div>
    </div>

    <div class="card ui-pro-panel mt-1">
      <div class="mb-3.5 flex gap-2.5">
        <button
          class="btn opacity-60"
          type="button"
          :class="{ '!opacity-100': tab === 'members' }"
          @click="tab = 'members'"
        >
          Miembros
        </button>

        <button
          class="btn opacity-60"
          type="button"
          :class="{ '!opacity-100': tab === 'ownerships' }"
          @click="tab = 'ownerships'"
        >
          Titularidades
        </button>
      </div>

      <div class="grid gap-3.5">
        <FamilyMemberManager v-if="tab === 'members'" />
        <OwnershipManager v-else />
      </div>
    </div>
  </div>
</template>
