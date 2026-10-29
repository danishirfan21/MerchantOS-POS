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
  readonly categoryCount = (category: string): number => category === 'All products' ? this.products().length : this.products().filter((p) => p.category === category).length;

  formatMoney(halalas: number): string { return new Intl.NumberFormat(this.isArabic() ? 'ar-SA' : 'en-SA', { style: 'currency', currency: 'SAR', minimumFractionDigits: 2 }).format(halalas / 100); }
  printReceipt(): void { window.print(); }
  showOrders(): void { this.screen.set('orders'); this.checkoutRepository.orders().subscribe({ next: orders => this.orders.set(orders), error: () => this.checkoutError.set('Could not load orders.') }); }
  showReceipt(id: string): void { this.checkoutRepository.order(id).subscribe({ next: receipt => { this.receipt.set(receipt); this.screen.set('receipt'); }, error: () => this.checkoutError.set('Could not load receipt.') }); }
  submitCheckout(): void {
    if (this.submitting() || !this.cart.itemCount()) return;
    this.checkoutError.set(null);
    const fingerprint = JSON.stringify({ items: this.cart.lines().map(line => ({ id: line.product.id, quantity: line.quantity })), discount: this.discountPercent(), method: this.paymentMethod(), tender: this.cashTendered(), scenario: this.cardScenario() });
    if (this.pendingFingerprint !== fingerprint) { this.pendingKey = crypto.randomUUID(); this.pendingFingerprint = fingerprint; }
    const payload: CheckoutPayload = { items: this.cart.lines().map(line => ({ productId: line.product.id, quantity: line.quantity })), discountPercent: this.discountPercent(), paymentMethod: this.paymentMethod(), cashTenderedHalalas: this.paymentMethod() === 'cash' ? Math.round(Number(this.cashTendered()) * 100) : null, idempotencyKey: this.pendingKey!, cardScenario: this.paymentMethod() === 'card' ? this.cardScenario() : null };
    if (this.paymentMethod() === 'cash' && (!Number.isFinite(payload.cashTenderedHalalas) || payload.cashTenderedHalalas! < this.totalHalalas())) { this.checkoutError.set('Cash tendered is less than the total due.'); return; }
    this.submitting.set(true);
    this.checkoutRepository.checkout(payload).subscribe({ next: receipt => { this.receipt.set(receipt); this.cart.clear(); this.pendingKey = null; this.pendingFingerprint = null; this.paymentOpen.set(false); this.cartOpen.set(false); this.screen.set('receipt'); this.loadProducts(); this.submitting.set(false); }, error: (error: HttpErrorResponse) => { this.submitting.set(false); const code = error.error?.code; this.checkoutError.set(code === 'insufficient_stock' ? 'Insufficient stock. Refreshing catalog.' : code === 'card_declined' ? 'Simulated card declined.' : code === 'insufficient_cash' ? 'Cash tendered is insufficient.' : code === 'idempotency_conflict' ? 'Checkout changed during retry. Start again.' : 'Checkout failed. Retry safely with the same request.'); if (code === 'insufficient_stock') this.loadProducts(); if (code === 'card_declined' || code === 'insufficient_cash' || code === 'idempotency_conflict') this.pendingKey = null; } });
  }
  addProduct(product: Product): void { this.cart.add(product); this.pendingKey = null; }
  setDiscount(event: Event): void { const value = Number((event.target as HTMLSelectElement).value); this.discountPercent.set(value); this.pendingKey = null; }
  brand(product: Product): string { return product.name.split(' ')[0].toUpperCase(); }
  onKeydown(event: KeyboardEvent): void { if (event.key === 'Escape') this.cartOpen.set(false); if (event.key === 'F2') { event.preventDefault(); document.querySelector<HTMLInputElement>('#product-search')?.focus(); } }
  selectCategory(category: string): void { this.selectedCategory.set(category); }
  onSearch(event: Event): void { this.query.set((event.target as HTMLInputElement).value); }
  setNav(item: string): void { this.activeNav.set(item); }
  toggleLanguage(): void { this.isArabic.update((value) => !value); }
  increase(id: string): void { const line = this.cart.lines().find((item) => item.product.id === id); if (line) { this.cart.setQuantity(id, line.quantity + 1); this.pendingKey = null; } }
  decrease(id: string): void { const line = this.cart.lines().find((item) => item.product.id === id); if (line) { this.cart.setQuantity(id, line.quantity - 1); this.pendingKey = null; } }
  handleProductKey(event: KeyboardEvent, product: Product): void { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); this.addProduct(product); } }
  getCategoryLabel(category: string): string { return this.isArabic() ? ({'All products':'كل المنتجات',Phones:'الهواتف',Audio:'الصوتيات',Wearables:'الأجهزة القابلة للارتداء',Accessories:'الإكسسوارات',Power:'الشواحن',Gaming:'الألعاب'} as Record<string,string>)[category] ?? category : category; }
}
