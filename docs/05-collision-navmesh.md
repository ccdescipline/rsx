# 碰撞和导航网格

v3.0.4.24 这份安装（`D:\Apex`，`gameversion.txt`）没有 VPK。世界碰撞和 `.nm` 都是 rpak 里的 `wrap` 资源，不在基础 `<map>.rpak` 里。

用 `D:\code\rsx\bin\Release_NoGui\rsx.exe`（2026-11-05 起是合了上游 r-ex/rsx 2.4.1 的版本），或旧发布目录的 `rsx_nogui.exe`（`C:\Users\Administrator\Downloads\rsx_2.4.0\rsx_nogui.exe`）。导模型只能用前者，见「静态道具碰撞」。前者导训练场客户端 lump 写出 65 个文件，旧版只写出 29 个。碰撞相关的 `0003/000E/0010/0012/0013/0023` 两边逐字节相同。带界面的 `rsx.exe` 会停在窗口上，不要用它跑批处理。RSX 会自动读 pak 同目录的 `patch_master.rpak`。`(01)` / `(02)` 补丁不要单独再导。

已导出的例子（训练场，不用再导一遍）：

```
collision_example/client/wrap/maps/          # 客户端 lump
collision_example/server_temp/wrap/maps/navmesh/mp_rr_canyonlands_staging_mu1/
collision_example/props/mdl/...               # 被世界 BVH 引用的模型的碰撞网格，模型空间 STL，两档：<名>.stl / <名>_d1.stl
collision_example/props_world/                # 道具实例表（摆放、solid、BVH 引用、用哪档）
collision_example/map_info.txt                # worldspawn 原点 / decodeScale / 量化步长（训练场没有 overview）
exported_props_physics/<map>/                 # rsx 的完整导出（地图包里所有模型），props/ 从这里挑
```

道具碰撞的原理见文末「静态道具碰撞」。换图一键导出（lump + server_temp + 道具）见 [06 换图导出碰撞数据](06-map-collision-export.md)。

## 一张图在哪些包

| 要什么 | 包 | wrap 资源名 |
|---|---|---|
| 世界碰撞 | `<map>_client_perm.rpak` + `<map>_client_temp.rpak` | `maps/<map>.bsp`，`maps/<map>.bsp.<LLLL>.bsp_lump.client` |
| 导航网格 | `<map>_server_temp.rpak` | `maps/navmesh/<map>/<hull>.nm` |
| 服务端 lump、实体、AI 图 | 同一个 `_server_temp` | `.bsp_lump.server`、`*_env.ent` 等、`maps/graphs/<map>.ain` |
| 静态道具碰撞 | `<map>.rpak`，共享模型在 `common.rpak` / `common_mp.rpak` | `mdl_`，物理在模型上；摆放在 lump `0023` 的 `sprp` |

`<LLLL>` 是 lump 编号，十六进制，和 `D:\code\rsx\src\game\rtech\utils\bsp\lumps.h` 一致。碰撞只看这两块：

| 编号 | 名字 | 训练场上的大小 |
|---|---|---|
| `0012` | `LUMP_BVH_NODES` | 2,062,592 |
| `0013` | `LUMP_BVH_LEAF_DATA` | 1,692,056 |

叶子里是三角/四边形（含 packed 顶点）和静态道具引用。顶点在 `0003`（`LUMP_VERTEXES`），内容掩码 `0010`，表面属性 `0011`。服务端 lump 没有 BVH。

### 引擎加载的全部碰撞 lump（`CollisionBSPData_Load`，r2 PDB；1.30 一致）

| lump | 内容 |
|---|---|
| `0003` | float3 顶点 |
| `0014` | packed 顶点，3 × **有符号** int16 |
| `0010` | 内容掩码（u32） |
| `0011` / `000F` | 表面属性（8 字节）/ 表面名字符串 |
| `0012` / `0013` | BVH 节点（64 字节）/ 叶子数据（u32） |
| `0015` | heightfield（地形），每个 40 字节：origin(3f) scale(3f) dims(2×u16) heightCount(u32) 指针(8，运行时) |
| `0016` | heightfield 高度采样（u8），各 heightfield 按顺序各取 heightCount 个 |
| `000E` | dmodel：`+32` bvhNode、`+36` bvhLeaf、`+40` vertIndex、`+44` bvhFlags、`+48` origin、`+60` decodeScale |

- dmodel 的 `bvhFlags` 第 0 位为 1 时，这个模型的顶点是 `0014`（packed），否则是 `0003`（float3），都从 `vertIndex` 开始。`map_info.txt` 里写了 worldspawn 的这两个值。
- packed 顶点和节点包围盒同一个还原公式：`origin + float(q << 16) × decodeScale`，q 是**有符号** int16（等于 `q × 65536 × decodeScale`）。
- 子节点类型：0 节点、1 空、2 跳过、3 bundle、4/6 float 三角/四边形、5/7 packed 三角/四边形、8 凸包（自带 origin/decodeScale 和 packed 顶点，头 20 字节）、9 静态道具、**10 heightfield patch**（只出现在 worldspawn，数据在 `0015`/`0016`）。
- 四边形：`p0 = v`、`p1 = v+1+b`、`p3 = v+1+c`、`p2 = p1 − p0 + p3`，拆成 `(p0,p1,p2)` 和 `(p0,p2,p3)`。
- heightfield patch（40 字节）：u16 coord[2]、u8 dims[2]、u8（第 0 位 triangulateTopToBottom，1–7 位 heightfield 下标）、u8 quadsPerPlane、float maxVerticalError、u32 heightDataOffset、float heightBias、float heightScale、u64 表面属性 RLE 位、u16 表面属性[4]。高度采样 0 是空洞，其余 `z = (s − 1) × heightScale + heightBias`。完整的三角化（含空洞判定）在 `tools/bvh_decode.py` 的 `_heightfield`，照搬引擎 `CollHeightfield_PatchIter`。
- 地形碰撞**不在**道具 STL 里。`export_map_collision.py` 现在会多写一个 `props_world/<bsp>_terrain_collision.stl`（世界坐标，空洞已去掉）；navdemo 也可以直接读 `0015`/`0016` 自己解。

`.nm` 是 Detour 集合：文件头魔数 `TESM`，训练场这两份是版本 9、tile 512。体型名来自 r5sdk 的 `NavMeshType_e`：

| 文件名 | 体型 | 训练场 |
|---|---|---|
| `small.nm` | 人形（`traverseCount` 5） | 有，3,399,844 字节，501 tile |
| `med_short.nm` | 中等偏矮（`traverseCount` 1） | 有，2,324,636 字节，491 tile |
| `medium.nm` / `large.nm` / `extra_large.nm` | 更大的体型 | 这张图没有 |

有的图在 `maps/navmesh/<map>/` 下还有模式专用网格，文件名不是体型，例如 `control_layout_*.nm`、`fdm_*.nm`。

## 哪些图有 `.nm`

只有带 `*_server_temp.rpak` 的图才有。当前 `D:\Apex\paks\Win64` 里有的是：

`mp_lobby`、`mp_rr_arena_habitat`、`mp_rr_arena_phase_runner`、`mp_rr_canyonlands_hu`、`mp_rr_canyonlands_staging_mu1`、`mp_rr_desertlands_hu`、`mp_rr_divided_moon_mu1`、`mp_rr_olympus_mu2`、`mp_rr_party_crasher`、`mp_rr_thunderdome`、`mp_rr_tropic_island_mu2`。

没有服务端包、因此没有 `.nm` 的包括现在的大逃杀图 `mp_rr_desertlands_mu5`、`mp_rr_olympus_mu3`。它们仍有客户端 BSP 碰撞。先看 `exported_maps/_meta/lists/<map>_server_temp.csv` 里有没有 `.nm`，不必先导文件。

## 命令

先列资源，不导出：

```
rsx_nogui.exe -nocachedb --loadwhitelist wrap,Ptch --list <pak>.csv --listformat csv <pak>.rpak
```

导航网格（没有 `_server_temp.rpak` 就跳过）：

```
rsx_nogui.exe -nocachedb --loadwhitelist wrap,Ptch -export --exporttypes wrap --exportfilter navmesh --exportdir <out>\server_temp <map>_server_temp.rpak
```

`--exportfilter` 是资源名子串。`navmesh` 只留 `.nm`。去掉它会把同包的 `.ent`、`.ain`、脚本一起带出来。

世界碰撞。两个客户端包放在同一次调用里。只加载 `_client_perm` 时，BSP 加载会报缺 lump（那些 lump 在 `_client_temp`），进程以退出码 1 结束，排在后面的 lump 可能没写出来。

```
rsx_nogui.exe -nocachedb --loadwhitelist wrap,Ptch -export --exporttypes wrap --exportfilter .bsp --exportdir <out>\client <map>_client_perm.rpak <map>_client_temp.rpak
```

`.bsp` 这个过滤能同时命中 `.bsp` 和 `.bsp_lump`，因为资源名里都有 `.bsp`。

## 导出文件长什么样

落在 `<exportdir>/wrap/` 下，第一层目录名（`maps`）保留。带 `.client` / `.server` 后缀的名字会被对调：

```
maps/<map>.bsp.0012.bsp_lump.client
  -> wrap/maps/<map>.bsp.0012.client.bsp_lump
```

`.nm` 没有这个后缀，路径不变：`wrap/maps/navmesh/<map>/small.nm`。

这个 `rsx_nogui.exe` 打开了 BSP 支持（源码里 `HAS_BSP_SUPPORT` 是 false，但这份二进制不是）。结果是：

- `.bsp_lump` 按原始字节写出。碰撞用 `0012` 和 `0013`。
- `.bsp` 本身不会是 rBSP。`CBSPData::Export` 把它写成 OBJ（`v x y z`）。那是渲染顶点，不是碰撞 BVH。缺 lump 时顶点是 `v nan nan nan`。这个文件不要当碰撞用。

`--loadwhitelist wrap,Ptch` 不要拿掉，否则会把贴图和模型一起加载。

## 静态道具碰撞

世界 BVH（`0012`/`0013`）里道具只是引用：子节点类型 9（`STATIC_PROP`），三角形在道具自己的模型里。所以要两样东西：每个模型的碰撞网格，加上 `sprp` 里的摆放。

### 模型碰撞的两档细节

rmdl 里的碰撞是 BVH4（节点、叶子格式和地图 BSP 的一样），分成若干 part。studiohdr（v19.2 起的布局，v3.0.4.24 的模型是 v21）：

- `+0xE6` u16 `bvhOffset`：碰撞段偏移。低位为 1 时实际偏移是 `(值 & ~1) << 4`（rsx 的 `FIX_OFFSET`）。
- `+0xE8` int8 `collisionPartForDetail[2]`：detail 0 / detail 1 各用哪个 part，`-1` 表示没有这一档。
- 碰撞段开头 4 个 int：`contentMasksIndex, surfacePropsIndex, surfaceNamesIndex, partCount`。之后每个 part 10 个 dword：`flags, nodesOff, vertsOff, leafOff, surfacePropDataOff, u8 count, u8 count, u16, origin.xyz, decodeScale`，偏移都相对碰撞段开头。

训练场包里 415 个有碰撞的模型：295 个是 2 个 part、`(1, 0)`，即 detail 0 = part 1（粗外壳，常常就是一个盒子，例如 `box_small_01` 12 个三角），detail 1 = part 0（细网格，1036 个三角）。119 个是 1 个 part、`(-1, 0)`，只有 detail 1，多是弹壳、垃圾袋、灯、通风口、贴花这类小东西。1 个动画模型 24 个 part、`(-1, -1)`。两个 part 的 contents 都是 `CONTENTS_SOLID` 一类（`0x1`，部分带 `0x2`/`0x8`），不是按掩码区分用途。

地图 BVH 的道具叶子 dword 第 31 位为 1（`solid=7`）时，这个实例只用 detail 1。

引擎怎么选档（v3.0.1.30 `StaticProp_TraceDetailLevel`，r2 PDB 同名函数）：

1. 第 31 位为 1，或 convar `perTriangleCollisionForced`（默认 0）打开 → detail 1
2. 查询带 LOW 标志（`queryFlags & 1`），或 `perTriangleCollision`（默认 1）关掉 → detail 0
3. 查询带 HIGH 标志（`& 2`）→ detail 1
4. 查询带 HIGH_AT_START（`& 4`）→ 查询起点在道具包围盒里时用 detail 1，否则 detail 0

navdemo 那边按引擎代码确认过玩家移动是「第 31 位为 1 用 detail 1，其余用 detail 0」，也就是上面的第 1、2 条（移动具体带哪个查询标志这边没追到）。带 HIGH / HIGH_AT_START 的查询会用到 detail 1，那种情况这份规则不适用。节点包围盒和这条规则一致，但只靠节点框推不出来：

| 实例 | 数量（有节点框的） | 节点框和谁吻合（误差 ≤ 4） |
|---|---|---|
| 第 31 位 = 1（solid 7） | 259 | detail 1：259 个全中，最大误差 2.0。用 detail 0 只有 31 个对得上 |
| 第 31 位 = 0（solid 6） | 4597 | detail 0 ∪ detail 1：4593 个。只用 detail 0：3418 个；只用 detail 1：3872 个 |

solid 6 的节点框把两档都包进去了，所以用 `bounds_err` 验收时，普通实例要拿 d0∪d1 去比，只拿 d0 比会有 1400 多个超过 3。射线/子弹用哪档没有核对。剩下 4 个对不上的是 `eden_tree_dry_03` 和 `tarp_02`。

训练场被 BVH 引用的 365 个模型里有 75 个没有 detail 0。其中 61 个被 655 个普通实例引用，这些实例对玩家移动没有碰撞。另外 14 个只被第 31 位的实例引用，用的是 detail 1。

2026-11-05 之前的 rsx 会把所有 part 合进一个 STL，结果是两档的并集。solid 7 的石头因此比游戏里宽 10–40 单位，`bounds_err` 最大 403。

2026-11-12 之前的 rsx 把 packed 顶点（叶子类型 5/7/8）当成**无符号** uint16 × 0xFFFF 解，引擎是有符号 int16 × 65536（`src/game/rtech/utils/bvh/bvh.cpp`）。坐标为负的 packed 顶点会被放到很远的地方，正坐标也差 1/65536。用到 packed 顶点的模型 STL 要用修好后的 rsx 重新导；之前 thunderdome / skulltown 那些 `bounds_err` 几十的异常模型先看是不是这个原因。

### 1. 导模型碰撞网格

用 `D:\code\rsx\bin\Release_NoGui\rsx.exe`。2026-11-05 把上游 r-ex/rsx 2.4.1 合进了 fork 的 main，并重新编译。合并之前的 exe 导不出，原因有两个：

- NoGui 不读 `imgui.ini`，`mdl_` 只能导默认的 CAST。改 ini 里的 `Setting=5` 没用，带界面的 `rsx.exe` 也不会执行 `-export`。新版本加了 `--exportformat <类型>=<格式>`，格式写名字或编号，名字忽略大小写和标点。
- 2026-11-04 游戏更新后，模型资源变成版本 21。旧版只认到 19，在 Release 下不报错，直接跳过。表现是模型名全是 `mdl\0x...` 哈希、`--exportfilter` 一个也匹配不到、导出 0 个文件。上游 2.4.1 支持 20/21。

`stl_respawn_physics` 读模型里的 Respawn BVH（`stl_valve_physics` 读旧的 `.phy`，不用）。同日又改了 `ExportPhysicsModelBVH`（`src/game/rtech/assets/model.cpp`），按 `collisionPartForDetail` 分档写文件：

- `<名>.stl`：detail 0 的 part。模型没有 detail 0 就不写。
- `<名>_d1.stl`：detail 1 的 part。和 detail 0 是同一个 part 时不写，用 `<名>.stl`。
- 头里没有这两个字节的旧版本模型（v16 之前），或者两个值都是 -1：照旧把所有 part 合进 `<名>.stl`。

白名单要带上依赖类型，否则 rsx 会在后处理里空指针崩溃（`latest_crash/rsx_crash.txt`）：

- 物理：`mdl_,asqd,Ptch`。少了 `asqd`，会崩在 `animdata.cpp` 的 `ParseSequence`，因为解析动作序列要用到它。
- CAST：不加 `--loadwhitelist`。只加 `asqd,matl` 也不够，进程会以 `0xC0000409` 退出。

先导到中间目录，第 2 步再挑出要交付的：

```
cd /d D:\Apex\paks\Win64
rsx.exe -nogui -nocachedb -exportfullpaths --loadwhitelist mdl_,asqd,Ptch -export --exporttypes mdl_ ^
  --exportformat mdl_=stl_respawn_physics --exportdir <项目根目录>\exported_props_physics\<map> <map>.rpak
```

`-exportfullpaths` 要加，输出路径（`mdl/ola/sewer_grate_01.stl`）才能和 `sprp` 里的模型名对上。整个训练场包不到 1 秒：494 个模型里 415 个有碰撞，写出 301 个 `<名>.stl`（其中 `leviathan_kingscanyon_animated` 是 24 个 part 合并的）+ 420 个 `<名>_d1.stl`（都含下面补导的 6 个）。其余是特效、远景、植被。

地图引用的模型有一部分不在地图包里。先跑一遍第 2 步，它会列出「BVH props with no physics STL」，再从共享包按名字补导到同一个目录：

```
rsx.exe ...同上... --exportfilter "sewer_grate_01.rmdl,firing_range_mu1_targets_01_stand,..." common.rpak common_mp.rpak
```

训练场补了 6 个：`sewer_grate_01`、`firing_range_mu1_targets_01_stand`、`sewer_staircase_quad`、`sewer_railing_01_128`、`zipline_arm`、`mp_setting_menu`。

合并之前的 exe 备份在 `D:\code\rsx\bin\Release_NoGui_seqdump_old\`。它带 ApexRadar 用的 SEQDUMP/RIGDUMP 调试输出，但读不了 v21 模型。那段源码没进 main，在 `D:\code\rsx` 的 `git stash list` 里（`pre-upstream-2.4.1: ...`）。

### 2. 挑出交付的网格，写实例表

```
python -I tools\place_prop_collision.py --lumps collision_example\client\wrap\maps ^
  --props exported_props_physics\mp_rr_canyonlands_staging_mu1 --map mp_rr_canyonlands_staging_mu1 ^
  --out collision_example\props_world --deliver collision_example\props
```

- `--deliver`：把被世界 BVH 引用的模型的 `<名>.stl` 和 `<名>_d1.stl` 拷过去（模型坐标、不乘 scale、二进制 STL）。训练场 365 个模型，290 个 detail 0 + 365 个 detail 1，共 34 MB。`sprp` 里 `pelican_case_large_drabGreen` 和 `_drabgreen` 是同一个模型的两种大小写，按名字找文件时要忽略大小写。
- `<map>_props_instances.csv`：每个 `sprp` 实例一行。列：`index, model, in_bvh, has_stl, solid, flags, contents, leaf_dword, ox, oy, oz, pitch, yaw, roll, scale, tris, bounds_err`。`has_stl`、`tris` 按移动规则算：第 31 位用 detail 1（没有 `_d1` 就用 `<名>.stl`），否则用 detail 0。`bounds_err` 是摆好后的包围盒和节点框的最大偏差：第 31 位的实例拿 detail 1 比，其余实例拿 d0∪d1 比。
- `--world-stl`：再写一份所有实例摆好后的世界坐标 STL（`<map>_props_collision.stl`，规则同上）。`--obj` 写按实例分组的 OBJ。默认都不写，navdemo 用单模型网格加实例表自己拼。

玩家移动用法：`leaf_dword` 第 31 位为 1 的实例用 `<名>_d1.stl`，没有就用 `<名>.stl`。其余实例用 `<名>.stl`，模型没有这个文件就是没有移动碰撞。

训练场：10957 个实例，BVH 引用 6530 个（第 31 位 309 个，用到 25 个模型），都有网格。没被引用的 4427 个里有 2015 个 `solid=0`，其余 `solid=6` 的不进世界 BVH。按上面的规则，5875 个实例有网格，一共 199 万三角。另外 655 个 solid 6 实例的模型没有 detail 0。

数据格式（训练场 sprp v54 上核对过）：

- `0023` 第一个 game lump 是 `sprp`：`int dictCount`、`char[128] × dictCount`、`int propCount`、两个不用的 int、`64 字节 × propCount`。实例：origin `+0`、angles（pitch/yaw/roll，度）`+12`、scale `+24`、模型下标 u16 `+28`、solid `+30`、flags `+31`。
- 类型 9 叶子是一个 dword：**低 24 位**是 `sprp` 下标（引擎 `StaticProp_Trace`：`dword & 0xFFFFFF`），第 24–31 位整个字节被引擎拷进 trace 结果，第 31 位为 1 表示用 detail 1（训练场上就是 `solid=7` 的道具）。训练场不到 65536 个实例；`mp_rr_olympus_mu3` 有 466427 个实例，下标用到第 18 位，只取低 16 位会全错。第 24–30 位目前的数据里没见到非 0，`place_prop_collision.py` 遇到会打印出来。bundle（类型 3）里的子叶子也可能是类型 9。
- 只从 worldspawn 的根节点（dmodel 0 的 `bvhNode`=0、`bvhLeaf`=0）往下遍历。节点 lump 里还有别的 brush 模型的树，它们的子节点下标相对自己的基址，按 worldspawn 读会越界（olympus_mu3 上出现过）。
- 节点包围盒是 int16，每个轴先存 4 个 min 再存 4 个 max（不是 min/max 交替）。还原：`世界坐标 = worldspawn 原点 + q × decodeScale × 65536`。原点在 `000E` 第 0 个 dmodel 的 `+48`，decodeScale 在 `+60`。训练场原点 `(-5834, 3753, -9664)`、decodeScale 2⁻¹⁵（即 × 2）；`mp_rr_olympus_mu3` 是 2⁻¹⁴（× 4），不能写死 2。
- 变换：Source `AngleMatrix(pitch, yaw, roll)`，`世界 = origin + R × (scale × v)`。

核对数据见上面「模型碰撞的两档细节」的表。

换图：导该图的 `_client_perm` + `_client_temp` lump（见上面「命令」），用该图的 `<map>.rpak` 跑第 1 步，按第 2 步列出的缺失模型从 `common*.rpak` 补导，再跑第 2 步。
