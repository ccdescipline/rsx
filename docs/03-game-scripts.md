# 游戏脚本（client / ui / server）

全局 Squirrel 脚本在这些 pak 里，不是地图 pak：

| pak | 内容 |
|-----|------|
| `script_client.rpak` + `script_client(01).rpak` | 客户端 `*.client.nut` / `.gnut` |
| `script_ui.rpak` + `script_ui(01).rpak` | UI `*.ui.nut` / `.gnut` |
| `script_server.rpak` | 服务端 `*.server.nut` / `.gnut`（当前包没有 `(01)`） |

类型是 `wrap`。引擎里文件名是 `foo.nut.client`，RSX 默认倒成 `foo.client.nut`（`Wrap_GetPathWithSwappedExtensions`）。两种是同一个文件。

上一轮手工导出只用了目录里那 4 个 client/ui rpak，结果在：

`exported/wrap/scripts/vscripts/`

1665 个文件：997 client + 668 ui，没有 server。

## 命令

```bat
python tools/export_game_scripts.py
```

会从 `D:\Apex\paks\Win64` 导 client + ui + server。只要 client/ui（和原来一样）：

```bat
python tools/export_game_scripts.py --no-server
```

等价 RSX：

```
rsx.exe -nocachedb --loadwhitelist wrap,rson,Ptch
  -export --exporttypes wrap --exportfilter "scripts\vscripts"
  --exportdir exported
  script_client.rpak script_ui.rpak script_server.rpak
```

`Ptch` 仍然要带，client/ui 的 `(01)` 才会套上。

如果 `patch_master` 指向 `script_server(01).rpak`、但客户端安装里没有这个补丁文件，工具会自动把 server 单独从临时目录无补丁导出，日志写到 `rsx_game_scripts_server.log`，资源清单合并回 `game_scripts_assets.csv`。

## 产出

| 路径 | 内容 |
|------|------|
| `exported/wrap/scripts/vscripts/**/*.client.nut` | 客户端 |
| `exported/wrap/scripts/vscripts/**/*.ui.nut` | UI |
| `exported/wrap/scripts/vscripts/**/*.server.nut` | 服务端（默认导） |
| `exported/game_scripts_inventory.csv` | 清单 |
| `exported/game_scripts_assets.csv` | RSX 资源列表 |

和排位/赛季对账时常用的脚本也在这里，例如 `sh_items.*.gnut`、`sh_ranked.*.gnut`、`sh_cal_events.*.gnut`、`sh_stats_ranked`（若存在）。
