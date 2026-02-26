<script setup lang="ts">
import { onMounted } from 'vue';
import BaseModal from '@/domains/ui/components/BaseModal.vue';
import { usePeopleMembers } from '@/domains/people/composables';

const {
  store,
  form,
  saving,
  rowBusy,
  createOpen,
  successMessage,
  editOpen,
  editForm,
  prettyError,
  membersSorted,
  ensureLoaded,
  refreshMembers,
  openCreate,
  closeCreate,
  submit,
  toggleActive,
  openEdit,
  closeEdit,
  saveEdit,
  removeMember,
} = usePeopleMembers();

onMounted(async () => {
  await ensureLoaded();
});
</script>

<template>
  <div>
    <div v-if="prettyError" class="alert ui-people-alert">
      {{ prettyError }}
    </div>
    <div v-if="successMessage" class="ui-alert-success">
      {{ successMessage }}
    </div>
    <!-- Lista -->
    <section class="card">
      <div class="card-header">
        <h2 class="card-header-title">Miembros</h2>
        <div class="ui-people-header-actions">
          <button class="btn" type="button" :disabled="store.loading" @click="refreshMembers()">
            Refrescar
          </button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="store.loading"
            @click="openCreate"
          >
            Nuevo miembro
          </button>
        </div>
      </div>

      <table class="ui-data-table">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Rol</th>
            <th class="text-right">Estado</th>
            <th class="ui-data-table-actions">Acciones</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="m in membersSorted" :key="m.id">
            <td>
              {{ m.name }}
            </td>

            <td>
              <span class="subtle">
                {{ m.role === 'adult' ? 'Adulto' : 'Niño' }}
              </span>
            </td>

            <td class="text-right">
              <button
                class="btn"
                type="button"
                :disabled="store.loading || rowBusy[m.id]"
                :class="{ 'ui-people-status-inactive': !m.is_active }"
                @click="toggleActive(m.id, !m.is_active)"
              >
                {{ m.is_active ? 'Activo' : 'Inactivo' }}
              </button>
            </td>

            <td class="ui-data-table-actions">
              <div class="ui-people-row-actions">
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
            <td colspan="4" class="ui-table-empty">No hay miembros todavía.</td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="store.loading" class="ui-status-line">Cargando miembros...</div>

    <!-- Modal crear -->
    <BaseModal :open="createOpen" title="Nuevo miembro" @close="closeCreate">
      <div class="form-grid">
        <div class="subtle ui-people-card-subtitle">
          Crea miembros de la familia. Al crear un adulto, se generará automáticamente su
          titularidad individual.
        </div>

        <div>
          <div class="subtle ui-people-field-label">Nombre</div>
          <input v-model="form.name" placeholder="Nombre (ej. Pablo)" class="input" />
        </div>

        <div>
          <div class="subtle ui-people-field-label">Rol</div>
          <select v-model="form.role" class="select">
            <option value="adult">Adulto</option>
            <option value="child">Niño</option>
          </select>
        </div>

        <div class="ui-form-actions">
          <button class="btn ui-form-action-btn" type="button" @click="closeCreate">
            Cancelar
          </button>
          <button
            class="btn btn-primary ui-form-action-btn"
            type="button"
            :disabled="saving || store.loading"
            @click="submit"
          >
            Crear
          </button>
        </div>
      </div>
    </BaseModal>

    <!-- Modal editar -->
    <BaseModal :open="editOpen" title="Editar miembro" @close="closeEdit">
      <div class="form-grid">
        <div>
          <div class="subtle ui-people-field-label">Nombre</div>
          <input v-model="editForm.name" class="input" />
        </div>

        <div>
          <div class="subtle ui-people-field-label">Rol</div>
          <select v-model="editForm.role" class="select">
            <option value="adult">Adulto</option>
            <option value="child">Niño</option>
          </select>
        </div>

        <div class="ui-form-actions">
          <button class="btn ui-form-action-btn" type="button" @click="closeEdit">Cancelar</button>
          <button
            class="btn ui-form-action-btn"
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
