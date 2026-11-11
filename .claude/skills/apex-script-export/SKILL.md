---
name: apex-script-export
description: Export Apex Legends scripts with RSX after a game update — game scripts (client/ui/server), map scripts (wrap+rson), and optional weapon-script verification. Use when the user says 游戏更新了/导出脚本, or mentions exported_YYYYMMDD, exported_maps_YYYYMMDD, rsx, rpak, script_client, script_ui, script_server.
---

# Apex 脚本导出

游戏更新后重新导出 `exported_<日期>/` 和 `exported_maps_<日期>/`。所有命令都在项目根目录执行：

`D:\code\rsx`

日期用导出当天，例如 `20261111`；把下面命令里的 `YYYYMMDD` 换成它。不要覆盖已有的日期目录。

## 固定路径

| 项 | 路径 |
|---|---|
| 游戏 pak | `D:\Apex\paks\Win64` |
| RSX | `D:\code\rsx\bin\Release_NoGui\rsx.exe` |
| 游戏脚本工具 | `tools\export_game_scripts.py` |
| 地图脚本工具 | `tools\export_map_scripts.py` |
| 武器脚本工具 | `tools\export_weapon_scripts.py` |
| 文档 | `docs\03-game-scripts.md`、`docs\04-map-scripts.md` |

## 0. 先确认更新内容

```powershell
Get-ChildItem D:\Apex\paks\Win64\patch_master.rpak,
  D:\Apex\paks\Win64\script_client*.rpak,
  D:\Apex\paks\Win64\script_ui*.rpak,
  D:\Apex\paks\Win64\script_server*.rpak |
  Select-Object Name, Length, LastWriteTime
```

- `patch_master.rpak` 和 `(01)` 补丁时间是更新标志。
- `script_server(01).rpak` 可能不存在，这是正常的，工具会自动处理。
- 不要单独导 `(01)` pak；RSX 会通过 `patch_master` 自动套用。

## 1. 游戏脚本

```bat
python -I tools\export_game_scripts.py --out exported_YYYYMMDD
```

- 默认导 client + ui + server。
- 如果 `patch_master` 指向 `script_server(01).rpak` 但文件不存在，工具会自动把 server 复制到临时目录、无 `patch_master` 导出，再合并 `game_scripts_assets.csv`；日志会多一个 `rsx_game_scripts_server.log`。
- 只要 client+ui 时加 `--no-server`。
- 预期产出（2026-11-11 基线）：2391 个脚本（client 999 / ui 676 / server 716），`game_scripts_inventory.csv`、`game_scripts_assets.csv`。

## 2. 地图脚本

先找出需要 `--skip` 的 pak：

```bat
python -I .claude\skills\apex-script-export\scripts\find_unpatched.py
```

输出形如：

```text
--skip mp_rr_divided_moon_mu1_server_temp
--skip mp_lobby_server_temp
```

脚本用 `patch_master` 里的 `.rpak` 名字做启发式判断；每行一个 `--skip`，全部原样追加到下面的命令里。如果漏报，RSX 会在该 pak 上报 `PTCH: Using patch file ...` 后 exit 1，把对应 stem 加进 `--skip` 重跑即可。

然后导出（建议后台跑，68 个 pak 约 10–20 分钟）：

```bat
python -I tools\export_map_scripts.py --no-bsp ^
  --skip <上面列出的 stem> ^
  --out exported_maps_YYYYMMDD
```

- `--no-bsp` 使用 `--exportfilter scripts\vscripts,0x`：导脚本 + rson、跳过 BSP lump。**必须加**；当前 RSX 对单独的 `_client_perm` pak 会尝试导 BSP，缺 lump 时 exit 1。
- 不要用 `--only` 排除 pak：`--only mp_rr_xxx` 会把同名的 `_client_perm` / `_server_temp` 一起带进来；要排除用 `--skip`。
- 导出完成后重建报告（包含被 `--skip` 的目录）：

```bat
python -I tools\export_map_scripts.py --from-existing --out exported_maps_YYYYMMDD
```

预期：

- 68 个 pak 目录、145 个文件左右：81 个 `.nut/.gnut` + 64 个 `.rson`（2026-11-11 基线）。
- `_meta\map_scripts_report.csv` 68 行，`missing_from_rson` 全空。
- `_meta\lists\` 68 份、`_meta\logs\` 68 份。
- 不应有 `.bsp` 文件。

## 3. 武器脚本（可选核对）

`common.rpak` 也会被 `common(01).rpak` 补丁更新。先导到临时目录比对，不要直接覆盖：

```bat
python -I tools\export_weapon_scripts.py --out <临时目录>
python -I tools\compare_exports.py ^
  weapon_scripts\scripts\weapons <临时目录>\scripts\weapons --suffix .txt
```

- `changed=0`：保持 `weapon_scripts\` 不动。
- 有变化：先问用户是否覆盖，再更新 `weapon_scripts\`。

## 4. 校验与新旧对比

游戏脚本：

```bat
python -I tools\compare_exports.py ^
  exported_<旧日期>\wrap exported_<新日期>\wrap --suffix .nut --suffix .gnut
```

地图脚本：

```bat
python -I tools\compare_exports.py ^
  exported_maps_<旧日期> exported_maps_<新日期> --suffix .nut --suffix .gnut
```

再检查日志：

```bat
findstr /i "failed error" exported_maps_YYYYMMDD\_meta\logs\*.log
```

只有 `pc_all(03).starpak` 缺失这类 warning 可以忽略（不影响脚本/rson）。

## 5. 汇报

给用户：

1. 游戏脚本总数、client/ui/server 数量。
2. 变化文件清单（按 client/ui/server 分组）。
3. 地图 pak 数、脚本数、rson 数、`missing_from_rson` 是否为 0。
4. 地图脚本有无内容变化；rson 新增数量。
5. 武器脚本是否变化。
6. 本次遇到的坑（缺 server 补丁、BSP、starpak warning）。

## 已知坑

| 现象 | 原因 | 处理 |
|---|---|---|
| `PTCH: Using patch file "script_server(01).rpak"` 后 exit 1 | 客户端安装没有 server 补丁 | 工具已自动 fallback；手工时把 server 复制到无 `patch_master` 的临时目录，用 `--loadwhitelist wrap,rson` 导 |
| `BSP: Map ... expected lump ID ...` 后 exit 1 | 单独地图 pak 缺 BSP lump | 加 `--no-bsp` |
| `--only` 带出了 `_server_temp` | `--only` 按前缀匹配同族 pak | 用 `--skip <stem>` 精确排除 |
| `Failed to open StarPak file "pc_all(03).starpak"` | 客户端缺 starpak 补丁 | warning，脚本/rson 正常，可忽略 |
| 导入错模块 / 同名 py 抢先加载 | 没用 `-I`，当前目录的 py 文件被优先导入 | 一律 `python -I ...` |
| 地图导出很慢 | 每张图单独跑一次 RSX | 后台运行，不要在前台等 |

## 不要做的事

- 不要覆盖已有的 `exported_<日期>` / `exported_maps_<日期>`。
- 不要单独导 `(01)` / `(02)` pak；`patch_master` 会套用。
- 不要用项目根目录的 `rsx.exe`（旧版），用 `D:\code\rsx\bin\Release_NoGui\rsx.exe`。
- 不要把地图导出改成 `--exporttypes wrap,rson` 全量（会碰 BSP）。
