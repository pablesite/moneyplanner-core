<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import BaseModal from "@/components/BaseModal.vue";
import { usePeopleStore } from "@/stores/people";

const store = usePeopleStore();

const form = reactive({
  name: "",
  role: "adult" as "adult" | "child",
});

const saving = ref(false);
const rowBusy = ref<Record<number, boolean>>({});

// modal edición
const editOpen = ref(false);
const editForm = reactive({
  id: null as number | null,
  name: "",
  role: "adult" as "adult" | "child",
});

const prettyError = computed(() => store.error);

const membersSorted = computed(() => {
  const arr = [...store.members];
  arr.sort((a, b) => {
    if (a.role !== b.role) return a.role === "adult" ? -1 : 1;
    if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  return arr;
});

async function submit() {
  const name = form.name.trim();
  if (!name) return;

  saving.value = true;
  store.clearError();

  try {
    await store.createMember({ name, role: form.role });
    form.name = "";
    form.role = "adult";
  } finally {
    saving.value = false;
  }
}

async function toggleActive(id: number, next: boolean) {
  if (rowBusy.value[id]) return;

  rowBusy.value[id] = true;
  store.clearError();

  try {
    await store.updateMember(id, { is_active: next });
  } finally {
    rowBusy.value[id] = false;
  }
}

function openEdit(m: any) {
  store.clearError();
  editForm.id = m.id;
  editForm.name = m.name;
  editForm.role = m.role;
  editOpen.value = true;
}

async function saveEdit() {
  if (editForm.id == null) return;
  const name = editForm.name.trim();
  if (!name) return;

  rowBusy.value[editForm.id] = true;
  store.clearError();

  try {
    await store.updateMember(editForm.id, { name, role: editForm.role });
    editOpen.value = false;
  } finally {
    rowBusy.value[editForm.id] = false;
  }
}

async function removeMember(m: any) {
  const ok = window.confirm(`¿Eliminar a "${m.name}"?\n\nSolo se podrá si no está en uso.`);
  if (!ok) return;

  rowBusy.value[m.id] = true;
  store.clearError();

  try {
    await store.deleteMember(m.id);
  } finally {
    rowBusy.value[m.id] = false;
  }
}

onMounted(async () => {
  if (!store.members.length) await store.fetchMembers();
});
</script>

<template>
  <div>
    <div v-if="prettyError" class="alert" style="margin-bottom: 12px;">
      {{ prettyError }}
    </div>

    <!-- Crear -->
    <div class="card" style="padding: 14px; margin-bottom: 14px;">
      <div class="subtle" style="margin-bottom: 10px;">
        Crea miembros de la familia. Al crear un adulto, se generará automáticamente su titularidad individual.
      </div>

      <div style="display:flex; gap: 10px; flex-wrap: wrap; align-items: center;">
        <input v-model="form.name" placeholder="Nombre (ej. Pablo)" style="min-width: 240px;" />

        <select v-model="form.role" style="min-width: 160px;">
          <option value="adult">Adulto</option>
          <option value="child">Niño</option>
        </select>

        <button class="btn" type="button" :disabled="saving || store.loading" @click="submit">
          Crear
        </button>
      </div>
    </div>

    <!-- Lista -->
    <div class="card" style="padding: 14px;">
      <div style="display:flex; align-items:center; justify-content: space-between; gap: 10px; margin-bottom: 10px;">
        <div class="subtle">Miembros</div>
        <button class="btn" type="button" :disabled="store.loading" @click="store.fetchMembers()">
          Refrescar
        </button>
      </div>

      <table style="width:100%; border-collapse: collapse;">
        <thead>
          <tr>
            <th style="text-align:left; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Nombre</th>
            <th style="text-align:left; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Rol</th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Estado</th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Acciones</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="m in membersSorted" :key="m.id">
            <td style="padding:8px 6px;">
              {{ m.name }}
            </td>

            <td style="padding:8px 6px;">
              <span class="subtle">
                {{ m.role === 'adult' ? 'Adulto' : 'Niño' }}
              </span>
            </td>

            <td style="padding:8px 6px; text-align:right;">
              <button
                class="btn"
                type="button"
                :disabled="store.loading || rowBusy[m.id]"
                @click="toggleActive(m.id, !m.is_active)"
                :style="m.is_active ? '' : 'opacity:.7'"
              >
                {{ m.is_active ? 'Activo' : 'Inactivo' }}
              </button>
            </td>

            <td style="padding:8px 6px; text-align:right;">
              <div style="display:inline-flex; gap: 10px;">
                <button class="btn" type="button" :disabled="store.loading || rowBusy[m.id]" @click="openEdit(m)">
                  Editar
                </button>
                <button class="btn" type="button" :disabled="store.loading || rowBusy[m.id]" @click="removeMember(m)">
                  Eliminar
                </button>
              </div>
            </td>
          </tr>

          <tr v-if="!membersSorted.length">
            <td colspan="4" class="subtle" style="padding: 10px 6px;">
              No hay miembros todavía.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal editar -->
    <BaseModal :open="editOpen" title="Editar miembro" @close="editOpen = false">
      <div style="display:grid; gap: 12px;">
        <div>
          <div class="subtle" style="margin-bottom: 6px;">Nombre</div>
          <input v-model="editForm.name" />
        </div>

        <div>
          <div class="subtle" style="margin-bottom: 6px;">Rol</div>
          <select v-model="editForm.role">
            <option value="adult">Adulto</option>
            <option value="child">Niño</option>
          </select>
        </div>

        <div style="display:flex; justify-content: flex-end; gap: 10px;">
          <button class="btn" type="button" @click="editOpen = false">Cancelar</button>
          <button
            class="btn"
            type="button"
            :disabled="store.loading || (editForm.id != null && rowBusy[editForm.id])"
            @click="saveEdit"
          >
            Guardar
          </button>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
