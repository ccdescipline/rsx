# 换图导出碰撞数据（给 navdemo）

一张图的世界碰撞 lump、`server_temp`（`.ent` / `.nm`）、静态道具碰撞网格和实例表，一条命令导完。原理和数据格式见 [05 碰撞和导航网格](05-collision-navmesh.md)。

## 给 navdemo：要改和会变的地方

训练场上碰不到、换大图才会出错的（navdemo 代码要改）：

1. **道具下标取低 31 位**：`leaf_dword & 0x7FFFFFFF`，不能 `& 0xFFFF`。训练场 10957 个实例，第 16–30 位都是 0，所以看不出来；`mp_rr_olympus_mu3` 有 466427 个实例，下标用到第 18 位。第 31 位仍是 detail 1 标志。
2. **节点包围盒的还原系数**：`q × decodeScale × 65536`，decodeScale 在 `000E` 第 0 个 dmodel 的 `+60`。训练场是 2⁻¹⁵（×2），`olympus_mu3` 是 2⁻¹⁴（×4）。写死 ×2 的地方要改。
3. **遍历世界 BVH 从 worldspawn 根节点开始**：从节点 0 出发，沿子类型 0（NODE）往下走。不要线性扫整个 `0012`：里面还有别的 brush 模型的树，它们的子下标相对自己的 `bvhNode` / `bvhLeaf` 基址，当成 worldspawn 读会越界（`olympus_mu3` 上就越界了）。

交付内容和训练场那份相比有变化的：

4. **新图的目录**：`collision_maps\<图>\`，内部布局和 `collision_example\` 相同。训练场仍在 `collision_example\`。
5. **文件名按 BSP 名，不按图名**：lump 是 `<bsp>.bsp.<LLLL>.client.bsp_lump`，实例表是 `<bsp>_props_instances.csv`。BSP 名可能和 pak 名、导航网格目录名不同：`mp_rr_canyonlands_hu` 的 BSP 是 `mp_rr_canyonlands_hu_avt`，`.nm` 在 `navmesh/mp_rr_canyonlands_hu/`。
6. **有的图没有 `.nm` / `.ent`**：没有 `_server_temp` 包的图（`mp_rr_olympus_mu3`、`mp_rr_desertlands_mu5`）不会有 `server_temp/` 目录。
7. **`props/` 下的大小写跟 rsx 导出的实际文件名走**，不跟 `sprp` 里的写法：例如目录是 `mdl/imc_base/`，`sprp` 写的是 `mdl/IMC_base/...`。按模型名找文件要忽略大小写。训练场的 `collision_example\props` 已经按这个规则重新生成，内容没变，只有大小写变了。
8. **`bounds_err` 的含义改了**（列不变）：第 31 位的实例拿 detail 1 比，其余实例拿 d0∪d1 比，就是之前建议的验收方法。`has_stl`、`tris` 仍按移动规则算。
9. **`client/` 里 lump 更多**：新 rsx 训练场写 64 个，旧版是 29 个，多出来的都是非碰撞 lump。`<bsp>.bsp` 本体（渲染顶点 OBJ）和以前一样不导。碰撞用的 `000E/0010/0012/0013/0023` 和旧版逐字节相同。
10. **新增 `overview/` 和 `map_info.txt`**：`overview/wrap/resource/overviews/<map>.txt` 是地图包里 `resource/overviews/<map>.txt` 的原样导出。`pos_x` / `pos_y` / `scale` 给出小地图图片和世界坐标的对应。`map_info.txt` 把这些数和 BSP 的 worldspawn 原点 / decodeScale / 量化步长写在一起，navdemo 直接读这个文件即可。训练场没有 overview 文件（它的地图包里就没有，小地图用 `overviews/mp_rr_canyonlands_bg` 平铺背景），`map_info.txt` 里只有 BSP 那几项。

不变的：STL 是模型坐标、不乘 scale 的二进制 STL；`<模型>.stl` 是 detail 0，`<模型>_d1.stl` 是 detail 1（没有 `_d1` 就是两档同一个 part）；没有 `<模型>.stl` 的模型没有移动碰撞；`.ent` 末尾的 `\0` 已去掉，和以前一样；CSV 列不变。

导不了的图（`arena_habitat`、`olympus_mu2` 等）见下面「各图情况」。

## 一条命令

```
python -I tools\export_map_collision.py --map mp_rr_thunderdome
```

默认值：rsx 用 `D:\code\rsx\bin\Release_NoGui\rsx.exe`，pak 目录 `D:\Apex\paks\Win64`，输出到 `collision_maps\<map>\`，中间文件放在 `exported_props_physics\<map>\`。都能用 `--rsx` / `--paks` / `--out` / `--work` 改。加 `--dry-run` 只打印 rsx 命令。

用时：训练场约 15 秒，`mp_rr_olympus_mu3` 约 1.5 分钟。

脚本按顺序做六件事：

1. 用 `<map>_client_perm` + `<map>_client_temp` 导客户端 lump（过滤 `bsp_lump`），然后检查 `000E` 的 worldspawn 是否正常、`0023` 里有没有 `sprp`。不正常就停下。
2. 导 `<map>_server_temp`（不加过滤：`.ent`、`navmesh/*.nm`、AI 图、脚本）。去掉 `.ent` 末尾的 `\0`。没有这个包就跳过。
3. 从 `<map>.rpak` 导出 `resource/overviews/<map>.txt`（小地图 overview）。没有这个文件的图跳过。
4. 从 `<map>.rpak` 导所有模型的碰撞网格（`stl_respawn_physics`，按两档分文件）。
5. 找出被世界 BVH 引用、但地图包里没有的模型，从 `common_mp` / `common` / `common_early` 按名字补导。还缺的会列出来。
6. 跑 `place_prop_collision.py`：写实例表，把被引用模型的网格拷到 `props\`（这个目录每次重建），打印验收数据。

## 交付给 navdemo 的内容

```
collision_maps/<map>/
  client/wrap/maps/<bsp>.bsp.<LLLL>.client.bsp_lump
  server_temp/wrap/maps/*.ent, navmesh/<map>/*.nm, ...
  overview/wrap/resource/overviews/<map>.txt   小地图 overview（pos_x / pos_y / scale）
  map_info.txt                                  worldspawn 原点 / decodeScale / 步长 / overview 值
  props/mdl/.../<模型>.stl       detail 0
  props/mdl/.../<模型>_d1.stl    detail 1（和 detail 0 是同一个 part 时不写）
  props_world/<bsp>_props_instances.csv
```

训练场的那份在 `collision_example\`，布局相同，只是没有 `overview/`（地图包里没有这个文件）。下面这些不用再导，navdemo 不读：合并后的世界坐标 STL（`place_prop_collision.py --world-stl` 才写）、只被未引用实例用到的模型、`client_perm/`、`_pak_nostar/`、`staging_mdl_list.csv`。

STL 是模型坐标、不乘 scale 的二进制 STL。只给被世界 BVH 引用的模型，两档都给。文件名要忽略大小写匹配，例如训练场 `sprp` 里 `pelican_case_large_drabGreen` 和 `_drabgreen` 指的是同一个模型。

实例表的列：`index, model, in_bvh, has_stl, solid, flags, contents, leaf_dword, ox, oy, oz, pitch, yaw, roll, scale, tris, bounds_err`。

## navdemo 读数据的规则

已经核对过的：

- **道具下标**：`leaf_dword & 0x7FFFFFFF`。不能只取低 16 位，大图的实例数会超过 65536（`mp_rr_olympus_mu3` 有 466427 个）。
- **玩家移动碰撞**：第 31 位为 1 的实例用 `<模型>_d1.stl`，没有就用 `<模型>.stl`；其余实例用 `<模型>.stl`，没有这个文件就没有移动碰撞。navdemo 那边按引擎代码确认过。
- **摆放**：Source `AngleMatrix(pitch, yaw, roll)`，`世界 = origin + R × (scale × v)`。navdemo 用单模型网格加实例表自己拼，误差在 0.1 以内。
- **节点包围盒**：`世界 = worldspawn 原点 + q × decodeScale × 65536`。原点在 `000E` 第 0 个 dmodel 的 `+48`，decodeScale 在 `+60`。训练场是 ×2，`olympus_mu3` 是 ×4，不能写死。
- **小地图 ↔ 世界坐标**：`overview/wrap/resource/overviews/<map>.txt`（地图包里的 `resource/overviews/<map>.txt` 原样导出）。`pos_x` / `pos_y` 是图片左上角的世界坐标，`scale` 是世界单位/像素。`px = (x - pos_x) / scale`，`py = (pos_y - y) / scale`；反过来 `x = pos_x + px × scale`，`y = pos_y - py × scale`。这是**小地图图片的原点**，不是 BSP 的 worldspawn 原点（后者在 `000E` 的 `+48` / `+60`，用来还原 `0012`）。文件名按 pak/变体走，里面的根名字可能是基础图名（`mp_rr_canyonlands_hu_avt.txt` 的根是 `mp_rr_canyonlands_hu`）。
- **`map_info.txt`**：`bsp`、`sprp_version`、`worldspawn_origin`、`worldspawn_decode_scale`、`node_bounds_step`（= decodeScale × 65536），有 overview 的图还有 `overview_pos_x` / `overview_pos_y` / `overview_scale`。还原节点包围盒和顶点直接用这几个数，不用自己从 `000E` 取。

## 验收

脚本最后会打印：

```
bounds_err bit31 vs d1: ...        第 31 位的实例，detail 1 摆好后的包围盒 vs 节点框
bounds_err other vs d0+d1: ...     其余实例，d0∪d1 vs 节点框
```

正常的结果是中位数和 p95 不超过量化步长（`decodeScale × 65536`）。超过 1.5 倍步长的会单独计数，都是少数：

| 图 | 实例 / BVH 引用 / 第 31 位 | 第 31 位 vs d1 | 其余 vs d0∪d1 |
|---|---|---|---|
| 训练场（步长 2） | 10957 / 6530 / 309 | 259 个，最大 2.0 | 4597 个，p99 2.0，> 3 的 9 个 |
| `mp_rr_olympus_mu3`（步长 4） | 466427 / 189375 / 3776 | 3225 个，最大 4.0 | 124305 个，p99 9.2，> 6 的 1683 个 |

普通实例只拿 d0 去比会有大量误差，那是比较方法的问题，不是数据错了：节点框包的是两档的并集。

navdemo 那边对训练场的核对结果：旧的合并 STL 三角数等于两档之和（9,745,977）；第 31 位实例和 d1 范围吻合（p99 4.5），其余和 d0∪d1 吻合（p99 2.0）。

还会打印「BVH-referenced models with no STL」。补导之后还缺的模型，要么不在默认的三个共享包里（用 `--shared` 加包），要么模型本身没有 BVH 碰撞。

## 各图情况（v3.0.4.24，2026-11-05）

| 图 | 命令参数 | 情况 |
|---|---|---|
| `mp_rr_canyonlands_staging_mu1` | `--map mp_rr_canyonlands_staging_mu1` | 完整跑过，结果和 `collision_example\` 逐文件相同 |
| `mp_rr_olympus_mu3` | `--map mp_rr_olympus_mu3` | 完整跑过。没有 `_server_temp`，所以没有 `.nm` / `.ent` |
| `mp_lobby`、`mp_rr_divided_moon_mu1`、`mp_rr_thunderdome` | `--map <图>` | 只验过客户端 lump（两次导出相同、worldspawn 正常、有 `sprp`）。有 `_server_temp` |
| `mp_rr_desertlands_mu5` | `--map mp_rr_desertlands_mu5` | 同上，没有 `_server_temp` |
| `mp_rr_canyonlands_hu` | `--map mp_rr_canyonlands_hu_avt --server-pak mp_rr_canyonlands_hu_server_temp` | 客户端包在 `_avt` 变体下，BSP 名是 `mp_rr_canyonlands_hu_avt`，导航网格目录是 `navmesh/mp_rr_canyonlands_hu/`。只验过 lump |
| `mp_rr_tropic_island_mu2` | `--map mp_rr_tropic_island_mu2_landscape --server-pak mp_rr_tropic_island_mu2_server_temp` | 同上，用 `_landscape` 变体（另有 `_hopscotch`）。变体和 `server_temp` 是否同一张图没核对 |
| `mp_rr_olympus_mu2` | — | 客户端包只有 `(01)` 补丁，没有基础包，导不出 lump |
| `mp_rr_arena_habitat` | — | rsx 解不出 `0002` / `000E` / `002D`：前约 300 字节像没解压的数据，后面是未初始化内存，每次导出都不一样。`0023` 为空。旧版 `rsx_nogui.exe` 也一样。脚本会在第 1 步停下 |
| `mp_rr_arena_phase_runner`、`mp_rr_desertlands_hu`、`mp_rr_party_crasher` | — | 只有 server 包，没有客户端包 |

`resource/overviews/<map>.txt` 大多数图都有，会导出到 `overview/`；训练场没有（地图包里没有这个文件）。

`(NN)` 补丁不用自己指定，rsx 通过 `patch_master.rpak` 自动套到基础包上。

## 踩过的坑

- **rsx 版本**：要用 `D:\code\rsx` 编出来的 `Release_NoGui\rsx.exe`。旧发布目录的 `rsx_nogui.exe` 读不了 v21 模型，也不会按两档分文件。按两档导出是 2026-11-05 改的 `ExportPhysicsModelBVH`（`src/game/rtech/assets/model.cpp`），提交为 `c43c095`，已推到 fork `ccdescipline/rsx` 的 main。之前的版本会把所有 part 合进一个 STL。换机器或重新编译 rsx 时，要从这个提交之后的 main 编。
- **白名单**：导模型要 `--loadwhitelist mdl_,asqd,Ptch`。少了 `asqd` 会崩在 `ParseSequence`。
- **`--exportfilter`**：逗号分隔、不分大小写的子串匹配。rsx 里的资源名用反斜杠（`mdl\ola\sewer_grate_01.rmdl`），`sprp` 里是正斜杠，按完整路径过滤前要先换斜杠。
- **客户端 lump 只过滤 `bsp_lump`**：过滤 `.bsp` 会顺带导出 `.bsp` 本体（渲染顶点 OBJ，不是碰撞），这一步在 habitat 上让 rsx 崩过（`wrap.cpp` 里的 `CBSPData::Export`）。两个客户端包要放在同一次调用里。
- **`_env.ent` 末尾的 `\0`**：新 rsx 会把字符串结尾的 `\0` 也写进去，旧版不会。脚本会去掉，和 navdemo 已经在用的文件保持一致。
- **新 rsx 多写的 lump**：客户端会多写出 30 多个 lump（训练场 64 个，旧版 29 个）。碰撞相关的 `000E/0010/0012/0013/0023` 和旧版逐字节相同。

## 手动跑某一步

```
cd /d D:\Apex\paks\Win64
rsx.exe -nogui -nocachedb --loadwhitelist wrap,Ptch -export --exporttypes wrap --exportfilter bsp_lump --exportdir <out>\client <map>_client_perm.rpak <map>_client_temp.rpak
rsx.exe -nogui -nocachedb --loadwhitelist wrap,Ptch -export --exporttypes wrap --exportdir <out>\server_temp <map>_server_temp.rpak
rsx.exe -nogui -nocachedb -exportfullpaths --loadwhitelist mdl_,asqd,Ptch -export --exporttypes mdl_ --exportformat mdl_=stl_respawn_physics --exportdir <work> <map>.rpak
python -I tools\place_prop_collision.py --lumps <out>\client\wrap\maps --props <work> --map <bsp> --out <out>\props_world --deliver <out>\props
```

`place_prop_collision.py` 还能加 `--world-stl`（世界坐标合并 STL，移动规则）和 `--obj`。

## 按场地裁剪（混合模式）

混合模式的图是完整 BR 地图里的一小块，playlist 用 `cull_entity_spawn_circle "<x,y,z> r"` 圈出场地。导完标准交付后，用下面这条把世界 BVH 和道具实例裁到球内：

```
python -I tools\crop_map_collision.py --map-dir collision_maps\<bsp> --bsp <bsp> \
    --sphere cx,cy,cz,r [--sphere cx,cy,cz,r ...]
```

- `--sphere` 可重复；desertlands（fragment + monument）和风暴点（barometer + wattson）各有两个。
  没有 `cull_entity_spawn_circle` 的图（thunderdome、skulltown）不用跑，整张图就是场地。
- 世界 BVH 是**格式不变**的裁剪：不相交子节点槽的 child type 改成 `NO_CHILD`，节点/叶子/顶点数据不动。
  从 worldspawn 根节点走下来只看到球内几何；`0012` 文件大小不变。
- 实例表保留“摆好后的模型 AABB 与球相交”的实例，再并上裁剪后 BVH 仍引用的下标；`props/` 只交这些实例用到的模型。
- 会写 `cull.txt`，并在 `exported_props_physics\<bsp>\crop_original\` 留未裁剪的 `0012` 和全量实例表，可换球重裁。
- `--stats-only` 只打印裁剪统计；`--full-csv` 指定未过滤的实例表（重复裁剪时用）。
- 裁剪粒度是 BVH 子节点 AABB，球外的少量三角面会保留（训练过的 5 张图越界比例 0.02%–0.6%）。
  球的半径取实体裁剪范围，比实际可走区域略大。
