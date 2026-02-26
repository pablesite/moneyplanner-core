import { computed, reactive, ref } from 'vue';
import { usePeopleStore } from '@/domains/people/store';
import type { FamilyMember, OwnershipRead } from '@/domains/people/types';

type MemberRole = 'adult' | 'child';

export function usePeopleMembers() {
  const store = usePeopleStore();

  const form = reactive({
    name: '',
    role: 'adult' as MemberRole,
  });

  const saving = ref(false);
  const rowBusy = ref<Record<number, boolean>>({});
  const createOpen = ref(false);
  const successMessage = ref<string | null>(null);

  const editOpen = ref(false);
  const editForm = reactive({
    id: null as number | null,
    name: '',
    role: 'adult' as MemberRole,
  });

  const prettyError = computed(() => store.error);

  const membersSorted = computed(() => {
    const arr = [...store.members];
    arr.sort((a, b) => {
      if (a.role !== b.role) return a.role === 'adult' ? -1 : 1;
      if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    return arr;
  });

  async function ensureLoaded() {
    if (!store.members.length) await store.fetchMembers();
  }

  async function refreshMembers() {
    await store.fetchMembers();
  }

  function openCreate() {
    store.clearError();
    successMessage.value = null;
    form.name = '';
    form.role = 'adult';
    createOpen.value = true;
  }

  function closeCreate() {
    createOpen.value = false;
  }

  async function submit() {
    const name = form.name.trim();
    if (!name) return;

    saving.value = true;
    store.clearError();
    successMessage.value = null;

    try {
      await store.createMember({ name, role: form.role });
      form.name = '';
      form.role = 'adult';
      createOpen.value = false;
      successMessage.value = 'Miembro creado correctamente.';
    } finally {
      saving.value = false;
    }
  }

  async function withRowBusy(id: number, fn: () => Promise<void>) {
    if (rowBusy.value[id]) return;
    rowBusy.value[id] = true;
    store.clearError();
    successMessage.value = null;
    try {
      await fn();
    } finally {
      rowBusy.value[id] = false;
    }
  }

  async function toggleActive(id: number, next: boolean) {
    await withRowBusy(id, async () => {
      await store.updateMember(id, { is_active: next });
      successMessage.value = next
        ? 'Miembro activado correctamente.'
        : 'Miembro desactivado correctamente.';
    });
  }

  function openEdit(member: FamilyMember) {
    store.clearError();
    successMessage.value = null;
    editForm.id = member.id;
    editForm.name = member.name;
    editForm.role = member.role;
    editOpen.value = true;
  }

  function closeEdit() {
    editOpen.value = false;
  }

  async function saveEdit() {
    if (editForm.id == null) return;
    const name = editForm.name.trim();
    if (!name) return;

    await withRowBusy(editForm.id, async () => {
      await store.updateMember(editForm.id!, { name, role: editForm.role });
      editOpen.value = false;
      successMessage.value = 'Miembro actualizado correctamente.';
    });
  }

  async function removeMember(member: FamilyMember) {
    const ok = window.confirm(`¿Eliminar a "${member.name}"?\n\nSolo se podrá si no está en uso.`);
    if (!ok) return;
    await withRowBusy(member.id, async () => {
      await store.deleteMember(member.id);
      successMessage.value = 'Miembro eliminado correctamente.';
    });
  }

  return {
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
  };
}

export function usePeopleOwnerships() {
  const store = usePeopleStore();

  const showModal = ref(false);
  const editId = ref<number | null>(null);
  const successMessage = ref<string | null>(null);

  const form = reactive({
    memberIds: [] as number[],
    percents: {} as Record<number, string>,
  });

  const adults = computed(() => store.activeAdults);

  const canCreate = computed(() => {
    if (form.memberIds.length < 2) return false;

    for (const id of form.memberIds) {
      const p = Number(String(form.percents[id] ?? '').replace(',', '.'));
      if (!Number.isFinite(p) || p <= 0 || p > 100) return false;
    }

    const total = form.memberIds.reduce((acc, id) => {
      const p = Number(String(form.percents[id] ?? '0').replace(',', '.'));
      return acc + (Number.isFinite(p) ? p : 0);
    }, 0);

    return Math.abs(total - 100) < 0.0001;
  });

  const ownershipsSorted = computed(() => {
    const arr = [...store.ownerships].filter((ownership) => ownership.kind === 'shared');
    arr.sort((a, b) => a.id - b.id);
    return arr;
  });

  async function ensureLoaded() {
    if (!store.ownerships.length) await store.fetchOwnerships();
    if (!store.members.length) await store.fetchMembers();
  }

  async function refreshOwnerships() {
    await store.fetchOwnerships();
  }

  function resetModal() {
    showModal.value = false;
    form.memberIds = [];
    form.percents = {};
    editId.value = null;
  }

  function openCreate() {
    successMessage.value = null;
    editId.value = null;
    form.memberIds = [];
    form.percents = {};
    showModal.value = true;
  }

  function openEdit(ownership: OwnershipRead) {
    if (ownership.kind !== 'shared') return;
    successMessage.value = null;
    editId.value = ownership.id;
    form.memberIds = (ownership.splits ?? [])
      .map((split) => split.member?.id)
      .filter((id): id is number => id != null);
    form.percents = {};
    (ownership.splits ?? []).forEach((split) => {
      if (split.member?.id != null) form.percents[split.member.id] = String(split.percent ?? '');
    });
    showModal.value = true;
  }

  function toggleMember(id: number) {
    const idx = form.memberIds.indexOf(id);
    if (idx >= 0) {
      form.memberIds.splice(idx, 1);
      delete form.percents[id];
    } else {
      form.memberIds.push(id);
      form.percents[id] = form.percents[id] ?? '';
    }
  }

  function setEqualSplit() {
    if (form.memberIds.length < 2) return;
    const each = (100 / form.memberIds.length).toFixed(2);
    for (const id of form.memberIds) form.percents[id] = each;

    const sum = (form.memberIds.length - 1) * Number(each);
    const last = (100 - sum).toFixed(2);
    const lastMemberId = form.memberIds[form.memberIds.length - 1];
    if (lastMemberId == null) return;
    form.percents[lastMemberId] = last;
  }

  async function submit() {
    if (!canCreate.value) return;
    successMessage.value = null;

    const splits = form.memberIds.map((id) => ({
      member_id: id,
      percent: String(form.percents[id]).replace(',', '.'),
    }));

    if (editId.value != null) {
      await store.updateSharedOwnership(editId.value, { splits });
      successMessage.value = 'Titularidad compartida actualizada correctamente.';
    } else {
      await store.createSharedOwnership({ splits });
      successMessage.value = 'Titularidad compartida creada correctamente.';
    }

    resetModal();
  }

  async function removeOwnership(id: number) {
    const ok = window.confirm('¿Eliminar esta titularidad compartida? (Solo si no está en uso)');
    if (!ok) return;
    successMessage.value = null;
    await store.deleteOwnership(id);
    successMessage.value = 'Titularidad compartida eliminada correctamente.';
  }

  return {
    store,
    showModal,
    editId,
    successMessage,
    form,
    adults,
    canCreate,
    ownershipsSorted,
    ensureLoaded,
    refreshOwnerships,
    resetModal,
    openCreate,
    openEdit,
    toggleMember,
    setEqualSplit,
    submit,
    removeOwnership,
  };
}
