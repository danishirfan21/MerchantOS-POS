"""Isolated historical fixture, never run on a real developer/production database."""
import os,subprocess
if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('CI-only fixture')
def sql(s):
 return subprocess.check_output(['psql','-h','127.0.0.1','-p','5433','-U','merchantos','-d','merchantos','-v','ON_ERROR_STOP=1','-Atc',s],text=True).strip()
def seed():
 sql("""INSERT INTO orders(id,order_number,created_at,currency,status,subtotal_halalas,discount_halalas,vat_halalas,payable_halalas,payment_method,change_halalas)
 SELECT md5('historical-'||g)::uuid,'HIST-'||lpad(g::text,5,'0'),t,'SAR','completed',3000,300,405,3105,CASE WHEN g%2=0 THEN 'cash' ELSE 'card' END,0
 FROM generate_series(1,10000)g CROSS JOIN LATERAL (SELECT timestamp with time zone '2020-01-01 21:00:00+00'+(g/100)*interval '1 hour' t)dt ON CONFLICT(id) DO NOTHING;
 INSERT INTO order_items(order_id,product_id,sku,name,quantity,unit_price_halalas)
 SELECT o.id,x.pid,x.sku,x.name,x.q,x.price FROM orders o CROSS JOIN (VALUES('p01','HIST-A','Historical Phone',2,1000),('p02','HIST-B','Historical Audio',1,1000)) x(pid,sku,name,q,price)
 WHERE o.order_number LIKE 'HIST-%' AND NOT EXISTS(SELECT 1 FROM order_items i WHERE i.order_id=o.id);
 INSERT INTO payments(order_id,method,result,tendered_halalas,change_halalas) SELECT id,payment_method,'completed',4000,895 FROM orders WHERE order_number LIKE 'HIST-%' ON CONFLICT(order_id) DO NOTHING;
 INSERT INTO orders(id,order_number,created_at,currency,status,subtotal_halalas,discount_halalas,vat_halalas,payable_halalas,payment_method,change_halalas) VALUES
 ('00000000-0000-0000-0000-000000000001','BOUND-BEFORE','2020-01-01 20:59:59+00','SAR','completed',100,0,15,115,'cash',0),
 ('00000000-0000-0000-0000-000000000002','BOUND-AFTER','2020-01-02 21:00:00+00','SAR','completed',100,0,15,115,'cash',0),
 ('00000000-0000-0000-0000-000000000003','FAILED-REPORT','2020-01-02 00:00:00+00','SAR','failed',999999,0,0,999999,'card',0),
 ('00000000-0000-0000-0000-000000000004','OTHER-CURRENCY','2020-01-02 00:00:00+00','USD','completed',999999,0,0,999999,'cash',0) ON CONFLICT(id) DO NOTHING;
 ANALYZE orders; ANALYZE order_items;""")
if __name__=='__main__':seed();print('Isolated historical fixture: 10000 multi-item completed orders plus boundary/status/currency cases.')
