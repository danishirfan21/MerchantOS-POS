import '@angular/compiler';
import { HttpErrorResponse } from '@angular/common/http';
import { Injector, runInInjectionContext } from '@angular/core';
import { Subject, of } from 'rxjs';
import { beforeEach, describe, expect, it } from 'vitest';
import { CheckoutRepository, CheckoutPayload, Receipt } from '../../../core/services/checkout.repository';
import { ProductRepository } from '../../../core/services/product.repository';
import { Product } from '../../../core/models/product';
import { CheckoutComponent } from './checkout.component';

const product: Product = { id: 'p01', sku: 'P01', name: 'Phone', nameAr: 'هاتف', category: 'Phones', priceHalalas: 10000, stock: 8, color: 'mint', icon: '▣' };
const receipt: Receipt = { id: 'order-1', orderNumber: 'MOS-1', createdAt: '', currency: 'SAR', status: 'completed', subtotalHalalas: 10000, discountHalalas: 0, vatHalalas: 1500, payableHalalas: 11500, paymentMethod: 'cash', changeHalalas: 0, items: [] };

describe('checkout request identity', () => {
  let checkout: CheckoutComponent;
  let calls: CheckoutPayload[];
  let responses: Subject<Receipt>[];
  beforeEach(() => {
    calls = []; responses = [];
    const checkoutRepository = { checkout: (payload: CheckoutPayload) => { calls.push({ ...payload }); const response = new Subject<Receipt>(); responses.push(response); return response.asObservable(); } };
    const productRepository = { list: () => of([product]) };
    const injector = Injector.create({ providers: [{ provide: CheckoutRepository, useValue: checkoutRepository }, { provide: ProductRepository, useValue: productRepository }] });
    checkout = runInInjectionContext(injector, () => new CheckoutComponent());
    checkout.addProduct(product);
    checkout.cashTendered.set('500');
  });
  const reject = (responses: Subject<Receipt>[], status: number, code?: string) => responses.at(-1)!.error(new HttpErrorResponse({ status, error: { code } }));
  const submit = (checkout: CheckoutComponent, calls: CheckoutPayload[]) => { checkout.submitCheckout(); expect(calls.at(-1)?.idempotencyKey).toBeTruthy(); return calls.at(-1)!.idempotencyKey; };

  it('clears request state and cart after success; prevents another submission', () => {
    const key = submit(checkout, calls);
    responses[0].next(receipt);
    expect(checkout.cart.itemCount()).toBe(0);
    expect(checkout.screen()).toBe('receipt');
    checkout.submitCheckout();
    expect(calls).toHaveLength(1);
    checkout.addProduct(product); checkout.submitCheckout();
    expect(calls[1].idempotencyKey).not.toBe(key);
  });
  it('uses a fresh key after card decline, including retry of the same values', () => {
    checkout.paymentMethod.set('card'); checkout.cardScenario.set('decline');
    const key = submit(checkout, calls); reject(responses, 402, 'card_declined');
    expect(submit(checkout, calls)).not.toBe(key);
    reject(responses, 402, 'card_declined'); checkout.cardScenario.set('success');
    expect(submit(checkout, calls)).not.toBe(calls[1].idempotencyKey);
  });
  it('validates cash then corrects tender and retries with a new identity', () => {
    checkout.cashTendered.set('1'); checkout.submitCheckout(); expect(calls).toHaveLength(0);
    checkout.cashTendered.set('200'); const key = submit(checkout, calls);
    reject(responses, 400, 'insufficient_cash');
    checkout.cashTendered.set('250'); expect(submit(checkout, calls)).not.toBe(key);
  });
  it('recovers from idempotency conflict even with identical payload', () => {
    const key = submit(checkout, calls); reject(responses, 409, 'idempotency_conflict');
    expect(submit(checkout, calls)).not.toBe(key);
  });
  it('keeps the same key after ambiguous network failure and blocks double submissions', () => {
    const key = submit(checkout, calls);
    checkout.submitCheckout(); expect(calls).toHaveLength(1);
    checkout.closePayment(); expect(checkout.submitting()).toBe(true);
    reject(responses, 0);
    expect(submit(checkout, calls)).toBe(key);
  });
  it('changes identity for quantity, payment method, and discount changes', () => {
    let key = submit(checkout, calls); reject(responses, 0);
    checkout.increase(product.id); let next = submit(checkout, calls); expect(next).not.toBe(key); reject(responses, 0); key = next;
    checkout.paymentMethod.set('card'); next = submit(checkout, calls); expect(next).not.toBe(key); reject(responses, 0); key = next;
    checkout.discountPercent.set(5); next = submit(checkout, calls); expect(next).not.toBe(key);
  });
  it('never reuses an invalidated key when cart values return to earlier values', () => {
    const first = submit(checkout, calls); reject(responses, 0);
    checkout.increase(product.id); submit(checkout, calls); reject(responses, 0);
    checkout.decrease(product.id); expect(submit(checkout, calls)).not.toBe(first);
  });
  it('validates exact halalas and retains the cart after a failed payment', () => {
    checkout.cashTendered.set('200.001'); checkout.submitCheckout(); expect(calls).toHaveLength(0);
    checkout.cashTendered.set('200'); submit(checkout, calls); reject(responses, 402, 'card_declined');
    expect(checkout.cart.itemCount()).toBe(1);
  });
});
