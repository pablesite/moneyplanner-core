import axios from 'axios';
import { toApiErrorMessage } from '@/lib/errors';

export function toPeopleErrorMessage(err: unknown): string {
  if (!axios.isAxiosError(err)) return String(err);

  const data: unknown = err.response?.data;
  if (!data) {
    const mapped = toApiErrorMessage(err);
    return mapped && mapped !== 'Error' ? mapped : err.message;
  }

  if (typeof data === 'string') return data;

  if (typeof data === 'object' && data !== null) {
    const map = data as Record<string, unknown>;
    const maybeError = map.error;
    if (typeof maybeError === 'object' && maybeError !== null) {
      const code = (maybeError as Record<string, unknown>).code;
      if (code === 'permission_denied') {
        return 'No tienes permisos para esta acción.';
      }
    }
    if (typeof map.detail === 'string') return map.detail;

    const firstKey = Object.keys(map)[0];
    if (!firstKey) return err.message;
    const value = map[firstKey];
    if (Array.isArray(value)) return `${firstKey}: ${String(value[0] ?? err.message)}`;
    if (typeof value === 'string') return value;
  }

  const mapped = toApiErrorMessage(err);
  if (mapped && mapped !== 'Error') return mapped;
  return err.message;
}
