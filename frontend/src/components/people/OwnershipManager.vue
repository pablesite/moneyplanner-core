<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import BaseModal from "@/components/BaseModal.vue";
import { usePeopleStore } from "@/stores/people";
import OwnershipLabel from "@/components/people/OwnershipLabel.vue";

const store = usePeopleStore();

const showModal = ref(false);
const notes = ref("");

const form = reactive({
  memberIds: [] as number[],
  percents: {} as Record<number, string>,
});

const adults = computed(() => store.activeAdults);

const canCreate = computed(() => {
  if (form.memberIds.length < 2) return false;

  for (const id of form.memberIds) {
    const p = Number(String(form.percents[id] ?? "").replace(",", "."));
    if (!Number.isFinite(p) || p <= 0 || p > 100) return false;
  }

  const total = form.memberIds.reduce((acc, id) => {
    const p = Number(String(form.percents[id] ?? "0").replace(",", "."));
    return acc + (Number.isFinite(p) ? p : 0);
  }, 0);

  return Math.abs(total - 100) < 0.0001;
});

function toggleMember(id: number) {
  const idx = form.memberIds.indexOf(id);
  if (idx >= 0) {
    form.memberIds.splice(idx, 1);
    delete form.percents[id];
  } else {
    form.memberIds.push(id);
    form.percents[id] = form.percents[id] ?? "";
  }
}

function setEqualSplit() {
  if (form.memberIds.length < 2) return;
  const each = (100 / form.memberIds.length).toFixed(2);
  for (const id of form.memberIds) form.percents[id] = each;

  const sum = (form.memberIds.length - 1) * Number(each);
  const last = (100 - sum).toFixed(2);
  form.percents[form.memberIds[form.memberIds.length - 1]] = last;
}

async function submit() {
  if (!canCreate.value) return;

  const splits = form.memberIds.map((id) => ({
    member_id: id,
    percent: String(form.percents[id]).replace(",", "."),
  }));

  await store.createSharedOwnership({ splits, notes: notes.value });

  showModal.value = false;
  notes.value = "";
  form.memberIds = [];
  form.percents = {};
}

async function removeOwnership(id: number) {
  const ok = window.confirm("¿Eliminar esta titularidad compartida? (Solo si no está en uso)");
  if (!ok) return;
  await store.deleteOwnership(id);
}

onMounted(async () => {
  if (!store.ownerships.length) await store.fetchOwnerships();
  if (!store.members.length) await store.fetchMembers();
});

const ownershipsSorted = computed(() => {
  const arr = [...store.ownerships];
  arr.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === "individual" ? -1 : 1;
    const an = a.member?.name ?? "";
    const bn = b.member?.name ?? "";
    return an.localeCompare(bn);
  });
  return arr;
});
</script>

<template>
  <div>
    <div v-if="store.error" class="alert" style="margin-bottom: 12px;">
      {{ store.error }}
    </div>

    <div style="display:flex; align-items:center; justify-content: space-between; gap: 10px; margin-bottom: 10px;">
      <div class="subtle">Titularidades</div>

      <div style="display:flex; gap: 10px;">
        <button class="btn" type="button" :disabled="store.loading" @click="store.fetchOwnerships()">
          Refrescar
        </button>
        <button class="btn" type="button" :disabled="store.loading" @click="showModal = true">
          Nueva compartida
        </button>
      </div>
    </div>

    <div class="card" style="padding: 14px;">
      <table style="width:100%; border-collapse: collapse;">
        <thead>
          <tr>
            <th style="text-align:left; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Titularidad</th>
            <th style="text-align:left; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Notas</th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Acciones</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="o in ownershipsSorted" :key="o.id">
            <td style="padding:8px 6px;">
              <OwnershipLabel :kind="o.kind" :member="o.member" :splits="o.splits" />
            </td>

            <td style="padding:8px 6px;">
              <span class="subtle">{{ o.notes || "-" }}</span>
            </td>

            <td style="padding:8px 6px; text-align:right;">
              <div style="display:inline-flex; gap: 10px; align-items:center;">
                <span v-if="o.is_in_use" class="subtle">En uso</span>

                <button
                  v-else-if="o.kind === 'shared'"
                  class="btn"
                  type="button"
                  :disabled="store.loading"
                  @click="removeOwnership(o.id)"
                >
                  Eliminar
                </button>

                <span v-else class="subtle">—</span>
              </div>
            </td>
          </tr>

          <tr v-if="!ownershipsSorted.length">
            <td colspan="3" class="subtle" style="padding: 10px 6px;">
              No hay titularidades todavía.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal crear compartida -->
    <BaseModal :open="showModal" title="Nueva titularidad compartida" @close="showModal = false">
      <div style="display:grid; gap: 12px;">
        <div class="subtle">
          Selecciona al menos 2 adultos y reparte los porcentajes (suma 100).
        </div>

        <div class="card" style="padding: 12px;">
          <div style="display:flex; flex-wrap: wrap; gap: 10px;">
            <button
              v-for="m in adults"
              :key="m.id"
              class="btn"
              type="button"
              @click="toggleMember(m.id)"
              :style="form.memberIds.includes(m.id) ? '' : 'opacity:.65'"
            >
              {{ m.name }}
            </button>
          </div>

          <div v-if="form.memberIds.length" style="margin-top: 12px; display:grid; gap: 10px;">
            <div style="display:flex; align-items:center; justify-content: space-between;">
              <div class="subtle">Porcentajes</div>
              <button class="btn" type="button" @click="setEqualSplit">
                Reparto igual
              </button>
            </div>

            <div v-for="id in form.memberIds" :key="id" style="display:flex; gap: 10px; align-items:center;">
              <div style="min-width: 160px;">
                {{ adults.find(a => a.id === id)?.name ?? ('ID ' + id) }}
              </div>

              <input
                v-model="form.percents[id]"
                inputmode="decimal"
                placeholder="50.00"
                style="max-width: 140px;"
              />
              <span class="subtle">%</span>
            </div>
          </div>
        </div>

        <div>
          <div class="subtle" style="margin-bottom: 6px;">Notas (opcional)</div>
          <input v-model="notes" placeholder="Ej: Pablo/Ana" />
        </div>

        <div style="display:flex; justify-content: flex-end; gap: 10px;">
          <button class="btn" type="button" @click="showModal = false">Cancelar</button>
          <button class="btn" type="button" :disabled="!canCreate || store.loading" @click="submit">
            Crear
          </button>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
