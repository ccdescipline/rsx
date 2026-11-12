#pragma once
#include <game/vpk/vpk.h>

// Flags as used by the engine (WrappedFile_Load / WrappedFileSystem_Read):
#define WRAP_FLAG_FILE_IS_COMPRESSED	0x1   // Oodle stream: OodleLZ_Decompress(data, cmpSize, out, dcmpSize), whatever the sizes are.
#define WRAP_FLAG_FILE_IS_PERMANENT		0x4   // data lives in the pak page and is decoded into memory at load time.
#define WRAP_FLAG_FILE_IS_STREAMED		0x10  // data lives in the starpak at the asset's stream offset.
#define WRAP_FLAG_FILE_IS_DECODED		0x20  // runtime only: set after a permanent file was decoded.

struct WrapAssetHeader_v1_t
{
	uint32_t size;
	uint32_t unk_4; // never used and we don't wanna accidently make a large file if it is
	void* data;
};

// engine WrappedFile_s
struct WrapAssetHeader_v7_t
{
	char* path;      // fullPath
	void* data;      // fileData

	uint32_t hash;   // assetPathHash
	uint32_t cmpSize;
	uint32_t dcmpSize;

	uint16_t realmPos;    // offset of the VM/realm suffix (".client", ".server", ".ui") in path, == length without it
	uint16_t gamePathPos; // offset of the path after the first folder
	uint16_t fileNamePos;

	uint16_t flags;
	uint16_t alignment;   // allocation alignment of the decoded buffer
	uint8_t callbackIdx;
	uint8_t pad;
};
static_assert(sizeof(WrapAssetHeader_v7_t) == 40);



class WrapAsset
{
public:
	WrapAsset() = default;
	WrapAsset(WrapAssetHeader_v1_t* const hdr) : path(nullptr), data(hdr->data), cmpSize(hdr->size), dcmpSize(hdr->size), pathSize(0u), skipFirstFolderPos(0u),
		fileNamePos(0u), flags(0u), isCompressed(false), isStreamed(false), parsedData(nullptr), type(VPKFileType_e::UNKNOWN)
	{

	}
	WrapAsset(WrapAssetHeader_v7_t* const hdr) : path(hdr->path), data(hdr->data), cmpSize(hdr->cmpSize), dcmpSize(hdr->dcmpSize), pathSize(hdr->realmPos), skipFirstFolderPos(hdr->gamePathPos),
		fileNamePos(hdr->fileNamePos), flags(hdr->flags), parsedData(nullptr), type(VPKFileType_e::UNKNOWN)
	{
		// Same rule as the engine: the compressed flag alone decides. Small or incompressible
		// files can have cmpSize >= dcmpSize (Oodle stored blocks carry a header), Oodle still
		// decodes them; no size heuristic or manual header skip.
		isCompressed = (flags & WRAP_FLAG_FILE_IS_COMPRESSED) != 0;
		isStreamed = (flags & WRAP_FLAG_FILE_IS_STREAMED) != 0;
	};

	~WrapAsset();

	char* path;
	void* data;

	uint32_t cmpSize;
	uint32_t dcmpSize;

	uint16_t pathSize;           // engine realmPos: path length without the VM extension
	uint16_t skipFirstFolderPos; // engine gamePathPos
	uint16_t fileNamePos;

	uint16_t flags;
	//
	bool isCompressed;
	bool isStreamed;

	VPKFileType_e type;

	void* parsedData; // data class for something like 


	std::unique_ptr<char[]> rawData;
};