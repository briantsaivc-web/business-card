import sqlite3
from db import get_supabase

conn = sqlite3.connect('data/contacts.db')
conn.row_factory = sqlite3.Row
rows = [dict(r) for r in conn.execute('SELECT * FROM contacts').fetchall()]
print(f'讀到 {len(rows)} 筆，開始上傳...')

sb = get_supabase()
for i in range(0, len(rows), 100):
    batch = [{k: ('' if v is None else str(v)) for k,v in r.items()} for r in rows[i:i+100]]
    sb.table('contacts').upsert(batch, on_conflict='id').execute()
    print(f'上傳 {min(i+100, len(rows))}/{len(rows)}')

print('完成!')