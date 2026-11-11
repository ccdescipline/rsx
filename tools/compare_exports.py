#!/usr/bin/env python3
"""Compare two export trees by SHA-256 and print added / removed / changed files.

  python -I .claude/skills/apex-script-export/scripts/compare_exports.py ^
      exported_20261104 exported_20261111 --suffix .nut --suffix .gnut
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def snap(root: Path, suffixes: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if suffixes and p.suffix.lower() not in suffixes:
            continue
        out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--suffix", action="append", default=[], help="limit to a suffix, e.g. .nut")
    ap.add_argument("--max", type=int, default=200, help="max paths printed per category")
    args = ap.parse_args()

    suffixes = tuple(s.lower() if s.startswith(".") else "." + s.lower() for s in args.suffix)
    old = snap(args.old, suffixes)
    new = snap(args.new, suffixes)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])

    print(f"old={len(old)} new={len(new)} added={len(added)} removed={len(removed)} changed={len(changed)}")
    for label, items in (("added", added), ("removed", removed), ("changed", changed)):
        if not items:
            continue
        print(f"--- {label} ---")
        for item in items[: args.max]:
            print(item)
        if len(items) > args.max:
            print(f"... {len(items) - args.max} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
