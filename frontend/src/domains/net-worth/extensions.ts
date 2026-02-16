import type { Component } from 'vue';

type ExtensionProps = Record<string, unknown>;

export type NetWorthViewExtensions = {
  HeaderActions: Component | null;
  itemFormProps: ExtensionProps;
  itemListProps: ExtensionProps;
};

export function useNetWorthViewExtensions(_store?: unknown): NetWorthViewExtensions {
  return {
    HeaderActions: null,
    itemFormProps: {},
    itemListProps: {},
  };
}
