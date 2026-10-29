import { Injectable, computed, signal } from '@angular/core';
import { Product } from '../../../core/models/product';

export interface CartLine { product: Product; quantity: number; }

@Injectable()
export class CartService {
  private readonly linesState = signal<CartLine[]>([]);
  readonly lines = this.linesState.asReadonly();
  readonly itemCount = computed(() => this.linesState().reduce((sum, line) => sum + line.quantity, 0));
  readonly subtotalHalalas = computed(() => this.linesState().reduce((sum, line) => sum + line.product.priceHalalas * line.quantity, 0));

  add(product: Product): boolean {
    const existing = this.linesState().find((line) => line.product.id === product.id);
    if ((existing?.quantity ?? 0) >= product.stock) return false;
    this.linesState.update((lines) => existing
      ? lines.map((line) => line.product.id === product.id ? { ...line, quantity: line.quantity + 1 } : line)
      : [...lines, { product, quantity: 1 }]);
    return true;
  }

  setQuantity(productId: string, quantity: number): void {
    this.linesState.update((lines) => lines.flatMap((line) => {
      if (line.product.id !== productId) return [line];
      const nextQuantity = Math.min(line.product.stock, Math.max(0, Math.floor(quantity)));
      return nextQuantity === 0 ? [] : [{ ...line, quantity: nextQuantity }];
    }));
  }

  /** Refresh cart product references and clamp quantities when the catalog is refetched. */
  syncCatalog(products: Product[]): void {
    const byId = new Map(products.map((product) => [product.id, product]));
    this.linesState.update((lines) => lines.flatMap((line) => {
      const updated = byId.get(line.product.id);
      if (!updated || updated.stock <= 0) return [];
      return [{ product: updated, quantity: Math.min(line.quantity, updated.stock) }];
    }));
  }

  remove(productId: string): void { this.linesState.update((lines) => lines.filter((line) => line.product.id !== productId)); }
  clear(): void { this.linesState.set([]); }
}
