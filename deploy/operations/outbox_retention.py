"""Migration-owner maintenance only; pending events are never pruned due to age/outage."""
import argparse
import psycopg
from common import read_config
p=argparse.ArgumentParser();p.add_argument('--database',required=True);a=p.parse_args()
with psycopg.connect(read_config(a.database)['dsn'],connect_timeout=3) as db:
 result=db.execute("DELETE FROM security_event_outbox WHERE sequence IN (SELECT sequence FROM security_event_outbox WHERE delivered_at<clock_timestamp()-interval '90 days' ORDER BY sequence LIMIT 1000)")
print('Bounded delivered-outbox retention completed; pending events preserved.')
