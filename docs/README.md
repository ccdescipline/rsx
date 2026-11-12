# Apex RPak 导出

用 `D:\code\rsx\bin\Release_NoGui\rsx.exe` 从 `D:\Apex\paks\Win64` 导资源。RSX 会自动读同目录的 `patch_master.rpak`，把 `foo.rpak` 打成最新的 `foo(NN).rpak`。

工具脚本在 `tools/`。公共参数：

```
--rsx <rsx.exe>
--paks <Win64 目录>
--out <导出根目录>
--from-existing    不跑 RSX，只根据已有文件重建表
--dry-run          只打印命令
```

| 文档 | 脚本 | 现有产出 |
|------|------|----------|
| [01 赛季 GUID / SAID](01-season-guids.md) | `tools/export_season_guids.py` | `exported_seasons/season_guids.csv` |
| [02 排位周期 SAID](02-ranked-periods.md) | `tools/export_ranked_periods.py` | `exported_seasons/ranked_period_saids.csv` |
| [03 游戏脚本](03-game-scripts.md) | `tools/export_game_scripts.py` | `exported/wrap/scripts/vscripts/` |
| [04 地图脚本](04-map-scripts.md) | `tools/export_map_scripts.py` | `exported_maps/<pak>/wrap/` `rson/` |
| [05 碰撞和导航网格](05-collision-navmesh.md) | 原理和格式；道具摆放 `tools/place_prop_collision.py` | `collision_example/`（训练场） |
| [06 换图导出碰撞数据](06-map-collision-export.md) | `tools/export_map_collision.py --map <图>` | `collision_maps/<图>/` |
| [07 武器脚本](07-weapon-scripts.md) | `tools/export_weapon_scripts.py` | `weapon_scripts/scripts/weapons/` |

辅助脚本：`tools/bvh_decode.py`（按引擎解碰撞 BVH：packed 顶点、凸包、地形 heightfield，`crop_map_collision.py` / `place_prop_collision.py` 用它）、`tools/compare_weapon_scripts.py`（按值比较两次武器导出，区分格式变化和真实改动）、`tools/compare_exports.py`（按文件哈希比较两次导出）。

`--rsx` 默认是本仓库的 `bin\Release_NoGui\rsx.exe`，`--paks` 默认 `D:\Apex\paks\Win64`，可用环境变量 `APEX_PAKS` 改。

一次性重跑（按顺序，2 依赖 1 的 common 解包缓存不是必须）：

```bat
python tools/export_season_guids.py
python tools/export_ranked_periods.py
python tools/export_game_scripts.py
python tools/export_map_scripts.py
```

地图导出要对每个 pak 调一次 RSX，最久。可先 `--dry-run` 或 `--only mp_rr_desertlands_mu5`。

## Skills

| Skill | 用途 |
|---|---|
| `apex-script-export` | 游戏脚本 + 地图脚本 + 武器核对 |
| `apex-map-collision-export` | 地图碰撞（navdemo）+ mixtape 裁剪 |
| `apex-weapon-export` | 武器脚本 WEPN 导出 |

入口在 `.claude/skills/<name>/SKILL.md`。下次直接说“游戏更新了，导出脚本”/“导出碰撞”/“导出武器”，或调用对应的 `/skill-name`。
