"""Match the static prop instances of a map with per-model collision STLs (rsx
--exportformat mdl_=stl_respawn_physics) and check them against the world collision BVH.

Inputs
  --lumps   dir with <map>.bsp.<LLLL>.client.bsp_lump (rsx wrap export of _client_perm + _client_temp)
  --props   rsx mdl_ export dir made with -exportfullpaths (mdl/.../<name>.stl, <name>_d1.stl)
  --map     map stem, e.g. mp_rr_canyonlands_staging_mu1
  --out     output dir

Which props: the ones the world collision BVH references (child type 9 = static prop).
Leaf data is one dword: low 31 bits = sprp index (needs more than 16 bits on big maps: mp_rr_olympus_mu3
has 466k props), bit 31 set (solid==7 props) = the prop always uses collision detail 1. Player movement: bit 31 -> detail 1, else detail 0 (engine rule, confirmed
by the navdemo side); a model without a detail 0 part has no movement collision.
rsx writes detail 0 as <name>.stl and detail 1 as <name>_d1.stl when it is a different part
(no _d1 file = same mesh as detail 0, no <name>.stl = model has no detail 0).
Node bounds are int16, per axis min[4] then max[4], world = worldspawn bvh origin + q * decodeScale * 65536
(decodeScale 2^-15 -> q * 2 on the training map, 2^-14 -> q * 4 on mp_rr_olympus_mu3).
They span detail 1 for bit-31 props and detail 0 + detail 1 for the others; bounds_err uses that.

Outputs (world coordinates, Z up, same space as the BSP lumps)
  <map>_props_instances.csv   every sprp instance; has_stl/tris follow the movement rule,
                              bounds_err = placed mesh bounds vs BVH node bounds (as above)
  <map>_props_collision.stl   movement collision of all placed props, binary STL (only with --world-stl)
  <map>_props_collision.obj   same, one object per instance (only with --obj, ~2.3x the STL size)
  --deliver DIR               copy <name>.stl / <name>_d1.stl of every BVH-referenced model into DIR
"""
import argparse
import collections
import csv
import math
import os
import shutil
import struct

LUMP_MODELS = 0x0E
LUMP_CONTENTS_MASKS = 0x10
LUMP_BVH_NODES = 0x12
LUMP_BVH_LEAF_DATA = 0x13
LUMP_GAME_LUMP = 0x23
CHILD_NODE = 0
CHILD_BUNDLE = 3
CHILD_STATIC_PROP = 9
SPRP_ID = 0x73707270  # 'prps' on disk
LEAF_DETAIL1 = 0x80000000
PROP_INDEX_MASK = 0x7FFFFFFF


def read_lump(d, m, i):
    with open(os.path.join(d, f"{m}.bsp.{i:04X}.client.bsp_lump"), "rb") as f:
        return f.read()


def parse_sprp(gl):
    n = struct.unpack_from("<i", gl, 0)[0]
    ids = [struct.unpack_from("<IHH", gl, 4 + i * 16) for i in range(n)]
    if not ids or ids[0][0] != SPRP_ID:
        raise SystemExit(f"first game lump is not sprp: {ids}")
    b = gl[4 + n * 16:]
    dc = struct.unpack_from("<i", b, 0)[0]
    names = [b[4 + i * 128:4 + (i + 1) * 128].split(b"\0")[0].decode() for i in range(dc)]
    off = 4 + dc * 128
    pc = struct.unpack_from("<i", b, off)[0]
    off += 12  # propCount + two counts we do not use
    props = []
    for i in range(pc):
        p = b[off + i * 64:off + (i + 1) * 64]
        props.append({
            "model": names[struct.unpack_from("<H", p, 28)[0]],
            "origin": struct.unpack_from("<3f", p, 0),
            "angles": struct.unpack_from("<3f", p, 12),
            "scale": struct.unpack_from("<f", p, 24)[0] or 1.0,
            "solid": p[30],
            "flags": p[31],
        })
    return ids[0][2], props


def bvh_prop_refs(nodes, leafs, masks):
    """yield (prop index, raw dword, contents mask, node bounds or None)"""
    def u32(i):
        return struct.unpack_from("<I", leafs, i * 4)[0]

    # Walk the worldspawn tree from its root (dmodel 0: bvhNode 0, bvhLeaf 0). The lump also holds the
    # trees of the other brush models, whose child indices are relative to their own node/leaf base.
    stack = [0]
    seen = set()
    while stack:
        k = stack.pop()
        if k in seen:
            continue
        seen.add(k)
        ax = struct.unpack_from("<24h", nodes, k * 64)
        w = struct.unpack_from("<4I", nodes, k * 64 + 48)
        cm = masks[w[0] & 0xFF]
        idx = [w[0] >> 8, w[1] >> 8, w[2] >> 8, w[3] >> 8]
        ty = [w[2] & 0xF, (w[2] >> 4) & 0xF, w[3] & 0xF, (w[3] >> 4) & 0xF]
        for c in range(4):
            if ty[c] == CHILD_NODE:
                stack.append(idx[c])
            elif ty[c] == CHILD_STATIC_PROP:
                bounds = [(ax[a * 8 + c], ax[a * 8 + 4 + c]) for a in range(3)]
                dw = u32(idx[c])
                yield dw & PROP_INDEX_MASK, dw, cm, bounds
            elif ty[c] == CHILD_BUNDLE:
                ix = idx[c]
                cnt = u32(ix)
                o = 1 + cnt
                for s in range(cnt):
                    scm, pt, ln = struct.unpack_from("<BBH", leafs, (ix + 1 + s) * 4)
                    if pt == CHILD_STATIC_PROP:
                        dw = u32(ix + o)
                        yield dw & PROP_INDEX_MASK, dw, masks[scm], None
                    o += ln


def load_map(lumps, m):
    """(sprp version, props, BVH refs {prop index: {dword, contents, bounds}}, worldspawn bvh origin, node bounds scale)"""
    sprp_ver, props = parse_sprp(read_lump(lumps, m, LUMP_GAME_LUMP))
    # worldspawn dmodel_t: mins, maxs, firstMesh, meshCount, bvhNode, bvhLeaf, vertIndex, flags, origin, decodeScale
    md = read_lump(lumps, m, LUMP_MODELS)
    origin = struct.unpack_from("<3f", md, 48)
    qscale = struct.unpack_from("<f", md, 60)[0] * 65536.0
    if struct.unpack_from("<2I", md, 32) != (0, 0):
        raise SystemExit(f"worldspawn bvhNode/bvhLeaf are {struct.unpack_from('<2I', md, 32)}, expected (0, 0)")
    masks_raw = read_lump(lumps, m, LUMP_CONTENTS_MASKS)
    masks = struct.unpack_from(f"<{len(masks_raw) // 4}I", masks_raw)
    refs = {}
    for pi, dw, cm, bounds in bvh_prop_refs(read_lump(lumps, m, LUMP_BVH_NODES),
                                            read_lump(lumps, m, LUMP_BVH_LEAF_DATA), masks):
        if pi >= len(props):
            raise SystemExit(f"bvh prop index {pi} >= sprp count {len(props)}")
        r = refs.setdefault(pi, {"dword": dw, "contents": cm, "bounds": None})
        if bounds is not None:
            r["bounds"] = bounds
    return sprp_ver, props, refs, origin, qscale


def angle_matrix(a):
    # Source AngleMatrix: angles = (pitch, yaw, roll) in degrees, rows are world axes
    p, y, r = (math.radians(v) for v in a)
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    return ((cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy),
            (cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy),
            (-sp, sr * cp, cr * cp))


def load_stl(path):
    with open(path, "rb") as f:
        b = f.read()
    n = struct.unpack_from("<I", b, 80)[0]
    return [struct.unpack_from("<9f", b, 84 + t * 50 + 12) for t in range(n)]


def model_files(props_dir, model):
    """(detail 0 rel path or None, detail 1-only rel path or None)"""
    base = model.rsplit(".", 1)[0]

    def have(rel):
        return rel if os.path.exists(os.path.join(props_dir, rel.replace("/", os.sep))) else None
    return have(base + ".stl"), have(base + "_d1.stl")


def disk_case(root, rel):
    """rel with the letter case of the existing file (Windows paths match case-insensitively)"""
    out, cur = [], root
    for part in rel.split("/"):
        names = {n.lower(): n for n in os.listdir(cur)}
        part = names.get(part.lower(), part)
        out.append(part)
        cur = os.path.join(cur, part)
    return "/".join(out)


def missing_models(props_dir, props, refs):
    """BVH-referenced models with no STL at all (not in the exported pak), case-insensitively unique"""
    out = {}
    for pi in refs:
        name = props[pi]["model"]
        if model_files(props_dir, name) == (None, None):
            out.setdefault(name.lower(), name)
    return sorted(out.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lumps", required=True)
    ap.add_argument("--props", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--world-stl", action="store_true", help="also write all placed movement collision as one world-space STL (large)")
    ap.add_argument("--obj", action="store_true", help="also write a merged OBJ (large)")
    ap.add_argument("--deliver", help="copy <name>.stl / <name>_d1.stl of every BVH-referenced model into this dir")
    args = ap.parse_args()

    m = args.map
    sprp_ver, props, refs, origin, qscale = load_map(args.lumps, m)

    os.makedirs(args.out, exist_ok=True)
    obj_path = os.path.join(args.out, f"{m}_props_collision.obj")
    stl_path = os.path.join(args.out, f"{m}_props_collision.stl")
    csv_path = os.path.join(args.out, f"{m}_props_instances.csv")

    tri_cache = {}
    vert_cache = {}

    def tris_of(rel):
        if rel not in tri_cache:
            tri_cache[rel] = load_stl(os.path.join(args.props, rel.replace("/", os.sep)))
        return tri_cache[rel]

    def verts_of(rel):
        if rel not in vert_cache:
            vert_cache[rel] = list({t[k * 3:k * 3 + 3] for t in tris_of(rel) for k in range(3)})
        return vert_cache[rel]

    used = set()
    total_tris = 0
    vbase = 1
    errs = collections.defaultdict(list)
    no_d0 = collections.Counter()
    rows = []
    obj = open(obj_path, "w", newline="\n") if args.obj else None
    stl = open(stl_path, "wb") if args.world_stl else None
    if obj:
        obj.write(f"# {m} static prop movement collision, world space (Z up). sprp v{sprp_ver}, {len(refs)} BVH props\n")
    if stl:
        stl.write(b"\0" * 80 + struct.pack("<I", 0))
    for pi, p in enumerate(props):
        ref = refs.get(pi)
        f0, f1 = model_files(args.props, p["model"])
        detail1 = bool(ref and ref["dword"] & LEAF_DETAIL1)
        # movement collision: bit 31 -> detail 1 (same part as detail 0 when there is no _d1 file), else detail 0
        rel = (f1 or f0) if detail1 else f0
        row = {
            "index": pi, "model": p["model"], "in_bvh": int(ref is not None), "has_stl": int(rel is not None),
            "solid": p["solid"], "flags": p["flags"],
            "contents": f"0x{ref['contents']:08X}" if ref else "",
            "leaf_dword": f"0x{ref['dword']:08X}" if ref else "",
            "ox": p["origin"][0], "oy": p["origin"][1], "oz": p["origin"][2],
            "pitch": p["angles"][0], "yaw": p["angles"][1], "roll": p["angles"][2], "scale": p["scale"],
            "tris": 0, "bounds_err": "",
        }
        rows.append(row)
        if ref is None:
            continue
        M = angle_matrix(p["angles"])
        o, s = p["origin"], p["scale"]

        def xf(v):
            return tuple(o[j] + s * (M[j][0] * v[0] + M[j][1] * v[1] + M[j][2] * v[2]) for j in range(3))

        # node bounds span detail 1 for bit-31 props, detail 0 + detail 1 for the others
        span = [x for x in ([rel] if detail1 else [f0, f1]) if x]
        if ref["bounds"] is not None and span:
            lo = [1e30] * 3
            hi = [-1e30] * 3
            for x in span:
                for v in verts_of(x):
                    w = xf(v)
                    for j in range(3):
                        lo[j] = min(lo[j], w[j])
                        hi[j] = max(hi[j], w[j])
            e = max(max(abs(origin[j] + ref["bounds"][j][0] * qscale - lo[j]),
                        abs(origin[j] + ref["bounds"][j][1] * qscale - hi[j])) for j in range(3))
            row["bounds_err"] = round(e, 2)
            errs["bit31 vs d1" if detail1 else "other vs d0+d1"].append(e)
        if rel is None:
            if f1:
                no_d0[p["model"].lower()] += 1  # model has no detail 0 part: no movement collision
            continue
        used.add(rel)
        tris = tris_of(rel)
        row["tris"] = len(tris)
        total_tris += len(tris)
        if not (stl or obj):
            continue
        if obj:
            obj.write(f"o p{pi}_{os.path.basename(p['model']).rsplit('.', 1)[0]}\n")
        out_tris = bytearray()
        lines = []
        for t in tris:
            wv = [xf(t[k * 3:k * 3 + 3]) for k in range(3)]
            if obj:
                lines += [f"v {w[0]:.3f} {w[1]:.3f} {w[2]:.3f}\n" for w in wv]
                lines.append(f"f {vbase} {vbase + 1} {vbase + 2}\n")
            vbase += 3
            if stl:
                out_tris += struct.pack("<12fH", 0, 0, 0, *wv[0], *wv[1], *wv[2], 0)
        if obj:
            obj.write("".join(lines))
        if stl:
            stl.write(out_tris)
    if stl:
        stl.seek(80)
        stl.write(struct.pack("<I", total_tris))
        stl.close()
    if obj:
        obj.close()

    with open(csv_path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    missing = missing_models(args.props, props, refs)
    placed = sum(1 for r in rows if r["tris"])
    print(f"sprp v{sprp_ver}: {len(props)} instances, {len(set(p['model'] for p in props))} models, bvh origin {origin}, node bounds scale {qscale:g}")
    print(f"BVH static prop refs: {len(refs)} (bit 31 / detail 1: {sum(1 for r in refs.values() if r['dword'] & LEAF_DETAIL1)})")
    print(f"movement collision: {placed} instances, {total_tris} triangles, {len(used)} STLs; "
          f"{sum(no_d0.values())} instances of {len(no_d0)} models without a detail 0 part (no movement collision)")
    for k, e in sorted(errs.items()):
        e.sort()

        def q(f):
            return e[min(len(e) - 1, int(len(e) * f))]
        print(f"  bounds_err {k}: {len(e)} checked, median {q(0.5):.1f}  p95 {q(0.95):.1f}  p99 {q(0.99):.1f}  "
              f"max {e[-1]:.1f}  (>{1.5 * qscale:g}: {sum(1 for x in e if x > 1.5 * qscale)})")
    if missing:
        print(f"BVH-referenced models with no STL ({len(missing)}), export them from the shared paks:")
        for name in missing:
            print(f"  {name}")
    if args.deliver:
        # both detail levels of every BVH-referenced model
        # (sprp can name one model twice with different case, e.g. pelican_case_large_drabGreen / _drabgreen)
        ship = {}
        for pi in refs:
            for rel in model_files(args.props, props[pi]["model"]):
                if rel:
                    ship.setdefault(rel.lower(), disk_case(args.props, rel))
        size = 0
        for rel in sorted(ship.values()):
            dst = os.path.join(args.deliver, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(args.props, rel.replace("/", os.sep)), dst)
            size += os.path.getsize(dst)
        extra = []
        for dp, _, fs in os.walk(args.deliver):
            for fn in fs:
                rel = os.path.relpath(os.path.join(dp, fn), args.deliver).replace(os.sep, "/")
                if rel.lower() not in ship:
                    extra.append(rel)
        n1 = sum(1 for r in ship if r.endswith("_d1.stl"))
        print(f"delivered {len(ship)} STLs ({len(ship) - n1} detail 0, {n1} detail 1, {size} bytes) to {args.deliver}"
              + (f"; {len(extra)} other files already there, e.g. {extra[:3]}" if extra else ""))
    if args.obj:
        print("wrote", obj_path, os.path.getsize(obj_path))
    if args.world_stl:
        print("wrote", stl_path, os.path.getsize(stl_path))
    print("wrote", csv_path)


if __name__ == "__main__":
    main()
