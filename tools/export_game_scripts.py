#!/usr/bin/env python3
"""Export Apex wrap scripts from script_client / script_ui / script_server rpaks."""
from __future__ import annotations

import csv
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rsx_common import WORKSPACE, add_common_args, ensure_dir, pak, run_rsx  # noqa: E402

SCRIPT_PAKS = [
    "script_client.rpak",
    "script_ui.rpak",
    "script_server.rpak",
]


def has_patch(paks_dir: Path, stem: str) -> bool:
    """True when a <stem>(NN).rpak patch file exists next to the base pak."""
    return any(paks_dir.glob(f"{stem}([0-9][0-9]).rpak"))


def merge_asset_lists(dst: Path, extra: Path) -> None:
    with dst.open(newline="", encoding="utf-8") as f:
        main = list(csv.reader(f))
    with extra.open(newline="", encoding="utf-8") as f:
        other = list(csv.reader(f))
    if not main or not other or main[0] != other[0]:
        raise RuntimeError(f"asset list headers differ: {dst} vs {extra}")
    with dst.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(main)
        w.writerows(other[1:])
    extra.unlink()


def classify(name: str) -> str:
    n = name.lower()
    if n.endswith(".client.nut") or n.endswith(".client.gnut"):
        return "client"
    if n.endswith(".ui.nut") or n.endswith(".ui.gnut"):
        return "ui"
    if n.endswith(".server.nut") or n.endswith(".server.gnut"):
        return "server"
    if n.endswith(".nut") or n.endswith(".gnut"):
        return "other_script"
    return "other"


def inventory(out_dir: Path) -> None:
    wrap = out_dir / "wrap"
    files = [p for p in wrap.rglob("*") if p.is_file()] if wrap.exists() else []
    counts = Counter(classify(p.name) for p in files)
    report = out_dir / "game_scripts_inventory.csv"
    ensure_dir(out_dir)
    with report.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["relpath", "class", "bytes"])
        for p in sorted(files, key=lambda x: str(x).lower()):
            w.writerow([p.relative_to(out_dir).as_posix(), classify(p.name), p.stat().st_size])
    print(f"files={len(files)}  {dict(counts)}")
    print(f"wrote {report}")
    print(f"scripts root: {wrap / 'scripts' / 'vscripts'}")


def main() -> int:
    import argparse

    ap = add_common_args(argparse.ArgumentParser(description=__doc__))
    ap.add_argument(
        "--include-server",
        action="store_true",
        default=True,
        help="include script_server.rpak (default on)",
    )
    ap.add_argument("--no-server", action="store_true", help="client+ui only, matching the original dump")
    args = ap.parse_args()
    out_dir = args.out or (WORKSPACE / "exported")
    server_pak = pak(args.paks, "script_server.rpak")
    # patch_master may reference script_server(NN).rpak that the client install
    # never ships; RSX then fails while loading the patch. Export the base server
    # pak from a temp dir without patch_master in that case.
    server_separate = (
        not args.no_server
        and server_pak.exists()
        and not has_patch(args.paks, "script_server")
    )
    names = list(SCRIPT_PAKS)
    if args.no_server or server_separate:
        names = [n for n in names if "server" not in n]
    paks = [pak(args.paks, n) for n in names if pak(args.paks, n).exists()]
    if not paks:
        raise SystemExit(f"no script_*.rpak under {args.paks}")

    if not args.from_existing:
        run_rsx(
            args.rsx,
            paks,
            log_path=out_dir / "rsx_game_scripts.log",
            loadwhitelist="wrap,rson,Ptch",
            export=True,
            exporttypes="wrap",
            exportfilter=r"scripts\vscripts",
            exportdir=out_dir,
            list_path=out_dir / "game_scripts_assets.csv",
            listformat="csv",
            parsethreads=args.parsethreads,
            dry_run=args.dry_run,
        )
        if server_separate:
            if args.dry_run:
                print(f"NOTE: no script_server(NN).rpak; would export {server_pak.name} without patch_master")
            else:
                with tempfile.TemporaryDirectory(prefix="rsx_server_") as td:
                    server_copy = Path(td) / server_pak.name
                    shutil.copy2(server_pak, server_copy)
                    run_rsx(
                        args.rsx,
                        [server_copy],
                        log_path=out_dir / "rsx_game_scripts_server.log",
                        loadwhitelist="wrap,rson",
                        export=True,
                        exporttypes="wrap",
                        exportfilter=r"scripts\vscripts",
                        exportdir=out_dir,
                        list_path=out_dir / "game_scripts_assets_server.csv",
                        listformat="csv",
                        parsethreads=args.parsethreads,
                    )
                merge_asset_lists(
                    out_dir / "game_scripts_assets.csv",
                    out_dir / "game_scripts_assets_server.csv",
                )
        if args.dry_run:
            return 0

    inventory(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
