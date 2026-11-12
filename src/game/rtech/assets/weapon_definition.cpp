#include "pch.h"
#include <game/rtech/assets/weapon_definition.h>

extern RSXSettings_t g_rsxSettings;

void LoadWeaponDefinitionAsset(CAssetContainer* const pak, CAsset* const asset)
{
    UNUSED(pak);
    UNUSED(asset);

    CPakAsset* pakAsset = static_cast<CPakAsset*>(asset);
    const WepnAssetHeader_v1_t* const header = reinterpret_cast<const WepnAssetHeader_v1_t* const>(pakAsset->header());

    const std::string assetName = "weapon/" + std::string(header->weaponName) + ".rpak";
    pakAsset->SetAssetName(assetName);
}

// Escape only what would break the "key" "value" line. Backslashes are left alone: values such as
// sourceFilename ("game\r2\scripts\weapons\...") are stored with literal backslashes.
static std::string Wepn_EscapeString(const char* const str)
{
    std::string out;

    for (const char* c = str; *c; ++c)
    {
        switch (*c)
        {
        case '"':  out += "\\\""; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        default:   out += *c; break;
        }
    }

    return out;
}

// Shortest text that round-trips to the same float, always keeping a '.' or exponent so the
// value is not mistaken for an integer when the file is read back.
static std::string Wepn_FormatFloat(const float value)
{
    std::string out = std::format("{}", value);

    if (out.find_first_of(".eEn") == std::string::npos) // 'n' covers inf/nan
        out += ".0";

    return out;
}

std::string R_GetWeaponDefinitionAsString(const WepnData_v1_t* const key, const std::string& indentStr)
{
    std::string retVal = indentStr + "\"" + Wepn_EscapeString(key->name) + "\"\n" + indentStr + "{\n";

    // first loop over child values (stored in source order; valueOrder is only the hash lookup)
    for (int j = 0; j < key->numValues; ++j)
    {
        WepnKeyValue_v1_t* val = &key->childKVPairs[j];
        retVal += indentStr + "\t\"" + Wepn_EscapeString(val->key) + "\" \"";

        if (val->valueType == WepnValueType_t::STRING)
            retVal += Wepn_EscapeString(val->value.strVal);
        else if (val->valueType == WepnValueType_t::INTEGER)
            retVal += std::to_string(val->value.intVal);
        else if (val->valueType == WepnValueType_t::FLT)
            retVal += Wepn_FormatFloat(val->value.fltVal);
        else
        {
            retVal += "unk\" // " + std::string(val->key) + ": unknown type " + std::to_string(val->valueType) + ", rawval: " + std::format("{:X}", val->value.rawVal) + "\n";
            Log("WEPN: unknown var type: %s (type %i): %llX\n", val->key, val->valueType, val->value.rawVal);
            continue;
        }
        retVal += "\"\n";
    }

    // add a newline to separate the values and the objects
    retVal += "\n";

    // then loop over child objects
    for (int i = 0; i < key->numChildren; ++i)
    {
        WepnData_v1_t* childKey = &key->childObjects[i];

        retVal += R_GetWeaponDefinitionAsString(childKey, indentStr + "\t");

        if (i != key->numChildren - 1)
            retVal += "\n"; // as long as we aren't the last child object, add a new line as a separator
    }

    retVal += indentStr + "}\n";

    return retVal;
}

bool ExportWeaponDefinitionAsset(CAsset* const asset, const int setting)
{
    UNUSED(asset);
    UNUSED(setting);

    CPakAsset* pakAsset = static_cast<CPakAsset*>(asset);
    const WepnAssetHeader_v1_t* const header = reinterpret_cast<WepnAssetHeader_v1_t* const>(pakAsset->header());
    
    const std::string wepnTxt = R_GetWeaponDefinitionAsString(header->rootKey, "");

    // Create exported path + asset path.
    std::filesystem::path exportPath = g_rsxSettings.GetExportDirectory();
    const std::filesystem::path wepnPath(asset->GetAssetName());

    if (g_rsxSettings.exportPathsFull)
        exportPath.append(wepnPath.parent_path().string());
    else
        exportPath.append("weapon");

    if (!CreateDirectories(exportPath))
    {
        assertm(false, "Failed to create asset directory.");
        return false;
    }

    exportPath.append(wepnPath.filename().string());
    exportPath.replace_extension(".txt");

    StreamIO out;
    if (!out.open(exportPath.string(), eStreamIOMode::Write))
    {
        assertm(false, "Failed to open file for write.");
        return false;
    }

    out.write(wepnTxt.c_str(), wepnTxt.length());
    out.close();

    return true;
}

void InitWeaponDefinitionAssetType()
{
    static const char* settings[] = { "TXT" };
    AssetTypeBinding_t type =
    {
        .name = "Weapon Definition",
        .type = 'npew',
        .headerAlignment = 8,
        .loadFunc = LoadWeaponDefinitionAsset,
        .postLoadFunc = nullptr,
        .previewFunc = nullptr,
        .e = { ExportWeaponDefinitionAsset, 0, settings, ARRSIZE(settings) },
    };

    REGISTER_TYPE(type);
}