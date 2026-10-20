from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys

from sqlalchemy.engine import make_url
from supermart.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = PROJECT_ROOT / "backups" / "postgres"


def find_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found

    windows_path = Path(r"C:\Program Files\PostgreSQL\18\bin") / f"{name}.exe"
    if windows_path.is_file():
        return str(windows_path)

    raise FileNotFoundError(
        f"Cannot find {name}. Install PostgreSQL client tools or add them to PATH."
    )


def main() -> int:
    url = make_url(settings.database_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("This backup script requires a PostgreSQL DATABASE_URL.")
    if not url.password:
        raise RuntimeError("DATABASE_URL must contain a database password.")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{url.database}_{timestamp}.dump"

    env = os.environ.copy()
    env["PGPASSWORD"] = url.password

    dump_command = [
        find_tool("pg_dump"),
        "--host", url.host or "localhost",
        "--port", str(url.port or 5432),
        "--username", url.username or "",
        "--dbname", url.database or "",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file", str(backup_path),
    ]

    result = subprocess.run(dump_command, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print("pg_dump failed:", result.stderr.strip(), file=sys.stderr)
        return result.returncode

    if not backup_path.is_file() or backup_path.stat().st_size == 0:
        print("Backup file is missing or empty.", file=sys.stderr)
        return 1

    verify_command = [find_tool("pg_restore"), "--list", str(backup_path)]
    verified = subprocess.run(verify_command, env=env, capture_output=True, text=True)
    if verified.returncode != 0:
        print("Backup archive verification failed:", verified.stderr.strip(), file=sys.stderr)
        return verified.returncode

    entries = sum(1 for line in verified.stdout.splitlines() if line.strip() and not line.startswith(";"))
    print("Backup created and archive listing verified.")
    print(f"Database: {url.database}")
    print(f"File: {backup_path}")
    print(f"Size: {backup_path.stat().st_size:,} bytes")
    print(f"Archive entries: {entries}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
