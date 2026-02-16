import { computed, type Component, type ComputedRef } from 'vue';

type ExtensionProps = Record<string, unknown>;

export type NetWorthViewExtensions = {
  HeaderActions: Component | null;
  itemFormProps: ComputedRef<ExtensionProps>;
  itemListProps: ComputedRef<ExtensionProps>;
};

export function useNetWorthViewExtensions(_store?: unknown): NetWorthViewExtensions {
  const emptyProps = computed<ExtensionProps>(() => ({}));
  return {
    HeaderActions: null,
    itemFormProps: emptyProps,
    itemListProps: emptyProps,
  };
}
