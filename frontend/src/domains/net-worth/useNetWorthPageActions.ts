import { computed, type ComputedRef, type Ref } from 'vue';

type PositionRow = {
  id: number;
  type: 'asset' | 'liability';
  category: string;
};

type TimelinePreset = '1m' | '3m' | '6m' | '1a' | '5a' | 'all';

type StoreLike = {
  positionTimeline: unknown;
  assetValuations: unknown[];
  liabilityValuations: unknown[];
  investmentEvents: unknown[];
  liquidityEvents: unknown[];
  liabilityEvents: unknown[];
  fetchTimeline: (category: string | null, categoryType: 'asset' | 'liability') => Promise<void>;
  fetchPositionTimeline: (type: 'asset' | 'liability', id: number) => Promise<void>;
  fetchPositionActivity: (
    type: 'asset' | 'liability',
    id: number,
    category: string | null,
  ) => Promise<void>;
};

export function useNetWorthPageActions<
  TRow extends PositionRow,
  TAssetPayload,
  TLiabilityPayload,
>(params: {
  store: StoreLike;
  selectedPositionType: Ref<'asset' | 'liability' | null>;
  selectedPositionId: Ref<number | null>;
  selectedTimelineCategory: Ref<string | null>;
  selectedTimelineCategoryType: Ref<'asset' | 'liability'>;
  selectedTimelinePreset: Ref<TimelinePreset>;
  customTimelineWindow: Ref<{ start: number; end: number } | null>;
  createAssetCategory: Ref<string | null>;
  createLiabilityCategory: Ref<string | null>;
  showAssetModal: Ref<boolean>;
  showLiabilityModal: Ref<boolean>;
  availablePositionRows: ComputedRef<TRow[]>;
  timelineWindow: ComputedRef<{ start: number; end: number }>;
  submitAsset: (payload: TAssetPayload) => Promise<void>;
  submitLiability: (payload: TLiabilityPayload) => Promise<void>;
  resetAccountingActivity: () => void;
  loadAccountingActivity: (row: TRow) => Promise<void>;
}) {
  function resetPositionSelection(): void {
    params.selectedPositionType.value = null;
    params.selectedPositionId.value = null;
    params.store.positionTimeline = null;
    params.store.assetValuations = [];
    params.store.liabilityValuations = [];
    params.store.investmentEvents = [];
    params.store.liquidityEvents = [];
    params.store.liabilityEvents = [];
    params.resetAccountingActivity();
  }

  function openCreateModal(type: 'asset' | 'liability', category: string | null = null): void {
    resetPositionSelection();
    if (type === 'asset') {
      params.createAssetCategory.value = category;
      params.showAssetModal.value = true;
      return;
    }
    params.createLiabilityCategory.value = category;
    params.showLiabilityModal.value = true;
  }

  async function submitAssetFromView(payload: TAssetPayload): Promise<void> {
    await params.submitAsset(payload);
    params.createAssetCategory.value = null;
  }

  async function submitLiabilityFromView(payload: TLiabilityPayload): Promise<void> {
    await params.submitLiability(payload);
    params.createLiabilityCategory.value = null;
  }

  async function applyTimelineCategoryFilter(
    category: string | null,
    categoryType: 'asset' | 'liability' = 'asset',
  ): Promise<void> {
    params.selectedTimelineCategory.value = category;
    params.selectedTimelineCategoryType.value = categoryType;
    params.selectedTimelinePreset.value = 'all';
    params.customTimelineWindow.value = null;
    resetPositionSelection();
    await params.store.fetchTimeline(category, categoryType);
  }

  async function resetTimelineSelection(): Promise<void> {
    await applyTimelineCategoryFilter(null, 'asset');
  }

  async function applyCompositionCategoryFilter(payload: {
    key: string;
    type: 'asset' | 'liability';
  }): Promise<void> {
    const isSelectedCategory =
      params.selectedTimelineCategory.value === payload.key &&
      params.selectedTimelineCategoryType.value === payload.type;

    if (isSelectedCategory) {
      await applyTimelineCategoryFilter(null, 'asset');
      return;
    }

    await applyTimelineCategoryFilter(payload.key, payload.type);
  }

  async function handleCompositionAddType(payload: { type: 'asset' | 'liability' }): Promise<void> {
    openCreateModal(payload.type, null);
  }

  async function selectPosition(row: TRow): Promise<void> {
    params.selectedPositionType.value = row.type;
    params.selectedPositionId.value = row.id;
    params.selectedTimelinePreset.value = 'all';
    params.customTimelineWindow.value = null;
    await Promise.all([
      params.store.fetchPositionTimeline(row.type, row.id),
      params.store.fetchPositionActivity(
        row.type,
        row.id,
        row.type === 'asset' ? row.category : null,
      ),
      params.loadAccountingActivity(row),
    ]);
  }

  function setTimelinePreset(preset: TimelinePreset): void {
    params.selectedTimelinePreset.value = preset;
    params.customTimelineWindow.value = null;
  }

  function updateTimelineWindowStart(rawValue: string): void {
    const nextStart = Number(rawValue);
    const currentEnd = params.timelineWindow.value.end;
    params.customTimelineWindow.value = {
      start: Math.min(nextStart, currentEnd),
      end: currentEnd,
    };
  }

  function updateTimelineWindowEnd(rawValue: string): void {
    const nextEnd = Number(rawValue);
    const currentStart = params.timelineWindow.value.start;
    params.customTimelineWindow.value = {
      start: currentStart,
      end: Math.max(currentStart, nextEnd),
    };
  }

  function onPositionSelection(event: Event): void {
    const target = event.target as HTMLSelectElement | null;
    const rawValue = target?.value ?? '';
    if (!rawValue) {
      resetPositionSelection();
      return;
    }

    const selectedId = Number(rawValue);
    const row = params.availablePositionRows.value.find((item) => item.id === selectedId);
    if (!row) {
      resetPositionSelection();
      return;
    }

    void selectPosition(row);
  }

  const assetCreateInitial = computed(() =>
    params.createAssetCategory.value ? { category: params.createAssetCategory.value } : undefined,
  );

  const liabilityCreateInitial = computed(() =>
    params.createLiabilityCategory.value
      ? { category: params.createLiabilityCategory.value }
      : undefined,
  );

  return {
    resetPositionSelection,
    openCreateModal,
    submitAssetFromView,
    submitLiabilityFromView,
    applyTimelineCategoryFilter,
    resetTimelineSelection,
    applyCompositionCategoryFilter,
    handleCompositionAddType,
    selectPosition,
    setTimelinePreset,
    updateTimelineWindowStart,
    updateTimelineWindowEnd,
    onPositionSelection,
    assetCreateInitial,
    liabilityCreateInitial,
  };
}
