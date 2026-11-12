#!/usr/bin/env python3
"""Shared helpers for Apex RPak exports via RSX NoGui."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Default export root: this project (tools/..), so `python tools/export_game_scripts.py`
# writes exported/ next to docs/ and the pak tools.
WORKSPACE = Path(__file__).resolve().parent.parent
# rsx built from this checkout (D:\code\rsx\bin\Release_NoGui\rsx.exe on the export machine);
# paks default to D:\Apex\paks\Win64, override with the APEX_PAKS environment variable or --paks.
DEFAULT_RSX = WORKSPACE / "bin" / "Release_NoGui" / "rsx.exe"
DEFAULT_PAKS = Path(os.environ.get("APEX_PAKS", r"D:\Apex\paks\Win64"))

TRAILING_COMMA = re.compile(r",\s*([}\]])")


def add_common_args(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p.add_argument("--rsx", type=Path, default=DEFAULT_RSX, help="rsx.exe (Release_NoGui)")
    p.add_argument("--paks", type=Path, default=DEFAULT_PAKS, help="Apex paks/Win64 directory")
    p.add_argument("--out", type=Path, default=None, help="export root (default depends on script)")
    p.add_argument("--parsethreads", type=int, default=8)
    p.add_argument("--from-existing", action="store_true", help="skip RSX, rebuild tables from files already on disk")
    p.add_argument("--dry-run", action="store_true", help="print the RSX command, do not run it")
    return p


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_rsx_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return json.loads(TRAILING_COMMA.sub(r"\1", text))


def pad_guid64(guid: str) -> str:
    g = guid.strip().lower().replace("0x", "")
    if not g:
        return ""
    return "0x" + g.upper().zfill(16)


def flavor_to_json(export_root: Path, flavor: str) -> Path:
    p = flavor.replace("\\", "/")
    if p.lower().endswith(".rpak"):
        p = p[:-5] + ".json"
    return export_root / Path(p)


def load_guid_map(csv_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not csv_path.exists():
        return out
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("asset_name") or "").replace("\\", "/")
            out[name.lower()] = row.get("guid") or ""
    return out


def run_rsx(
    rsx: Path,
    paks: list[Path],
    *,
    log_path: Path,
    loadwhitelist: str | None = None,
    export: bool = False,
    exporttypes: str | None = None,
    exportfilter: str | None = None,
    exportdir: Path | None = None,
    list_path: Path | None = None,
    listformat: str = "csv",
    parsethreads: int = 8,
    extra: list[str] | None = None,
    dry_run: bool = False,
) -> int:
    if not rsx.exists():
        raise FileNotFoundError(f"rsx.exe not found: {rsx}")
    missing = [p for p in paks if not p.exists()]
    if missing:
        raise FileNotFoundError("missing pak(s):\n  " + "\n  ".join(str(p) for p in missing))

    cmd: list[str] = [str(rsx), "-nocachedb", "--parsethreads", str(parsethreads)]
    if loadwhitelist:
        cmd += ["--loadwhitelist", loadwhitelist]
    if export:
        cmd.append("-export")
        if exporttypes:
            cmd += ["--exporttypes", exporttypes]
        if exportfilter:
            cmd += ["--exportfilter", exportfilter]
        if exportdir:
            ensure_dir(exportdir)
            cmd += ["--exportdir", str(exportdir)]
    if list_path:
        ensure_dir(list_path.parent)
        cmd += ["--list", str(list_path), "--listformat", listformat]
    if extra:
        cmd += extra
    cmd += [str(p) for p in paks]

    print("RSX:", " ".join(cmd))
    if dry_run:
        return 0

    ensure_dir(log_path.parent)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write("CMD: " + " ".join(cmd) + "\n")
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False)
    print(f"exit={proc.returncode}  log={log_path}")
    if proc.returncode != 0:
        raise RuntimeError(f"rsx failed ({proc.returncode}), see {log_path}")
    return proc.returncode


def pak(paks_dir: Path, name: str) -> Path:
    return paks_dir / name
