import { coreApi } from '@/lib/api';
import type { MonthlyCloseStateResponse } from './types';

export const budgetApi = coreApi;
export { toApiErrorMessage as toBudgetErrorMessage } from '@/lib/errors';

export async function getMonthlyClose(
  year: number,
  month: number,
): Promise<MonthlyCloseStateResponse> {
  const response = await coreApi.get<MonthlyCloseStateResponse>(
    `/api/budget/monthly-close/${year}/${month}/`,
  );
  return response.data;
}

export async function patchMonthlyClose(
  year: number,
  month: number,
  payload: Record<string, unknown>,
): Promise<MonthlyCloseStateResponse> {
  const response = await coreApi.patch<MonthlyCloseStateResponse>(
    `/api/budget/monthly-close/${year}/${month}/`,
    payload,
  );
  return response.data;
}

export async function finalizeMonthlyClose(year: number, month: number): Promise<void> {
  await coreApi.post(`/api/budget/monthly-close/${year}/${month}/finalize/`);
}

export async function reopenMonthlyClose(year: number, month: number): Promise<void> {
  await coreApi.post(`/api/budget/monthly-close/${year}/${month}/reopen/`);
}

export async function lockMonthlyClose(year: number, month: number): Promise<void> {
  await coreApi.post(`/api/budget/monthly-close/${year}/${month}/lock/`);
}
