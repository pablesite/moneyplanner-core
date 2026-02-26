import { computed, type Component, type ComputedRef } from 'vue';
import { capabilities } from '@/domains/capabilities';

type ExtensionProps = Record<string, unknown>;

export type NetWorthViewExtensions = {
  HeaderActions: Component | null;
  itemFormProps: ComputedRef<ExtensionProps>;
  itemListProps: ComputedRef<ExtensionProps>;
};

export function useNetWorthViewExtensions(store?: unknown): NetWorthViewExtensions {
  const ownershipProps = computed<ExtensionProps>(() => {
    const baseCurrency =
      store && typeof store === 'object'
        ? (('baseCurrency' in store &&
            typeof (store as { baseCurrency?: unknown }).baseCurrency === 'string'
            ? (store as { baseCurrency?: string | null }).baseCurrency
            : null) ??
          (('summary' in store &&
            typeof (store as { summary?: { base_currency?: unknown } | null }).summary?.base_currency ===
              'string')
            ? String((store as { summary?: { base_currency?: string | null } | null }).summary?.base_currency)
            : null))
        : null;
    const baseProps = baseCurrency ? { defaultCurrency: baseCurrency } : {};

    if (!capabilities.people || !store || typeof store !== 'object') {
      return baseProps;
    }
    if (!('ownerships' in store)) {
      return baseProps;
    }

    const ownerships = (store as { ownerships?: unknown }).ownerships;
    if (!Array.isArray(ownerships)) {
      return baseProps;
    }

    return { ...baseProps, ownerships };
  });

  return {
    HeaderActions: null,
    itemFormProps: ownershipProps,
    itemListProps: ownershipProps,
  };
}
