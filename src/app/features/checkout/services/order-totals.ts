export function calculateTotals(subtotalHalalas: number, discountPercent: number) {
  const discountHalalas = Math.round(subtotalHalalas * discountPercent / 100);
  const taxHalalas = Math.round((subtotalHalalas - discountHalalas) * 15 / 100);
  return { subtotalHalalas, discountHalalas, taxHalalas, payableHalalas: subtotalHalalas - discountHalalas + taxHalalas };
}
