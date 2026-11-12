#include <pch.h>
#include <game/rtech/assets/wrap.h>
#include <game/rtech/cpakfile.h>
#include <game/rtech/utils/utils.h>
#include <game/bsp/bsp.h>
#include <thirdparty/imgui/imgui.h>
#include <thirdparty/imgui/misc/imgui_memory_editor.h>
#include <thirdparty/oodle/oodle2.h>

WrapAsset::~WrapAsset()
{
    if (type == VPKFileType_e::BSP && parsedData)
    {
        delete reinterpret_cast<CBSPData*>(parsedData);
        parsedData = nullptr;
    }
}

void LoadWrapAsset(CAssetContainer* const pak, CAsset* const asset)
{
    UNUSED(pak);
    CPakAsset* pakAsset = static_cast<CPakAsset*>(asset);
    WrapAsset* wrapAsset = nullptr;

    switch (pakAsset->version())
    {
    case 1:
    {
        WrapAssetHeader_v1_t* hdr = reinterpret_cast<WrapAssetHeader_v1_t*>(pakAsset->header());
        wrapAsset = new WrapAsset(hdr);
        break;
    }
    case 7:
    {
        WrapAssetHeader_v7_t* hdr = reinterpret_cast<WrapAssetHeader_v7_t*>(pakAsset->header());
        wrapAsset = new WrapAsset(hdr);
        break;
    }
    default:
    {
        assertm(false, "unaccounted asset version, will cause major issues!");
        return;
    }
    }

    if (wrapAsset->path)
    {
        const std::string name = std::string(wrapAsset->path + wrapAsset->skipFirstFolderPos);
        pakAsset->SetAssetName(name, true);
    }

    pakAsset->setExtraData(wrapAsset);
}


static std::unique_ptr<char[]> GetStreamedDataForWrapAsset(CPakAsset* const asset, const uint32_t size)
{
    // engine: FS_ReadAsyncFile(streamHandle, streamOffset, size) - no header to skip
    AssetPtr_t streamEntry = asset->getStarPakStreamEntry(false);
    if (!IS_ASSET_PTR_INVALID(streamEntry))
        return asset->getStarPakData(streamEntry.offset, size, false);

    streamEntry = asset->getStarPakStreamEntry(true);
    if (!IS_ASSET_PTR_INVALID(streamEntry))
        return asset->getStarPakData(streamEntry.offset, size, true);

    return nullptr;
}

// Mirrors WrappedFile_Load / WrappedFileSystem_Read: read cmpSize (compressed) or dcmpSize (raw)
// bytes from the pak page or the starpak, then OodleLZ_Decompress when the compressed flag is set.
// Returns nullptr instead of a partially filled buffer when anything fails.
std::unique_ptr<char[]> GetWrapAssetData(CAsset* const asset, uint64_t* outSize)
{
    CPakAsset* pakAsset = static_cast<CPakAsset*>(asset);

    const WrapAsset* const wrapAsset = reinterpret_cast<WrapAsset*>(pakAsset->extraData());

    if (outSize)
        *outSize = 0;

    const uint32_t srcSize = wrapAsset->isCompressed ? wrapAsset->cmpSize : wrapAsset->dcmpSize;
    std::unique_ptr<char[]> srcData;

    if (wrapAsset->isStreamed)
    {
        srcData = GetStreamedDataForWrapAsset(pakAsset, srcSize);
    }
    else if (wrapAsset->data)
    {
        srcData = std::make_unique<char[]>(srcSize);
        memcpy_s(srcData.get(), srcSize, wrapAsset->data, srcSize);
    }

    if (!srcData)
    {
        Log("WRAP: no data for %s (flags 0x%X, cmp %u, dcmp %u, streamed %d)\n", asset->GetAssetName().c_str(),
            wrapAsset->flags, wrapAsset->cmpSize, wrapAsset->dcmpSize, wrapAsset->isStreamed);
        return nullptr;
    }

    if (!wrapAsset->isCompressed)
    {
        if (outSize)
            *outSize = wrapAsset->dcmpSize;

        return srcData;
    }

    std::unique_ptr<char[]> outData = std::make_unique<char[]>(wrapAsset->dcmpSize);
    const OO_SINTa decoded = OodleLZ_Decompress(srcData.get(), wrapAsset->cmpSize, outData.get(), wrapAsset->dcmpSize,
        OodleLZ_FuzzSafe_Yes, OodleLZ_CheckCRC_No, OodleLZ_Verbosity_None);

    if (decoded != static_cast<OO_SINTa>(wrapAsset->dcmpSize))
    {
        Log("WRAP: Oodle decode failed for %s (flags 0x%X, cmp %u, dcmp %u, got %lld)\n", asset->GetAssetName().c_str(),
            wrapAsset->flags, wrapAsset->cmpSize, wrapAsset->dcmpSize, static_cast<long long>(decoded));
        return nullptr;
    }

    if (outSize)
        *outSize = wrapAsset->dcmpSize;

    return outData;
}

// eugh
std::string Wrap_GetPathWithSwappedExtensions(const WrapAsset* const wrapAsset, const std::string& origAssetName)
{
    // size of the asset path excluding the first folder and the VM extension (ui, client, server)
    const uint64_t realPathSize = static_cast<uint64_t>(wrapAsset->pathSize) - wrapAsset->skipFirstFolderPos;

    if (origAssetName.length() == realPathSize)
        return origAssetName;

    const std::string vmExtension = origAssetName.substr(realPathSize);

    const std::string assetPathWithoutVMExt = origAssetName.substr(0, realPathSize);

    std::filesystem::path fsPath(assetPathWithoutVMExt);

    const std::string realExtension = fsPath.extension().string();

    fsPath.replace_extension(vmExtension);
    fsPath += realExtension;

    return fsPath.string();
}

// if there is a VM extension at the end of the file name, cut it off
// 
// usually, wrapAsset->pathSize will equal everything up until ".ui" or ".client"
// but the asset name already has the first folder cut off by this point, so we have to account for that in this check
inline void Wrap_StripVMExtensionFromPath(WrapAsset* const wrapAsset, std::string& assetPath)
{
    if (assetPath.length() != (wrapAsset->pathSize - wrapAsset->skipFirstFolderPos))
        assetPath = assetPath.substr(0, wrapAsset->pathSize - wrapAsset->skipFirstFolderPos);
}

void PostLoadWrapAsset(CAssetContainer* const pak, CAsset* const asset)
{
    UNUSED(pak);
    CPakAsset* pakAsset = static_cast<CPakAsset*>(asset);

    WrapAsset* const wrapAsset = reinterpret_cast<WrapAsset*>(pakAsset->extraData());

    // Default wrap asset type is "unknown"; basically if the file's extension isn't registered against a file type, it's previewed as binary data
    wrapAsset->type = VPKFileType_e::UNKNOWN;

    std::string assetName = asset->GetAssetName();
    
    Wrap_StripVMExtensionFromPath(wrapAsset, assetName);

    std::filesystem::path assetPath = std::filesystem::path(assetName);
    const std::string extension = assetPath.extension().string();

    // wrapped filesystem is the successor of vpk so we use VPK types, not the other way around
    if (auto it = s_vpkFileTypes.find(extension); it != s_vpkFileTypes.end())
        wrapAsset->type = it->second;

    switch (wrapAsset->type)
    {
    case VPKFileType_e::BSP:
    {
#if (HAS_BSP_SUPPORT)
        std::unique_ptr<char[]> wrapData = GetWrapAssetData(asset, nullptr);

        if (!wrapData)
            break;

        CBSPData* bspData = new CBSPData(assetPath.stem().string());
        bspData->PopulateFromPakAsset(pakAsset, wrapData.get());

        wrapAsset->parsedData = bspData;
#endif
        break;
    }
    }
}

bool ExportWrapAsset(CAsset* const asset, const int setting)
{
    UNUSED(setting);
    CPakAsset* pakAsset = static_cast<CPakAsset*>(asset);

    const WrapAsset* const wrapAsset = reinterpret_cast<WrapAsset*>(pakAsset->extraData());

    // Create exported path + asset path.
    std::filesystem::path exportPath = g_rsxSettings.GetExportDirectory() / fourCCToString(asset->GetAssetType());
    if (!CreateDirectories(exportPath))
    {
        assertm(false, "Failed to create asset type directory.");
        return false;
    }

    if (g_rsxSettings.useOrigScriptExportExtensions)
        exportPath.append(asset->GetAssetName());
    else
        exportPath.append(Wrap_GetPathWithSwappedExtensions(wrapAsset, asset->GetAssetName()));

    if (!CreateDirectories(exportPath.parent_path()))
    {
        assertm(false, "Failed to create export directory.");
        return false;
    }

    switch (wrapAsset->type)
    {
    case VPKFileType_e::UNKNOWN:
    case VPKFileType_e::TEXT:
#if !HAS_BSP_SUPPORT
    case VPKFileType_e::BSP:
#endif
    {
        StreamIO wrapOut;

        if (!wrapOut.open(exportPath.string(), eStreamIOMode::Write))
        {
            assertm(false, "Failed to open file for write.");
            return false;
        }

        uint64_t wrapOutSize = 0;
        std::unique_ptr<char[]> wrapData = GetWrapAssetData(asset, &wrapOutSize);

        if (!wrapData || wrapOutSize == 0)
            return false;

        // If the file has been detected as a text file and the last byte of the data is a null terminator, adjust the file size so we don't write it
        // In theory, the last byte will ALWAYS be a null byte, but it doesn't hurt to double check
        if (wrapAsset->type == VPKFileType_e::TEXT && wrapData[wrapOutSize - 1] == '\0')
            wrapOutSize--;

        wrapOut.write(wrapData.get(), wrapOutSize);
        wrapOut.close();
        break;
    }
#if (HAS_BSP_SUPPORT)
    case VPKFileType_e::BSP:
    {
        CBSPData* bspData = reinterpret_cast<CBSPData*>(wrapAsset->parsedData);

        // missing lumps (e.g. _client_temp not loaded) or a failed decode: skip this file only
        if (!bspData)
            return false;

        StreamIO wrapOut;

        if (!wrapOut.open(exportPath.string(), eStreamIOMode::Write))
        {
            assertm(false, "Failed to open file for write.");
            return false;
        }

        const bool exported = bspData->Export(wrapOut.W());

        wrapOut.close();

        if (!exported)
        {
            std::filesystem::remove(exportPath);
            return false;
        }

        break;
    }
#endif
    default:
    {
        unreachable();
        break;
    }
    }

    return true;
}

void* Wrap_PreviewTextOrBinary(CAsset* const asset, WrapAsset* const wrapAsset, const bool firstFrameForAsset)
{
    // this leaks memory
    if (firstFrameForAsset && !wrapAsset->rawData)
    {
        uint64_t wrapOutSize = 0;
        std::unique_ptr<char[]> wrapData = GetWrapAssetData(asset, &wrapOutSize);

        if (!wrapData || wrapOutSize == 0)
        {
            assert(0);
            return nullptr;
        }

        wrapAsset->rawData = std::move(wrapData);
    }

    if (ImGui::BeginChild("##Wrap Preview", ImVec2(-1, -1), true, ImGuiWindowFlags_HorizontalScrollbar))
    {
        if(wrapAsset->type == VPKFileType_e::TEXT)
            ImGui::TextUnformatted(reinterpret_cast<const char*>(wrapAsset->rawData.get()));
        else
        {
            static MemoryEditor wrapPreview;

            wrapPreview.ReadOnly = true;
            wrapPreview.OptShowDataPreview = true;
            //wrapPreview.UserData = &previewData;
            //wrapPreview.BgColorFn = UIArgData_BGColorCallback;

            wrapPreview.DrawContents(wrapAsset->rawData.get(), wrapAsset->dcmpSize);
        }
    }
    ImGui::EndChild();

    // there's nothing to put in the main scene window
    return nullptr;
}

void* PreviewWrapAsset(CAsset* const asset, const bool firstFrameForAsset)
{
    CPakAsset* const pakAsset = static_cast<CPakAsset*>(asset);

    WrapAsset* const wrapAsset = reinterpret_cast<WrapAsset*>(pakAsset->extraData());

    if (!wrapAsset) UNLIKELY
        return nullptr;

    switch (wrapAsset->type)
    {
#if !(HAS_BSP_SUPPORT) // if no bsp-specific support, just show it as a binary file
    case VPKFileType_e::BSP:
#endif
    case VPKFileType_e::TEXT:
    case VPKFileType_e::UNKNOWN:
        return Wrap_PreviewTextOrBinary(asset, wrapAsset, firstFrameForAsset);
#if (HAS_BSP_SUPPORT)
    case VPKFileType_e::BSP:
    {
        if (!wrapAsset->parsedData)
            return Wrap_PreviewTextOrBinary(asset, wrapAsset, firstFrameForAsset);

        return reinterpret_cast<CBSPData*>(wrapAsset->parsedData)->ConstructPreviewData();
    }
#endif
    default:
        return nullptr;
    }

    unreachable();
}

void InitWrapAssetType()
{
    AssetTypeBinding_t type =
    {
        .name = "Wrapped File",
        .type = 'parw',
        .headerAlignment = 8,
        .loadFunc = LoadWrapAsset,
        .postLoadFunc = PostLoadWrapAsset,
        .previewFunc = PreviewWrapAsset,
        .e = { ExportWrapAsset, 0, nullptr, 0ull },
    };

    REGISTER_TYPE(type);
}