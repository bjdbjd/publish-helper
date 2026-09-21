# Publish Helper v2.0.0

> 本次为大版本更新：核心层完成结构重组（`core/tool.py` 拆分为按领域的模块）、
> API 层修复一批安全与契约缺陷、新增交互式 CLI。**升级前请先读下面的「升级须知」**。

---

## ⚠️ 升级须知（老用户必读）

### 1. PT-Gen 接口地址已变更 —— 不改会直接不可用

默认接口由

```
旧：https://api.iyuu.cn/App.Movie.Ptgen
新：https://pt-gen.hares.dpdns.org/api/getData
```

**如果你沿用旧的 `static/settings.json`**，「获取 PT-Gen 简介」会失败，因为旧地址已失效。

处理办法（二选一）：

1. 打开软件 → 设置页 → 把 **PT-Gen 接口地址** 改成上面的新地址；
2. 或删除 `static/settings.json` 让软件重建默认配置，再重新填自己的设置。

> 本版本**不会**自动覆盖你已有的 `settings.json`（升级不抹配置），
> 所以这一步需要你手动完成。

### 2. `auto_feed_link` 默认值是占位地址，必须替换

`settings.json` 中 `auto_feed_link` 的默认值为：

```
https://example.com/upload.php#separator#name#linkstr#{主标题}#linkstr#...
```

其中 `https://example.com/upload.php` 是**占位符，不是真实站点**。请整体替换为你自己
PT 站提供的 auto_feed 地址，否则「一键上传」生成的链接无效。

> 文件里若看到 `\u4e3b\u6807\u9898` 这种写法，那是 JSON 的 Unicode 转义，
> 读出来就是 `{主标题}`，属正常现象，**不要手动改成中文**。

### 3. 应用数据目录变了（仅影响安装包用户）

打包版首次启动会在**可执行文件所在目录**创建 `static/`、`media/`、`temp/`、`logs/`。
请把程序放在有写入权限、不会被系统清理的目录（如 `D:\PublishHelper\`），
不要放 `C:\Program Files\` 或临时目录。

---

## ✨ 新增

- **交互式 CLI**：`python src/main_cli.py` 提供命令行一键发布工作流。
- **新版 PT-Gen 服务**：接入带 HMAC 签名的新接口，并兼容旧接口自动判定。
- **PT-Gen 签名密钥配置**：设置页可填签名密钥，备用接口允许留空。
- **自动下载并上传豆瓣海报**。
- **API 可选鉴权 + CORS 收窄**：设 `API_AUTH_TOKEN` 后全端点要求
  `Authorization: Bearer <token>`；`API_CORS_ORIGINS` 可收白名单。**默认均关闭，向后兼容**。

## 🐛 修复

### 安全

- **media 目录越权读写（严重）**：越界检查原用字符串 `startswith` 比较，
  `../media_evil` 这类**前缀相同的兄弟目录可绕过**，实现越权读写。
  已改为 `os.path.commonpath` 按路径分隔符边界判断（13 处）。
  同时修正了 `moveFileToFolder` 相对路径一律被拒、以及空路径校验分支恒不成立的死代码问题。

- **`/api/getFile` 文件鉴权加固**：改用 `TEMP_DIR` 基准 + `Path.resolve` 解析软链 +
  `parents` 边界判断，杜绝前缀绕过与目录逃逸。

- **登录态安全修正（前端站点）**：上述越权影响所有暴露 API 的部署，
  建议尽快升级。

### 核心层

- **`text.py` 字典字面量被注释打断**：`‘` 的取值变成了注释文本，且 `’` 根本不是键（非法中文引号处理错误）。
- **`chinese_to_int` 万进位错误**：`十二万` 得到 `20010`，正确为 `120000`。
- **`get_video_info` 高度检查写错**：`other_width` 误写成 `other_height`，导致竖屏资源分辨率误标。
- **`rename_file` 重复追加扩展名**：`z.mkv` 会变成 `z.mkv.mkv`。
- **`480P` 被误判为 `480i`**。
- **PT-Gen 地址缺 scheme 时拼出双 `/api/getData`**（必然 404）。
- **`get_thumbnail` 在 `video_capture` 为 `None` 时抛 `AttributeError`** 穿透。
- **`settings.update_all_settings` 改为合并语义**：少传一个键不再永久丢键。

### GUI

- **短剧页签 4 处跨页签写错**：截图路径误写进电影控件、重命名读错剧集的季数控件
  （`episodesStartBoxPlaylet` 此前从未被读取）、PT-Gen 回调误调电影版处理器。
- **截图多线程上传乱序**：信号加序号，按槽位收集后统一回填。
- **设置窗口重复弹出**：`actionsettings.triggered` 被重复 connect。
- **窗口图标丢失**：图标原用相对路径，从非项目根目录启动时静默失效。

### API 契约

- `getPtGenInfo` 的 `message` / `statusCode` 互换。
- `getPTGenInfoByResourceUrl` 返回未解包的元组。
- `media/file/list` 失败分支键名与成功分支不一致（`description` → `fileList`）。
- `createHardLink` 未判定成功即执行后续操作。
- `getPlayletDescription` 省略 `seasonNumber` 不再 500（默认第 1 季）。
- 鉴权失败 `statusCode` 统一为 `UNAUTHORIZED`；注册 404/405 处理器，
  未知路径与错误方法也返回统一 JSON 包络。

## 🔧 变更（可能影响脚本调用方）

- **`core/tool.py` 已删除**，按领域拆分为 `data` / `text` / `video` / `torrent` /
  `settings_tool` / `picturebed` / `ptgen` 等模块。**如果你 import 过 `src.core.tool`，需要改导入路径。**
- **API 参数现可放 body**：新增兼容式载荷解析（JSON body 优先，回退 form / query），
  旧 query 用法仍兼容。
- `autoHandleVideo` 由 GET 改 POST（副作用语义，仓库内无调用方）。
- 异常响应不再回传原始异常文本，改为统一提示「详情请查看服务端日志」。

## 📦 产物

| 平台 | 文件 |
|---|---|
| Windows x64 | `Publish.Helper.v2.0.0.windows-x64.zip`（内含 `Publish Helper.exe`） |
| macOS arm64 | `Publish.Helper.v2.0.0.macos-arm64.zip`（内含 `Publish Helper.app`） |
| Linux x64 | `Publish.Helper.v2.0.0.linux-x64.zip` |

压缩包内附 **`首次运行必读.txt`**，含上述升级步骤与目录说明。

### 服务端（Docker）

```bash
docker pull <your-registry>/publish-helper:2.0.0
```

Linux 需系统库 `libmediainfo0v5` / `libzen0v5`（镜像内已装）。

## 🧪 测试

- 测试套件 **420 条通过**（1 条因 Windows 无 symlink 权限跳过），覆盖 24 个测试文件。
- 新增 `tests/test_api_bug_locks.py` 锁定上表各缺陷回归。
- 打包产物经**真实安装验证**：干净目录启动、`static/` 播种、
  **设置修改后重启不丢失**（升级不覆盖用户配置）。

## 📄 许可证

GPLv3。完整协议见 `LICENSE`。
