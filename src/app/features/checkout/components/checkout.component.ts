import { Component, computed, DestroyRef, inject, signal, Input, Output, EventEmitter } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ProductRepository } from '../../../core/services/product.repository';
import { CheckoutRepository, CheckoutPayload, Receipt } from '../../../core/services/checkout.repository';
import { HttpErrorResponse } from '@angular/common/http';
import { Product } from '../../../core/models/product';
import { CartService } from '../services/cart.service';
import { calculateTotals } from '../services/order-totals';
import { CopyKey, translate } from './checkout.i18n';

@Component({
  selector: 'mos-checkout', standalone: true, imports: [FormsModule], providers: [CartService],
  templateUrl: './checkout.component.html', styleUrl: './checkout.component.scss'
})
export class CheckoutComponent {
  @Input() username = "";
  @Output() readonly signOut = new EventEmitter<void>();
  private readonly productRepository = inject(ProductRepository);
  private readonly checkoutRepository = inject(CheckoutRepository);
  readonly screen = signal<'checkout' | 'orders' | 'receipt'>('checkout');
  readonly paymentOpen = signal(false);
  readonly paymentMethod = signal<'cash' | 'card'>('cash');
  readonly cashTendered = signal('');
  readonly cardScenario = signal<'success' | 'decline'>('success');
  readonly submitting = signal(false);
  readonly checkoutError = signal<string | null>(null);
  readonly receipt = signal<Receipt | null>(null);
  readonly orders = signal<Receipt[]>([]);
  private pendingKey: string | null = null;
  private pendingFingerprint: string | null = null;
  private readonly destroyRef = inject(DestroyRef);
  private focusBeforeDialog: HTMLElement | null = null;
  private focusBeforeCart: HTMLElement | null = null;
  readonly products = signal<Product[]>([]);
  readonly isLoading = signal(true);
  readonly loadError = signal<string | null>(null);

  constructor() { this.loadProducts(); }

  loadProducts(): void {
    this.isLoading.set(true);
    this.loadError.set(null);
    this.productRepository.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (products) => {
        this.products.set(products);
        this.cart.syncCatalog(products);
        this.isLoading.set(false);
      },
      error: () => {
        this.loadError.set(this.t('catalogError'));
        this.isLoading.set(false);
      }
    });
  }
  readonly categories = ['All products', 'Phones', 'Audio', 'Wearables', 'Accessories', 'Power', 'Gaming'] as const;
  readonly categoryIcons: Record<string, string> = { 'All products':'◫', Phones:'▣', Audio:'◖', Wearables:'◷', Accessories:'◈', Power:'ϟ', Gaming:'⌁' };
  readonly selectedCategory = signal<string>('All products');
  readonly query = signal('');
  readonly activeNav = signal('New sale');
  readonly cartOpen = signal(false);
  readonly discountPercent = signal(0);
  readonly totals = computed(() => calculateTotals(this.cart.subtotalHalalas(), this.discountPercent()));
  readonly discountHalalas = computed(() => this.totals().discountHalalas);
  readonly isArabic = signal(false);
  readonly catalog = computed(() => {
    const q = this.query().trim().toLowerCase();
    return this.products().filter((p) => (this.selectedCategory() === 'All products' || p.category === this.selectedCategory()) && (!q || `${p.name} ${p.nameAr} ${p.sku} ${p.category}`.toLowerCase().includes(q)));
  });
  readonly cart = new CartService();
  readonly subtotal = computed(() => this.formatMoney(this.cart.subtotalHalalas()));
  readonly taxHalalas = computed(() => this.totals().taxHalalas);
  readonly totalHalalas = computed(() => this.totals().payableHalalas);
  readonly changeHalalas = computed(() => Math.max(0, Math.round(Number(this.cashTendered() || 0) * 100) - this.totalHalalas()));
  t(key: CopyKey): string { return translate(key, this.isArabic()); }
  formatDate(value: string): string { return new Intl.DateTimeFormat(this.isArabic() ? 'ar-SA' : 'en-SA', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)); }
  productName(id: string, fallback: string): string { return this.isArabic() ? this.products().find(p => p.id === id)?.nameAr ?? fallback : fallback; }
  productImage(product: Product): string { return '/products/' + product.category.toLowerCase() + '.svg'; }
  hideBrokenImage(event: Event): void { (event.target as HTMLImageElement).hidden = true; }
  private focusSoon(selector: string): void { setTimeout(() => document.querySelector<HTMLElement>(selector)?.focus()); }
  openPayment(): void { if (!this.cart.itemCount() || this.submitting()) return; this.focusBeforeDialog = document.activeElement as HTMLElement; this.paymentOpen.set(true); this.focusSoon('.payment-dialog select'); }
  onPaymentBackdrop(event: MouseEvent): void { if (event.target === event.currentTarget) this.closePayment(); }
  openCart(): void { this.focusBeforeCart = document.activeElement as HTMLElement; this.cartOpen.set(true); this.focusSoon('.cart .close'); }
  closeCart(): void { if (!this.cartOpen()) return; this.cartOpen.set(false); this.focusBeforeCart?.focus(); }
  goCheckout(): void { this.screen.set('checkout'); this.closeCart(); this.checkoutError.set(null); }
  trapFocus(event: KeyboardEvent): void {
    if (event.key !== 'Tab') return;
    const root = event.currentTarget as HTMLElement;
    const controls = [...root.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex="-1"])')].filter(el => el.getClientRects().length);
    if (!controls.length) return;
    if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls.at(-1)?.focus(); }
    else if (!event.shiftKey && document.activeElement === controls.at(-1)) { event.preventDefault(); controls[0].focus(); }
  }
  private resetPendingRequest(): void { this.pendingKey = null; this.pendingFingerprint = null; }
  closePayment(): void { if (!this.submitting() && this.paymentOpen()) { this.paymentOpen.set(false); this.focusBeforeDialog?.focus(); } }
  clearCart(): void { if (!this.submitting()) { this.cart.clear(); this.resetPendingRequest(); } }
  removeProduct(id: string): void { if (!this.submitting()) { this.cart.remove(id); this.resetPendingRequest(); } }
  readonly categoryCount = (category: string): number => category === 'All products' ? this.products().length : this.products().filter((p) => p.category === category).length;

  formatMoney(halalas: number): string { return 'SAR ' + new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(halalas / 100); }
  printReceipt(): void { window.print(); }
  showOrders(): void { this.closeCart(); this.checkoutError.set(null); this.screen.set('orders'); this.checkoutRepository.orders().subscribe({ next: orders => this.orders.set(orders), error: () => this.checkoutError.set(this.t('ordersError')) }); }
  showReceipt(id: string): void { this.checkoutRepository.order(id).subscribe({ next: receipt => { this.receipt.set(receipt); this.screen.set('receipt'); }, error: () => this.checkoutError.set(this.t('receiptError')) }); }
  submitCheckout(): void {
    if (this.submitting() || !this.cart.itemCount()) return;
    this.checkoutError.set(null);
    const tender = this.cashTendered().trim();
    if (this.paymentMethod() === 'cash' && (!/^\d+(?:\.\d{1,2})?$/.test(tender) || !Number.isSafeInteger(Math.round(Number(tender) * 100)) || Math.round(Number(tender) * 100) < this.totalHalalas())) {
      this.checkoutError.set(this.t('insufficientCashInput')); return;
    }
    const request = { items: this.cart.lines().map(line => ({ productId: line.product.id, quantity: line.quantity })).sort((a, b) => a.productId.localeCompare(b.productId)), discountPercent: this.discountPercent(), paymentMethod: this.paymentMethod(), cashTenderedHalalas: this.paymentMethod() === 'cash' ? Math.round(Number(tender) * 100) : null, cardScenario: this.paymentMethod() === 'card' ? this.cardScenario() : null };
    const fingerprint = JSON.stringify(request);
    if (this.pendingFingerprint !== fingerprint || !this.pendingKey) { this.pendingKey = crypto.randomUUID(); this.pendingFingerprint = fingerprint; }
    const payload: CheckoutPayload = { ...request, idempotencyKey: this.pendingKey };
    this.submitting.set(true);
    this.checkoutRepository.checkout(payload).subscribe({ next: receipt => { this.receipt.set(receipt); this.cart.clear(); this.resetPendingRequest(); this.paymentOpen.set(false); this.closeCart(); this.screen.set('receipt'); this.loadProducts(); this.submitting.set(false); }, error: (error: HttpErrorResponse) => { this.submitting.set(false); const code = error.error?.code; const ambiguous = error.status === 0 || error.status >= 500; this.checkoutError.set(code === 'insufficient_stock' ? this.t('insufficientStock') : code === 'card_declined' ? this.t('cardDeclined') : code === 'insufficient_cash' ? this.t('insufficientCash') : code === 'idempotency_conflict' ? this.t('idempotencyConflict') : ambiguous ? this.t('uncertain') : this.t('rejected')); if (!ambiguous) this.resetPendingRequest(); if (code === 'insufficient_stock') this.loadProducts(); } });
  }
  addProduct(product: Product): void { if (!this.submitting() && this.cart.add(product)) this.resetPendingRequest(); }
  setDiscount(event: Event): void { const value = Number((event.target as HTMLSelectElement).value); this.discountPercent.set(value); this.resetPendingRequest(); }
  brand(product: Product): string { return product.name.split(' ')[0].toUpperCase(); }
  onKeydown(event: KeyboardEvent): void { if (event.key === 'Escape') { if (this.paymentOpen()) this.closePayment(); else this.closeCart(); } if (event.key === 'F2') { event.preventDefault(); document.querySelector<HTMLInputElement>('#product-search')?.focus(); } }
  selectCategory(category: string): void { this.selectedCategory.set(category); }
  onSearch(event: Event): void { this.query.set((event.target as HTMLInputElement).value); }
  setNav(item: string): void { this.activeNav.set(item); }
  toggleLanguage(): void { this.isArabic.update((value) => !value); this.checkoutError.set(null); if (this.loadError()) this.loadError.set(this.t('catalogError')); }
  increase(id: string): void { const line = this.cart.lines().find((item) => item.product.id === id); if (line && !this.submitting()) { this.cart.setQuantity(id, line.quantity + 1); this.resetPendingRequest(); } }
  decrease(id: string): void { const line = this.cart.lines().find((item) => item.product.id === id); if (line && !this.submitting()) { this.cart.setQuantity(id, line.quantity - 1); this.resetPendingRequest(); } }
  handleProductKey(event: KeyboardEvent, product: Product): void { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); this.addProduct(product); } }
  getCategoryLabel(category: string): string { const keys: Record<string, CopyKey> = { 'All products':'allProducts', Phones:'phones', Audio:'audio', Wearables:'wearables', Accessories:'accessories', Power:'power', Gaming:'gaming' }; return this.t(keys[category]); }
}
