import { describe, expect, it } from 'vitest';
import { nextTick, ref } from 'vue';
import { useDataInputFilters } from '@/views/data-input/useDataInputFilters';

describe('useDataInputFilters', () => {
  it('keeps asset/liability filters synced with global filter', async () => {
    const options = ref([
      { id: 1, label: 'Alice' },
      { id: 2, label: 'Bob' },
    ]);
    const filters = useDataInputFilters(options);

    expect(filters.globalOwnershipFilter.value).toBe('all');
    expect(filters.assetOwnershipFilter.value).toBe('all');
    expect(filters.liabilityOwnershipFilter.value).toBe('all');

    filters.globalOwnershipFilter.value = 2;
    await nextTick();
    expect(filters.assetOwnershipFilter.value).toBe(2);
    expect(filters.liabilityOwnershipFilter.value).toBe(2);

    filters.globalOwnershipFilter.value = 'unassigned';
    await nextTick();
    expect(filters.assetOwnershipFilter.value).toBe('unassigned');
    expect(filters.liabilityOwnershipFilter.value).toBe('unassigned');
  });

  it('resets global filter when selected owner disappears from options', async () => {
    const options = ref([
      { id: 1, label: 'Alice' },
      { id: 2, label: 'Bob' },
    ]);
    const filters = useDataInputFilters(options);
    filters.globalOwnershipFilter.value = 2;
    await nextTick();

    options.value = [{ id: 1, label: 'Alice' }];
    await nextTick();
    expect(filters.globalOwnershipFilter.value).toBe('all');
    expect(filters.assetOwnershipFilter.value).toBe('all');
    expect(filters.liabilityOwnershipFilter.value).toBe('all');
  });
});
