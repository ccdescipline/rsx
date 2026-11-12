"""Crop an exported map's collision data (see export_map_collision.py) to one or more
playlist cull spheres (cull_entity_spawn_circle "<x,y,z> r").

The world BVH (LUMP_BVH_NODES, 0012) is cropped in place, format-preserving: a node
child whose stored AABB does not intersect any sphere has its child type set to
NO_CHILD (1). Nodes, leaf data and vertices are otherwise untouched, so the walk from
the worldspawn root sees only the spheres' geometry while the file stays a valid BVH.
The prop instance CSV is filtered to instances whose origin is in a sphere, and props/
is rebuilt with only the models those instances need.

  python -I tools/crop_map_collision.py --map-dir collision_maps\\mp_rr_divided_moon_mu1 \\
      --bsp mp_rr_divided_moon_mu1 --sphere -32590,-3912,4235,15000 --stats-only
"""
import argparse
import csv
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_prop_collision as ppc  # noqa: E402
import bvh_decode as bd  # noqa: E402

LUMP_MODELS = 0x0E
LUMP_BVH_NODES = 0x12

NO_CHILD = bd.NO_CHILD
STATIC_PROP = bd.STATIC_PROP


def lump_path(lumps, bsp, i):
    return os.path.join(lumps, f"{bsp}.bsp.{i:04X}.client.bsp_lump")


def read_lump(lumps, bsp, i):
    with open(lump_path(lumps, bsp, i), "rb") as f:
        return f.read()


def worldspawn(lumps, bsp):
    md = read_lump(lumps, bsp, LUMP_MODELS)
    return struct.unpack_from("<3f", md, 48), struct.unpack_from("<f", md, 60)[0]


def aabb_hits_sphere(lo, hi, c, r):
    d2 = 0.0
    for j in range(3):
        if c[j] < lo[j]:
            d2 += (lo[j] - c[j]) ** 2
        elif c[j] > hi[j]:
            d2 += (c[j] - hi[j]) ** 2
    return d2 <= r * r


def decode_children(nodes, off):
    ax = struct.unpack_from("<24h", nodes, off)
    w = struct.unpack_from("<4I", nodes, off + 48)
    idx = (w[0] >> 8, w[1] >> 8, w[2] >> 8, w[3] >> 8)
    ty = (w[2] & 0xF, (w[2] >> 4) & 0xF, w[3] & 0xF, (w[3] >> 4) & 0xF)
    return ax, idx, ty


def child_bounds(ax, child, origin, qscale):
    lo = [origin[a] + ax[a * 8 + child] * qscale for a in range(3)]
    hi = [origin[a] + ax[a * 8 + 4 + child] * qscale for a in range(3)]
    return lo, hi


def clear_child_type(nodes, off, child):
    wo = off + 48 + (2 + child // 2) * 4
    w = struct.unpack_from("<I", nodes, wo)[0]
    shift = 0 if child % 2 == 0 else 4
    w = (w & ~(0xF << shift)) | (NO_CHILD << shift)
    struct.pack_into("<I", nodes, wo, w)


def walk(nodes, world, origin, qscale, spheres, on_poly=None, prune=False, inflate=None, stats=None):
    """walk the worldspawn BVH; optionally clear outside child slots. returns (pruned, nodes_seen).
    nodes is the (possibly cropped) node lump; leaf triangles are decoded by bvh_decode.World,
    the same way the engine does (packed verts, hulls, heightfield patches included)."""
    if stats is None:
        stats = {}
    eps = qscale if inflate is None else inflate
    seen = set()
    stack = [0]
    pruned = 0

    def emit(tri, is_hole):
        if not is_hole:
            on_poly(tri)

    while stack:
        k = stack.pop()
        if k in seen or k * 64 + 64 > len(nodes):
            continue
        seen.add(k)
        stats["nodes"] = stats.get("nodes", 0) + 1
        off = k * 64
        ax, idx, ty = decode_children(nodes, off)
        for c in range(4):
            t = ty[c]
            if t == NO_CHILD or t == 2:
                continue
            lo, hi = child_bounds(ax, c, origin, qscale)
            lo = [v - eps for v in lo]
            hi = [v + eps for v in hi]
            if not any(aabb_hits_sphere(lo, hi, s[0], s[1]) for s in spheres):
                # any child type with a stored AABB can be dropped; the payload stays in the lumps,
                # it simply stops being reachable from the root
                if prune:
                    clear_child_type(nodes, off, c)
                pruned += 1
                stats["pruned_" + str(t)] = stats.get("pruned_" + str(t), 0) + 1
                continue
            stats["kept_" + str(t)] = stats.get("kept_" + str(t), 0) + 1
            if t == 0:
                stack.append(idx[c])
            elif on_poly and t != STATIC_PROP:
                world.decode_child(0, t, idx[c], emit)
    return pruned, len(seen)


def in_spheres(origin, spheres):
    return any((origin[0] - c[0]) ** 2 + (origin[1] - c[1]) ** 2 + (origin[2] - c[2]) ** 2 <= r * r
               for c, r in spheres)


def angle_matrix(a):
    """Source AngleMatrix(pitch, yaw, roll), as in place_prop_collision.py"""
    import math
    p, y, r = (math.radians(v) for v in a)
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    return ((cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy),
            (cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy),
            (-sp, sr * cp, cr * cp))


_BBOX_CACHE = {}


def model_bbox(props_src, model):
    key = model.lower()
    if key in _BBOX_CACHE:
        return _BBOX_CACHE[key]
    lo, hi = [1e30] * 3, [-1e30] * 3
    for _rel, p in model_stls(props_src, model):
        with open(p, "rb") as f:
            b = f.read()
        n = struct.unpack_from("<I", b, 80)[0]
        for t in range(n):
            for k in range(3):
                x, y, z = struct.unpack_from("<3f", b, 84 + t * 50 + 12 + k * 12)
                lo[0], lo[1], lo[2] = min(lo[0], x), min(lo[1], y), min(lo[2], z)
                hi[0], hi[1], hi[2] = max(hi[0], x), max(hi[1], y), max(hi[2], z)
    out = None if lo[0] > hi[0] else (tuple(lo), tuple(hi))
    _BBOX_CACHE[key] = out
    return out


def instance_hits_sphere(row, spheres, props_src):
    """placed prop AABB vs spheres; falls back to the origin when the model has no STL"""
    o = (float(row["ox"]), float(row["oy"]), float(row["oz"]))
    bbox = model_bbox(props_src, row["model"])
    if bbox is None:
        return in_spheres(o, spheres)
    s = float(row["scale"]) or 1.0
    M = angle_matrix((float(row["pitch"]), float(row["yaw"]), float(row["roll"])))
    lo, hi = [1e30] * 3, [-1e30] * 3
    (x0, y0, z0), (x1, y1, z1) = bbox
    for x in (x0, x1):
        for y in (y0, y1):
            for z in (z0, z1):
                for j in range(3):
                    w = o[j] + s * (M[j][0] * x + M[j][1] * y + M[j][2] * z)
                    lo[j], hi[j] = min(lo[j], w), max(hi[j], w)
    return any(aabb_hits_sphere(lo, hi, c, r) for c, r in spheres)


def model_stls(props_src, model):
    base = model.rsplit(".", 1)[0]
    out = []
    for rel in (base + ".stl", base + "_d1.stl"):
        p = os.path.join(props_src, rel.replace("/", os.sep))
        if os.path.exists(p):
            out.append((rel, p))
    return out


def disk_case(root, rel):
    out, cur = [], root
    for part in rel.split("/"):
        names = {n.lower(): n for n in os.listdir(cur)}
        part = names.get(part.lower(), part)
        out.append(part)
        cur = os.path.join(cur, part)
    return "/".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map-dir", required=True)
    ap.add_argument("--bsp", required=True)
    ap.add_argument("--sphere", action="append", required=True,
                    help="cx,cy,cz,radius (repeatable); from cull_entity_spawn_circle")
    ap.add_argument("--props-src", help="rsx mdl_ export dir, default exported_props_physics/<bsp>")
    ap.add_argument("--full-csv", help="unfiltered instance CSV (default: <map-dir>/props_world/<bsp>_props_instances.csv)")
    ap.add_argument("--stats-only", action="store_true")
    args = ap.parse_args()

    spheres = []
    for s in args.sphere:
        v = [float(x) for x in s.split(",")]
        if len(v) != 4:
            raise SystemExit(f"bad --sphere {s}")
        spheres.append(((v[0], v[1], v[2]), v[3]))

    lumps = os.path.join(args.map_dir, "client", "wrap", "maps")
    origin, decode_scale = worldspawn(lumps, args.bsp)
    qscale = decode_scale * 65536.0
    nodes = bytearray(read_lump(lumps, args.bsp, LUMP_BVH_NODES))
    world = bd.World(lumps, args.bsp)
    print(f"worldspawn origin {origin}, decodeScale {decode_scale:g} (bounds step {qscale:g}); "
          f"{len(nodes)//64} nodes, {len(world.fverts)//3} float verts, {len(world.pverts)//3} packed verts, "
          f"{len(world.heightfields)} heightfields")

    stats = {"tris": 0, "tris_in": 0}

    def count_poly(poly):
        stats["tris"] += 1
        lo = [min(p[j] for p in poly) for j in range(3)]
        hi = [max(p[j] for p in poly) for j in range(3)]
        if any(aabb_hits_sphere(lo, hi, s[0], s[1]) for s in spheres):
            stats["tris_in"] += 1

    walk(nodes, world, origin, qscale, spheres, on_poly=count_poly)
    print(f"triangles with AABB intersecting a sphere: {stats['tris_in']} / {stats['tris']}")
    pruned, seen = walk(nodes, world, origin, qscale, spheres, stats={})
    print(f"nodes seen {seen}, child slots that a prune would drop {pruned}")
    if args.stats_only:
        return

    pruned, _ = walk(nodes, world, origin, qscale, spheres, prune=True, stats={})
    if len(nodes) % 64:
        raise SystemExit("node lump size not a multiple of 64")
    # keep the uncropped node lump once, so a different sphere set can be re-applied
    props_src = args.props_src or os.path.join("exported_props_physics", args.bsp)
    backup_dir = os.path.join(props_src, "crop_original")
    backup = os.path.join(backup_dir, f"{args.bsp}.bsp.{LUMP_BVH_NODES:04X}.client.bsp_lump")
    if not os.path.exists(backup):
        os.makedirs(backup_dir, exist_ok=True)
        with open(lump_path(lumps, args.bsp, LUMP_BVH_NODES), "rb") as f:
            orig = f.read()
        with open(backup, "wb") as f:
            f.write(orig)
        print("backup of the uncropped 0012:", backup)
    with open(lump_path(lumps, args.bsp, LUMP_BVH_NODES), "wb") as f:
        f.write(nodes)

    after = {"tris": 0, "tris_in": 0}

    def after_poly(poly):
        after["tris"] += 1
        lo = [min(p[j] for p in poly) for j in range(3)]
        hi = [max(p[j] for p in poly) for j in range(3)]
        if any(aabb_hits_sphere(lo, hi, s[0], s[1]) for s in spheres):
            after["tris_in"] += 1

    walk(nodes, world, origin, qscale, spheres, on_poly=after_poly)
    print(f"pruned {pruned} node child slots; triangles after crop: {after['tris']} "
          f"({after['tris_in']} intersect a sphere, {after['tris'] - after['tris_in']} overshoot)")

    # props: keep instances whose placed mesh touches a sphere, plus every instance the cropped
    # world BVH still references (the stored node AABB and the placed mesh AABB can disagree at
    # the boundary; dropping a referenced index would leave a dangling leaf in the CSV contract)
    csv_path = os.path.join(args.map_dir, "props_world", f"{args.bsp}_props_instances.csv")
    full_csv = args.full_csv or csv_path
    with open(full_csv, newline="") as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames
        rows = list(rd)
    _sprp, _props, refs, _origin, _q = ppc.load_map(lumps, args.bsp)
    refidx = set(refs)
    kept = [r for r in rows
            if instance_hits_sphere(r, spheres, props_src) or int(r["index"]) in refidx]
    if not os.path.exists(csv_path + ".full") and full_csv == csv_path:
        shutil.copyfile(csv_path, csv_path + ".full")
    with open(csv_path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields)
        wr.writeheader()
        wr.writerows(kept)
    print(f"prop instances kept {len(kept)} / {len(rows)} "
          f"({sum(1 for r in kept if int(r['index']) in refidx)} BVH refs)")

    # props/: only models used by kept BVH instances
    props_out = os.path.join(args.map_dir, "props")
    if os.path.isdir(props_out):
        shutil.rmtree(props_out)
    ship, size = {}, 0
    for r in kept:
        if r.get("in_bvh") != "1":
            continue
        for rel, src in model_stls(props_src, r["model"]):
            if rel.lower() not in ship:
                ship[rel.lower()] = (disk_case(props_src, rel), src)
    for rel, src in sorted(ship.values()):
        dst = os.path.join(props_out, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        size += os.path.getsize(dst)
    print(f"delivered {len(ship)} prop STLs ({size} bytes)")

    with open(os.path.join(args.map_dir, "cull.txt"), "w", encoding="utf-8") as f:
        f.write(f"bsp {args.bsp}\nworldspawn origin {origin} decodeScale {decode_scale:g}\n")
        for c, r in spheres:
            f.write(f"sphere {c[0]:.3f} {c[1]:.3f} {c[2]:.3f} {r:.3f}\n")
        f.write(f"nodes pruned {pruned}; triangles {after['tris']} "
                f"({after['tris_in']} in sphere)\n")


if __name__ == "__main__":
    main()
