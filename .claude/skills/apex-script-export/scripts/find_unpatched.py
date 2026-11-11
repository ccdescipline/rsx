#!/usr/bin/env python3
"""Print --skip arguments for map paks whose patch_master patch file is missing.

RSX loads patch_master.rpak for every pak and rewrites <stem>.rpak to
<stem>(NN).rpak when patch_master has an entry. Client installs do not ship
every server pak, so the patch file can be absent and RSX exits 1 while
loading it. This script lists the stems that need --skip.

  python -I .claude/skills/apex-script-export/scripts/find_unpatched.py
  python -I .claude/skills/apex-script-export/scripts/find_unpatched.py --all
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def default_project() -> Path:
    # Prefer the current directory when it looks like the export project, so
    # this also works if the skill is copied to ~/.claude/skills.
    cwd = Path.cwd()
    if (cwd / "tools" / "export_map_scripts.py").exists():
        return cwd
    # <project>/.claude/skills/apex-script-export/scripts/find_unpatched.py
    return Path(__file__).resolve().parents[4]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=default_project())
    ap.add_argument("--paks", type=Path, default=Path(r"D:\Apex\paks\Win64"))
    ap.add_argument("--all", action="store_true", help="also print entries that do have a patch file")
    args = ap.parse_args()

    sys.path.insert(0, str(args.project / "tools"))
    from export_map_scripts import discover_map_paks

    patch_master = args.paks / "patch_master.rpak"
    if not patch_master.exists():
        raise SystemExit(f"patch_master not found: {patch_master}")

    # patch_master stores base pak names as strings; the PTCH asset itself has
    # no JSON export, so use the printable .rpak names as the entry list.
    names = {
        m.decode("latin1")
        for m in re.findall(rb"[ -~]{4,}", patch_master.read_bytes())
        if m.lower().endswith(b".rpak")
    }

    missing: list[str] = []
    for pak in discover_map_paks(args.paks):
        if pak.name not in names:
            continue
        patches = sorted(pak.parent.glob(f"{pak.stem}([0-9][0-9]).rpak"))
        if patches and not args.all:
            continue
        if patches:
            print(f"# {pak.stem}: {', '.join(p.name for p in patches)}")
        else:
            print(f"--skip {pak.stem}")
            missing.append(pak.stem)

    if not missing:
        print("all patch_master map entries have patch files", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
