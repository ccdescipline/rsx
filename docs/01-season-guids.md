# 赛季 GUID / SAID

从 `common.rpak`（自动套 `common(01).rpak`）导出 `stgs` 资源：

`settings/itemflav/calevent/seasonNN.rpak`

`common_mp.rpak` 里没有额外赛季条目。明文扫不到路径（RPak v8 压缩页），必须走 RSX。

## 在 pak 里怎么定位

- 类型 `stgs`。header v2：`+0` layout GUID，`+8` valueData，`+16` name，`+40` u32 `uniqueId`。
- `uniqueId` 就是 Bakery 生成的 itemflavor id，导出 JSON 里的 `settingsAssetID`（`SAIDxxxxxxxxxxx`）是同一个数。
- 64 位资源 GUID 是路径的 `RTech::StringToGuid`，和 RSX `--list csv` 的 `guid` 列一致。

## 命令

```bat
python tools/export_season_guids.py
```

等价 RSX：

```
rsx.exe -nocachedb --parsethreads 8 --loadwhitelist stgs,stlt,Ptch
  -export --exporttypes stgs --exportfilter "itemflav\calevent\season"
  --exportdir exported_seasons
  --list exported_seasons\season_stgs_filtered.csv --listformat csv
  D:\Apex\paks\Win64\common.rpak
```

`--loadwhitelist` 必须带 `Ptch`，否则 patch_master 不生效，会落到没打补丁的基础包。`stlt` 是 layout，没有它 JSON 导不出来。

只重建表：

```bat
python tools/export_season_guids.py --from-existing
```

## 产出

| 文件 | 内容 |
|------|------|
| `exported_seasons/settings/itemflav/calevent/seasonNN.json` | 完整 stgs |
| `exported_seasons/season_guids.csv` | 表 |
| `exported_seasons/season_guids.txt` | 同上，纯文本 |

当前包 season01–30 都在。已知 SAID（01/09–15/25）全部对得上。

| season | guid64 | uniqueId | SAID |
|--------|--------|----------|------|
| season01 | `0xBB7ED37EC7D7912D` | 1769158912 | SAID01769158912 |
| season02 | `0xB990C567ED1FE901` | 1774506873 | SAID01774506873 |
| season03 | `0xB7A2B750F998E911` | 724938940 | SAID00724938940 |
| season04 | `0xB5B4A93A507FF06D` | 1092263930 | SAID01092263930 |
| season05 | `0xB3C69B235CF8F07D` | 835358768 | SAID00835358768 |
| season06 | `0xB1D88D0C82414851` | 49860047 | SAID00049860047 |
| season07 | `0xAFEA7EF5C058F7E9` | 777894692 | SAID00777894692 |
| season08 | `0xADFC70DEE5A14FBD` | 831495238 | SAID00831495238 |
| season09 | `0xAC0E62C823B8FF55` | 1080534582 | SAID01080534582 |
| season10 | `0xD0823E80D28D34F3` | 1783977028 | SAID01783977028 |
| season11 | `0xCE943069DF063503` | 48930450 | SAID00048930450 |
| season12 | `0xCCA622531D1DE49B` | 479992436 | SAID00479992436 |
| season13 | `0xCAB8143C2996E4AB` | 798342294 | SAID00798342294 |
| season14 | `0xC8CA062567AE9443` | 1642977899 | SAID01642977899 |
| season15 | `0xC6DBF80EA5C643DB` | 589335273 | SAID00589335273 |
| season16 | `0xC4EDE9F7B23F43EB` | 801928788 | SAID00801928788 |
| season17 | `0xC2FFDBE0F056F383` | 134970849 | SAID00134970849 |
| season18 | `0xC111CDCA2E6EA31B` | 134750981 | SAID00134750981 |
| season19 | `0xBF23BFB334B3CD3A` | 1615095880 | SAID01615095880 |
| season20 | `0xE37122E5B95297CA` | 1518645858 | SAID01518645858 |
| season21 | `0xE18314CEB963EBF8` | 1452791135 | SAID01452791135 |
| season22 | `0xDF9506B803E34772` | 519237306 | SAID00519237306 |
| season23 | `0xDDA6F8A14E62A2EC` | 1826978392 | SAID01826978392 |
| season24 | `0xDBB8EA8A4E73F71A` | 1334467340 | SAID01334467340 |
| season25 | `0xD9CADC738023FAD0` | 1353540285 | SAID01353540285 |
| season26 | `0xD7DCCE5C9904A6C2` | 1466277730 | SAID01466277730 |
| season27 | `0xD5EEC045E384023C` | 971173844 | SAID00971173844 |
| season28 | `0xD400B22F153405F2` | 1905679460 | SAID01905679460 |
| season29 | `0xD212A4181B793011` | 1358038473 | SAID01358038473 |
| season30 | `0xF660074AA017FAA1` | 2010069277 | SAID02010069277 |
