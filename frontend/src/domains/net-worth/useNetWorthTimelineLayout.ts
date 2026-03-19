import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from 'vue';
import type {
  DisplayedTimelinePoint,
  PositionRow,
} from '@/domains/net-worth/useNetWorthPageMetrics';

export function useNetWorthTimelineLayout(params: {
  showCategoryWorkspace: ComputedRef<boolean>;
  visibleTimelineRows: ComputedRef<DisplayedTimelinePoint[]>;
  selectedPosition: ComputedRef<PositionRow | null>;
  timelineColumnRef: Ref<HTMLElement | null>;
}) {
  const timelineSidebarHeight = ref<number | null>(null);
  const isDesktopTimelineLayout = ref(false);
  let timelineColumnResizeObserver: ResizeObserver | null = null;

  function syncTimelineLayoutViewport(): void {
    if (typeof window === 'undefined') return;
    isDesktopTimelineLayout.value = window.innerWidth > 1024;
  }

  function syncTimelineSidebarHeight(): void {
    if (!isDesktopTimelineLayout.value) {
      timelineSidebarHeight.value = null;
      return;
    }

    const nextHeight = params.timelineColumnRef.value?.offsetHeight ?? null;
    timelineSidebarHeight.value = nextHeight && nextHeight > 0 ? nextHeight : null;
  }

  const timelineSidebarPanelStyle = computed<Record<string, string> | undefined>(() => {
    if (!isDesktopTimelineLayout.value || timelineSidebarHeight.value == null) return undefined;
    const height = `${timelineSidebarHeight.value}px`;
    return {
      height,
      maxHeight: height,
    };
  });

  onMounted(() => {
    syncTimelineLayoutViewport();
    void nextTick(syncTimelineSidebarHeight);

    if (typeof window !== 'undefined') {
      window.addEventListener('resize', syncTimelineLayoutViewport);
      window.addEventListener('resize', syncTimelineSidebarHeight);
    }

    if (typeof ResizeObserver !== 'undefined') {
      timelineColumnResizeObserver = new ResizeObserver(() => {
        syncTimelineSidebarHeight();
      });
      if (params.timelineColumnRef.value) {
        timelineColumnResizeObserver.observe(params.timelineColumnRef.value);
      }
    }
  });

  onBeforeUnmount(() => {
    timelineColumnResizeObserver?.disconnect();
    timelineColumnResizeObserver = null;

    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', syncTimelineLayoutViewport);
      window.removeEventListener('resize', syncTimelineSidebarHeight);
    }
  });

  watch(
    [params.showCategoryWorkspace, params.visibleTimelineRows, params.selectedPosition],
    async () => {
      await nextTick();
      syncTimelineSidebarHeight();
    },
    { deep: true },
  );

  return {
    timelineSidebarPanelStyle,
  };
}
