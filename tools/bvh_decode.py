"""Decode Respawn collision BVH4 data the way the engine does (r5 CollBvh_VisitLeafs,
CollPoly_Visit_5/7, CollHeightfield_PatchIter; layouts checked against v3.0.1.30).

World collision lumps (<bsp>.bsp.<LLLL>.client.bsp_lump):
  0003 float3 vertices            0014 packed vertices (int16 x3)
  000E dmodel_t[] (64 bytes)      0010 contents masks (u32)
  0012 nodes (64 bytes)           0013 leaf data (u32 stream)
  0015 heightfields (40 bytes)    0016 heightfield height samples (u8)

dmodel_t: mins(12) maxs(12) firstMesh meshCount | bvhNode bvhLeaf vertIndex bvhFlags | origin(12) decodeScale
  node/leaf indices of a model are relative to its bvhNode / bvhLeaf; bvhFlags bit 0 = the model's
  verts are the packed array (else float3), starting at vertIndex.

Node (64 bytes): int16 minMax[3 axes][min x4, max x4], then 4 u32:
  [0] low byte = contents mask index, >> 8 = child 0 index
  [1] >> 8 = child 1 index, [2] low nibble/high nibble of byte 0 = child 0/1 type, >> 8 = child 2 index
  [3] byte 0 nibbles = child 2/3 type, >> 8 = child 3 index
  bound/packed vertex decode: origin + float(q << 16) * decodeScale   (q is signed int16)

Child types: 0 node, 1 empty, 2 skipped, 3 bundle, 4 tri (float3), 5 tri (packed), 6 quad (float3),
7 quad (packed), 8 convex hull, 9 static prop, 10 heightfield patch (worldspawn only).
"""
import os
import struct

NODE, NO_CHILD, SKIP, BUNDLE, TRI, TRI_PACKED, QUAD, QUAD_PACKED, HULL, STATIC_PROP, HEIGHTFIELD = range(11)
POLY_TYPES = (TRI, TRI_PACKED, QUAD, QUAD_PACKED, HULL, HEIGHTFIELD)

LUMP_VERTEXES = 0x03
LUMP_MODELS = 0x0E
LUMP_CONTENTS_MASKS = 0x10
LUMP_BVH_NODES = 0x12
LUMP_BVH_LEAF_DATA = 0x13
LUMP_PACKED_VERTICES = 0x14
LUMP_HEIGHTFIELDS = 0x15
LUMP_HEIGHTFIELD_HEIGHTS = 0x16


def lump_path(lumps, bsp, i):
    return os.path.join(lumps, f"{bsp}.bsp.{i:04X}.client.bsp_lump")


def read_lump(lumps, bsp, i, required=True):
    p = lump_path(lumps, bsp, i)
    if not os.path.exists(p):
        if required:
            raise FileNotFoundError(p)
        return b""
    with open(p, "rb") as f:
        return f.read()


def parse_dmodel(md, i):
    o = i * 64
    return {
        "mins": struct.unpack_from("<3f", md, o),
        "maxs": struct.unpack_from("<3f", md, o + 12),
        "bvhNode": struct.unpack_from("<I", md, o + 32)[0],
        "bvhLeaf": struct.unpack_from("<I", md, o + 36)[0],
        "vertIndex": struct.unpack_from("<I", md, o + 40)[0],
        "bvhFlags": struct.unpack_from("<I", md, o + 44)[0],
        "origin": struct.unpack_from("<3f", md, o + 48),
        "decodeScale": struct.unpack_from("<f", md, o + 60)[0],
    }


class World:
    """All collision lumps of one bsp plus helpers to walk a brush model's BVH."""

    def __init__(self, lumps, bsp):
        self.bsp = bsp
        md = read_lump(lumps, bsp, LUMP_MODELS)
        self.models = [parse_dmodel(md, i) for i in range(len(md) // 64)]
        self.nodes = read_lump(lumps, bsp, LUMP_BVH_NODES)
        self.leafs = read_lump(lumps, bsp, LUMP_BVH_LEAF_DATA)
        masks = read_lump(lumps, bsp, LUMP_CONTENTS_MASKS)
        self.masks = struct.unpack_from(f"<{len(masks) // 4}I", masks)
        fv = read_lump(lumps, bsp, LUMP_VERTEXES, required=False)
        self.fverts = struct.unpack_from(f"<{len(fv) // 4}f", fv) if fv else ()
        pv = read_lump(lumps, bsp, LUMP_PACKED_VERTICES, required=False)
        self.pverts = struct.unpack_from(f"<{len(pv) // 2}h", pv) if pv else ()
        hf = read_lump(lumps, bsp, LUMP_HEIGHTFIELDS, required=False)
        heights = read_lump(lumps, bsp, LUMP_HEIGHTFIELD_HEIGHTS, required=False)
        # the engine hands each heightfield the next heightCount samples, in lump order
        self.heightfields = []
        pos = 0
        for i in range(len(hf) // 40):
            o = i * 40
            count = struct.unpack_from("<I", hf, o + 28)[0]
            self.heightfields.append({
                "origin": struct.unpack_from("<3f", hf, o),
                "scale": struct.unpack_from("<3f", hf, o + 12),
                "dims": struct.unpack_from("<2H", hf, o + 24),
                "heights": heights[pos:pos + count],
            })
            pos += count

    def u32(self, i):
        return struct.unpack_from("<I", self.leafs, i * 4)[0]

    def node(self, model, k):
        """(axes int16[24], child indices[4], child types[4], contents mask) of node k of a model"""
        off = (self.models[model]["bvhNode"] + k) * 64
        ax = struct.unpack_from("<24h", self.nodes, off)
        w = struct.unpack_from("<4I", self.nodes, off + 48)
        idx = (w[0] >> 8, w[1] >> 8, w[2] >> 8, w[3] >> 8)
        ty = (w[2] & 0xF, (w[2] >> 4) & 0xF, w[3] & 0xF, (w[3] >> 4) & 0xF)
        return ax, idx, ty, self.masks[w[0] & 0xFF] if self.masks else 0

    def child_bounds(self, model, ax, c):
        m = self.models[model]
        step = m["decodeScale"] * 65536.0
        lo = tuple(m["origin"][a] + ax[a * 8 + c] * step for a in range(3))
        hi = tuple(m["origin"][a] + ax[a * 8 + 4 + c] * step for a in range(3))
        return lo, hi

    def decode_child(self, model, ty, leaf, on_tri, stats=None, only=None):
        """emit every triangle of one leaf child (leaf = index relative to the model's bvhLeaf).
        on_tri((p0, p1, p2), is_hole) receives world-space float tuples. only: set of child types
        to decode (bundles are always opened), None = all."""
        m = self.models[model]
        base = m["bvhLeaf"] + leaf
        if stats is not None:
            stats[ty] = stats.get(ty, 0) + 1
        if ty == BUNDLE:
            cnt = self.u32(base)
            o = 1 + cnt
            for s in range(cnt):
                _cm, sub_ty, length = struct.unpack_from("<BBH", self.leafs, (base + 1 + s) * 4)
                self.decode_child(model, sub_ty, leaf + o, on_tri, stats, only)
                o += length
        elif only is not None and ty not in only:
            return
        elif ty in (TRI, QUAD):
            self._polys(base, ty, self._float_vert(m), on_tri)
        elif ty in (TRI_PACKED, QUAD_PACKED):
            self._polys(base, ty, self._packed_vert(m, m["origin"], m["decodeScale"]), on_tri)
        elif ty == HULL:
            self._hull(base, on_tri)
        elif ty == HEIGHTFIELD:
            self._heightfield(base, on_tri)
        # NODE/NO_CHILD/SKIP/STATIC_PROP carry no triangles of their own

    def _float_vert(self, m):
        fv, vb = self.fverts, m["vertIndex"]
        return lambda i: (fv[(vb + i) * 3], fv[(vb + i) * 3 + 1], fv[(vb + i) * 3 + 2])

    def _packed_vert(self, m, origin, scale, src=None, vb=None):
        pv = self.pverts if src is None else src
        vb = m["vertIndex"] if vb is None else vb
        step = scale * 65536.0
        return lambda i: tuple(origin[a] + pv[(vb + i) * 3 + a] * step for a in range(3))

    def _polys(self, dw, ty, vert, on_tri):
        """one poly list (types 4-7) starting at absolute dword dw; returns dwords used"""
        hdr = self.u32(dw)
        count = ((hdr >> 12) & 0xF) + 1
        v = (hdr >> 16) << 10
        for i in range(count):
            t = self.u32(dw + 1 + i)
            if ty in (TRI, TRI_PACKED):
                v += t & 0x7FF
                on_tri((vert(v), vert(v + 1 + ((t >> 11) & 0x1FF)), vert(v + 1 + ((t >> 20) & 0x1FF))), False)
            else:
                # engine quad: p0, p1 = v+1+b, p3 = v+1+c, p2 = p1 - p0 + p3
                v += t & 0x3FF
                p0, p1, p3 = vert(v), vert(v + 1 + ((t >> 10) & 0x1FF)), vert(v + 1 + ((t >> 19) & 0x1FF))
                p2 = tuple(p1[a] - p0[a] + p3[a] for a in range(3))
                on_tri((p0, p1, p2), False)
                on_tri((p0, p2, p3), False)
        return 1 + count

    def _hull(self, dw, on_tri):
        """type 8: u8 vertCount, faceCount, triLists, quadLists, float3 origin, float decodeScale (20 bytes),
        packed verts, 3 bytes per face, then (aligned to 4) the packed tri lists followed by the quad lists"""
        b = dw * 4
        vc, fc, tl, ql = struct.unpack_from("<4B", self.leafs, b)
        origin = struct.unpack_from("<3f", self.leafs, b + 4)
        scale = struct.unpack_from("<f", self.leafs, b + 16)[0]
        verts = struct.unpack_from(f"<{vc * 3}h", self.leafs, b + 20)
        vert = self._packed_vert(None, origin, scale, src=verts, vb=0)
        p = dw + (20 + 6 * vc + 3 * fc + 3) // 4
        for _ in range(tl):
            p += self._polys(p, TRI_PACKED, vert, on_tri)
        for _ in range(ql):
            p += self._polys(p, QUAD_PACKED, vert, on_tri)

    def _heightfield(self, dw, on_tri):
        """type 10 (CollLeafHeightfieldPatch_s, 40 bytes): u16 coord[2], u8 dims[2], u8 (bit 0
        triangulateTopToBottom, bits 1-7 heightfield index), u8 quadsPerPlane, float maxVerticalError,
        u32 heightDataOffset, float heightBias, float heightScale, u64 surfProp RLE bits, u16 surfProps[4].
        Port of CollHeightfield_PatchIter base polys (no skirts). Sample 0 = hole."""
        b = dw * 4
        cx, cy, dx_n, dy_n, bits, qpp = struct.unpack_from("<2H2BBB", self.leafs, b)
        off = struct.unpack_from("<I", self.leafs, b + 12)[0]
        bias, hscale = struct.unpack_from("<2f", self.leafs, b + 16)
        if (bits >> 1) >= len(self.heightfields):
            return
        h = self.heightfields[bits >> 1]
        hs = h["heights"]
        planes_x = (dx_n - 1) // qpp
        planes_y = (dy_n - 1) // qpp
        spr = planes_x + 1
        sx, sy = qpp * h["scale"][0], qpp * h["scale"][1]
        ox = cx * h["scale"][0] + h["origin"][0]
        oy = cy * h["scale"][1] + h["origin"][1]

        def sample(i):
            return hs[i] if i < len(hs) else 0

        def z(i):
            v = sample(i)
            return 0.0 if v == 0 else (v - 1) * hscale + bias

        def row_hole(i):
            # (bottom or top sample is a hole) << (bottom sample is a hole), as in the engine
            return int(sample(i) == 0 or sample(i + spr) == 0) << int(sample(i) == 0)

        # literal port of the iterator: a triangle strip per row, P0 = gridPos[0], P2 = gridPos[1],
        # the new vertex P1 alternates between the bottom row and the top row
        s = off
        gp0 = (ox, oy, z(s))
        gp1 = (ox, oy + sy, z(s + spr))
        hole = row_hole(s)
        s += 1
        side = bits & 1  # triangulateTopToBottom: start with the bottom-right vertex
        tris_per_row = 2 * planes_x
        row = 0
        for poly in range(planes_y * tris_per_row):
            i = s if side else s + spr
            g = gp0 if side else gp1
            new = (g[0] + sx, g[1], z(i))
            if sample(i) == 0:
                hole |= 3
            on_tri((gp0, new, gp1), hole != 0)
            hole = hole - 1 if hole else 0
            s += poly & 1
            if side:
                gp0 = new
            else:
                gp1 = new
            side ^= 1
            if poly + 1 == tris_per_row * (row + 1) and row + 1 < planes_y:
                gp0 = (ox, gp0[1] + sy, z(s))
                gp1 = (ox, gp1[1] + sy, z(s + spr))
                hole = row_hole(s)
                row += 1
                s += 1

    def walk(self, model, on_child):
        """depth-first over a model's tree; on_child(ax, c, ty, idx, contents) -> False prunes a node child"""
        stack, seen = [0], set()
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            ax, idx, ty, cm = self.node(model, k)
            for c in range(4):
                if ty[c] in (NO_CHILD, SKIP):
                    continue
                if on_child(ax, c, ty[c], idx[c], cm) is False:
                    continue
                if ty[c] == NODE:
                    stack.append(idx[c])
        return len(seen)


def write_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b"\0" * 80 + struct.pack("<I", len(tris)))
        for t in tris:
            f.write(struct.pack("<12fH", 0, 0, 0, *t[0], *t[1], *t[2], 0))
