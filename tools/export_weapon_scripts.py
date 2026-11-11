"""Export every weapon script (weapon/<name>.rpak -> scripts/weapons/<name>.txt) from the game paks.

Weapon definitions are WEPN assets. rsx names them "weapon/<name>.rpak" and exports them as text;
each exported file records its original source path in "sourceFilename"
(e.g. game\\r2\\scripts\\weapons\\mp_weapon_volt_smg.txt).

  python -I tools\\export_weapon_scripts.py
  python -I tools\\export_weapon_scripts.py --dry-run
  python -I tools\\export_weapon_scripts.py --paks D:\\Apex\\paks\\Win64 --out weapon_scripts

Layout:
  <out>/scripts/weapons/<name>.txt       all WEPN assets (weapon, melee, abilities, grenades, ...)
  <out>/weapon_assets_list.csv           rsx --list dump (type, guid, pak, asset name)
  <out>/weapon_scripts_index.csv         file name, asset name, sourceFilename, bytes
  <out>/rsx_export.log                   rsx output
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_RE = re.compile(r'"sourceFilename"\s+"([^"]+)"')

# well-known Apex codenames, only used for the summary line
WELL_KNOWN = {
    "volt": "mp_weapon_volt_smg",
    "r99": "mp_weapon_r97",
    "havoc": "mp_weapon_energy_ar",
    "lstar": "mp_weapon_lstar",
    "devotion": "mp_weapon_esaw",
    "nemesis": "mp_weapon_nemesis",
    "flatline": "mp_weapon_vinson",
    "r301": "mp_weapon_rspn101",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rsx", default=r"D:\code\rsx\bin\Release_NoGui\rsx.exe")
    ap.add_argument("--paks", default=r"D:\Apex\paks\Win64")
    ap.add_argument("--out", help=r"default weapon_scripts")
    ap.add_argument("--pak", default="common", help="pak stem that holds the WEPN assets (default common)")
    ap.add_argument("--dry-run", action="store_true", help="only print the rsx command")
    args = ap.parse_args()

    paks = args.paks
    out = os.path.abspath(args.out or os.path.join(ROOT, "weapon_scripts"))
    work = os.path.join(out, "_rsx_out")
    dest = os.path.join(out, "scripts", "weapons")
    pak = args.pak + ".rpak"
    pak_path = os.path.join(paks, pak)
    if not os.path.exists(pak_path):
        raise SystemExit(f"pak not found: {pak_path}")

    list_csv = os.path.join(out, "weapon_assets_list.csv")
    log_path = os.path.join(out, "rsx_export.log")
    cmd = [args.rsx, "-nogui", "-nocachedb", "--parsethreads", "8",
           "--loadwhitelist", "wepn,Ptch",
           "--list", list_csv, "--listformat", "csv",
           "-export", "--exporttypes", "wepn", "--exportdir", work, pak]
    print(subprocess.list2cmdline(cmd))
    if args.dry_run:
        return

    os.makedirs(out, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as f:
        rc = subprocess.run(cmd, cwd=paks, stdout=f, stderr=subprocess.STDOUT).returncode
    print(f"rsx exit {rc}, log {log_path}")
    if rc != 0:
        raise SystemExit(rc)

    src_dir = os.path.join(work, "weapon")
    if not os.path.isdir(src_dir):
        raise SystemExit(f"rsx wrote no weapon/ directory under {work}")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    exported = []
    for name in sorted(os.listdir(src_dir)):
        if not name.lower().endswith(".txt"):
            continue
        shutil.move(os.path.join(src_dir, name), os.path.join(dest, name))
        exported.append(name)
    shutil.rmtree(work, ignore_errors=True)

    # index: exported file -> asset name (weapon\<name>.rpak) -> original source path
    index_path = os.path.join(out, "weapon_scripts_index.csv")
    with open(index_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "asset_name", "source_filename", "bytes"])
        for name in exported:
            p = os.path.join(dest, name)
            with open(p, "r", encoding="utf-8", errors="replace") as g:
                text = g.read()
            m = SOURCE_RE.search(text)
            w.writerow([name, "weapon\\" + os.path.splitext(name)[0] + ".rpak",
                        m.group(1).replace("\\", "/") if m else "", os.path.getsize(p)])

    print(f"{len(exported)} weapon scripts -> {dest}")
    have = {os.path.splitext(n)[0] for n in exported}
    missing = []
    for label, stem in WELL_KNOWN.items():
        ok = stem in have
        if not ok:
            missing.append(f"{label} ({stem})")
        print(f"  {label:8s} {'ok' if ok else 'MISSING'}  {stem}.txt")
    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
