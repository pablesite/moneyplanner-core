import type { GuideScope } from './composables';
import { useGuidePhaseDetailState } from './composables';

export function useGuidePhaseDetail(scope: GuideScope) {
  return useGuidePhaseDetailState(scope);
}
