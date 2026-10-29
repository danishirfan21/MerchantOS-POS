import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Product } from '../models/product';

/** API-backed product catalog; a failed API request must never masquerade as live inventory. */
@Injectable({ providedIn: 'root' })
export class ProductRepository {
  private readonly http = inject(HttpClient);

  list(): Observable<Product[]> {
    return this.http.get<Product[]>('/api/products');
  }
}
