<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { FamilyMemberManager, OwnershipManager } from '@/domains/people';

const router = useRouter();
type Tab = 'members' | 'ownerships';
const tab = ref<Tab>('members');
</script>

<template>
  <div class="container ui-page-shell">
    <header class="ui-page-head">
      <div>
        <p class="ui-page-eyebrow">Configuracion familiar</p>
        <h1 class="ui-page-title">Personas</h1>
      </div>

      <div class="ui-page-actions">
        <button class="btn" type="button" @click="router.push('/account')">Cuenta</button>
        <button class="btn" type="button" @click="router.push('/patrimonio')">
          Volver a Patrimonio
        </button>
      </div>
    </header>

    <section class="mt-1 grid gap-3.5">
      <div class="ui-action-bar mb-3.5">
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
      <FamilyMemberManager v-if="tab === 'members'" />
      <OwnershipManager v-else />
    </section>
  </div>
</template>
