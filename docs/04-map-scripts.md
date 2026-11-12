# 地图脚本

每张图从 `paks\Win64` 里这几类 pak 导（有哪个导哪个）：

- `<map>.rpak`
- `<map>_client_perm.rpak`
- `<map>_client_temp.rpak`
- `<map>_server_temp.rpak`（可选）
- `_gen3` 变体（当前包没有）
- 默认**不**导 `_loadscreen`、`_server_perm`（`--all-variants` 才带）

`(01)` / `(02)` 补丁不要单独再导一遍：`patch_master` 已经会把基础包指到最新补丁。上一轮对每个 `(01)` 又跑了一次，日志显示加载的还是同一份补丁，目录是重复的。新脚本跳过这些文件名。

## 优先级（脚本里的顺序）

1. `mp_rr_desertlands_mu5`（世界尽头）
2. `mp_rr_tropic_island_mu2_landscape`（风暴点 / control_barometer）
3. `mp_rr_canyonlands_staging_mu1`
4. `mp_rr_olympus_mu3`
5. `mp_rr_canyonlands_hu_avt_uh_night`
6. 其余 `mp_rr_*`，然后 `mp_lobby*`

## 产出布局

每个 pak 一个目录：

```
exported_maps/<pak_stem>/
  wrap/scripts/vscripts/...     # 脚本。RSX 写成 cl_<map>.client.nut
  rson/<GUID>.rson              # 按 GUID 命名，Scripts 列表用引擎原名
exported_maps/_meta/lists/<pak>.csv
exported_maps/_meta/logs/<pak>.export.log
exported_maps/_meta/map_scripts_report.csv
```

RSON 里是：

```
Scripts:
[
    mp/levels/cl_mp_rr_desertlands_mu5.nut
    mp/cl_lasermesh.gnut
]
```

对应导出：

`wrap/scripts/vscripts/mp/levels/cl_mp_rr_desertlands_mu5.client.nut`

（client_perm / client_temp → `.client.nut`，server_temp → `.server.nut`）

地图**脚本几乎都在** `_client_perm` / `_server_temp`。基础 `<map>.rpak` 通常只有 rson、没有 wrap 脚本。

## 命令

```bat
python tools/export_map_scripts.py
python tools/export_map_scripts.py --dry-run
python tools/export_map_scripts.py --only mp_rr_desertlands_mu5
python tools/export_map_scripts.py --scripts-only
python tools/export_map_scripts.py --no-bsp
python tools/export_map_scripts.py --skip mp_lobby_server_temp
python tools/export_map_scripts.py --from-existing
```

`--scripts-only` 加 `--exportfilter scripts\vscripts`，只导脚本。`--no-bsp` 用 `--exportfilter scripts\vscripts,0x`，导脚本 + rson、跳过 BSP lump：旧 RSX 对单独的地图 pak 会尝试导出 BSP，缺 lump 时直接 exit 1，所以 2026-11 更新后地图脚本用这个模式。2026-11-12 起 RSX 缺 lump 时只跳过那个 `.bsp`（日志 `BSP: not exporting ...`），不再退出，但 `--no-bsp` 仍然推荐（BSP 本体是渲染顶点 OBJ，没用）。

`--skip <pak>` 按 pak 名精确跳过；`--only` 会把同名的 `_client_perm` / `_server_temp` 一起带进来，需要排除时用 `--skip`。默认和上一轮一样导全部 `wrap,rson`（当前 RSX 会因 BSP 失败，建议加 `--no-bsp`）。

等价单图：

```
rsx.exe -nocachedb --loadwhitelist wrap,rson,Ptch
  -export --exporttypes wrap,rson
  --exportdir exported_maps\mp_rr_desertlands_mu5_client_perm
  D:\Apex\paks\Win64\mp_rr_desertlands_mu5_client_perm.rpak
```

## 上一轮结果（已在磁盘上）

`exported_maps/` 下 64 个 pak 目录、51 个逻辑名。其中 29 个目录有 `.nut`。

有 `cl_<map>.client.nut` 的图（client_perm）包括：desertlands_mu5、tropic_island_mu2_landscape、canyonlands_staging_mu1、olympus_mu3、canyonlands_hu_avt_uh_night，以及 district / divided_moon / thunderdome / skulltown / holiday 等。

`--from-existing` 会扫这些目录，写出 `map_scripts_report.csv`：每个 pak 的 wrap 脚本数、rson 里列出的脚本、对不上的名字、`cl_*` 文件。
