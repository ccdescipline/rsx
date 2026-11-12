# 武器脚本（weapon/<name>.rpak → scripts/weapons/<name>.txt）

全部武器脚本是 `common.rpak` 里的 **WEPN**（weapon definition）资产，其他包（`common_mp` / `common_early` / `server_misc` / `ai_behaviors`）里没有。

rsx 给 WEPN 资产的命名就是 `weapon/<name>.rpak`（`LoadWeaponDefinitionAsset`：`"weapon/" + header->weaponName + ".rpak"`）。每个导出文件里的 `sourceFilename` 是原始源码路径，例如：

```
"sourceFilename" "game\r2\scripts\weapons\mp_weapon_volt_smg.txt"
```

所以 IDA 里看到的 `weapon/<name>.rpak` ↔ `scripts/weapons/<name>.txt` 就是同一份数据；导出目录按后者原样摆放。

## 一条命令

```bat
python -I tools\export_weapon_scripts.py
```

默认：rsx `D:\code\rsx\bin\Release_NoGui\rsx.exe`，pak 目录 `D:\Apex\paks\Win64`，输出 `weapon_scripts\`。`--rsx` / `--paks` / `--out` / `--pak` 可改，`--dry-run` 只打印命令。

等价的 rsx：

```bat
cd /d D:\Apex\paks\Win64
rsx.exe -nogui -nocachedb --parsethreads 8 --loadwhitelist wepn,Ptch ^
    -export --exporttypes wepn --exportdir <tmp> common.rpak
```

输出在 `<tmp>\weapon\<name>.txt`，脚本会移到 `<out>\scripts\weapons\`。

## 产出

```
weapon_scripts/
  scripts/weapons/<name>.txt     324 个：全部枪械、近战、技能、投掷物、共享模式（viewkick_patterns / springs / blast_patterns ...）
  weapon_assets_list.csv         rsx --list：type,guid,file_name,asset_name
  weapon_scripts_index.csv       file ↔ asset_name ↔ source_filename ↔ bytes
  rsx_export.log                 rsx 输出
```

`--list` 的 324 条资产和 324 个文件一一对应，没有缺项；`log` 里没有 `WEPN: unknown var type`，即所有值的类型都被识别了。

## 常用枪的内部名

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

完整映射看 `weapon_scripts_index.csv` 或每个文件里的 `"sourceFilename"`。

## 格式

rsx 把 WEPN 结构还原成和源文件同构的 key/value 文本：

- `"键" "值"`，键和子块的顺序就是源文件的顺序（引擎 `KVGroup_s` 的 values / groups 按源顺序存，另有一份按 key hash 排好的下标表只用来二分查找）。2026-11-12 之前每行前有 `// val unk: N` / `// child unk: N`，那是这份下标表里的值，和内容无关，现在不再输出。
- 整数按有符号 64 位输出（之前按无符号，负数会变成 1844674407… 这种大数）；浮点用能原样读回的最短写法（`0.5`、`1e-07`，整数值写成 `1.0`），之前固定 6 位小数会把很小的值写成 `0.000000`；字符串里的 `"` 和换行会转义，反斜杠原样保留（`sourceFilename` 里的 `game\r2\...` 不变）。
- `"sourceFilename"` 和 `"weaponClassname"` 是文件头里的源路径和类名。

和 03 的游戏脚本（`wrap` 资产，原样字节）不同，WEPN 是**反序列化后重新排版**的文本；键值完整，但空白和注释不是原文件的排版。
