# 排位周期 SAID

不要猜路径。根资源是和赛季同一个 pak 里的：

`settings/base_itemflavors.rpak`

两个数组：

| 数组 | 用途 |
|------|------|
| `ranked2Pt0Periods` | Ranked 2.0，现在排位用。S17–S19 一季一条；S20 起每赛季 split1 + split2 |
| `calevents` | 老日历事件。按 `itemType` 筛：`calevent_rankedperiod`（S13 前那套 BR 排位，实际数组里是 S2–S16）、`calevent_arenas_ranked_period`、赛季、登录活动、apex cup 等 |

对数组里每条 `flavor` 再导一次 stgs，读名字和 `+40` uniqueId。顺手记下：

- `parentItemFlavor`：Ranked 2.0 指回所属 `seasonNN.rpak`
- `split2StartTime`：只有 split 2 有值
- `rankv2split`：`0` 整季，`1`/`2` 两个 split

## 命令

```bat
python tools/export_ranked_periods.py
```

一次 RSX 把根资源、ranked2pt0、calevent、apex cup container 都导出来，再按两个数组过滤建表。

```
rsx.exe ... --loadwhitelist stgs,stlt,Ptch -export --exporttypes stgs
  --exportfilter "base_itemflavors,ranked2pt0,itemflav\calevent,ranked_event_container"
  D:\Apex\paks\Win64\common.rpak
```

```bat
python tools/export_ranked_periods.py --from-existing
```

## 产出

| 文件 | 内容 |
|------|------|
| `exported_seasons/settings/base_itemflavors.json` | 根数组 |
| `exported_seasons/settings/itemflav/ranked2pt0/*.json` | Ranked 2.0 |
| `exported_seasons/settings/itemflav/calevent/rankedseason*.json` 等 | 老周期 |
| `exported_seasons/ranked_period_saids.csv` | 排位三张表 |
| `exported_seasons/ranked_and_calevents_full.csv` | 两个数组全量（含杯赛、里程碑） |

当前：Ranked 2.0 **25** 条，老 BR **15** 条（rankedseason02–16，没有 S1），竞技场 **6** 条（s10–s15）。

### Ranked 2.0

| asset | SAID | split | parent | split2StartTime |
|-------|------|-------|--------|-----------------|
| rankedperiod17 | SAID01711148254 | 0 | season17 | |
| rankedperiod18 | SAID01068186165 | 0 | season18 | |
| rankedperiod19 | SAID00254133756 | 0 | season19 | |
| rankedperiod20_split1 | SAID00400418920 | 1 | season20 | |
| rankedperiod20_split2 | SAID01350373342 | 2 | season20 | 2024-03-26 |
| rankedperiod21_split1 | SAID00635449927 | 1 | season21 | |
| rankedperiod21_split2 | SAID00969954275 | 2 | season21 | 2024-06-25 |
| rankedperiod22_split1 | SAID00858846781 | 1 | season22 | |
| rankedperiod22_split2 | SAID00517565421 | 2 | season22 | 2024-09-17 |
| rankedperiod23_split1 | SAID00034291796 | 1 | season23 | |
| rankedperiod23_split2 | SAID01865753387 | 2 | season23 | 2024-12-17 |
| rankedperiod24_split1 | SAID01737407620 | 1 | season24 | |
| rankedperiod24_split2 | SAID00596849492 | 2 | season24 | 2025-03-25 |
| rankedperiod25_split1 | SAID01471048100 | 1 | season25 | |
| rankedperiod25_split2 | SAID00954004831 | 2 | season25 | 2025-06-24 |
| rankedperiod26_split1 | SAID00116541249 | 1 | season26 | |
| rankedperiod26_split2 | SAID01577556661 | 2 | season26 | 2025-09-16 |
| rankedperiod27_split1 | SAID01474911493 | 1 | season27 | |
| rankedperiod27_split2 | SAID00342389537 | 2 | season27 | 2025-12-16 |
| rankedperiod28_split1 | SAID02050380540 | 1 | season28 | |
| rankedperiod28_split2 | SAID01572602493 | 2 | season28 | 2026-03-24 |
| rankedperiod29_split1 | SAID01939154007 | 1 | season29 | |
| rankedperiod29_split2 | SAID01863850050 | 2 | season29 | 2026-06-23 |
| rankedperiod30_split1 | SAID02098434896 | 1 | season30 | |
| rankedperiod30_split2 | SAID00056765722 | 2 | season30 | 2026-09-15 |

### 老 BR（`calevent_rankedperiod`）

| asset | SAID |
|-------|------|
| rankedseason02 | SAID00747315762 |
| rankedseason03 | SAID00091805734 |
| rankedseason04 | SAID00609587000 |
| rankedseason05 | SAID00638209737 |
| rankedseason06 | SAID01826354644 |
| rankedseason07 | SAID00461784517 |
| rankedseason08 | SAID01162744308 |
| rankedseason09 | SAID01649072598 |
| rankedseason10 | SAID01091892544 |
| rankedseason11 | SAID01007141711 |
| rankedseason12 | SAID01547807959 |
| rankedseason13 | SAID02144147554 |
| rankedseason14 | SAID01733022993 |
| rankedseason15 | SAID00102643758 |
| rankedseason16 | SAID02005235415 |

### 竞技场（`calevent_arenas_ranked_period`）

| asset | SAID |
|-------|------|
| rankedarenass10 | SAID00926519318 |
| rankedarenas11 | SAID00781342567 |
| rankedarenas12 | SAID00170407135 |
| rankedarenas13 | SAID00224037796 |
| rankedarenas14 | SAID00310546825 |
| rankedarenas15 | SAID00058416642 |

`calevents` 里其余类型（赛季、milestone、apex cup container、sku store 等）在 `ranked_and_calevents_full.csv`。
