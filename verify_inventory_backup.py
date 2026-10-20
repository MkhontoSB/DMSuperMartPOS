import sqlite3
import sys
from pathlib import Path

backup = Path(sys.argv[1])

if not backup.is_file():
    print("ERROR: Backup file does not exist:", backup)
    raise SystemExit(1)

with sqlite3.connect(str(backup)) as connection:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    tables = connection.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()[0]

print("Backup:", backup)
print("Integrity:", integrity)
print("Tables:", tables)

if integrity != "ok" or tables != 9:
    raise SystemExit(1)
