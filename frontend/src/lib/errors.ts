import axios from 'axios';

type ApiErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function getApiErrorCode(error: unknown): string | null {
  if (!axios.isAxiosError(error)) return null;
  const data = error.response?.data;
  if (!isRecord(data)) return null;
  const envelope = data as ApiErrorEnvelope;
  return typeof envelope.error?.code === 'string' ? envelope.error.code : null;
}

function humanMessageForApiCode(code: string | null): string | null {
  if (code === 'permission_denied') {
    return 'No tienes permisos para realizar esta accion.';
  }
  if (code === 'subscription_blocked') {
    return 'Tu suscripcion no habilita esta funcionalidad premium.';
  }
  return null;
}

function humanMessageForAuthFailure(error: unknown): string | null {
  if (!axios.isAxiosError(error)) return null;

  const status = error.response?.status;
  const url = error.config?.url ?? '';
  if (status === 401 && url.includes('/api/auth/token/')) {
    return 'Usuario o contrasena incorrectos.';
  }

  const data = error.response?.data;
  if (isRecord(data) && typeof data.detail === 'string') {
    if (data.detail.toLowerCase().includes('no active account found')) {
      return 'Usuario o contrasena incorrectos.';
    }
  }

  return null;
}

function firstValidationMessage(data: unknown, path: string[] = []): string | null {
  const label = path.length > 0 ? `${path.join('.')}: ` : '';

  if (typeof data === 'string' && data.trim()) {
    return `${label}${data}`;
  }

  if (Array.isArray(data)) {
    for (const item of data) {
      const nested = firstValidationMessage(item, path);
      if (nested) return nested;
    }
    return null;
  }

  if (!isRecord(data)) return null;

  for (const [field, raw] of Object.entries(data)) {
    if (field === 'error') continue;
    const nextPath = field === 'detail' ? path : [...path, field];
    const nested = firstValidationMessage(raw, nextPath);
    if (nested) return nested;
  }

  if (typeof data.detail === 'string' && data.detail.trim()) {
    return `${label}${data.detail}`;
  }
  return null;
}

export function toApiErrorMessage(error: unknown): string {
  const code = getApiErrorCode(error);
  const mapped = humanMessageForApiCode(code);
  if (mapped) return mapped;

  const authMessage = humanMessageForAuthFailure(error);
  if (authMessage) return authMessage;

  const maybe = error as { response?: { data?: unknown }; message?: string } | null | undefined;
  const data = maybe?.response?.data;
  if (isRecord(data)) {
    const envelope = data as ApiErrorEnvelope;
    const detailsMessage = firstValidationMessage(envelope.error?.details);
    if (detailsMessage) return detailsMessage;

    if (typeof envelope.error?.message === 'string' && envelope.error.message.length > 0) {
      return envelope.error.message;
    }

    const validation = firstValidationMessage(data);
    if (validation) return validation;
  }
  if (typeof data === 'string') return data;
  if (maybe?.message) return maybe.message;
  return 'Error';
}
