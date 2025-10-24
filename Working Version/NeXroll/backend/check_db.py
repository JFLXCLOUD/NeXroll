import sqlite3
import json

# Connect without forcing the preroll deletion to see what refs exist
conn = sqlite3.connect('nexroll.db')
conn.execute('PRAGMA foreign_keys=ON')
cursor = conn.cursor()

output = []

# Check if there are actually any M2M entries for preroll 8
cursor.execute('SELECT COUNT(*) FROM preroll_categories WHERE preroll_id=8')
count = cursor.fetchone()
if count:
    output.append(f'M2M entries for preroll 8: {count[0]}')

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
output.append(f'\nAll tables: {[t[0] for t in tables]}')

# Check preroll 8 in categories table (single FK)
cursor.execute('SELECT category_id FROM prerolls WHERE id=8')
result = cursor.fetchone()
if result and result[0]:
    output.append(f'\nPreroll 8 category_id: {result[0]}')
else:
    output.append('\nPreroll 8 category_id: None (nullable)')

# Check schedules for preroll 8 in JSON  
cursor.execute('SELECT id, preroll_ids FROM schedules WHERE preroll_ids IS NOT NULL')
scheds = cursor.fetchall()
found_in_schedule = False
for sch_id, prs in scheds:
    try:
        pr_list = json.loads(prs)
        if 8 in pr_list:
            output.append(f'\nSchedule {sch_id} references preroll 8: {pr_list}')
            found_in_schedule = True
    except:
        pass
if not found_in_schedule:
    output.append('\nNo schedules reference preroll 8 in preroll_ids')

# Try a test delete with FK OFF
output.append('\n\nTrying test delete with FK OFF...')
try:
    cursor.execute('PRAGMA foreign_keys=OFF')
    cursor.execute('DELETE FROM prerolls WHERE id=8')
    output.append('Delete succeeded with FK OFF')
    conn.rollback()  # Don't actually delete
    output.append('Rolled back - no actual deletion')
except Exception as e:
    output.append(f'Delete STILL failed: {e}')
    conn.rollback()

conn.close()

msg = '\n'.join(output)
print(msg)
with open('check_result.txt', 'w') as f:
    f.write(msg)

