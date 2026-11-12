# 混合模式（mixtape）碰撞导出 — 2026-11-07

来源：`playlists_r5.txt` 的 `PlaylistRotation mixtape_rotation`（9 个 `mix_s_*` playlist），
外加同一批 map defaults 的私人对局。去重后是 5 个地图 lump；每个 lump 只保留
playlist 里 `cull_entity_spawn_circle` 圈出的场地范围。

## 5 个 lump 与场地

| 目录 | 地图 | 场地（map_location） | playlist | cull 球 (x,y,z,r) |
|---|---|---|---|---|
| `mp_rr_desertlands_mu5` | 世界尽头 | fdm_fragment | mix_s_tdm_fragment | 9186, 5536, -3324, 9000 |
| | | gun_run_monument | mix_s_gungame_monument | 3915, 9918, -3940, 8000 |
| `mp_rr_tropic_island_mu2_landscape` | 风暴点 | control_layout_barometer | mix_s_control_barometer | -16000, -22000, 1000, 15000 |
| | | fdm_wattson | mix_s_gungame_wattson | 8320, -18184, 798, 9000 |
| `mp_rr_divided_moon_mu1` | 破碎月 | control_layout_production | mix_s_control_production | -32590, -3912, 4235, 15000 |
| `mp_rr_thunderdome` | 雷霆穹顶 | fdm_ / control_layout_cntrl_ / gr_thunderdome | tdm + control + gungame | 无（整张图） |
| `mp_rr_freedm_skulltown` | 骷髅镇 | skulltown | tdm + gungame | 无（整张图） |

desertlands 和 tropic 各含两个不连续的场地，放在同一个目录里，`cull.txt` 记录了球心。
navdemo 也可以按 `cull.txt` / playlist 的球自行拆分。

## 裁剪做法

1. **世界 BVH（`0012`）**：从 worldspawn 根节点遍历，用每个子节点槽自带的 int16 AABB
   （还原：`worldspawn 原点 + q × decodeScale × 65536`）和 cull 球做相交测试。不相交的
   子节点把 child type 改成 `NO_CHILD (1)`，节点/叶子/顶点数据不动。这样从根节点走下来
   只看得到球内几何，文件格式完全合法，`0012` 文件大小不变（不可达的数据保留）。
2. **道具实例表**：保留“摆好后的模型 AABB 与球相交”的实例，再并上裁剪后 BVH 仍引用的
   所有实例（避免边界上 CSV 少行、BVH 引用了不存在的下标）。
3. **`props/`**：只交保留实例用到的模型（<名>.stl / <名>_d1.stl），每次重建。

球是按 `cull_entity_spawn_circle` 取的实体裁剪范围，比实际可走区域略大，属于保守裁剪。
裁剪粒度是 BVH 子节点 AABB；未命中球的三角面只占保留量的 0.02%–0.6%。

## 校验结果

> 2026-11-12 注：下表「保留三角面」是旧版 `crop_map_collision.py` 算的。旧版解 packed 顶点（按无符号 × 0xFFFF × 步长）、
> 类型 8 凸包（顶点偏移多读 12 字节）和四边形（第二个三角形拆错）都有问题，也不解地形 heightfield（类型 10），
> 所以三角面数和球内/越界比例只能当参考。裁剪本身（按节点框改 `NO_CHILD`）不受影响，`0012` 不用重做；
> 想要准确的数，用新版脚本加 `--stats-only` 重算一遍。道具 STL 因为 rsx 的 packed 顶点修复需要重新导（见 06）。

| 目录 | 实例 保留/总数 | 裁剪后 BVH 引用 | 裁剪掉的子节点槽 | 保留三角面（球内 / 越界） | 道具 STL |
|---|---|---|---|---|---|
| mp_rr_divided_moon_mu1 | 37,377 / 378,122 | 17,107 | 17,001 | 245,953 (244,442 / 1,511) | 1,218，58.6 MB |
| mp_rr_tropic_island_mu2_landscape | 60,063 / 460,439 | 31,664 | 24,486 | 364,684 (364,021 / 663) | 1,331，62.9 MB |
| mp_rr_desertlands_mu5 | 34,116 / 370,833 | 17,038 | 17,400 | 405,081 (404,988 / 93) | 1,226，46.0 MB |
| mp_rr_thunderdome | 12,489 / 12,489 | 7,915 | 0（整图） | — | 876，48.1 MB |
| mp_rr_freedm_skulltown | 24,849 / 24,849 | 16,640 | 0（整图） | — | 804，27.2 MB |

用 `place_prop_collision.py` 对裁剪后的 lump 复算，`bounds_err` 仍在量化步长 2 附近：
divided moon 最大 2.7；desertlands 最大 5.9（>3 的 4 个）；tropic 最大 8.9（>3 的 14 个）；
thunderdome 最大 51.7（>3 的 44 个）；skulltown 最大 32.0（>3 的 35 个）。这些是少数
异常模型，和全图导出时一致，不是裁剪引入的。

## 目录内容

```
collision_maps/<bsp>/
  client/wrap/maps/<bsp>.bsp.<LLLL>.client.bsp_lump   # 0012 已按球裁剪
  server_temp/...                                      # 有 _server_temp 包才写
  overview/wrap/resource/overviews/<bsp>.txt           # 小地图 overview（pos_x/pos_y/scale）
  map_info.txt                                         # worldspawn 原点/decodeScale/步长/overview 值
  props/...                                            # 只含保留实例引用的模型，两档
  props_world/<bsp>_props_instances.csv                # 已过滤
  cull.txt                                             # 球心/半径和裁剪统计
```

- 5 张图都有 `overview/wrap/resource/overviews/<bsp>.txt`（`pos_x` / `pos_y` / `scale` 是小地图图片到世界坐标的变换）；训练场 `collision_example` 没有，地图包里就没有这个文件。
- 有 `.nm` 的图：broken moon 用 `control_layout_production_*.nm`；风暴点用
  `control_layout_barometer_*.nm` / `fdm_wattson_*.nm`；雷霆穹顶用
  `fdm_thunderdome_*.nm` / `control_layout_cntrl_thunderdome_*.nm` / `gr_thunderdome_*.nm`。
- `mp_rr_desertlands_mu5`、`mp_rr_olympus_mu3` 类图没有 `_server_temp`，所以没有 `.nm` / `.ent`；
  skulltown 也没有 `_server_temp`。
- `client/` 其余 lump（渲染顶点等）和裁剪前逐字节相同；navdemo 不读的可以直接忽略。
- `000E` 里 worldspawn 的 mins/maxs 仍是整张父图的范围（裁剪只动 `0012` 的子节点槽）；
  导航网格范围请按 `cull.txt` 的球或裁剪后实际遍历到的几何来定。
- 未裁剪的 `0012` 备份在 `exported_props_physics/<bsp>/crop_original/`，实例全表在
  `exported_props_physics/<bsp>/crop_original/instances_full.csv`，可换球重裁。

## 命令

```
python -I tools\export_map_collision.py --map mp_rr_divided_moon_mu1
python -I tools\crop_map_collision.py --map-dir collision_maps\mp_rr_divided_moon_mu1 ^
    --bsp mp_rr_divided_moon_mu1 --sphere -32590,-3912,4235,15000
```

`--stats-only` 只算不写；`--sphere` 可重复；`--full-csv` 指向未过滤的实例表。
