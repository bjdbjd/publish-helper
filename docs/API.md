# Publish Helper API 接口文档

> 本文档是 **Flask REST API**（`src/api/startapi.py`，28 个路由）的接口级参考，
> 面向**调用方**（客户端 / 脚本 / 集成）。每个路由给出：方法、参数、请求示例、响应结构、状态码。
>
> - 想看「实现细节、已知 bug、测试覆盖」→ [`BUSINESS_LOGIC.md §5`](BUSINESS_LOGIC.md#5-api-接口清单srcapistartapipy2517-行)
> - 想启动服务 → `python src/main_api.py`（默认端口 `15372`，见 [`DEVELOPMENT.md`](DEVELOPMENT.md)）
>
> 本文档描述的是 **v2.0.0** 代码行为。如与运行时代码不符，以代码为准并请提交修正。

---

## 目录

- [1. 通用约定](#1-通用约定)
- [2. 媒体信息](#2-媒体信息)
- [3. 媒体文件操作](#3-媒体文件操作)
- [4. 图片上传](#4-图片上传)
- [5. PT-Gen 简介](#5-pt-gen-简介)
- [6. 命名模板](#6-命名模板)
- [7. 种子制作](#7-种子制作)
- [8. 设置](#8-设置)
- [9. 下拉数据](#9-下拉数据)
- [10. 文件下载](#10-文件下载)
- [11. 自动处理（一键发布）](#11-自动处理一键发布)

---

## 1. 通用约定

### 1.1 基地址与端口

```
GET/POST http://localhost:15372/api/...
```

端口来自 `static/settings.json` 的 `api_port`（默认 `15372`），host 来自环境变量 `API_HOST`（默认 `0.0.0.0`）。

### 1.2 请求参数：query / form / JSON body 三种写法都行

`GET` 通常用 query 字符串；`POST` 支持 JSON body **或** 表单 **或** query。内部统一经 `_payload()` 解析：**JSON body 优先，其次 form，最后 query**。

```bash
# 三种等价（以 getMediaInfo 为例）
curl "http://localhost:15372/api/getMediaInfo?path=视频.mkv"
curl -X POST "http://localhost:15372/api/getMediaInfo" -d "path=视频.mkv"
curl -X POST "http://localhost:15372/api/getMediaInfo" \
     -H "Content-Type: application/json" -d '{"path": "视频.mkv"}'
```

### 1.3 响应包络

所有端点（除 `getFile` 直接回二进制）返回统一 JSON：

```json
{ "data": { ... }, "message": "...", "statusCode": "..." }
```

### 1.4 鉴权（默认关闭）

设环境变量 `API_AUTH_TOKEN` 后，**所有端点**要求：

```bash
curl -H "Authorization: Bearer <API_AUTH_TOKEN>" "..."
```

未设 token 或 token 错误 → `401` / `statusCode: UNAUTHORIZED`。默认**不设该变量，服务完全开放**（向后兼容）。

CORS：默认 `*`。可设 `API_CORS_ORIGINS`（逗号分隔白名单）收窄。

### 1.5 `path` 参数与 media 边界

所有接受文件/目录路径的路由都以 **`media/`** 目录为根，且参数是**相对 media 的**：

- 传 `path=视频.mkv` → 实际操作 `media/视频.mkv`
- 传入 `../`、绝对路径等**逃逸 media** 的写法 → `401` / `UNAUTHORIZED`
- `path` 为空/缺省 → `422` / `MISSING_REQUIRED_PARAMETER`

例外：`getFile` 以 `temp/` 为根（见 [§10](#10-文件下载)）；`uploadPicture` 接受任意存在路径（见 [§4](#4-图片上传)）。

### 1.6 状态码 ↔ statusCode 速查

| HTTP | statusCode | 含义 |
|---|---|---|
| 200 | `OK` | 成功 |
| 200 | `OK`（`media/file/list`） | 成功列出目录（空 path = 列 media 根） |
| 400 | `BACKEND_PROCESSING_ERROR` | 后端处理失败（截图/上传/重命名/解析等） |
| 401 | `UNAUTHORIZED` | 越权访问 media 外 / token 错误 |
| 404 | `NOT_FOUND` | 未注册路由 |
| 404 | `FILE_NOT_FOUND` | `getFile` 目标文件不存在 |
| 405 | `METHOD_NOT_ALLOWED` | 方法不对 |
| 422 | `MISSING_REQUIRED_PARAMETER` | 缺少必填参数 |
| 422 | `PARAMETER_RANGE_ERROR` | 参数不在白名单 |
| 422 | `VALUE_RANGE_ERROR` | 数值越界 |
| 422 | `VALUE_RELATIONSHIP_ERROR` | 数值关系错误（如起>止） |
| 422 | `RUNTIME_ERROR` | `autoHandleVideo` 参数/取值错误 |
| 500 | `GENERAL_ERROR` | 未预期异常（详情只在服务端日志） |
| 500 | `RUNTIME_ERROR` | `autoHandleVideo` 运行时失败（已记日志） |

> 不含自动生成的 405/404：已注册错误处理器，`OPTIONS` 之外的方法与未知路径也返回统一 JSON 包络。

### 1.7 常用 GET 参数类型

路由内用 `_payload().get(key, default, type=str)` 取参，很多数字参数虽是字符串传输但会被转 `int`/`float`。文档中「类型」列给出**逻辑类型**；传非数字会导致 `500 / GENERAL_ERROR`。

---

## 2. 媒体信息

### 2.1 `GET /api/getMediaInfo`

读取指定视频/文件夹的 **MediaInfo 文本**。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `path` | ✓ | string | — | 相对 `media/` 的视频文件或目录 |

**成功 `200`：**

```json
{ "data": { "mediaInfo": "General\n...", "videoPath": "media/视频.mkv" }, "message": "获取MediaInfo成功。", "statusCode": "OK" }
```

**失败**：越权→`401`；缺 path→`422`；路径不存在→`422 FILE_PATH_ERROR`；解析失败→`400 BACKEND_PROCESSING_ERROR`；异常→`500`。

---

### 2.2 `GET /api/getVideoInfo`

读取视频的**关键参数**（分辨率/编码/色深/HDR/帧率/音频等）。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `path` | ✓ | string | — | 相对 `media/` |

**成功 `200`：**
`data` 含：`videoPath, videoFormat, videoCodec, bitDepth, hdrFormat, frameRate, audioCodec, channels, audioNum`（`videoFormat` 如 `1080p`，`bitDepth` 如 `10bit`）。

> ⚠️ **这些字段是「命名口径」**：`bitDepth`/`hdrFormat`/`frameRate`/`audioNum`/`channels` 会经缩写表
> （`src/core/data.py`）筛除默认值 —— `8 bits`、`30.000 FPS`、单音轨等会被**刻意映射为空串**，
> 因为 PT 发布命名惯例不写默认值。空的字段**不代表获取失败**。
>
> 若需**如实展示**真实规格，用 `data.raw`（原始值，未经缩写筛除）：
> `{ videoFormatRaw, videoCodecRaw, bitDepthRaw, hdrFormatRaw, frameRateRaw, audioCodecRaw, channelsRaw, audioNumRaw }`，
> 例如 `bitDepthRaw: "8 bits"`、`frameRateRaw: "30.000 FPS"`、`audioNumRaw: "1"`。

**失败**：同 `getMediaInfo`（越权/缺参/路径不存在/解析失败/异常对应 `401/422/422/400/500`）。

---

### 2.3 `GET /api/getScreenshot`

对视频按百分比区间截取**多张截图**。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `path` | ✓ | string | — | 相对 `media/` 的视频 |
| `screenshotStoragePath` |  | string | `temp/pic`(设置) | 截图保存目录（相对） |
| `screenshotNumber` |  | int | `3`(设置) | 张数，**1-5** |
| `screenshotThreshold` |  | float | `30.0`(设置) | 关键帧阈值 |
| `screenshotStartPercentage` |  | float | `0.10`(设置) | 起始点，(0,1) |
| `screenshotEndPercentage` |  | float | `0.90`(设置) | 终止点，(0,1) |
| `screenshotMinIntervalPercentage` |  | float | `0.01` | 最小帧间隔 |

**成功 `200`：** `data: { screenshotNumber: "3", screenshotPath: ["shot.png", ...], videoPath: "..." }`
（`screenshotPath` 是相对 `media/` 的路径数组；`screenshotNumber` 是**字符串**，取实际张数。）

**失败**：越权→`401`；缺 path→`422`；路径不存在→`422`；数量>5 或 <1→`422 VALUE_RANGE_ERROR`；起/止不在(0,1)→`422 VALUE_RANGE_ERROR`；起>止→`422 VALUE_RELATIONSHIP_ERROR`；截图失败→`400`；异常→`500`。

---

### 2.4 `GET /api/getThumbnail`

生成一张**缩略图**（行列网格拼图）。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `path` | ✓ | string | — | 相对 `media/` 的视频 |
| `screenshotStoragePath` |  | string | `temp/pic`(设置) | 保存目录 |
| `thumbnailRows` |  | int | `3`(设置) | 行数，>0 |
| `thumbnailCols` |  | int | `3`(设置) | 列数，>0 |
| `screenshotStartPercentage` |  | float | `0.10`(设置) | 起始点 |
| `screenshotEndPercentage` |  | float | `0.90`(设置) | 终止点 |

**成功 `200`**：`data: { thumbnailPath: "th.jpg", videoPath: "..." }`

**失败**：越权→`401`；缺参→`422`；行列≤0→`422 VALUE_RANGE_ERROR`；起/止越界→`422 VALUE_RANGE_ERROR`；起>止→`422 VALUE_RELATIONSHIP_ERROR`；失败→`400`；异常→`500`。

---

### 2.5 `GET /api/getTotalEpisode`

统计文件夹内视频的**集数区间**。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `folderPath` | ✓ | string | — | 相对 `media/` 的**文件夹** |
| `episodeStartNumber` |  | int | `1` | 起始集号 |

**成功 `200`**：`data: { totalEpisode: "全3集" | "第5-7集" | "第5集" }`

| episodeStartNumber / 文件数 | 结果 |
|---|---|
| start=1 | `全N集` |
| start≠1 且 N>1 | `第start-(start+N-1)集` |
| start≠1 且 N=1 | `第start集` |

**失败**：越权→`401`；缺/空 path→`422`；路径不存在→`422`；非文件夹→`400 BACKEND_PROCESSING_ERROR`；异常→`500`。

---

## 3. 媒体文件操作

### 3.1 `GET /api/media/file/list`

列出目录内容（名称 / 大小 / 类型）。**空 path 即列出 media 根目录**（返回 `200`）。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `path` |  | string | "" | 相对 `media/` 的目录，空=根 |

**成功 `200`：**

```json
{ "data": { "fileList": [ { "name": "视频.mkv", "size": "1.23 GB", "type": "文件" }, { "name": "剧集", "size": "N/A", "type": "文件夹" } ] }, "message": "获取成功", "statusCode": "OK" }
```

`size` 经 `convert_size()` 转可读格式；`type` 为 `文件` / `文件夹`。

**失败**：越权→`401`；目录异常→`500 GENERAL_ERROR`（`data.fileList: []`）。

---

### 3.2 `POST /api/renameFolder`

重命名**文件夹**。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `folderPath` | ✓ | string | 相对 `media/` 的文件夹 |
| `newFolderName` | ✓ | string | 新名称 |

**成功 `200`**：`data: { newFolderPath: "新名" }`（相对 `media/`）
**失败**：越权→`401`；缺/空参数→`422`；路径不存在→`422`；失败→`400`；异常→`500`。

---

### 3.3 `POST /api/renameFile`

重命名**单个文件**。`newFileName` 已带扩展名时**不会重复追加**扩展名。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `filePath` | ✓ | string | 相对 `media/` 的文件 |
| `newFileName` | ✓ | string | 新名称（可带扩展名） |

**成功 `200`**：`data: { newFilePath: "新名.ext" }`
**失败**：同上（越权/缺参/不存在/失败/异常 → `401/422/422/400/500`）。

---

### 3.4 `POST /api/createHardLink`

创建**硬链接**。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `path` | ✓ | string | 相对 `media/` 的目标 |

**成功 `200`**：`data: { hardLinkPath: "目标-hardlink.ext" }`（仅成功时裁剪为相对路径）
**失败**：越权→`401`；空→`422`；不存在→`422`；失败→`400`；异常→`500`。

---

### 3.5 `POST /api/moveFileToFolder`

把文件**移动**进指定文件夹。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `filePath` | ✓ | string | 相对 `media/` 的文件 |
| `folderName` | ✓ | string | 目标文件夹名 |

**成功 `200`**：`data: { newFilePath: "..." }`
**失败**：越权→`401`；缺 filePath/folderName→`422`；filePath 不存在→`422`；失败→`400`；异常→`500`。

---

### 3.6 `POST /api/renameEpisode`

**批量重命名**一个文件夹内的剧集（如 `S01E01.mkv` …），并顺带重命名文件夹。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `folderPath` | ✓ | string | — | 相对 `media/` 的**文件夹** |
| `newFileName` | ✓ | string | — | 含 `{集数}` 占位符（会被替换为补零集号） |
| `episodeStartNumber` |  | int | `1` | 起始集号 |

**成功 `200`**：`data: { newFolderPath: "..." }`（相对 `media/`，去掉前导 `/`）
**失败**：越权→`401`；缺参→`422`；不存在→`422`；**传了文件而非文件夹**→`400 "不支持文件路径"`；某个文件重命名失败→抛 `OSError`→`500`；异常→`500`。

---

## 4. 图片上传

### 4.1 `POST /api/uploadPicture`

把本地图片上传到图床，返回 BBCode 与裸 URL。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `picturePath` | ✓ | string | — | **任意**存在图片的本地路径（非 media 相对） |
| `pictureBedApiUrl` |  | string | 设置值 | 图床 API URL |
| `pictureBedApiToken` |  | string | 设置值 | 图床 Token |

**成功 `200`：**

```json
{ "data": { "pictureBbCode": "[img]https://.../1.png[/img]", "pictureUrl": "https://.../1.png" }, "message": "上传图片成功。", "statusCode": "OK" }
```

> `pictureUrl` = `pictureBbCode[5:-6]`（去掉 `[img]` 与 `[/img]`）。

**失败**：缺 `picturePath`→`422`；路径不存在→`422 FILE_PATH_ERROR`；上传失败→`400`；异常→`500`。

---

## 5. PT-Gen 简介

### 5.1 `GET /api/getPtGenDescription`

调用 PT-Gen 生成简介文本。可顺带自动下载并上传豆瓣海报（当设置 `auto_download_upload_poster` 为真）。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `resourceUrl` | ✓ | string | — | 豆瓣 / IMDB 资源链接 |
| `ptGenApiUrl` |  | string | 设置值 | PT-Gen 接口地址 |

**成功 `200`：**

```json
{ "data": { "description": "◎片　　名　...", "posterUrl": "https://..." }, "message": "获取PT-Gen简介成功。", "statusCode": "OK" }
```

**失败**：缺 `resourceUrl`→`422`；PT-Gen 调用失败→`400`；异常→`500`。

---

### 5.2 `GET|POST /api/getPlayletDescription`

本地拼装**短剧**简介（不调用网络）。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `originalTitle` | ✓ | string | — | 剧名 |
| `year` |  | string | "" | 年份 |
| `area` |  | string | "" | 产地 |
| `category` |  | string | "" | 类型 |
| `language` |  | string | "" | 语言 |
| `seasonNumber` |  | int | `1` | 季号（不传按第 1 季，不追加「第N季」） |

**成功 `200`**：`data: { playletDescription: "\n◎片　　名　...\n◎年　　代　..." }`
**失败**：缺 `originalTitle`→`422`；异常→`500`（如 `seasonNumber` 为非数字）。

---

### 5.3 `GET|POST /api/getPtGenInfo`

从一段 **PT-Gen 简介文本**解析出关键字段（主演 / 别名合并为 `/` 分隔字符串，别名末尾去掉最后一个 ` /`）。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `description` | ✓ | string | PT-Gen 简介文本 |

**成功 `200`**：`data: { originalTitle, englishTitle, year, otherTitles, category, actors }`
**失败**：缺 `description`→`422`；解析异常→`500`。

---

### 5.4 `GET /api/getPTGenInfoByResourceUrl`

一步到位：给链接 → 取简介 + 解析关键字段。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `resourceUrl` | ✓ | string | — | 资源链接 |
| `ptGenApiUrl` |  | string | 设置值 | PT-Gen 接口地址 |

**成功 `200`**：`data: { originalTitle, englishTitle, year, otherTitles, category, actors, description }`
**失败**：缺 `resourceUrl`→`422`；调用失败→`400`；异常→`500`。

---

## 6. 命名模板

### 6.1 `GET|POST /api/getNameFromTemplate`

按模板与字段生成标题 / 副标题 / 文件名。**模板必须命中白名单**，否则 `422 PARAMETER_RANGE_ERROR`。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `template` | ✓ | string | 模板名：`main_title_movie` / `main_title_tv` / `main_title_playlet` / `second_title_movie` / `second_title_tv` / `second_title_playlet` / `file_name_movie` / `file_name_tv` / `file_name_playlet` |
| `englishTitle` / `originalTitle` / `season` / `year` / `videoFormat` / `source` / `videoCodec` / `bitDepth` / `hdrFormat` / `frameRate` / `audioCodec` / `channels` / `audioNum` / `team` / `otherTitles` / `seasonNumber` / `totalEpisode` / `playletSource` / `category` / `actors` |  | string | 模板占位符对应的字段值 |

**成功 `200`**：`data: { name: "..." }`（`englishTitle` 会先经 `delete_season_number` 去掉季后缀）
**失败**：缺 `template`→`422`；模板不在白名单→`422 PARAMETER_RANGE_ERROR`；其余异常→`500`。

> **英文名自动兜底**：`englishTitle` 为空且 `originalTitle` 是中文时，后端会自动用汉语拼音
> （`fill_english_title` → `chinese_name_to_pinyin`）作为英文名，无需调用方处理；显式传入
> `englishTitle` 时不会被覆盖。同一兜底也应用于 `/api/autoHandleVideo`。
> 前端若要给用户**预览/编辑**拼音建议，可先调 `GET|POST /api/chineseNameToPinyin`。

---

### 6.2 `GET|POST /api/chineseNameToPinyin`

中文原名 → 汉语拼音（供未获取到英文名时给出建议）。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `originalTitle` | ✓ | string | 中文原名 |

**成功 `200`**：`data: { pinyin: "Nian Hui Bu Neng Ting! 2" }`
**失败**：缺 `originalTitle`→`422 MISSING_REQUIRED_PARAMETER`；异常→`500`。

---

## 7. 种子制作

### 7.1 `POST /api/makeTorrent`

为文件/文件夹制作 `.torrent`。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `path` | ✓ | string | — | 相对 `media/` 的文件或目录 |
| `torrentStoragePath` |  | string | 设置值 | 种子保存目录（相对） |

**成功 `200`**：`data: { torrentPath: "..." }`
**失败**：越权→`401`；缺 path→`422`；不存在→`422`；制作失败→`400`；异常→`500`。

---

## 8. 设置

### 8.1 `GET /api/settings`

读取**全部**设置。

**成功 `200`**：`data: { settings: { ...38 键... } }`

### 8.2 `POST /api/settings/update`

用 **JSON body** 更新全部设置，**合并语义**（只覆盖传入的键，其余保留）。

```bash
curl -X POST "http://localhost:15372/api/settings/update" \
     -H "Content-Type: application/json" \
     -d '{"api_port": "15372", "screenshot_number": "3"}'
```

**成功 `200`**：`data: {}`
**失败**：body 非 JSON / 异常→`500`。

### 8.3 `GET /api/getSettings`（单键查询）

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `settingsName` | ✓ | string | 设置键名，如 `api_port` |

**成功 `200`**：`data: { settingsData: "15372" }`（注意布尔键返回字符串，见 BUSINESS_LOGIC §1.4）
**失败**：缺 `settingsName`→`422`；异常→`500`。

### 8.4 `POST /api/updateSettings`（单键更新）

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `settingsName` | ✓ | string | 设置键名 |
| `settingsData` | ✓ | string | 新值 |

**成功 `200`**：`data: {}`
**失败**：缺任一→`422`；异常→`500`。

> 三处写法：`GET /api/settings`（全量读）、`POST /api/settings/update`（合并写，JSON body）、`GET/POST /api/getSettings|updateSettings`（按名称单键读写，可走 query）。实际写 `settings.json` 的是 `POST /api/settings/update` 与 `POST /api/updateSettings`。

---

## 9. 下拉数据

### 9.1 `GET /api/getComboBoxData`

读取下拉框候选数据（来源 / 小组 / 短剧来源）。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `configurationName` | ✓ | string | 取值：`source` / `team` / `playlet-source`，否则 `422 PARAMETER_RANGE_ERROR` |

**成功 `200`**：`data: { configurationData: "..." }`

### 9.2 `POST /api/updateComboBoxData`

更新下拉数据。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `configurationName` | ✓ | string | `source` / `team` / `playlet-source` |
| `configurationData` | ✓ | string | 新数据（多值用**真实换行**，非字面 `\n`） |

**成功 `200`**：`data: {}`；缺参/越界→`422`；失败→`400`；异常→`500`。

---

## 10. 文件下载

### 10.1 `GET /api/getFile`

**唯一返回二进制而非 JSON** 的端点：按 `filePath` 下载文件（附 `Content-Disposition: attachment`）。

| 参数 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `filePath` | ✓ | string | **相对 `temp/`**（不是 media）的文件路径 |

> 基准是 `config.TEMP_DIR`（项目根 `temp/`），经 `Path.resolve()` + `parents` 边界判断防目录逃逸。

**行为**：越权（不在 `temp/` 下）→`401 UNAUTHORIZED`；缺参→`422`；文件不存在→`404 FILE_NOT_FOUND`；成功→ `200` 文件内容；异常→`500`。

---

## 11. 自动处理（一键发布）

### 11.1 `POST /api/autoHandleVideo`

**最重的端点，副作用极大**：一次完成「取简介 + 截图上传 + 缩略图上传 + 命名 + 重命名 + 制作种子 + 返回全套发布数据」。**会改动磁盘上的文件和目录**（重命名、塞文件夹、删截图），慎用。

- `category=Movie|TV`：简介走 PT-Gen（需 `resourceUrl`）。
- `category=Playlet`（短剧）：简介由本地表单字段拼装（**不需要** `resourceUrl`），跳过视频参数解析与非短剧的「分析关键参数」，并对文件夹内剧集做批量重命名（同 TV）。

**流式返回（NDJSON）**：HTTP 恒为 `200`，响应体是逐行的 JSON——每到一个阶段边界输出一条进度事件，最后输出结果/错误包络。每行用 `\n` 分隔：

```jsonc
{"type":"progress","stage":"PT_GEN_FETCH","label":"获取PT-Gen简介","percent":9,"message":"正在获取PT-Gen简介"}   // 进度行（11 个 stage，顺序见后端 _AUTO_HANDLE_STAGES）
{"data":{...},"message":"获取成功。","statusCode":"OK"}                                                      // 末行：结果包络（statusCode 判成败）
```

前端以 `statusCode` 判成败；校验失败（缺参/越权）也会作为一条错误包络输出（HTTP 仍为 200），不再单独 4xx。

| 参数 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `resourceUrl` | Movie/TV ✓ | string | — | 豆瓣 / IMDB 链接（短剧不需要） |
| `path` | ✓ | string | — | 相对 `media/`（Movie=文件或目录，TV/Playlet=**必须文件夹**） |
| `source` | Movie/TV ✓ | string | — | 资源来源（短剧用「资源来源」，对应模板 `{source}`） |
| `team` | ✓ | string | — | 制作组（含 `AGSV` 自动加标签 `官方`,`冰种`） |
| `category` | ✓ | string | — | `Movie` / `TV` / `Playlet`（→电影 / 剧集 / 短剧） |
| `season` |  | string | `1` | 季号 |
| `episodesStartNumber` |  | int | `1` | 起始集号（TV 分支内部实际硬编码为 1） |
| `originalTitle` | Playlet ✓ | string | — | 短剧名称（短剧必填，用于拼简介与命名） |
| `year` |  | string | — | 短剧年份 |
| `area` |  | string | — | 短剧产地 |
| `language` |  | string | — | 短剧语言 |
| `playletSource` |  | string | — | 短剧来源（模板 `{playlet_source}`） |
| `categories` |  | string | — | 短剧类型勾选串（如 `恐怖 / 动作`，模板 `{categories}`） |
| `seasonNumber` |  | string | — | 短剧季数（拼接简介用） |
| `coverPath` |  | string | — | 短剧封面（相对 `media/`），上传图床后追加到简介；越权→`UNAUTHORIZED`，**上传失败不中断发布**（仅跳过封面） |

**成功**（末行 `statusCode=OK`）：`data` 为 camelCase 字段，主要含：
`resourceUrl, area, audioCodec, audioNum, bitDepth, category, channels, description, doubanUrl, fileName, frameRate, hdrFormat, imdbUrl, mediaInfo, medium, mainTitle, newPath, raw, secondTitle, source, tags[], team, torrentFileUrl, videoCodec, videoFormat`。

其中：
- `newPath`（相对 `media/`）是重命名后磁盘上的新路径，供前端回写 `flow.path`（一键发布会改名磁盘，前端路径会过期）。
- `raw` 是未做命名缩写筛除的原始规格 dict（`videoFormatRaw`/`bitDepthRaw`/`frameRateRaw`/…，同 `/api/getVideoInfo` 的 `data.raw`），供前端如实展示真实参数——命名口径字段（`bitDepth`/`frameRate`/…）会按 PT 惯例把默认值置空，前端展示卡用 `raw` 回退。

> ⚠️ 已知限制（v2.0.0）：TV 分支 `episodes_start_number` 被硬编码为 `1`，传入的 `episodesStartNumber` 被忽略。

---

## 附录 A：路由速查表

| 方法 | 路径 | 摘要 | 需 `path`(media) |
|---|---|---|---|
| GET | `/api/getMediaInfo` | MediaInfo 文本 | ✓ |
| GET | `/api/getVideoInfo` | 视频关键参数 | ✓ |
| GET | `/api/getScreenshot` | 多张截图 | ✓ |
| GET | `/api/getThumbnail` | 单张缩略图 | ✓ |
| GET | `/api/getTotalEpisode` | 集数区间 | ✓(folder) |
| GET | `/api/media/file/list` | 列目录 | ✓(可空) |
| POST | `/api/renameFolder` | 重命名文件夹 | ✓ |
| POST | `/api/renameFile` | 重命名文件 | ✓ |
| POST | `/api/createHardLink` | 建硬链接 | ✓ |
| POST | `/api/moveFileToFolder` | 移入文件夹 | ✓ |
| POST | `/api/renameEpisode` | 批量重命名剧集 | ✓ |
| POST | `/api/uploadPicture` | 上传图床 | ✗（任意本地路径） |
| GET | `/api/getPtGenDescription` | PT-Gen 简介 | ✗ |
| GET/POST | `/api/getPlayletDescription` | 短剧简介 | ✗ |
| GET/POST | `/api/getPtGenInfo` | 解析简介字段 | ✗ |
| GET | `/api/getPTGenInfoByResourceUrl` | 链接→简介+字段 | ✗ |
| GET/POST | `/api/getNameFromTemplate` | 模板命名 | ✗ |
| POST | `/api/makeTorrent` | 制作种子 | ✓ |
| GET | `/api/settings` | 读全部设置 | ✗ |
| POST | `/api/settings/update` | 合并写设置 | ✗ |
| GET | `/api/getSettings` | 单键读 | ✗ |
| POST | `/api/updateSettings` | 单键写 | ✗ |
| GET | `/api/getComboBoxData` | 读下拉数据 | ✗ |
| POST | `/api/updateComboBoxData` | 写下拉数据 | ✗ |
| GET | `/api/getFile` | 下载文件（temp/） | ✗（temp/） |
| GET/POST | `/api/chineseNameToPinyin` | 中文原名→拼音 | ✗ |
| POST | `/api/getAutoFeedLink` | 生成 auto_feed 链接 | ✗ |
| POST | `/api/autoHandleVideo` | 一键自动发布 | ✓ |

共 **28** 个路由。