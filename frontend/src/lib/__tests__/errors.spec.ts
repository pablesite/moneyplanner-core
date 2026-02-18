import { describe, expect, it } from 'vitest';
import { toApiErrorMessage } from '@/lib/errors';

describe('core api error helper', () => {
  it('maps response payload, message and default', () => {
    expect(toApiErrorMessage({ response: { data: { detail: 'x' } }, message: 'fallback' })).toBe(
      JSON.stringify({ detail: 'x' })
    );
    expect(toApiErrorMessage({ message: 'fallback' })).toBe('fallback');
    expect(toApiErrorMessage({})).toBe('Error');
  });
});
