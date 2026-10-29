export type ProductCategory = 'Phones' | 'Audio' | 'Wearables' | 'Accessories' | 'Power' | 'Gaming';

export interface Product {
  id: string;
  sku: string;
  name: string;
  nameAr: string;
  category: ProductCategory;
  priceHalalas: number;
  stock: number;
  color: string;
  icon: string;
  badge?: string;
}
