import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ReceiptLine { productId: string; sku: string; name: string; quantity: number; unitPriceHalalas: number; }
export interface Receipt { id: string; orderNumber: string; createdAt: string; currency: string; status: string; subtotalHalalas: number; discountHalalas: number; vatHalalas: number; payableHalalas: number; paymentMethod: string; changeHalalas: number; items: ReceiptLine[]; }
export interface CheckoutPayload { items: { productId: string; quantity: number }[]; discountPercent: number; paymentMethod: 'cash' | 'card'; cashTenderedHalalas: number | null; idempotencyKey: string; cardScenario: 'success' | 'decline' | null; }

@Injectable({ providedIn: 'root' })
export class CheckoutRepository {
  private readonly http = inject(HttpClient);
  checkout(payload: CheckoutPayload): Observable<Receipt> { return this.http.post<Receipt>('/api/checkout', payload); }
  orders(): Observable<Receipt[]> { return this.http.get<Receipt[]>('/api/receipts'); }
  order(id: string): Observable<Receipt> { return this.http.get<Receipt>(`/api/orders/${encodeURIComponent(id)}`); }
}
