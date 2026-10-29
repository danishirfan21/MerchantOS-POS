import { Component, computed, signal } from '@angular/core';
import { CheckoutComponent } from './features/checkout/components/checkout.component';

@Component({ selector: 'mos-root', standalone: true, imports: [CheckoutComponent], template: '<mos-checkout />' })
export class AppComponent {}
