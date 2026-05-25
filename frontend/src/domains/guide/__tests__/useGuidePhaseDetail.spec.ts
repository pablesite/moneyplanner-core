import { describe, expect, it, vi } from 'vitest';
import { useGuidePhaseDetail } from '../useGuidePhaseDetail';

vi.mock('../composables', () => ({
  useGuidePhaseDetailState: vi.fn((scope: 'core') => ({ scope })),
}));

describe('useGuidePhaseDetail', () => {
  it('delegates to useGuidePhaseDetailState preserving scope', () => {
    expect(useGuidePhaseDetail('core')).toEqual({ scope: 'core' });
  });
});
