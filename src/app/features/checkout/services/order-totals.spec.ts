import { describe, expect, it } from 'vitest';
import { calculateTotals } from './order-totals';

describe('order totals in integer halalas', () => {
  it('returns zero values for an empty cart', () => expect(calculateTotals(0, 0)).toEqual({ subtotalHalalas: 0, discountHalalas: 0, taxHalalas: 0, payableHalalas: 0 }));
  it('applies a discount before VAT', () => expect(calculateTotals(10000, 5)).toEqual({ subtotalHalalas: 10000, discountHalalas: 500, taxHalalas: 1425, payableHalalas: 10925 }));
  it('rounds fractional halalas at VAT calculation', () => expect(calculateTotals(101, 0).taxHalalas).toBe(15));
});
