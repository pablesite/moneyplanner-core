import axios from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { toPeopleErrorMessage } from '@/domains/people/errors';

describe('people error mapper', () => {
  it('returns plain string for non axios errors', () => {
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(false);
    expect(toPeopleErrorMessage('x')).toBe('x');
    spy.mockRestore();
  });

  it('prefers mapped API message when available', () => {
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);
    const err = {
      response: { data: { error: { code: 'permission_denied' } } },
      message: 'fallback',
    };
    expect(toPeopleErrorMessage(err)).toContain('permisos');
    spy.mockRestore();
  });

  it('uses detail/first field or axios message as fallback', () => {
    const spy = vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);
    expect(toPeopleErrorMessage({ response: { data: { detail: 'detail-msg' } } })).toBe(
      'detail-msg',
    );
    expect(toPeopleErrorMessage({ response: { data: { field: ['first-error'] } } })).toBe(
      'field: first-error',
    );
    expect(toPeopleErrorMessage({ response: { data: null }, message: 'axios-msg' })).toBe(
      'axios-msg',
    );
    spy.mockRestore();
  });
});
