#!/usr/bin/env python3
"""Export wrap+rson from each map pak and inventory per-map vscripts."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rsx_common import WORKSPACE, add_common_args, ensure_dir, run_rsx  # noqa: E402

PATCH_NAME = re.compile(r"^(.*)(\(\d+\))\.rpak$", re.I)
SKIP_SUFFIXES = (
    "_loadscreen",
    "_server_perm",
)
KEEP_SUFFIXES = (
    "",
    "_client_perm",
    "_client_temp",
    "_server_temp",
)
PRIORITY = [
    "mp_rr_desertlands_mu5",
    "mp_rr_tropic_island_mu2_landscape",
    "mp_rr_canyonlands_staging_mu1",
    "mp_rr_olympus_mu3",
    "mp_rr_canyonlands_hu_avt_uh_night",
]
RSON_SCRIPT = re.compile(r"^\s*([A-Za-z0-9_./\\-]+\.(?:nut|gnut))\s*$")


def discover_map_paks(paks_dir: Path, *, all_variants: bool = False) -> list[Path]:
    """Base paks only. patch_master applies (01)/(02). Skip those filenames."""
    found: list[Path] = []
    for p in sorted(paks_dir.glob("*.rpak")):
        name = p.name
        if PATCH_NAME.match(name):
            continue
        stem = p.stem
        if not (stem == "mp_lobby" or stem.startswith("mp_lobby_") or stem.startswith("mp_rr_")):
            continue
        if not all_variants:
            if any(stem.endswith(suf) for suf in SKIP_SUFFIXES):
                continue
            core = stem
            for suf in ("_client_perm", "_client_temp", "_server_temp"):
                if core.endswith(suf):
                    core = core[: -len(suf)]
                    break
            core = re.sub(r"_gen3$", "", core)
            rest = stem[len(core):]
            if rest not in KEEP_SUFFIXES and not rest.startswith("_gen3"):
                continue
        found.append(p)
    def rank(path: Path) -> tuple[int, str]:
        stem = path.stem
        # group by map family
        fam = stem
        for suf in ("_client_perm", "_client_temp", "_server_temp"):
            if fam.endswith(suf):
                fam = fam[: -len(suf)]
                break
        fam = re.sub(r"_gen3$", "", fam)
        try:
            pri = PRIORITY.index(fam)
        except ValueError:
            pri = 100 + (0 if fam.startswith("mp_rr_") else 200)
        return (pri, stem)

    found.sort(key=rank)
    return found


def parse_rson_scripts(rson_dir: Path) -> list[str]:
    scripts: list[str] = []
    if not rson_dir.exists():
        return scripts
    in_block = False
    for rp in rson_dir.glob("*.rson"):
        for line in rp.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("Scripts:"):
                in_block = True
                continue
            if in_block:
                if stripped == "]":
                    in_block = False
                    continue
                m = RSON_SCRIPT.match(stripped)
                if m:
                    scripts.append(m.group(1).replace("\\", "/"))
    return scripts


def expected_exported_name(rson_script: str, pak_stem: str) -> str:
    """RSON has mp/levels/foo.nut; RSX writes foo.client.nut / foo.server.nut."""
    base = Path(rson_script).name  # foo.nut / foo.gnut
    stem, ext = base, ""
    if base.endswith(".gnut"):
        stem, ext = base[:-5], ".gnut"
    elif base.endswith(".nut"):
        stem, ext = base[:-4], ".nut"
    vm = ""
    if "_server_temp" in pak_stem:
        vm = ".server"
    elif "_client_perm" in pak_stem or "_client_temp" in pak_stem:
        vm = ".client"
    if vm:
        return stem + vm + ext
    return base


def inventory_one(out_root: Path, pak_stem: str) -> dict:
    dest = out_root / pak_stem
    wrap = dest / "wrap"
    rson = dest / "rson"
    nuts = list(wrap.rglob("*.nut")) + list(wrap.rglob("*.gnut")) if wrap.exists() else []
    rson_scripts = parse_rson_scripts(rson)
    exported_names = {p.name.lower() for p in nuts}
    missing = []
    for s in rson_scripts:
        expect = expected_exported_name(s, pak_stem).lower()
        if expect not in exported_names:
            # also accept original extension order foo.nut.client
            alt = Path(s).name.lower()
            if alt not in exported_names:
                missing.append(s)
    cl_hits = [p.name for p in nuts if p.name.lower().startswith("cl_")]
    return {
        "pak": pak_stem,
        "wrap_scripts": len(nuts),
        "rson_scripts": len(rson_scripts),
        "missing_from_rson": ";".join(missing),
        "cl_scripts": ";".join(cl_hits),
        "script_files": ";".join(p.relative_to(dest).as_posix() for p in sorted(nuts)),
    }


def write_report(out_root: Path, rows: list[dict]) -> None:
    meta = ensure_dir(out_root / "_meta")
    report = meta / "map_scripts_report.csv"
    fields = ["pak", "wrap_scripts", "rson_scripts", "missing_from_rson", "cl_scripts", "script_files"]
    with report.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {report}")
    print(f"{'pak':<48} wrap  rson  missing  cl_")
    for r in rows:
        miss_n = 0 if not r["missing_from_rson"] else r["missing_from_rson"].count(";") + 1
        print(f"{r['pak']:<48} {r['wrap_scripts']:4d}  {r['rson_scripts']:4d}  {miss_n:7d}  {r['cl_scripts']}")


def main() -> int:
    import argparse

    ap = add_common_args(argparse.ArgumentParser(description=__doc__))
    ap.add_argument("--only", action="append", default=[], help="only these pak stems (repeatable)")
    ap.add_argument("--skip", action="append", default=[], help="skip these pak stems (repeatable)")
    ap.add_argument("--scripts-only", action="store_true", help="exportfilter vscripts (skip bsp wrap lumps)")
    ap.add_argument(
        "--no-bsp",
        action="store_true",
        help="export scripts + rson, skip bsp wrap lumps (current RSX exits 1 on standalone map paks with missing lumps)",
    )
    ap.add_argument("--all-variants", action="store_true", help="also export loadscreen / server_perm paks")
    args = ap.parse_args()
    out_root = args.out or (WORKSPACE / "exported_maps")
    ensure_dir(out_root)
    meta_logs = ensure_dir(out_root / "_meta" / "logs")
    meta_lists = ensure_dir(out_root / "_meta" / "lists")

    paks = discover_map_paks(args.paks, all_variants=args.all_variants)
    if args.only:
        allow = {s.lower() for s in args.only}
        paks = [p for p in paks if p.stem.lower() in allow or p.stem.lower().split("_client")[0].split("_server")[0] in allow]
    if args.skip:
        skip = {s.lower() for s in args.skip}
        paks = [p for p in paks if p.stem.lower() not in skip]
    if not paks:
        raise SystemExit(f"no map paks under {args.paks}")

    print(f"map paks to process: {len(paks)}")
    for p in paks:
        print(" ", p.name)

    if args.scripts_only:
        exportfilter = r"scripts\vscripts"
    elif args.no_bsp:
        exportfilter = r"scripts\vscripts,0x"
    else:
        exportfilter = None
    exporttypes = "wrap,rson"

    if not args.from_existing:
        for p in paks:
            dest = out_root / p.stem
            run_rsx(
                args.rsx,
                [p],
                log_path=meta_logs / f"{p.stem}.export.log",
                loadwhitelist="wrap,rson,Ptch",
                export=True,
                exporttypes=exporttypes,
                exportfilter=exportfilter,
                exportdir=dest,
                list_path=meta_lists / f"{p.stem}.csv",
                listformat="csv",
                parsethreads=args.parsethreads,
                dry_run=args.dry_run,
            )
        if args.dry_run:
            return 0

    rows = [inventory_one(out_root, p.stem) for p in paks]
    # also inventory dirs that already exist if --from-existing without --only
    if args.from_existing and not args.only:
        rows = []
        for d in sorted(out_root.iterdir()):
            if d.is_dir() and d.name != "_meta":
                rows.append(inventory_one(out_root, d.name))
    write_report(out_root, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
