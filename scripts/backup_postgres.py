
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote

from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from supermart.config import settings


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


def safe_stderr(stderr: str, password: str) -> str:
    """Redact the database password from client-tool diagnostics."""
    if not password:
        return stderr

    return (
        stderr.replace(password, "[REDACTED]")
        .replace(quote(password, safe=""), "[REDACTED]")
    )


def main() -> int:
    url = make_url(settings.database_url)

    if url.get_backend_name() != "postgresql":
        raise RuntimeError(
            "This backup script requires a PostgreSQL DATABASE_URL."
        )

    if not url.password:
        raise RuntimeError(
            "DATABASE_URL must contain a database password."
        )

    if not url.database or not url.username:
        raise RuntimeError(
            "DATABASE_URL must specify a database and username."
        )

    pg_dump = find_tool("pg_dump")
    pg_restore = find_tool("pg_restore")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().astimezone().strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    backup_path = BACKUP_DIR / f"{url.database}_{timestamp}.dump"
    temporary_path = BACKUP_DIR / f"{url.database}_{timestamp}.dump.partial"

    if backup_path.exists() or temporary_path.exists():
        raise FileExistsError(
            "The generated backup filename already exists; refusing to overwrite it."
        )

    env = os.environ.copy()
    env["PGPASSWORD"] = url.password

    dump_command = [
        pg_dump,
        "--host", url.host or "localhost",
        "--port", str(url.port or 5432),
        "--username", url.username,
        "--dbname", url.database,
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file", str(temporary_path),
    ]

    try:
        result = subprocess.run(
            dump_command,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print(
                "pg_dump failed:",
                safe_stderr(result.stderr.strip(), url.password),
                file=sys.stderr,
            )
            return result.returncode or 1

        if (
            not temporary_path.is_file()
            or temporary_path.stat().st_size == 0
        ):
            print(
                "Backup archive is missing or empty.",
                file=sys.stderr,
            )
            return 1

        verify_command = [
            pg_restore,
            "--list",
            str(temporary_path),
        ]

        verified = subprocess.run(
            verify_command,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        if verified.returncode != 0:
            print(
                "Backup archive verification failed:",
                safe_stderr(verified.stderr.strip(), url.password),
                file=sys.stderr,
            )
            return verified.returncode or 1

        entries = sum(
            1
            for line in verified.stdout.splitlines()
            if line.strip() and not line.startswith(";")
        )

        if entries == 0:
            print(
                "Backup archive contains no listed entries.",
                file=sys.stderr,
            )
            return 1

        # Publish the backup only after pg_restore verifies the archive.
        temporary_path.replace(backup_path)

        print("Backup created and archive listing verified.")
        print(f"Database: {url.database}")
        print(f"File: {backup_path}")
        print(f"Size: {backup_path.stat().st_size:,} bytes")
        print(f"Archive entries: {entries}")

        return 0

    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError as exc:
                print(
                    f"Warning: could not remove temporary backup "
                    f"{temporary_path.name}: {exc}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
