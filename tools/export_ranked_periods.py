#!/usr/bin/env python3
"""Export the ranked period stgs from common.rpak and build the SAID tables (docs/02-ranked-periods.md).

Root asset: settings/base_itemflavors.rpak, two arrays:
  ranked2Pt0Periods   Ranked 2.0 (S17+), one entry per season or per split
  calevents           old calendar events; split by itemType:
                        calevent_rankedperiod          BR ranked before Ranked 2.0
                        calevent_arenas_ranked_period  arenas ranked
Every array entry names a flavor asset; its own stgs gives uniqueId (SAID), parentItemFlavor,
rankv2split (0 whole season, 1/2 split) and split2StartTime.

  python tools/export_ranked_periods.py
  python tools/export_ranked_periods.py --from-existing
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rsx_common import (WORKSPACE, add_common_args, ensure_dir, flavor_to_json, load_guid_map,  # noqa: E402
                        load_rsx_json, pad_guid64, pak, run_rsx)

ROOT_ASSET = "settings/base_itemflavors.rpak"
ARRAYS = ("ranked2Pt0Periods", "calevents")
TABLES = (
    ("ranked2", "ranked2Pt0Periods", None),
    ("br", "calevents", "calevent_rankedperiod"),
    ("arenas", "calevents", "calevent_arenas_ranked_period"),
)


def said(unique_id) -> str:
    return "" if unique_id in (None, "") else f"SAID{int(unique_id):011d}"


def flavor_of(entry) -> str:
    """asset path held by one array entry: the first string value that is an .rpak asset"""
    if isinstance(entry, str):
        return entry if entry.lower().endswith(".rpak") else ""
    if isinstance(entry, dict):
        for v in entry.values():
            if isinstance(v, str) and v.lower().endswith(".rpak"):
                return v
    return ""


def stem(asset: str) -> str:
    return Path(asset.replace("\\", "/")).stem if asset else ""


def as_date(v) -> str:
    """split2StartTime: unix seconds -> YYYY-MM-DD (UTC); strings are kept, 0/empty -> ''"""
    if v in (None, "", 0, "0"):
        return ""
    try:
        return dt.datetime.fromtimestamp(int(v), dt.timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError, OSError):
        return str(v)


def build(out_dir: Path) -> tuple[list[dict], list[dict]]:
    guids = load_guid_map(out_dir / "ranked_stgs.csv")
    root_json = flavor_to_json(out_dir, ROOT_ASSET)
    if not root_json.exists():
        raise SystemExit(f"{root_json} missing (run without --from-existing first)")
    root = load_rsx_json(root_json).get("settings", {})

    full = []
    for array in ARRAYS:
        entries = root.get(array)
        if not isinstance(entries, list):
            print(f"WARNING: {array} not found in {root_json}")
            continue
        for i, entry in enumerate(entries):
            asset = flavor_of(entry).replace("\\", "/")
            row = {"array": array, "index": i, "asset": stem(asset), "itemType": "", "uniqueId": "",
                   "SAID": "", "guid64": pad_guid64(guids.get(asset.lower(), "")), "parent": "",
                   "rankv2split": "", "split2StartTime": "", "flavor": asset}
            p = flavor_to_json(out_dir, asset) if asset else None
            if p is not None and p.exists():
                data = load_rsx_json(p)
                s = data.get("settings", {})
                uid = data.get("uniqueId")
                row.update({
                    "itemType": s.get("itemType", ""),
                    "uniqueId": "" if uid is None else uid,
                    "SAID": said(uid),
                    "parent": stem(s.get("parentItemFlavor", "")),
                    "rankv2split": s.get("rankv2split", ""),
                    "split2StartTime": as_date(s.get("split2StartTime")),
                })
            elif asset:
                print(f"  no exported json for {asset}")
            full.append(row)

    ranked = []
    for table, array, item_type in TABLES:
        for r in full:
            if r["array"] == array and (item_type is None or r["itemType"] == item_type):
                ranked.append({"table": table, **{k: r[k] for k in (
                    "asset", "SAID", "uniqueId", "guid64", "rankv2split", "parent", "split2StartTime", "itemType")}})
    return ranked, full


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        print(f"nothing to write to {path}")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def main() -> int:
    ap = add_common_args(argparse.ArgumentParser(description=__doc__))
    ap.add_argument("--pak", default="common.rpak")
    args = ap.parse_args()
    out_dir = ensure_dir(args.out or (WORKSPACE / "exported_seasons"))

    if not args.from_existing:
        run_rsx(
            args.rsx,
            [pak(args.paks, args.pak)],
            log_path=out_dir / "rsx_ranked_periods.log",
            loadwhitelist="stgs,stlt,Ptch",
            export=True,
            exporttypes="stgs",
            exportfilter=r"base_itemflavors,ranked2pt0,itemflav\calevent,ranked_event_container",
            exportdir=out_dir,
            list_path=out_dir / "ranked_stgs.csv",
            listformat="csv",
            parsethreads=args.parsethreads,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            return 0

    ranked, full = build(out_dir)
    for table, _, _ in TABLES:
        print(f"  {table}: {sum(1 for r in ranked if r['table'] == table)}")
    write_csv(out_dir / "ranked_period_saids.csv", ranked)
    write_csv(out_dir / "ranked_and_calevents_full.csv", full)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
