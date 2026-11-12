#pragma once
#include <game/rtech/cpakfile.h>

// Layouts match the engine's KVValue_s / KVGroup_s / WeaponAssetHeader (r5 kv.cpp).
enum WepnValueType_t : uint32_t
{
	INTEGER = 0,
	FLT = 1,
	STRING = 2,
};

union WepnValue_u
{
	const char* strVal;
	int64_t intVal; // engine reads this as __int64 (KVGroup_GetInt)
	float fltVal;

	uint64_t rawVal;
};

struct WepnKeyValue_v1_t
{
	const char* key;
	uint32_t keyHash;   // lookup key, values are binary searched by this hash via WepnData_v1_t::valueOrder
	uint32_t valueType; // WepnValueType_t
	WepnValue_u value;
};
static_assert(sizeof(WepnKeyValue_v1_t) == 24);

struct WepnData_v1_t
{
	const char* name;
	uint32_t keyHash;
	uint16_t numValues;
	uint16_t numChildren;
	WepnKeyValue_v1_t* childKVPairs; // 24 bytes per numValues, stored in source order
	WepnData_v1_t* childObjects;     // 48 bytes per numChildren, stored in source order

	// Indices into childKVPairs / childObjects sorted by keyHash, used by the engine to binary
	// search a key (KVGroup_GetValue). Not part of the file contents.
	uint16_t* valueOrder;
	uint16_t* childOrder;
};
static_assert(sizeof(WepnData_v1_t) == 48);

struct WepnAssetHeader_v1_t
{
	const char* weaponName;
	WepnData_v1_t* rootKey;

	WepnData_v1_t* rootKeyBackup; // engine "rootGroupBackup", mostly null
	void** assetRefs;
};
static_assert(sizeof(WepnAssetHeader_v1_t) == 32);

class WeaponAsset
{
public:
	WeaponAsset() = default;
};
