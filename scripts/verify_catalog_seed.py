"""Fast, dependency-free SQL seed contract check using SQLite syntax compatibility.

This is NOT a substitute for running the actual PostgreSQL/EF API integration tests.
"""
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / 'db/init/001_schema.sql').read_text(encoding='utf-8')
SEED = (ROOT / 'db/init/002_seed.sql').read_text(encoding='utf-8')

with sqlite3.connect(':memory:') as db:
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript(SCHEMA)
    db.executescript(SEED)
    assert db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 30
    assert db.execute('SELECT COUNT(*) FROM inventory_levels').fetchone()[0] == 30
    assert db.execute('SELECT COUNT(DISTINCT sku) FROM products').fetchone()[0] == 30
    assert db.execute('SELECT COUNT(*) FROM products p JOIN inventory_levels i ON i.product_id = p.id').fetchone()[0] == 30
    assert db.execute('SELECT COUNT(*) FROM products WHERE price_halalas < 0').fetchone()[0] == 0
    assert db.execute('SELECT COUNT(*) FROM inventory_levels WHERE quantity_on_hand < 0').fetchone()[0] == 0
    assert db.execute('SELECT COUNT(*) FROM products WHERE name_ar = \'\'').fetchone()[0] == 0
    db.executescript(SEED)
    assert db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 30
    try:
        db.execute("UPDATE inventory_levels SET quantity_on_hand = -1 WHERE product_id = 'p01'")
        raise AssertionError('Missing nonnegative-inventory constraint')
    except sqlite3.IntegrityError:
        pass
    try:
        db.execute("UPDATE products SET price_halalas = -1 WHERE id = 'p01'")
        raise AssertionError('Missing nonnegative-price constraint')
    except sqlite3.IntegrityError:
        pass
print('Seed contract passed: 30 products, 30 inventory rows, unique SKU/FK/check constraints, repeatable seed.')
