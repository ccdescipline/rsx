#pragma once

// Per axis the node stores the four children's mins first, then their four maxs
// (engine CollBvh4Node_s minMax[axis][2][4]); decode = origin + float(q << 16) * decodeScale.
struct dbvhaxis_t
{
	short minChild[4];
	short maxChild[4];
};
static_assert(sizeof(dbvhaxis_t) == 16);

enum dbvhchildtype_e
{
	NODE,
	NO_CHILD,
	INVALID = 2,
	UNK_3,
	PRIM_TRI,         // triangle primitive using float3 verts
	PRIM_TRI_PACKED,  // triangle primitive using int16 verts (CollPackedPos_s), see dmodel bvhFlags bit 0
	PRIM_QUAD,        // quad primitive using float3 verts
	PRIM_QUAD_PACKED, // quad primitive using int16 verts (CollPackedPos_s)
	UNK_8,            // convex hull: own origin/decodeScale + packed verts, then tri/quad lists
	STATIC_PROP,      // dword: prop index in bits 0-23, bit 31 forces collision detail 1
	HEIGHTFIELD,      // CollLeafHeightfieldPatch_s, worldspawn only, data in lumps 0x15/0x16
};

struct dbvhleaf_poly_t
{
	uint32_t unk : 12;
	uint32_t polyCount : 4; // +1
	uint32_t baseVertexOffset : 16; // used when the leaf refers to verts beyond an index of 1024
};

// type 3 elements
struct dbvhsubleaf_t
{
	uint8_t cmIndex;
	uint8_t primitiveType;
	uint16_t length; // in dwords
};

// type 8 leaf
struct dbvhtype8_t
{
	uint8_t vertexCount;
	uint8_t faceCount;
	uint8_t triCount;
	uint8_t quadCount;
	Vector origin;
	float decodeScale;
};

struct dbvhtri_t
{
	uint32_t vertAIndex : 11;
	uint32_t vertBIndex : 9;
	uint32_t vertCIndex : 9;
	uint32_t edgeMask : 3;
};


struct dbvhquad_t
{
	uint32_t vertAIndex : 10;
	uint32_t vertBIndex : 9;
	uint32_t vertCIndex : 9;
	uint32_t edgeMask : 4;
};

// LUMP_BVH_NODES (18 - 0x0012)
struct dbvhnode_t
{
	dbvhaxis_t x;
	dbvhaxis_t y;
	dbvhaxis_t z;

	uint32_t cmIndex : 8; // 8-bit index into 32-bit collision mask array
	uint32_t index0 : 24;

	uint32_t pad : 8;
	uint32_t index1 : 24;

	uint32_t child0Type : 4;
	uint32_t child1Type : 4;
	uint32_t index2 : 24;

	uint32_t child2Type : 4;
	uint32_t child3Type : 4;
	uint32_t index3 : 24;
};
