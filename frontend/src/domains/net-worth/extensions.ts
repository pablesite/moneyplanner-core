import { computed, type Component, type ComputedRef } from 'vue';

type ExtensionProps = Record<string, unknown>;

export type NetWorthViewExtensions = {
  HeaderActions: Component | null;
  itemFormProps: ComputedRef<ExtensionProps>;
  itemListProps: ComputedRef<ExtensionProps>;
};

export function useNetWorthViewExtensions(_store?: unknown): NetWorthViewExtensions {
  const emptyProps = computed<ExtensionProps>(() => {
    if (!_store || typeof _store !== 'object') return {};
    const baseCurrency =
      ('baseCurrency' in _store && typeof (_store as { baseCurrency?: unknown }).baseCurrency === 'string'
        ? (_store as { baseCurrency?: string | null }).baseCurrency
        : null) ??
      (('summary' in _store &&
        typeof (_store as { summary?: { base_currency?: unknown } | null }).summary?.base_currency ===
          'string')
        ? String((_store as { summary?: { base_currency?: string | null } | null }).summary?.base_currency)
        : null);
    return baseCurrency ? { defaultCurrency: baseCurrency } : {};
  });
  return {
    HeaderActions: null,
    itemFormProps: emptyProps,
    itemListProps: emptyProps,
  };
}
