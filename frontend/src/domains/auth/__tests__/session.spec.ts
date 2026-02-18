import { beforeEach, describe, expect, it } from 'vitest';
import {
  clearAuthTokens,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from '@/domains/auth/session';

describe('auth session tokens', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('stores and retrieves access/refresh tokens', () => {
    setAccessToken('a1');
    setRefreshToken('r1');
    expect(getAccessToken()).toBe('a1');
    expect(getRefreshToken()).toBe('r1');
  });

  it('clears stored tokens', () => {
    setAccessToken('a1');
    setRefreshToken('r1');
    clearAuthTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });
});
