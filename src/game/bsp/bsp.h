#pragma once
#include <game/asset.h>

#include "entities.h"
#include "bvh.h"

// todo
//class CBSPFile : public CAssetContainer
//{
//
//};

constexpr uint8_t NUM_BSP_LUMPS = 0x80;

struct lump_t
{
	int fileofs;
	int filelen;
	int version;
	int uncompLen;
};

struct BSPHeader_t
{
	int ident; // rBSP
	uint16_t version;
	uint16_t flags; // surely flags and not just a bool right?
	int mapRevision;
	int lastLump;

	lump_t lumps[NUM_BSP_LUMPS];
};

// vertex type flags
#define MESH_VERTEX_LIT_FLAT 0x000
#define MESH_VERTEX_LIT_BUMP 0x200
#define MESH_VERTEX_UNLIT    0x400
#define MESH_VERTEX_UNLIT_TS 0x600

// structs are all based on apex for now
// eventually these should be split into different versions
struct dmodel_t
{
	Vector mins;
	Vector maxs;
	int firstMesh;
	int meshCount;

	// collision (engine CollisionBSPData_ConvertArray<dmodel_t, CollBvh4_s>)
	uint32_t bvhNode;    // first node in LUMP_BVH_NODES, child node indices are relative to it
	uint32_t bvhLeaf;    // first dword in LUMP_BVH_LEAF_DATA, leaf indices are relative to it
	uint32_t vertIndex;  // first vertex in LUMP_VERTEXES, or in LUMP_PACKED_VERTICES when (bvhFlags & 1)
	uint32_t bvhFlags;   // bit 0: this model's verts are packed (int16) instead of float3
	Vector origin;       // decode origin for node bounds and packed verts
	float decodeScale;   // world = origin + float(q << 16) * decodeScale
};
static_assert(sizeof(dmodel_t) == 64);

struct dmaterialsort_t
{
	short texdata;
	short lmapIdx;
	short cubemapIdx;
	short lastVtxOfs;
	int firstVertex;
};

struct dtexdata_t
{
	int nameStringTableID;
	int width;
	int height;
	int flags;
};

struct dmesh_t
{
	int firstIdx;
	short triCount;
	short firstVtxRel;
	short lastVtxOfs;
	char vtxType;
	char unused_0;
	char lightStyles[4];
	short luxelOrg[2];
	char luxelOfsMax[2];
	short mtlSortIdx;
	int flags;
};

struct dportal_t
{
	bool isReversed;
	char type;
	char numRefs;
	char padding;

	short firstRef;
	short cell;
	int plane;
};

class CPakAsset;
class CDXDrawData;
struct ID3D11ShaderResourceView;
struct ID3D11Buffer;

class CBSPData
{
public:
	CBSPData(std::string name) : 
		m_mapName(name), m_drawData(nullptr),
		m_vertPositionsBuffer(nullptr), m_vertNormalsBuffer(nullptr),
		m_vertPositionsSRV(nullptr), m_vertNormalsSRV(nullptr),
		envEntitiesKV(), scriptEntitiesKV()
	{};

	~CBSPData();

	void PopulateFromPakAsset(CPakAsset* pakAsset, void* bspData);

	CDXDrawData* ConstructPreviewData();

	// Writes the render geometry as OBJ. Returns false (and writes nothing) when a lump it needs
	// is missing or failed to decode, e.g. when only one of the _client_perm/_client_temp paks is loaded.
	bool Export(std::ofstream* out);

	bool HasLumpData(int lumpId) const
	{
		const auto it = m_lumpData.find(static_cast<uint8_t>(lumpId));
		return it != m_lumpData.end() && it->second != nullptr;
	}

	const std::shared_ptr<char[]> GetLumpData(int lumpId) const
	{
		if (!m_lumpData.contains(static_cast<uint8_t>(lumpId)))
		{
			Log("WARNING: BSP for map \"%s\" attempted to use lump %04x but no such data exists.\n", m_mapName.c_str(), lumpId);
			
			return nullptr;
		}

		return m_lumpData.at(static_cast<uint8_t>(lumpId));
	}

	uint32_t GetLumpSize(int lumpId)
	{
		if (!m_lumpSizes.contains(static_cast<uint8_t>(lumpId)))
		{
			//Log("WARNING: BSP for map \"%s\" attempted to get size for lump %04x but no such lump exists.\n", m_mapName.c_str(), lumpId);

			return 0;
		}

		return m_lumpSizes.at(static_cast<uint8_t>(lumpId));
	}

	void SetLumpData(uint8_t lumpId, std::shared_ptr<char[]> data)
	{
		// this isn't a terrible condition to hit but it's most likely indicative of problems elsewhere
		assert(!m_lumpData.contains(lumpId));

		m_lumpData[lumpId] = data;
	}

	int GetVersion() const { return m_version; };

	void SetVersion(int version) { m_version = version; };

private:

	void CreateOrUpdatePreviewStructuredBuffers();
	std::unordered_map<int, uint32_t> ParseModelFlagsFromEntities() const;

private:
	std::string m_mapName;
	std::unordered_map<uint8_t, std::shared_ptr<char[]>> m_lumpData;
	std::unordered_map<uint8_t, uint32_t> m_lumpSizes;

	CDXDrawData* m_drawData;

	int m_version;

	struct {
		int numModels;
		int numMeshes;

		int numVertPositions;
		int numVertNormals;
	} l;

	ID3D11Buffer* m_vertPositionsBuffer;
	ID3D11Buffer* m_vertNormalsBuffer;

	ID3D11ShaderResourceView* m_vertPositionsSRV;
	ID3D11ShaderResourceView* m_vertNormalsSRV;

	std::vector<BSPEntity_s> envEntitiesKV;
	std::vector<BSPEntity_s> scriptEntitiesKV;

	bool hasEntities_env;
	bool hasEntities_script;
};
