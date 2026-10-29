-- Apply once to an existing database; safe to rerun without dropping catalog data.
CREATE TABLE IF NOT EXISTS orders (
 id uuid PRIMARY KEY, order_number varchar(32) NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(), currency char(3) NOT NULL DEFAULT 'SAR',
 status varchar(20) NOT NULL, subtotal_halalas bigint NOT NULL,
 discount_halalas bigint NOT NULL, vat_halalas bigint NOT NULL, payable_halalas bigint NOT NULL,
 payment_method varchar(20) NOT NULL, change_halalas bigint NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS order_items (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, order_id uuid NOT NULL REFERENCES orders(id),
 product_id varchar(32) NOT NULL, sku varchar(80) NOT NULL, name varchar(240) NOT NULL,
 quantity integer NOT NULL CHECK (quantity > 0), unit_price_halalas bigint NOT NULL CHECK (unit_price_halalas >= 0)
);
CREATE TABLE IF NOT EXISTS payments (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, order_id uuid NOT NULL UNIQUE REFERENCES orders(id),
 method varchar(20) NOT NULL, result varchar(20) NOT NULL, tendered_halalas bigint,
 change_halalas bigint NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS checkout_idempotency (
 key varchar(128) PRIMARY KEY, request_hash varchar(64) NOT NULL,
 order_id uuid NOT NULL UNIQUE REFERENCES orders(id)
);
