-- Additive reporting indexes; apply during a local/isolated maintenance window.
BEGIN;
CREATE INDEX IF NOT EXISTS ix_orders_chronological ON orders(created_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS ix_orders_completed_sar ON orders(created_at) INCLUDE(subtotal_halalas,discount_halalas,vat_halalas,payable_halalas,payment_method) WHERE status='completed' AND currency='SAR';
CREATE INDEX IF NOT EXISTS ix_order_items_order ON order_items(order_id);
COMMIT;
