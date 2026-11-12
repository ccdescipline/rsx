#!/usr/bin/env python3
"""Compare two weapon_scripts exports by value, not by bytes.

Made for checking the 2026-11-12 WEPN export changes: the old rsx printed "// val unk" comments,
floats with 6 decimals and negative integers as unsigned 64-bit (18446744073709551615 for -1).
Those differences are reported per kind; anything else is a real change.

  python -I tools/compare_weapon_scripts.py weapon_scripts_old/scripts/weapons weapon_scripts/scripts/weapons
"""
from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path

KV_RE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"')
NAME_RE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*$')


def parse(path: Path) -> list[tuple[str, str]]:
    """flatten to (block/path/key, value) in file order, comments dropped"""
    out, stack, pending = [], [], None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        m = KV_RE.match(s)
        if m:
            out.append(("/".join(stack + [m.group(1)]), m.group(2)))
            continue
        m = NAME_RE.match(s)
        if m:
            pending = m.group(1)
        elif s == "{":
            stack.append(pending or "")
            pending = None
        elif s == "}":
            if stack:
                stack.pop()
    return out


def as_number(v: str):
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return None


def classify(old: str, new: str) -> str:
    if old == new:
        return "same"
    a, b = as_number(old), as_number(new)
    if isinstance(a, int) and isinstance(b, int) and a >= 2 ** 63 and a - 2 ** 64 == b:
        return "negative int fixed"
    if a is not None and b is not None:
        fa, fb = float(a), float(b)
        if fa == fb:
            return "float formatting only"
        if abs(fa - fb) <= 5e-7 * max(1.0, abs(fb)):
            return "float precision (old 6 decimals)"
        return "VALUE CHANGED"
    if old.replace('\\"', '"') == new.replace('\\"', '"'):
        return "string escaping only"
    return "VALUE CHANGED"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--max", type=int, default=40)
    args = ap.parse_args()

    old_files = {p.name.lower(): p for p in args.old.glob("*.txt")}
    new_files = {p.name.lower(): p for p in args.new.glob("*.txt")}
    kinds = collections.Counter()
    real = []
    for name in sorted(set(old_files) | set(new_files)):
        if name not in old_files or name not in new_files:
            real.append(f"{name}: only in {'new' if name in new_files else 'old'}")
            continue
        a, b = parse(old_files[name]), parse(new_files[name])
        if [k for k, _ in a] != [k for k, _ in b]:
            real.append(f"{name}: key order/set differs ({len(a)} vs {len(b)} keys)")
        bmap = dict(b)
        for k, v in a:
            if k not in bmap:
                continue
            kind = classify(v, bmap[k])
            kinds[kind] += 1
            if kind == "VALUE CHANGED":
                real.append(f"{name}: {k}: {v!r} -> {bmap[k]!r}")

    print(f"files old={len(old_files)} new={len(new_files)}")
    for kind, n in kinds.most_common():
        print(f"  {kind}: {n}")
    if real:
        print(f"--- {len(real)} real differences ---")
        for r in real[: args.max]:
            print(r)
        if len(real) > args.max:
            print(f"... {len(real) - args.max} more")
    else:
        print("no real differences")
    return 1 if real else 0


if __name__ == "__main__":
    raise SystemExit(main())
