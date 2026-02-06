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
const createOpen = ref(false);

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
    createOpen.value = false;
  } finally {
    saving.value = false;
  }
}

function openCreate() {
  store.clearError();
  form.name = "";
  form.role = "adult";
  createOpen.value = true;
}

function closeCreate() {
  createOpen.value = false;
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
    <div v-if="prettyError" class="alert member-alert">
      {{ prettyError }}
    </div>
    <!-- Lista -->
    <section class="card member-section">
      <div class="card-header">
        <h2 class="card-header-title">Miembros</h2>
        <div class="member-header-actions">
          <button class="btn" type="button" :disabled="store.loading" @click="store.fetchMembers()">
            Refrescar
          </button>
          <button class="btn btn-primary" type="button" :disabled="store.loading" @click="openCreate">
            Nuevo miembro
          </button>
        </div>
      </div>

      <table class="member-table">
        <thead>
          <tr>
            <th class="member-th">Nombre</th>
            <th class="member-th">Rol</th>
            <th class="member-th member-th-right">Estado</th>
            <th class="member-th member-th-right">Acciones</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="m in membersSorted" :key="m.id">
            <td class="member-td">
              {{ m.name }}
            </td>

            <td class="member-td">
              <span class="subtle">
                {{ m.role === 'adult' ? 'Adulto' : 'Niño' }}
              </span>
            </td>

            <td class="member-td member-td-right">
              <button
                class="btn"
                type="button"
                :disabled="store.loading || rowBusy[m.id]"
                @click="toggleActive(m.id, !m.is_active)"
                :class="{ 'member-status-inactive': !m.is_active }"
              >
                {{ m.is_active ? 'Activo' : 'Inactivo' }}
              </button>
            </td>

            <td class="member-td member-td-right">
              <div class="member-actions">
                <button
                  class="icon-btn"
                  type="button"
                  title="Editar"
                  aria-label="Editar"
                  :disabled="store.loading || rowBusy[m.id]"
                  @click="openEdit(m)"
                >
                  &#9998;&#65039;
                </button>
                <button
                  class="icon-btn"
                  type="button"
                  title="Eliminar"
                  aria-label="Eliminar"
                  :disabled="store.loading || rowBusy[m.id]"
                  @click="removeMember(m)"
                >
                  &#128465;&#65039;
                </button>
              </div>
            </td>
          </tr>

          <tr v-if="!membersSorted.length">
            <td colspan="4" class="subtle member-empty">
              No hay miembros todavía.
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Modal crear -->
    <BaseModal :open="createOpen" title="Nuevo miembro" @close="closeCreate">
      <div class="member-edit-grid">
        <div class="subtle member-card-subtitle">
          Crea miembros de la familia. Al crear un adulto, se generara automaticamente su titularidad individual.
        </div>

        <div>
          <div class="subtle member-field-label">Nombre</div>
          <input v-model="form.name" placeholder="Nombre (ej. Pablo)" />
        </div>

        <div>
          <div class="subtle member-field-label">Rol</div>
          <select v-model="form.role">
            <option value="adult">Adulto</option>
            <option value="child">Nino</option>
          </select>
        </div>

        <div class="member-edit-actions">
          <button class="btn" type="button" @click="closeCreate">Cancelar</button>
          <button class="btn btn-primary" type="button" :disabled="saving || store.loading" @click="submit">
            Crear
          </button>
        </div>
      </div>
    </BaseModal>

    <!-- Modal editar -->
    <BaseModal :open="editOpen" title="Editar miembro" @close="editOpen = false">
      <div class="member-edit-grid">
        <div>
          <div class="subtle member-field-label">Nombre</div>
          <input v-model="editForm.name" />
        </div>

        <div>
          <div class="subtle member-field-label">Rol</div>
          <select v-model="editForm.role">
            <option value="adult">Adulto</option>
            <option value="child">Niño</option>
          </select>
        </div>

        <div class="member-edit-actions">
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

<style scoped>
.member-alert{
  margin-bottom: 12px;
}

.member-card-subtitle{
  margin-bottom: 10px;
}

.member-header-actions{
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.member-table{
  width: 100%;
  border-collapse: collapse;
}

.member-th{
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.member-th-right{
  text-align: right;
}

.member-td{
  padding: 8px 6px;
}

.member-td-right{
  text-align: right;
}

.member-actions{
  display: inline-flex;
  gap: 10px;
}

.member-empty{
  padding: 10px 6px;
}

.member-status-inactive{
  opacity: 0.7;
}

.member-edit-grid{
  display: grid;
  gap: 12px;
}

.member-field-label{
  margin-bottom: 6px;
}

.member-edit-actions{
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
