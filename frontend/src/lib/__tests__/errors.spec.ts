import axios from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { getApiErrorCode, toApiErrorMessage } from '@/lib/errors';

describe('core api error helper', () => {
  it('extracts API code from axios envelope', () => {
    const err = { response: { data: { error: { code: 'permission_denied' } } } };
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);
    expect(getApiErrorCode(err)).toBe('permission_denied');
    spy.mockRestore();
  });

  it('maps known API codes to human messages', () => {
    const err = { response: { data: { error: { code: 'subscription_blocked' } } } };
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);
    expect(toApiErrorMessage(err)).toContain('suscripcion');
    spy.mockRestore();
  });

  it('prioritizes validation details from API envelope', () => {
    const err = {
      response: {
        data: {
          error: {
            code: 'validation_error',
            message: 'Request failed.',
            details: {
              market_value_override_date: ['Requerida si se informa valor de mercado manual.'],
            },
          },
        },
      },
      message: 'fallback',
    };
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);
    expect(toApiErrorMessage(err)).toBe(
      'market_value_override_date: Requerida si se informa valor de mercado manual.',
    );
    spy.mockRestore();
  });

  it('falls back to envelope message, validation payload, string payload, error message and default', () => {
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);
    expect(
      toApiErrorMessage({ response: { data: { error: { message: 'boom' } } }, message: 'x' }),
    ).toBe('boom');
    expect(toApiErrorMessage({ response: { data: { detail: 'x' } }, message: 'fallback' })).toBe(
      'x',
    );
    expect(toApiErrorMessage({ response: { data: 'plain' }, message: 'x' })).toBe('plain');
    expect(toApiErrorMessage({ message: 'fallback' })).toBe('fallback');
    expect(toApiErrorMessage({})).toBe('Error');
    spy.mockRestore();
  });

  it('maps 401 token endpoint to invalid credentials message', () => {
    const err = {
      response: {
        status: 401,
        data: { detail: 'No active account found with the given credentials' },
      },
      config: { url: '/api/auth/token/' },
      message: 'Request failed with status code 401',
    };
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);
    expect(toApiErrorMessage(err)).toBe('Usuario o contraseña incorrectos.');
    spy.mockRestore();
  });

  it('returns null code for non axios errors', () => {
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(false);
    expect(getApiErrorCode(new Error('x'))).toBeNull();
    spy.mockRestore();
  });
});
