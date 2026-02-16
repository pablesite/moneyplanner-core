import type { Component } from 'vue';

export type NetWorthViewExtensions = {
  HeaderActions: Component | null;
};

export function useNetWorthViewExtensions(): NetWorthViewExtensions {
  return {
    HeaderActions: null,
  };
}
