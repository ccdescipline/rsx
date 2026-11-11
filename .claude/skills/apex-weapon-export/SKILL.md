---
name: apex-weapon-export
description: Export Apex weapon scripts (WEPN assets) from common.rpak with RSX into weapon_scripts/ — scripts/weapons/*.txt, weapon_assets_list.csv, weapon_scripts_index.csv. Use when the user says 导出武器/weapon scripts, mentions weapon_scripts, WEPN, common.rpak, or weapon definitions.
---

# 武器脚本导出

所有武器脚本都在 `common.rpak` 的 WEPN 资产里；RSX 自动通过 `patch_master.rpak` 套用 `common(01).rpak`。每个 WEPN 导出成 `scripts\weapons\<name>.txt`，`sourceFilename` 是原始路径 `game/r2/scripts/weapons/<name>.txt`。

所有命令在项目根目录执行：

`D:\code\rsx`

说明见 `docs\07-weapon-scripts.md`。

## 固定路径

| 项 | 路径 |
|---|---|
| 游戏 pak | `D:\Apex\paks\Win64` |
| RSX | `D:\code\rsx\bin\Release_NoGui\rsx.exe` |
| 导出工具 | `tools\export_weapon_scripts.py` |
| 默认输出 | `weapon_scripts\` |
| 通用对比 | `tools\compare_exports.py` |

## 1. 直接导出

```bat
python -I tools\export_weapon_scripts.py
```

先看命令不执行：

```bat
python -I tools\export_weapon_scripts.py --dry-run
```

可选参数：

```bat
python -I tools\export_weapon_scripts.py --out .tmp_weapon_export
python -I tools\export_weapon_scripts.py --paks D:\Apex\paks\Win64 --pak common
```

工具做的事：

1. 在 `D:\Apex\paks\Win64` 下跑 RSX：
   `-nogui -nocachedb --parsethreads 8 --loadwhitelist wepn,Ptch --list ... --listformat csv -export --exporttypes wepn --exportdir <out>\_rsx_out common.rpak`
2. 把 `<out>\_rsx_out\weapon\<name>.txt` 移到 `<out>\scripts\weapons\`，删掉 `_rsx_out`。
3. 写 `weapon_assets_list.csv`（RSX `--list`：`type,guid,file_name,asset_name`）。
4. 写 `weapon_scripts_index.csv`（`file,asset_name,source_filename,bytes`），并检查常见枪。

## 2. 输出

```text
weapon_scripts/
  scripts/weapons/<name>.txt        324 个
  weapon_assets_list.csv            324 行数据
  weapon_scripts_index.csv          324 行数据
  rsx_export.log
```

包含 `viewkick_patterns.txt`、`springs.txt`，以及全部枪械 / 近战 / 技能 / 投掷物定义。

常见枪对照：

| 游戏名 | 文件 |
|---|---|
| Volt | `mp_weapon_volt_smg.txt` |
| R-99 | `mp_weapon_r97.txt` |
| Havoc | `mp_weapon_energy_ar.txt` |
| L-STAR | `mp_weapon_lstar.txt` |
| Devotion | `mp_weapon_esaw.txt` |
| Nemesis | `mp_weapon_nemesis.txt` |
| Flatline | `mp_weapon_vinson.txt` |
| R-301 | `mp_weapon_rspn101.txt` |

## 3. 游戏更新后的更新流程

`common.rpak` 会被 `common(01).rpak` 补丁更新。不要直接覆盖 `weapon_scripts\`，先导到临时目录比对：

```bat
python -I tools\export_weapon_scripts.py --out .tmp_weapon_export
python -I tools\compare_exports.py weapon_scripts\scripts\weapons ^
  .tmp_weapon_export\scripts\weapons --suffix .txt
```

- `changed=0`：保持 `weapon_scripts\` 不动。
- 有变化：先问用户是否覆盖，再执行默认命令更新 `weapon_scripts\`。

## 4. 验收

```bat
python -I -c "from pathlib import Path; print(len(list(Path('weapon_scripts/scripts/weapons').glob('*.txt'))))"
python -I tools\compare_exports.py weapon_scripts\scripts\weapons weapon_scripts\scripts\weapons --suffix .txt
```

检查：

- 324 个 `.txt`（游戏更新可能增减，以实际为准）。
- `weapon_scripts_index.csv` 数据行数 = `.txt` 数量。
- 每行 `source_filename` 非空，形如 `game/r2/scripts/weapons/<name>.txt`。
- `weapon_assets_list.csv` 表头 `type,guid,file_name,asset_name`。
- 常见枪 8 个都在。

## 5. 已知坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 导出 0 个 / 只有 `_rsx_out` 空目录 | RSX 太旧或 `common(01)` 没套上 | 用 `D:\code\rsx\bin\Release_NoGui\rsx.exe`；确认 `patch_master.rpak` 和 `common(01).rpak` 存在 |
| `pak not found: ...\common.rpak` | `--paks` 指错 | 默认 `D:\Apex\paks\Win64` |
| 输出路径不对 | 工具在 `cwd=paks` 下跑 RSX，`--exportdir` 要绝对路径 | 用默认 `--out` 或传绝对路径 |
| 文本里有 `// val unk` / `// child unk` | RSX 保留结构字段序号注释 | 正常，键值完整，不要删 |
| 覆盖了旧导出 | 直接跑了默认 `--out` | 先用临时目录 + `compare_exports.py` 比对 |

## 6. 汇报

给用户：

1. 导出文件数、`weapon_scripts_index.csv` 行数。
2. 与上一版对比：added / removed / changed。
3. 常见枪是否齐全。
4. 是否覆盖了 `weapon_scripts\`；如果只是核对且无变化，明确说没有覆盖。
