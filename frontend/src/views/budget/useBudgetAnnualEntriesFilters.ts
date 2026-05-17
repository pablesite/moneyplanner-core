import { ref, watch, type Ref } from 'vue';

export type OwnerFilterValue = number | 'all' | 'unassigned';
export type VisibilityFilterMode = 'active' | 'archived' | 'all';
export type OwnershipOption = { id: number; label: string };

export function useBudgetAnnualEntriesFilters(
  globalOwnershipFilterOptions: Ref<OwnershipOption[]>,
) {
  const globalOwnershipFilter = ref<OwnerFilterValue>('all');
  const assetOwnershipFilter = ref<OwnerFilterValue>('all');
  const liabilityOwnershipFilter = ref<OwnerFilterValue>('all');
  const visibilityFilterMode = ref<VisibilityFilterMode>('active');

  watch(
    globalOwnershipFilterOptions,
    (options) => {
      const filter = globalOwnershipFilter.value;
      if (filter === 'all' || filter === 'unassigned') return;
      if (!options.some((option) => option.id === filter)) {
        globalOwnershipFilter.value = 'all';
      }
    },
    { immediate: true },
  );

  watch(
    globalOwnershipFilter,
    (value) => {
      assetOwnershipFilter.value = value;
      liabilityOwnershipFilter.value = value;
    },
    { immediate: true },
  );

  return {
    globalOwnershipFilter,
    assetOwnershipFilter,
    liabilityOwnershipFilter,
    visibilityFilterMode,
  };
}
