import { CartService } from './cart.service';
import { Product } from '../../../core/models/product';

const product: Product = { id:'test-1', sku:'TEST-1', name:'Test product', nameAr:'منتج', category:'Audio', priceHalalas:1299, stock:2, color:'mint', icon:'◖' };

import { describe, it, expect, beforeEach } from 'vitest';

describe('CartService', () => {
  let cart: CartService;
  beforeEach(() => { cart = new CartService(); });

  it('adds a product and calculates its integer-halalas subtotal', () => {
    expect(cart.add(product)).toBe(true);
    expect(cart.itemCount()).toBe(1);
    expect(cart.subtotalHalalas()).toBe(1299);
  });

  it('increments an existing line instead of creating duplicates', () => {
    cart.add(product); cart.add(product);
    expect(cart.lines().length).toBe(1);
    expect(cart.lines()[0].quantity).toBe(2);
    expect(cart.subtotalHalalas()).toBe(2598);
  });

  it('does not allow adding beyond available stock', () => {
    cart.add(product); cart.add(product);
    expect(cart.add(product)).toBe(false);
    expect(cart.itemCount()).toBe(2);
  });

  it('clamps quantity changes to stock and removes a line at zero', () => {
    cart.add(product); cart.setQuantity(product.id, 50);
    expect(cart.lines()[0].quantity).toBe(2);
    cart.setQuantity(product.id, 0);
    expect(cart.lines()).toEqual([]);
    expect(cart.subtotalHalalas()).toBe(0);
  });

  it('removes one product and clears all cart lines', () => {
    const second = { ...product, id:'test-2', stock:8 };
    cart.add(product); cart.add(second); cart.remove(product.id);
    expect(cart.lines().map((line) => line.product.id)).toEqual(['test-2']);
    cart.clear();
    expect(cart.itemCount()).toBe(0);
  });
});

describe('additional cart boundaries', () => {
  it('removes the final unit when decremented to zero', () => {
    const cart = new CartService(); cart.add(product); cart.setQuantity(product.id, 0);
    expect(cart.itemCount()).toBe(0);
    expect(cart.subtotalHalalas()).toBe(0);
  });
  it('totals multiple products and quantities', () => {
    const cart = new CartService(); const other = { ...product, id: 'other', priceHalalas: 250, stock: 4 };
    cart.add(product); cart.add(product); cart.add(other);
    expect(cart.subtotalHalalas()).toBe(2848);
    expect(cart.itemCount()).toBe(3);
  });
});

describe('API catalog reconciliation', () => {
  it('updates cart prices and clamps quantities to refreshed stock', () => {
    const cart = new CartService();
    cart.add(product); cart.add(product);
    cart.syncCatalog([{...product, priceHalalas: 2000, stock: 1}]);
    expect(cart.itemCount()).toBe(1);
    expect(cart.subtotalHalalas()).toBe(2000);
  });

  it('removes unavailable or deleted products after a catalog refresh', () => {
    const cart = new CartService(); cart.add(product);
    cart.syncCatalog([]);
    expect(cart.itemCount()).toBe(0);
  });
});
