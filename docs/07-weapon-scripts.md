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

- `"键" "值"`；每行前的 `// val unk: N` 是引擎结构里该键的字段序号，`// child unk: N` 同理，不是数据。
- 整数、浮点按原样输出（浮点带 6 位小数）；字符串按 Unicode 输出。
- `"sourceFilename"` 和 `"weaponClassname"` 是文件头里的源路径和类名。

和 03 的游戏脚本（`wrap` 资产，原样字节）不同，WEPN 是**反序列化后重新排版**的文本；键值完整，但空白和注释不是原文件的排版。
