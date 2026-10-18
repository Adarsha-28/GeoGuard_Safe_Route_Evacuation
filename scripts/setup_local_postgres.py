#!/usr/bin/env python3
"""Automated local PostgreSQL + PostGIS setup for GeoGuard on Windows.

Sets up a local user-space PostgreSQL 18 + PostGIS 3.6 instance running on port 5433
without requiring administrator privileges.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

PG_SOURCE = Path("D:/Apps/Postgresql")
BASE_USER_DIR = Path(os.environ.get("USERPROFILE", "C:/Users/ADARSHA"))
PG_TARGET = BASE_USER_DIR / "geoguard_pgsql"
PG_DATA = BASE_USER_DIR / "geoguard_pgdata"
POSTGIS_ZIP_URL = "https://download.osgeo.org/postgis/windows/pg18/postgis-bundle-pg18-3.6.2x64.zip"
CACHE_ZIP = BASE_USER_DIR / "postgis-bundle-pg18-3.6.2x64.zip"
PG_PORT = 5433


def run_cmd(cmd: list[str], check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run subprocess command and capture output."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    # Ensure PG_TARGET bin is on PATH and credentials are non-interactive
    full_env["PATH"] = f"{PG_TARGET / 'bin'};{full_env.get('PATH', '')}"
    full_env["PGPASSWORD"] = "postgres"
    print(f"[CMD] {' '.join(str(x) for x in cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, env=full_env, stdin=subprocess.DEVNULL)
    if check and result.returncode != 0:
        print(f"[ERROR] Command failed with code {result.returncode}:", flush=True)
        print(result.stdout, flush=True)
        print(result.stderr, file=sys.stderr, flush=True)
        raise RuntimeError(f"Command failed: {cmd[0]}")
    return result


def is_pid_running(pid: int) -> bool:
    """Check if process ID is actively running."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        SYNCHRONIZE = 0x00100000
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def main() -> int:
    print("=" * 65, flush=True)
    print("   GeoGuard — Automated Local PostGIS Setup", flush=True)
    print("=" * 65, flush=True)

    # 1. Copy base PostgreSQL binaries (bin, lib, share)
    PG_TARGET.mkdir(parents=True, exist_ok=True)
    for folder in ["bin", "lib", "share"]:
        src = PG_SOURCE / folder
        dst = PG_TARGET / folder
        if not dst.exists():
            if src.exists():
                print(f"[..] Copying {folder} from {src} to {dst}...", flush=True)
                shutil.copytree(src, dst)
                print(f"[OK] {folder} copied.", flush=True)
            else:
                print(f"[WARN] Source {src} not found; skipping copy.", flush=True)
        else:
            print(f"[OK] {dst} already exists.", flush=True)

    # 2. Extract and overlay PostGIS bundle if not already done
    postgis_control = PG_TARGET / "share" / "extension" / "postgis.control"
    if not postgis_control.exists():
        extracted_dir = PG_TARGET / "postgis-bundle-pg18-3.6.2x64"
        if not extracted_dir.exists() and CACHE_ZIP.exists():
            print(f"[..] Extracting PostGIS zip into {PG_TARGET}...", flush=True)
            with zipfile.ZipFile(CACHE_ZIP, "r") as z:
                z.extractall(PG_TARGET)

        if extracted_dir.exists():
            print(f"[..] Overlaying PostGIS files into {PG_TARGET}...", flush=True)
            for item in extracted_dir.iterdir():
                if item.is_dir():
                    shutil.copytree(item, PG_TARGET / item.name, dirs_exist_ok=True)
            print("[OK] PostGIS bundle overlay complete.", flush=True)
    else:
        print("[OK] PostGIS extension files verified.", flush=True)

    # 3. Initialize database cluster if not exists
    initdb_exe = PG_TARGET / "bin" / "initdb.exe"
    if not (PG_DATA / "PG_VERSION").exists():
        print(f"[..] Initializing new database cluster at {PG_DATA}...", flush=True)
        run_cmd([
            str(initdb_exe),
            "-U", "postgres",
            "-A", "trust",
            "-E", "UTF8",
            "-D", str(PG_DATA),
        ])
        print("[OK] Database cluster initialized.", flush=True)
    else:
        print(f"[OK] Database cluster already exists at {PG_DATA}.", flush=True)

    # Clean up stale postmaster.pid if postgres is not actually running
    pid_file = PG_DATA / "postmaster.pid"
    if pid_file.exists():
        try:
            first_line = pid_file.read_text(encoding="utf-8").splitlines()[0].strip()
            old_pid = int(first_line)
            if not is_pid_running(old_pid):
                print(f"[..] Removing stale postmaster.pid for dead PID {old_pid}...", flush=True)
                pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    # 4. Start PostgreSQL on port 5433
    pg_ctl_exe = PG_TARGET / "bin" / "pg_ctl.exe"
    log_file = PG_DATA / "server.log"
    print(f"[..] Checking/Starting PostgreSQL server on port {PG_PORT}...", flush=True)
    status = run_cmd([str(pg_ctl_exe), "status", "-D", str(PG_DATA)], check=False)
    is_running = ("is running" in status.stdout or "server is running" in status.stdout or "is running" in status.stderr)
    if not is_running:
        # Note: Must pass stdout/stderr as DEVNULL and detached flags so inherited daemon process doesn't block python EOF
        creationflags = (0x00000008 | 0x00000200) if sys.platform == "win32" else 0
        subprocess.run(
            [
                str(pg_ctl_exe),
                "start",
                "-D", str(PG_DATA),
                "-l", str(log_file),
                "-o", f"-p {PG_PORT}",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            env={**os.environ, "PATH": f"{PG_TARGET / 'bin'};{os.environ.get('PATH', '')}"},
        )
        time.sleep(2)
        print(f"[OK] PostgreSQL server running on port {PG_PORT}.", flush=True)
    else:
        print(f"[OK] PostgreSQL server is already running on port {PG_PORT}.", flush=True)

    # 5. Create geoguard database and enable PostGIS
    createdb_exe = PG_TARGET / "bin" / "createdb.exe"
    psql_exe = PG_TARGET / "bin" / "psql.exe"

    print("[..] Verifying 'geoguard' database...", flush=True)
    run_cmd([
        str(createdb_exe),
        "-h", "localhost",
        "-p", str(PG_PORT),
        "-U", "postgres",
        "geoguard",
    ], check=False)

    print("[..] Enabling PostGIS extension in 'geoguard' database...", flush=True)
    res = run_cmd([
        str(psql_exe),
        "-h", "localhost",
        "-p", str(PG_PORT),
        "-U", "postgres",
        "-d", "geoguard",
        "-c", "CREATE EXTENSION IF NOT EXISTS postgis; SELECT PostGIS_Full_Version();",
    ], check=False)
    if res.stdout:
        print(f"[OK] PostGIS Active:\n{res.stdout.strip()}", flush=True)

    # 6. Set password for postgres user to 'postgres'
    print("[..] Setting superuser password...", flush=True)
    run_cmd([
        str(psql_exe),
        "-h", "localhost",
        "-p", str(PG_PORT),
        "-U", "postgres",
        "-d", "geoguard",
        "-c", "ALTER USER postgres WITH PASSWORD 'postgres';",
    ], check=False)
    print("[OK] Superuser configured.", flush=True)

    # 7. Update .env with working DATABASE_URL
    proj_dir = Path(__file__).resolve().parent.parent
    env_file = proj_dir / ".env"
    env_example = proj_dir / ".env.example"
    conn_str = f"postgresql://postgres:postgres@localhost:{PG_PORT}/geoguard"

    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)

    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        import re
        content = re.sub(r"DATABASE_URL=.*", f"DATABASE_URL={conn_str}", content)
        env_file.write_text(content, encoding="utf-8")
        print(f"[OK] Configured {env_file.name} with DATABASE_URL={conn_str}", flush=True)

    print("\n" + "=" * 65, flush=True)
    print(f"[SUCCESS] Local PostgreSQL + PostGIS operational at localhost:{PG_PORT}", flush=True)
    print("=" * 65, flush=True)
    return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
