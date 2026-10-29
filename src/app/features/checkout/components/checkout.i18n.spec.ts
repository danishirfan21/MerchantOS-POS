import { describe, expect, it } from 'vitest';
import { copy, translate } from './checkout.i18n';

describe('English and Arabic UI copy', () => {
  it('has nonempty text in both languages for every supported control and state', () => {
    for (const key of Object.keys(copy) as (keyof typeof copy)[]) {
      expect(translate(key, false).trim()).not.toBe('');
      expect(translate(key, true).trim()).not.toBe('');
      expect(translate(key, true)).not.toBe(translate(key, false));
    }
  });
});
