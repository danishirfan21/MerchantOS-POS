import { Component, computed, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ProductRepository } from '../../../core/services/product.repository';
import { CheckoutRepository, CheckoutPayload, Receipt } from '../../../core/services/checkout.repository';
import { HttpErrorResponse } from '@angular/common/http';
import { Product, ProductCategory } from '../../../core/models/product';
import { CartService } from '../services/cart.service';
import { calculateTotals } from '../services/order-totals';

@Component({
  selector: 'mos-checkout', standalone: true, imports: [FormsModule], providers: [CartService],
  templateUrl: './checkout.component.html', styleUrl: './checkout.component.scss'
})
export class CheckoutComponent {
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
        this.loadError.set('Cannot reach the MerchantOS API. Start the API and database, then retry.');
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
  private resetPendingRequest(): void { this.pendingKey = null; this.pendingFingerprint = null; }
  closePayment(): void { if (!this.submitting()) this.paymentOpen.set(false); }
  clearCart(): void { if (!this.submitting()) { this.cart.clear(); this.resetPendingRequest(); } }
  removeProduct(id: string): void { if (!this.submitting()) { this.cart.remove(id); this.resetPendingRequest(); } }
  readonly categoryCount = (category: string): number => category === 'All products' ? this.products().length : this.products().filter((p) => p.category === category).length;

  formatMoney(halalas: number): string { return new Intl.NumberFormat(this.isArabic() ? 'ar-SA' : 'en-SA', { style: 'currency', currency: 'SAR', minimumFractionDigits: 2 }).format(halalas / 100); }
  printReceipt(): void { window.print(); }
  showOrders(): void { this.screen.set('orders'); this.checkoutRepository.orders().subscribe({ next: orders => this.orders.set(orders), error: () => this.checkoutError.set('Could not load orders.') }); }
  showReceipt(id: string): void { this.checkoutRepository.order(id).subscribe({ next: receipt => { this.receipt.set(receipt); this.screen.set('receipt'); }, error: () => this.checkoutError.set('Could not load receipt.') }); }
  submitCheckout(): void {
    if (this.submitting() || !this.cart.itemCount()) return;
    this.checkoutError.set(null);
    const tender = this.cashTendered().trim();
    if (this.paymentMethod() === 'cash' && (!/^\d+(?:\.\d{1,2})?$/.test(tender) || !Number.isSafeInteger(Math.round(Number(tender) * 100)) || Math.round(Number(tender) * 100) < this.totalHalalas())) {
      this.checkoutError.set('Enter sufficient cash in SAR (up to two decimal places).'); return;
    }
    const request = { items: this.cart.lines().map(line => ({ productId: line.product.id, quantity: line.quantity })).sort((a, b) => a.productId.localeCompare(b.productId)), discountPercent: this.discountPercent(), paymentMethod: this.paymentMethod(), cashTenderedHalalas: this.paymentMethod() === 'cash' ? Math.round(Number(tender) * 100) : null, cardScenario: this.paymentMethod() === 'card' ? this.cardScenario() : null };
    const fingerprint = JSON.stringify(request);
    if (this.pendingFingerprint !== fingerprint || !this.pendingKey) { this.pendingKey = crypto.randomUUID(); this.pendingFingerprint = fingerprint; }
    const payload: CheckoutPayload = { ...request, idempotencyKey: this.pendingKey };
    this.submitting.set(true);
    this.checkoutRepository.checkout(payload).subscribe({ next: receipt => { this.receipt.set(receipt); this.cart.clear(); this.resetPendingRequest(); this.paymentOpen.set(false); this.cartOpen.set(false); this.screen.set('receipt'); this.loadProducts(); this.submitting.set(false); }, error: (error: HttpErrorResponse) => { this.submitting.set(false); const code = error.error?.code; const ambiguous = error.status === 0 || error.status >= 500; this.checkoutError.set(code === 'insufficient_stock' ? 'Insufficient stock. Refreshing catalog.' : code === 'card_declined' ? 'Simulated card declined.' : code === 'insufficient_cash' ? 'Cash tendered is insufficient.' : code === 'idempotency_conflict' ? 'Checkout changed during retry. Start again.' : ambiguous ? 'Connection uncertain. Retry the same sale safely.' : 'Checkout rejected. Check the order and try again.'); if (!ambiguous) this.resetPendingRequest(); if (code === 'insufficient_stock') this.loadProducts(); } });
  }
  addProduct(product: Product): void { if (!this.submitting() && this.cart.add(product)) this.resetPendingRequest(); }
  setDiscount(event: Event): void { const value = Number((event.target as HTMLSelectElement).value); this.discountPercent.set(value); this.resetPendingRequest(); }
  brand(product: Product): string { return product.name.split(' ')[0].toUpperCase(); }
  onKeydown(event: KeyboardEvent): void { if (event.key === 'Escape') this.cartOpen.set(false); if (event.key === 'F2') { event.preventDefault(); document.querySelector<HTMLInputElement>('#product-search')?.focus(); } }
  selectCategory(category: string): void { this.selectedCategory.set(category); }
  onSearch(event: Event): void { this.query.set((event.target as HTMLInputElement).value); }
  setNav(item: string): void { this.activeNav.set(item); }
  toggleLanguage(): void { this.isArabic.update((value) => !value); }
  increase(id: string): void { const line = this.cart.lines().find((item) => item.product.id === id); if (line && !this.submitting()) { this.cart.setQuantity(id, line.quantity + 1); this.resetPendingRequest(); } }
  decrease(id: string): void { const line = this.cart.lines().find((item) => item.product.id === id); if (line && !this.submitting()) { this.cart.setQuantity(id, line.quantity - 1); this.resetPendingRequest(); } }
  handleProductKey(event: KeyboardEvent, product: Product): void { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); this.addProduct(product); } }
  getCategoryLabel(category: string): string { return this.isArabic() ? ({'All products':'كل المنتجات',Phones:'الهواتف',Audio:'الصوتيات',Wearables:'الأجهزة القابلة للارتداء',Accessories:'الإكسسوارات',Power:'الشواحن',Gaming:'الألعاب'} as Record<string,string>)[category] ?? category : category; }
}
