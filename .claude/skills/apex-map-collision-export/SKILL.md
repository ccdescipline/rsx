---
name: apex-map-collision-export
description: Export Apex map collision data for navdemo with RSX — world BVH lumps, server_temp (.ent/.nm), two-detail prop collision STLs, prop instance CSV, map_info, and mixtape cull cropping. Use when the user says 导出碰撞/地图 collision, mentions collision_maps, navdemo, export_map_collision, crop_map_collision, cull_entity_spawn_circle, or the mixtape manifest.
---

# 地图碰撞导出（navdemo）

一张图的完整交付：世界碰撞 lump、`server_temp`（`.ent` / `.nm`）、静态道具两档碰撞网格、实例表、`map_info.txt`；混合模式图再按 `cull_entity_spawn_circle` 裁剪。

所有命令在项目根目录执行：

`D:\code\rsx`

原理和格式见 `docs\05-collision-navmesh.md`，换图流程和 navdemo 约定见 `docs\06-map-collision-export.md`。

## 固定路径

| 项 | 路径 |
|---|---|
| 游戏 pak | `D:\Apex\paks\Win64` |
| RSX | `D:\code\rsx\bin\Release_NoGui\rsx.exe` |
| 一键导出 | `tools\export_map_collision.py` |
| 混合模式裁剪 | `tools\crop_map_collision.py` |
| 道具实例/交付 | `tools\place_prop_collision.py` |
| 通用对比 | `tools\compare_exports.py` |

**RSX 版本**：必须用 `D:\code\rsx` 编的 `Release_NoGui\rsx.exe`，且 main 在 `c43c095`（per-detail STL）之后。旧发布目录里的 `rsx_nogui.exe`（`C:\Users\Administrator\Downloads\rsx_2.4.0\rsx_nogui.exe`）读不了 v21 模型，也不会按 detail 0/1 分文件。

## 1. 标准全图导出

先 dry-run 看命令：

```bat
python -I tools\export_map_collision.py --map mp_rr_thunderdome --dry-run
```

正式跑：

```bat
python -I tools\export_map_collision.py --map mp_rr_thunderdome
```

默认值：

- `--out collision_maps\<map>`
- `--work exported_props_physics\<map>`
- `--client-paks <map>_client_perm,<map>_client_temp`
- `--server-pak <map>_server_temp`（不存在就自动跳过）
- `--shared common_mp,common,common_early`

变体图要显式指定：

```bat
python -I tools\export_map_collision.py --map mp_rr_canyonlands_hu_avt ^
  --server-pak mp_rr_canyonlands_hu_server_temp

python -I tools\export_map_collision.py --map mp_rr_tropic_island_mu2_landscape ^
  --server-pak mp_rr_tropic_island_mu2_server_temp
```

工具按顺序做 6 件事：

1. 用 `<map>_client_perm` + `<map>_client_temp` 导客户端 lump（过滤 `bsp_lump`），检查 `000E` worldspawn 和 `0023` 的 `sprp`；不正常就停。
2. 导 `<map>_server_temp`（`.ent`、`navmesh/*.nm`、AI 图、脚本）；去掉 `.ent` 末尾的 `\0`；没有这个包就跳过。
3. 从 `<map>.rpak` 导 `resource/overviews/<map>.txt`（小地图 overview）；没有就跳过。
4. 从 `<map>.rpak` 导所有模型碰撞网格（`stl_respawn_physics`，按 detail 0/1 分文件）。
5. 找出被世界 BVH 引用、但地图包里没有的模型，从共享包按名字补导。
6. 跑 `place_prop_collision.py`：写实例表，把被引用模型的网格拷到 `props\`（每次重建），打印验收数据。

输出布局：

```text
collision_maps/<map>/
  client/wrap/maps/<bsp>.bsp.<LLLL>.client.bsp_lump
  server_temp/wrap/maps/*.ent, navmesh/<map>/*.nm, ...
  overview/wrap/resource/overviews/<map>.txt
  map_info.txt
  props/mdl/.../<模型>.stl          detail 0
  props/mdl/.../<模型>_d1.stl       detail 1
  props_world/<bsp>_props_instances.csv
```

`props/` 只放被世界 BVH 引用的模型，两档都给；文件名大小写跟 rsx 实际输出走，按模型名找文件要忽略大小写。

## 2. 混合模式裁剪

球心来自 playlist 的 `cull_entity_spawn_circle "<x,y,z> r"`。当前 5 张 mixtape 图的球在 `docs\mixtape_manifest.md`：

| 目录 | 场地 | cull 球 (x,y,z,r) |
|---|---|---|
| `mp_rr_desertlands_mu5` | fdm_fragment | `9186,5536,-3324,9000` |
| | gun_run_monument | `3915,9918,-3940,8000` |
| `mp_rr_tropic_island_mu2_landscape` | control_layout_barometer | `-16000,-22000,1000,15000` |
| | fdm_wattson | `8320,-18184,798,9000` |
| `mp_rr_divided_moon_mu1` | control_layout_production | `-32590,-3912,4235,15000` |
| `mp_rr_thunderdome` | 整张图 | 无 |
| `mp_rr_freedm_skulltown` | 整张图 | 无 |

先只算不写：

```bat
python -I tools\crop_map_collision.py --map-dir collision_maps\mp_rr_divided_moon_mu1 ^
  --bsp mp_rr_divided_moon_mu1 --sphere -32590,-3912,4235,15000 --stats-only
```

确认后去掉 `--stats-only`。多个球重复 `--sphere`：

```bat
python -I tools\crop_map_collision.py --map-dir collision_maps\mp_rr_desertlands_mu5 ^
  --bsp mp_rr_desertlands_mu5 ^
  --sphere 9186,5536,-3324,9000 --sphere 3915,9918,-3940,8000
```

裁剪规则：

- 世界 BVH `0012` 格式不变：不相交子节点槽的 child type 改成 `NO_CHILD (1)`，节点/叶子/顶点数据不动。
- 实例表保留“摆好后的模型 AABB 与球相交”的实例，再并上裁剪后 BVH 仍引用的下标。
- `props/` 只交保留实例用到的模型。
- 写 `cull.txt`；未裁剪的 `0012` 备份在 `exported_props_physics\<bsp>\crop_original\`。
- 当前脚本还会在 `props_world\<bsp>_props_instances.csv.full` 留全量实例表；旧导出可能把全表放在 `exported_props_physics\<bsp>\crop_original\instances_full.csv`。换球重裁时用 `--full-csv` 指过去，并从 `crop_original` 恢复 `0012`，否则会在已裁剪的数据上再裁。

## 3. 验收

检查文件：

```bat
dir collision_maps\<map>\client\wrap\maps\*.bsp.0012.client.bsp_lump
dir collision_maps\<map>\props_world\*.csv
dir collision_maps\<map>\props
type collision_maps\<map>\map_info.txt
```

`map_info.txt` 应包含：

```text
bsp <bsp>
sprp_version <n>
worldspawn_origin <x> <y> <z>
worldspawn_decode_scale <v>
node_bounds_step <v>
overview_pos_x / overview_pos_y / overview_scale   （有 overview 的图）
```

`place_prop_collision.py` 最后会打印：

```text
bounds_err bit31 vs d1: ...
bounds_err other vs d0+d1: ...
```

正常结果：中位数和 p95 不超过量化步长（`decodeScale × 65536`）；超过 1.5 倍步长的应是少数。普通实例只拿 d0 比会有大量误差，那是比较方法问题，节点框包的是 d0∪d1。

新旧对比：

```bat
python -I tools\compare_exports.py collision_maps\<旧> collision_maps\<新>
```

## 4. 各图情况（2026-11-05 基线）

| 图 | 命令 | 情况 |
|---|---|---|
| `mp_rr_canyonlands_staging_mu1` | `--map mp_rr_canyonlands_staging_mu1` | 完整跑过，和 `collision_example\` 逐文件相同 |
| `mp_rr_olympus_mu3` | `--map mp_rr_olympus_mu3` | 完整跑过；没有 `_server_temp`，没有 `.nm` / `.ent` |
| `mp_lobby`、`mp_rr_divided_moon_mu1`、`mp_rr_thunderdome` | `--map <图>` | 客户端 lump 验过；有 `_server_temp` |
| `mp_rr_desertlands_mu5` | `--map mp_rr_desertlands_mu5` | 客户端 lump 验过；没有 `_server_temp` |
| `mp_rr_canyonlands_hu` | `--map mp_rr_canyonlands_hu_avt --server-pak mp_rr_canyonlands_hu_server_temp` | 客户端包在 `_avt` 变体；BSP 名是 `mp_rr_canyonlands_hu_avt`，`.nm` 在 `navmesh/mp_rr_canyonlands_hu/` |
| `mp_rr_tropic_island_mu2` | `--map mp_rr_tropic_island_mu2_landscape --server-pak mp_rr_tropic_island_mu2_server_temp` | 用 `_landscape` 变体 |
| `mp_rr_olympus_mu2` | — | 客户端只有 `(01)` 补丁，没有基础包，导不出 lump |
| `mp_rr_arena_habitat` | — | `0002/000E/002D` 解不出来，`0023` 为空；脚本会在第 1 步停 |
| `mp_rr_arena_phase_runner`、`mp_rr_desertlands_hu`、`mp_rr_party_crasher` | — | 只有 server 包，没有客户端包 |

旧的 `collision_maps\` 基线（2026-11-07/08）在 `C:\Users\Administrator\Downloads\rsx_2.4.0\collision_maps`；2026-11-11 游戏更新后，地图 pak 有 `(01)` 补丁，重导时 rsx 会自动套用。导完记得重新裁剪 mixtape 图。

## 5. 已知坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 模型名全是 `mdl\0x...`，`--exportfilter` 匹配不到，导出 0 个 | rsx 太旧，读不了 v21 模型 | 用 `D:\code\rsx\bin\Release_NoGui\rsx.exe`（main ≥ `c43c095`） |
| rsx 崩在 `ParseSequence` | 白名单少了 `asqd` | `--loadwhitelist mdl_,asqd,Ptch` |
| 客户端 lump 导出崩 / 写出 OBJ | 过滤了 `.bsp` 本体 | 只过滤 `bsp_lump` |
| BSP 缺 lump，exit 1 | 两个客户端包没放同一次调用 | `_client_perm` + `_client_temp` 一起传给 rsx |
| `.ent` 末尾多 `\0` | 新 rsx 保留了字符串终止符 | 工具会自动去掉 |
| `props/` 每次变少 | 工具每次重建 `props/` | 正常，以最新实例表为准 |
| 裁剪后三角面没变 | 在已裁剪的 lump 上再裁 | 从 `exported_props_physics\<bsp>\crop_original\` 恢复 `0012`，用全量 CSV 重裁 |
| Bash 里路径变成 `collision_mapsmp_rr_...` | 反斜杠被 shell 吃掉 | 用正斜杠或引号；cmd/PowerShell 里用反斜杠 |

## 6. 汇报

给用户：

1. 图名 / BSP 名、是否有 `server_temp`（`.nm` / `.ent`）。
2. 实例总数、BVH 引用数、第 31 位实例数。
3. `bounds_err` 中位数 / p95 / 超过 1.5 倍步长的数量。
4. 缺 STL 的模型列表（补导后应为空或说明原因）。
5. 是否裁剪、球心、保留实例 / 三角面 / 道具 STL 数量。
6. 本次 rsx 版本和遇到的坑。
