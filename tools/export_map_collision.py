"""Export one map's collision data for navdemo: world BVH lumps, server_temp (.ent / .nm),
static prop collision meshes (two detail levels) and the prop instance table.

  python -I tools\\export_map_collision.py --map mp_rr_canyonlands_staging_mu1
  python -I tools\\export_map_collision.py --map mp_rr_olympus_mu3 --dry-run

Paks are looked up as <stem>.rpak (rsx applies the (NN) patches through patch_master.rpak). Maps whose
client paks live under a variant name export with --map <variant> --server-pak <map>_server_temp, e.g.
  --map mp_rr_canyonlands_hu_avt --server-pak mp_rr_canyonlands_hu_server_temp

Layout (see docs/06-map-collision-export.md):
  <out>/client/wrap/maps/<bsp>.bsp.<LLLL>.client.bsp_lump
  <out>/server_temp/wrap/maps/...            .ent, navmesh/<map>/*.nm, graphs, scripts (if there is a _server_temp pak)
  <out>/overview/wrap/resource/overviews/<map>.txt   minimap overview (pos_x / pos_y / scale), if the map has one
  <out>/props/mdl/.../<name>.stl, <name>_d1.stl
  <out>/props_world/<bsp>_props_instances.csv
  <out>/map_info.txt                         worldspawn origin / decodeScale / node bounds step / overview values
  <work>/mdl/...                             full rsx mdl_ export of the map pak (+ models filled from shared paks)
  <work>/rsx_*.log
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_prop_collision as ppc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEEDED_LUMPS = (ppc.LUMP_MODELS, ppc.LUMP_CONTENTS_MASKS, ppc.LUMP_BVH_NODES, ppc.LUMP_BVH_LEAF_DATA, ppc.LUMP_GAME_LUMP)


def find_pak(paks, stem):
    """<stem>.rpak or None. rsx applies <stem>(NN).rpak patches itself via patch_master.rpak; a (NN) pak
    without its base only holds the changed assets (mp_rr_olympus_mu2_client_*(01) export no lumps)."""
    return stem + ".rpak" if os.path.exists(os.path.join(paks, stem + ".rpak")) else None


def patch_only(paks, stem):
    pat = re.compile(re.escape(stem) + r"\(\d+\)\.rpak$", re.I)
    return [f for f in os.listdir(paks) if pat.match(f)]


def check_lumps(lumps, bsp):
    """problems that make the exported lumps unusable (seen on mp_rr_arena_habitat: lumps left compressed)"""
    probs = []
    md = ppc.read_lump(lumps, bsp, ppc.LUMP_MODELS)
    if len(md) < 64:
        return ["000E (models) is empty"]
    mins, maxs = struct.unpack_from("<3f", md, 0), struct.unpack_from("<3f", md, 12)
    scale = struct.unpack_from("<f", md, 60)[0]
    if not all(abs(v) < 1e6 for v in mins + maxs) or not all(a < b for a, b in zip(mins, maxs)) \
            or scale not in (2.0 ** -16, 2.0 ** -15, 2.0 ** -14, 2.0 ** -13):
        probs.append(f"000E worldspawn looks wrong: mins {mins} maxs {maxs} decodeScale {scale}")
    gl = ppc.read_lump(lumps, bsp, ppc.LUMP_GAME_LUMP)
    if len(gl) < 20 or struct.unpack_from("<I", gl, 4)[0] != ppc.SPRP_ID:
        probs.append(f"0023 (game lump) has no sprp ({len(gl)} bytes)")
    return probs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, help="map stem, e.g. mp_rr_canyonlands_staging_mu1")
    ap.add_argument("--rsx", default=r"D:\code\rsx\bin\Release_NoGui\rsx.exe")
    ap.add_argument("--paks", default=r"D:\Apex\paks\Win64")
    ap.add_argument("--out", help=r"default collision_maps\<map>")
    ap.add_argument("--work", help=r"default exported_props_physics\<map>")
    ap.add_argument("--client-paks", help="comma list, default <map>_client_perm,<map>_client_temp")
    ap.add_argument("--map-pak", help="pak with the map's models, default <map>")
    ap.add_argument("--server-pak", help="default <map>_server_temp; 'none' to skip")
    ap.add_argument("--bsp", help="bsp name in the lump file names, default: detected from the client export")
    ap.add_argument("--shared", default="common_mp,common,common_early",
                    help="paks searched for BVH-referenced models that are not in the map pak")
    ap.add_argument("--dry-run", action="store_true", help="only print the rsx commands")
    args = ap.parse_args()

    m = args.map
    paks = args.paks
    out = os.path.abspath(args.out or os.path.join(ROOT, "collision_maps", m))
    work = os.path.abspath(args.work or os.path.join(ROOT, "exported_props_physics", m))

    def resolve(names):
        found, lost = [], []
        for n in names:
            n = n.strip()
            stem = n[:-5] if n.lower().endswith(".rpak") else n
            p = find_pak(paks, stem)
            (found if p else lost).append(p or stem)
        return found, lost

    def rsx(tag, cmd):
        full = [args.rsx, "-nogui", "-nocachedb"] + cmd
        print(f"[{tag}] " + subprocess.list2cmdline(full))
        if args.dry_run:
            return 0
        os.makedirs(work, exist_ok=True)
        log = os.path.join(work, f"rsx_{tag}.log")
        with open(log, "w", encoding="utf-8", errors="replace") as f:
            rc = subprocess.run(full, cwd=paks, stdout=f, stderr=subprocess.STDOUT).returncode
        print(f"    exit {rc}, log {log}")
        return rc

    client, lost = resolve((args.client_paks or f"{m}_client_perm,{m}_client_temp").split(","))
    for stem in lost:
        p = patch_only(paks, stem)
        print(f"[client] {stem}.rpak not found" + (f" (only patch paks {p}, not exportable on their own)" if p else ""))
    if lost:
        raise SystemExit("missing client paks: pass --client-paks / --map, e.g. the variant "
                         "mp_rr_canyonlands_hu_avt or mp_rr_tropic_island_mu2_landscape (see docs/06)")
    map_pak, _ = resolve([args.map_pak or m])
    server = None
    if (args.server_pak or "").lower() != "none":
        server, _ = resolve([args.server_pak or f"{m}_server_temp"])
        server = server[0] if server else None

    # 1. world collision lumps. All client paks in one call: the bsp loader looks lumps up across them.
    #    Filter on bsp_lump: exporting the .bsp asset itself (render-vertex OBJ, not collision) can crash rsx.
    client_dir = os.path.join(out, "client")
    rsx("client", ["--loadwhitelist", "wrap,Ptch", "-export", "--exporttypes", "wrap", "--exportfilter", "bsp_lump",
                   "--exportdir", client_dir] + client)
    lumps = os.path.join(client_dir, "wrap", "maps")
    bsp = args.bsp
    if not args.dry_run:
        if not bsp:
            stems = sorted({f.split(".bsp.")[0] for f in (os.listdir(lumps) if os.path.isdir(lumps) else [])
                            if f.endswith(".bsp.0012.client.bsp_lump")})
            if len(stems) != 1:
                raise SystemExit(f"cannot tell the bsp name from {lumps}: {stems} (pass --bsp)")
            bsp = stems[0]
        lost = [f"{i:04X}" for i in NEEDED_LUMPS
                if not os.path.exists(os.path.join(lumps, f"{bsp}.bsp.{i:04X}.client.bsp_lump"))]
        if lost:
            raise SystemExit(f"lumps missing after export: {lost} (see {work}\\rsx_client.log)")
        probs = check_lumps(lumps, bsp)
        print(f"[client] bsp {bsp}: " + ("; ".join(probs) if probs else "lumps look fine"))
        if probs:
            raise SystemExit("rsx did not export usable lumps for this map, stopping before the prop step")

    # 2. server_temp: .ent, navmesh .nm, ai graph, scripts. Not every map has one.
    if server:
        rsx("server_temp", ["--loadwhitelist", "wrap,Ptch", "-export", "--exporttypes", "wrap",
                            "--exportdir", os.path.join(out, "server_temp"), server])
        # this rsx keeps the string terminator of some .ent assets (<map>_env.ent ends in "}\n\0");
        # the older rsx_nogui.exe output that navdemo was written against does not have it
        ent_dir = os.path.join(out, "server_temp", "wrap", "maps")
        for fn in os.listdir(ent_dir) if os.path.isdir(ent_dir) and not args.dry_run else []:
            if fn.endswith(".ent"):
                p = os.path.join(ent_dir, fn)
                with open(p, "rb") as f:
                    b = f.read()
                if b.endswith(b"\0"):
                    with open(p, "wb") as f:
                        f.write(b.rstrip(b"\0"))
    else:
        print(f"[server_temp] no server_temp pak for {m}: no .nm / .ent")

    # 3. minimap overview: resource/overviews/<map>.txt in the map pak holds pos_x / pos_y / scale,
    #    the transform between the minimap image and world coordinates. Not every map has one
    #    (the training map uses a tiled background instead), so a missing file is not an error.
    if not map_pak:
        raise SystemExit(f"no model pak {args.map_pak or m}.rpak (pass --map-pak)")
    overview_dir = os.path.join(out, "overview")
    rsx("overview", ["--loadwhitelist", "wrap,Ptch", "-export", "--exporttypes", "wrap",
                     "--exportfilter", "overviews", "--exportdir", overview_dir, map_pak[0]])
    if not args.dry_run:
        ov_stem = os.path.splitext(os.path.basename(map_pak[0]))[0]
        ov = os.path.join(overview_dir, "wrap", "resource", "overviews", ov_stem + ".txt")
        print(f"[overview] {ov}" if os.path.exists(ov)
              else f"[overview] {map_pak[0]} has no resource/overviews/{ov_stem}.txt")

    # 4. prop collision meshes. asqd is required by model parsing; without it rsx crashes in ParseSequence.
    mdl_cmd = ["-exportfullpaths", "--loadwhitelist", "mdl_,asqd,Ptch", "-export", "--exporttypes", "mdl_",
               "--exportformat", "mdl_=stl_respawn_physics", "--exportdir", work]
    rsx("props", mdl_cmd + map_pak)
    if args.dry_run:
        print("[shared] models missing from the map pak are then exported from:", args.shared)
        return

    # 5. BVH-referenced models that live in the shared paks
    sprp_ver, props, refs, origin, qscale = ppc.load_map(lumps, bsp)
    missing = ppc.missing_models(work, props, refs)
    if missing:
        shared, _ = resolve(args.shared.split(","))
        print(f"[shared] {len(missing)} BVH-referenced models not in {map_pak[0]}, trying {shared}")
        # rsx asset names use backslashes (mdl\ola\sewer_grate_01.rmdl), sprp uses forward slashes
        rsx("shared", mdl_cmd + ["--exportfilter", ",".join(x.replace("/", "\\") for x in missing)] + shared)
        left = ppc.missing_models(work, props, refs)
        if left:
            print(f"[shared] still missing {len(left)}: {left}")

    # 6. deliver per-model STLs + instance table (props/ is fully regenerated)
    props_out = os.path.join(out, "props")
    if os.path.isdir(props_out):
        shutil.rmtree(props_out)
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "place_prop_collision.py"),
                    "--lumps", lumps, "--props", work, "--map", bsp,
                    "--out", os.path.join(out, "props_world"), "--deliver", props_out], check=True)

    # 7. map_info.txt: the numbers navdemo needs to decode the world BVH and place the minimap.
    #    The overview pos_x / pos_y / scale are copied from resource/overviews/<map>.txt when present.
    ov = os.path.join(overview_dir, "wrap", "resource", "overviews", ov_stem + ".txt")
    ov_vals = {}
    if os.path.exists(ov):
        with open(ov, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and parts[0] in ("pos_x", "pos_y", "scale"):
                    ov_vals[parts[0]] = parts[1]
    info = [
        f"bsp {bsp}",
        f"sprp_version {sprp_ver}",
        f"worldspawn_origin {origin[0]} {origin[1]} {origin[2]}",
        f"worldspawn_decode_scale {qscale / 65536.0!r}",
        f"node_bounds_step {qscale:g}",
    ]
    info += [f"overview_{k} {ov_vals[k]}" for k in ("pos_x", "pos_y", "scale") if k in ov_vals]
    info_path = os.path.join(out, "map_info.txt")
    with open(info_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(info) + "\n")
    print(f"[map_info] {info_path}")


if __name__ == "__main__":
    main()
