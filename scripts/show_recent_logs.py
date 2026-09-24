import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect("data/assistant.db")
cur = con.cursor()
rows = cur.execute("SELECT id, timestamp, level, category, booking_ref, message FROM system_logs ORDER BY id DESC LIMIT 40").fetchall()
for r in reversed(rows):
    print(f"[{r[1]}] [{r[2]}] [{r[3]}] [{r[4]}] {r[5]}")
