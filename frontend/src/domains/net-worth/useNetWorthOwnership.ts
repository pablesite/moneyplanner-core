import { computed, ref, watch, type Ref } from 'vue';
import type { Ownership } from '@/domains/net-worth/models';

export type OwnershipFilterValue = 'all' | number;

export type OwnershipOption = {
  value: OwnershipFilterValue;
  label: string;
};

function toNumber(raw: unknown): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const value = Number(normalized);
  return Number.isFinite(value) ? value : 0;
}

function normalizeOwnershipSharePercent(raw: unknown): number {
  const value = toNumber(raw);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return value <= 1 ? value * 100 : value;
}

export function useNetWorthOwnership(params: {
  ownerships: Ref<Ownership[]>;
  valueMode: Ref<'nominal' | 'real'>;
}) {
  const ownershipFilter = ref<OwnershipFilterValue>('all');

  const ownershipById = computed(() => {
    const map = new Map<number, Ownership>();
    for (const ownership of params.ownerships.value ?? []) {
      map.set(ownership.id, ownership);
    }
    return map;
  });

  function allocationFractionForNetWorthOwner(
    ownershipRef: number | null | undefined,
    selectedOwner: OwnershipFilterValue,
  ): number {
    if (selectedOwner === 'all') return 1;
    if (ownershipRef == null) return 0;

    const ownership = ownershipById.value.get(ownershipRef);
    if (!ownership) return 0;

    if (ownership.kind === 'individual') {
      return ownership.member?.id === selectedOwner ? 1 : 0;
    }

    const split = (ownership.splits ?? []).find((row) => row.member?.id === selectedOwner);
    if (!split) return 0;
    return normalizeOwnershipSharePercent(split.percent) / 100;
  }

  const ownershipOptions = computed<OwnershipOption[]>(() => {
    const options = new Map<number, OwnershipOption>();
    for (const ownership of params.ownerships.value ?? []) {
      if (ownership.kind === 'individual' && ownership.member?.id && ownership.member.name?.trim()) {
        options.set(ownership.member.id, {
          value: ownership.member.id,
          label: ownership.member.name.trim(),
        });
        continue;
      }

      for (const split of ownership.splits ?? []) {
        if (!split.member?.id || !split.member.name?.trim()) continue;
        options.set(split.member.id, {
          value: split.member.id,
          label: split.member.name.trim(),
        });
      }
    }

    return Array.from(options.values()).sort((a, b) => a.label.localeCompare(b.label, 'es'));
  });

  const selectedOwnershipFilterLabel = computed(() => {
    if (ownershipFilter.value === 'all') return 'Todos';
    return (
      ownershipOptions.value.find((option) => option.value === ownershipFilter.value)?.label ??
      'Todos'
    );
  });

  const ownershipFilterDisabled = computed(() => params.valueMode.value !== 'nominal');

  watch(ownershipOptions, (options) => {
    if (ownershipFilter.value === 'all') return;
    if (!options.some((option) => option.value === ownershipFilter.value)) {
      ownershipFilter.value = 'all';
    }
  });

  watch(params.valueMode, (mode) => {
    if (mode !== 'nominal') ownershipFilter.value = 'all';
  });

  function matchesOwnershipFilter(ownershipRef: number | null | undefined): boolean {
    return allocationFractionForNetWorthOwner(ownershipRef, ownershipFilter.value) > 0;
  }

  function ownershipBadge(ownershipRef: number | null | undefined): string | null {
    if (ownershipRef == null) return null;
    const ownership = ownershipById.value.get(ownershipRef);
    if (!ownership) return null;
    if (ownership.kind === 'individual') return ownership.member?.name?.trim() ?? null;
    const names = (ownership.splits ?? [])
      .map((split) => split.member?.name?.trim())
      .filter((name): name is string => !!name);
    return names.length ? names.join(' + ') : 'Compartido';
  }

  function setOwnershipFilter(value: OwnershipFilterValue): void {
    ownershipFilter.value = value;
  }

  function setValueMode(value: 'nominal' | 'real'): void {
    params.valueMode.value = value;
  }

  return {
    ownershipFilter,
    ownershipOptions,
    selectedOwnershipFilterLabel,
    ownershipFilterDisabled,
    allocationFractionForNetWorthOwner,
    matchesOwnershipFilter,
    ownershipBadge,
    setOwnershipFilter,
    setValueMode,
  };
}
