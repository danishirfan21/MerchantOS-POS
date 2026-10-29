-- Milestone 2 initial PostgreSQL schema. Run only on a fresh local volume.
-- For future schema changes, introduce EF Core migrations; don't edit this on populated databases.
CREATE TABLE IF NOT EXISTS products (
  id varchar(32) PRIMARY KEY,
  sku varchar(80) NOT NULL,
  name varchar(240) NOT NULL,
  name_ar varchar(240) NOT NULL,
  category varchar(80) NOT NULL,
  price_halalas bigint NOT NULL CHECK (price_halalas >= 0),
  color varchar(40) NOT NULL,
  icon varchar(20) NOT NULL,
  badge varchar(60) NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_sku ON products (sku);
CREATE INDEX IF NOT EXISTS ix_products_category ON products (category);
CREATE TABLE IF NOT EXISTS inventory_levels (
  product_id varchar(32) PRIMARY KEY REFERENCES products (id) ON DELETE CASCADE,
  quantity_on_hand integer NOT NULL CHECK (quantity_on_hand >= 0)
);
