# Publish Helper 业务逻辑与测试要点文档

> 目标读者：后续编写测试的开发者。
> 本文档以「业务逻辑契约 + 函数级断言点」为核心，覆盖 `src/core/*`（11 个核心模块）、`src/gui/startgui.py`（3 个页签业务流程）、`src/api/startapi.py`（26 个路由）、`static/` 数据文件与 `src/config/settings.py`，并给出「现有测试覆盖明细」与「未覆盖（gap）清单」两份矩阵。
> 约定：测试一律断言 **返回元组**，不依赖领域层异常（例外见 §1.2）。

---

## 1. 横切契约（所有测试的地基，先读这一节）

### 1.1 返回约定：`(success, payload)` 二元组

几乎**所有核心函数**返回 2 元组 `(success: bool, payload)`：

- 失败时 `payload` 为**中文错误字符串**（个别为 `[字符串]` 单元素列表）；
- 成功时 `payload` 为有用值：
  - `(True, [paths])`：`get_video_files`、`get_screenshot`（绝对 PNG 路径列表）、`get_combo_box_data`；
  - `(True, str)`：`get_thumbnail`（缩略图路径）、`get_media_info`（论坛格式文本）、`rename_file/rename_folder/move_file_to_folder/create_hard_link`（新路径）、`make_torrent`（种子路径）、`upload_picture`（bbcode）、`get_auto_feed_link`（链接）、`download_poster`（保存路径）等；
  - `(True, (format_data, data))` **嵌套元组**：`get_pt_gen_description`（格式化简介 + 原始 JSON 字典）。

**例外——直接返回非元组的核心函数**：
- `check_path_and_find_video(path) -> (int, str)`：三态码 `1=文件且是视频 / 2=文件夹中找到首个视频 / 0=错误`；
- `get_pt_gen_info(...) -> 8 元组`（原样解包，无 success 位）；
- `get_data_from_pt_gen_description(...) -> 8 元组`；
- `get_playlet_description(...) -> str`（固定模板字符串）；
- `get_poster_url_from_data(data) -> str`（空串表示未找到）；
- `get_settings / get_settings_json / update_settings* / is_filename_too_long / extract_numbers / chinese_to_int / base64encoding / natural_keys / int_to_* / validate_and_convert_to_int / combine_directories / get_abbreviation / load_names / approximate_resolution_by_width / load_min_widths_from_json / generate_image_filename` 等工具型函数。

### 1.2 领域层几乎不抛异常

- **`ConfigurationError`**（`src/core/settings_tool.py`）：settings 文件 JSON 损坏 / 不可写时抛（`_read_settings` / `_write_settings`）。
- **`ValueError`**：
  - `rename_folder`：路径非目录时 `raise ValueError('提供的路径不是一个目录或不存在')`（唯一"故意抛给调用方"的领域函数，API 路由靠它走 500 分支）；
  - `make_torrent`：路径不存在 / 空目录时 `raise ValueError(...)` 但**在函数内部被捕获**，仍返回 `(False, str(e))`；
  - `text.py::validate_and_convert_to_int`：空值 / 非数字时抛 `ValueError`。
- **`FileNotFoundError`**：`file_utils.py::get_file_hash` 文件不存在时抛。
- `src/utils/exceptions.py` 的 `PublishHelperError → ConfigurationError/MediaInfoError/ScreenshotError/ImageUploadError/TorrentError/PTGenError/RenameError/ValidationError` 层级**基本是死代码**——领域代码从不抛这些类型。**测试断言元组，不要 `pytest.raises(MediaInfoError)` 之类。**

### 1.3 设置优先级

`环境变量（key 大写） > static/settings.json > 调用方 default 参数`（见 `SettingsManager.get_setting`）。布尔设置经 `_BOOL_KEYS`（12 键）归一：字符串 `'True'/'False'/''` → 真 bool（`''` → `False`）；非布尔键保持字符串原样。

```python
_BOOL_KEYS = {auto_upload_screenshot, delete_screenshot, do_get_thumbnail, enable_api,
              make_dir, media_info_suffix, open_auto_feed_link, paste_screenshot_url,
              rename_file, create_hard_link, second_confirm_file_name, auto_download_upload_poster}
```

### 1.4 路径解析约定

- `combine_directories(path)` = `os.path.join(os.getcwd(), path)`（**cwd 相对**；`settings_tool.py` 与 `file_utils.py` 各有一份等价实现）。测试必须 `monkeypatch` cwd 或显式给绝对路径。
- `static/` 是项目根 `static/` 目录（`config.STATIC_DIR = BASE_DIR/"static"`），**不是** `src/static/`。
- `media/` 是 API 的资源根：`config.MEDIA_DIR = BASE_DIR/"media"`。
- `temp/` 有 `pic/`、`torrent/` 子目录，供截图与种子输出（`config.get_temp_pic_dir()/get_temp_torrent_dir()`）。

### 1.5 API 的 media 根域隔离

所有"文件类"API 把 `path` join 到 `media/` 后 `os.path.abspath`，再 `startswith(media_path)` 检查，不通过 → HTTP 401，JSON `statusCode='UNAUTHORIZED_ACCESS_ERROR'`。**`/api/getFile` 例外**：以 `config.TEMP_DIR` 为基准，用 `Path.resolve()` + `parents` 成员判断（详见 §5.3）。

### 1.6 断言模板（建议测试风格）

```python
from src.core.video import check_path_and_find_video

def test_xxx(tmp_path):
    ok, payload = check_path_and_find_video(str(tmp_path))
    assert ok is True        # 或 assert ok is False
    assert isinstance(payload, list)  # 或 str
    # 错误串断言：assert payload == '文件夹中没有符合类型的视频文件'
```

---

## 2. 核心模块业务逻辑（src/core）

### 2.1 video.py —— 视频路径判定与文件列举

| 项 | 内容 |
|---|---|
| 常量 | `VIDEO_EXTENSIONS` 11 种，**大小写不敏感**：`['.mp4','.m4v','.avi','.flv','.mkv','.mpeg','.mpg','.rm','.rmvb','.ts','.m2ts']`；`MIN_WIDTHS = {'9600':'8640p','4608':'4320p','3200':'2160p','2240':'1440p','1600':'1080p','900':'720p','533':'480p'}` |
| `check_path_and_find_video(path) -> (int, str)` | 业务职责：判定路径指向"文件视频 / 文件夹内首个视频 / 错误"。前置清理：去末尾 `/`；去开头 `file:///`。返回值：`(1, path)` 文件且符合视频类型；`(2, path+'/'+file)` 文件夹内首个匹配；三条错误消息：`'路径下获取到文件{path}，但该文件不符合视频类型'`、`'文件夹中没有符合类型的视频文件'`、`'您提供的路径{path}既不是文件也不是文件夹'` |
| `get_video_files(folder_path) -> (bool, list)` | 遍历目录收集视频文件，`list.sort(key=natural_keys)` **自然序**（EP2 < EP10）；无效目录不抛异常，返回 `(False, [f'错误：{e}'])` —— **错误包在单元素列表里** |
| `is_filename_too_long(filename) -> bool` | `len(filename) > 250` 返回 True（Windows 255 上限减后缀留余量） |
| `delete_season_number(title, season_number) -> str` | 移除**标题末尾**的季数后缀（不误伤中间数字）。候选后缀按长度降序匹配：`' Season N'/' season N'/' SeasonN'/' seasonN'/' N'/' N罗马数'/' N特殊罗马数(Ⅰ..Ⅹ)'`。**测试用例**：`"Ni Hao 1983"` + season='1' 应原样保留（不得变成 `"Ni Hao983"`）；`"Movie Season 1"` → `"Movie"` |

**测试要点**：三态码三个分支 + 三种中文消息；`file:///`、末尾 `/` 归一；自然排序（`['EP1','EP2','EP10']`）；错误入 `[列表]` 的形状；250 边界（251 True / 250 False）；`delete_season_number` 优先级（`' Season 1'` 必须先于 `' 1'` 匹配）。

### 2.2 screenshot.py —— 截图与缩略图（非确定性，必须 mock）

| 项 | 内容 |
|---|---|
| `get_screenshot(video_path, screenshot_path, screenshot_number, screenshot_threshold, screenshot_start, screenshot_end, screenshot_min_interval=0.01) -> (bool, list)` | 输出目录不存在则 `os.makedirs`（`PermissionError→(False,['权限不足，无法创建目录'])`、`FileExistsError→(False,['路径已存在，且不是目录'])`、其它→`(False,[f'创建目录时出错：{e}'])`）；`cv2.VideoCapture` 打不开→`(False,['无法加载视频'])`；`start_frame=int(total*screenshot_start)`、`end_frame=int(total*screenshot_end)`、`screenshot_min_interval = duration * min_interval`（**分数→秒**）；`timestamps = sorted(random.sample(range(start,end), number))`；逐帧取 `std=np.std(frame)`，满足 `std > threshold` **且** `current_time >= last_keyframe_time + interval` 才取为关键帧，否则**用 `random.sample(...,1)` 随机帧兜底**；成功返回 `(True, extracted_images)`（绝对 PNG 路径列表）；任何其它异常→`(False,[f'截图出错：{e}'])`，**含 `sample>population` 的 `ValueError`** |
| `get_thumbnail(video_path, screenshot_storage_path, thumbnail_rows, thumbnail_cols, screenshot_start_percentage, screenshot_end_percentage) -> (bool, str)` | 同样先建目录（同 mkdir 三种失败）；`interval=(end-start)//(cols*rows)`；按 `cols*rows` 张依次取帧，越界 `break`；`cv2.resize(image,(0,0), fx=fy=1/rows)`（**行数除法的怪癖**——fx/fy 都用 `thumbnail_rows`）；拼 `(cols*(h+2*5), rows*(w+2*5), 3)` 白底网格；`resized_images` 为空时 `resized_images[0]` 抛 `IndexError`，被兜底捕获返回 `(False, str(e))`；成功 `(True, thumbnail_path)` |

**测试要点（非确定性）**：必须 mock `cv2.VideoCapture`、`random.sample`、`np.std`、`PIL.Image`；断言 mkdir 失败三种消息；std ≤ threshold 走兜底帧；min_interval 秒数换算；返回图片数 == number；`sample>population` 的 `(False,[...])`；`get_thumbnail` 空帧列表的 IndexError 兜底、fx=fy=1/rows。

### 2.3 mediainfo.py —— MediaInfo 论坛文本

| 项 | 内容 |
|---|---|
| `get_media_info(file_path) -> (bool, str)` | 路径不存在→`(False, '视频文件路径不存在')`；`MediaInfo.parse` 后 `to_json()`，按 General/Video/Audio/Text/Menu 逐 track 输出，标签列 `f'{label:36}: {value}\n'` 对齐；`Complete name` 只保留文件名（`os.path.basename`）；Menu 章节用正则 `re.match(r'(\d{2})_(\d{2})_(\d{5})', key)` 格式化为 `HH:MM:SS.mmm`；`get_settings('media_info_suffix')` 为真时末尾追加 `'\nCreated by Publish Helper'`；错误：`(False, f'文件路径错误：{e}')`、`(False, f'无法解析文件：{e}')` |

**测试要点**：mock `MediaInfo.parse`；断言不存在路径消息；`{label:36}` 对齐（`'Format' + ' '*28`）；Menu 时间戳正则（`'00_00_00000'→'00:00:00.000'`）；suffix 开/关。

### 2.4 rename.py —— 命名流水线（最大模块）

| 项 | 内容 |
|---|---|
| `get_pt_gen_info(description, raw_data=None) -> 8元组` | `(original_title, english_title, year, other_titles(list), categories, actors(list), episodes, season)`。**raw_data 字段级优先，正则回退**：`chinese_title/foreign_title/year/aka/genre/cast/episodes/season`；`aka` 过滤掉主标题；`genre` 用 `' / '` 拼接；`cast` 取中文名（`[一-龥·]+`）**最多 5 个**；season 从 `chinese_title` 的 `第\d+季|第[汉字]季|Season N` 解析，汉字经 `chinese_to_int`。正则回退支持 `◎`/`❁` 前缀、`◎片名/译名/年代/类别/主演(多行)`、`regex_categories` 以"语"开头 → `'暂无分类'`；演员行清洗后**若中文名为 `'简'` 则 `break` 停止**；`◎` 格式把"片名"插到第一位 |
| `get_video_info(file_path) -> (bool, 9元素list)` | `(False,['视频文件路径不存在'])`；`(False,[f'文件路径错误：{e}。'])`；`(False,[f'无法解析文件：{e}。'])`；成功 `(True, [video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num, tags])`。General 取 `other_frame_rate`；Video 取宽高/格式/色深/HDR，`writing_library` 含 `x264/x265/x266` 时覆盖 codec；Audio 取首条 codec/channel_layout，`other_language` 中文→tags 加 `'国语'`，英文→`'英语'`；Text 中文→`'中字'`、英文→`'英字'`；取宽高较长边 → `get_abbreviation`；结尾 `' pixels'` → `approximate_resolution_by_width`；`audio_count==1` 时 `audio_num=''` 否则 `f'{n}Audio'` |
| `get_name_from_template(21 个占位参数 + template) -> str` | `template` 是 **settings 键**（`get_settings(template)` 取模板串）；21 个占位符：`{en_title} {original_title} {season} {episode} {year} {video_format} {source} {video_codec} {bit_depth} {hdr_format} {frame_rate} {audio_codec} {channels} {audio_num} {team} {other_titles} {season_number} {total_episodes} {playlet_source} {categories} {actors}`。**按模板名后处理**：`main_title_` 含下划线→空格、连续空白压一个、`' -'→'-'`、`' @'→'@'`；`second_title_` 有 `' /  | '→' | '`、`'标 / 简'→''`、开头 `' | '` 裁剪；`file_name_` 把 `[<>:'/\\|?*\s]` 替换为 `.`、连续点压缩、`'.-'→'-'`、`'.@'→'@'`；最终 `name[0]` 为 `.` 或空格时去掉 |
| `rename_file(file_path, new_file_name) -> (bool, str)` | 名称清洗 `[<>:'/\\|?*]→'.'`；保留原扩展名；`(True, new_name)`；`FileNotFoundError→(False, f'未找到文件：{file_path}')`；`OSError→(False, f'重命名文件时出错：{e}')` |
| `rename_folder(current_folder_path, new_name) -> (bool, str)` | 清洗同上；**非目录 → `raise ValueError('提供的路径不是一个目录或不存在')`**；`(True, new_dir)`；`OSError→(False, f'重命名目录时发生错误：{e}')` |
| `move_file_to_folder(file_path, folder_name) -> (bool, str)` | 已在同名目录中→`(True, file_path)` 原样返回；目标目录不存在则 `os.makedirs`；`shutil.move`；`(True, target_file)`；异常→`(False, f'移动文件时出错：{e}')` |
| `create_hard_link(path) -> (bool, str)` | 不存在→`(False, f'Path does not exist: {path}')`；文件→同目录 `{name}-hardlink{ext}`；文件夹→`{path}-hardlink/` 保留整树，每个文件 `{name}-hardlink{ext}`；`FileExistsError→'Hard link already exists'`；`PermissionError→'Permission denied, unable to create the hard link'`；`EXDEV→'Hard link cannot be created across different file systems'`；其它→`(False, f'OS error occurred: {str(e)}')` / `(False, f'Unexpected error: {str(e)}')` |
| 辅助 | `approximate_resolution_by_width(width) -> str`（按 `load_min_widths_from_json` 从大到小取第一个 `width>=k`，兜底 `'240p'`）；`load_min_widths_from_json(filepath='static/abbreviation.json') -> Dict[int,str]`（读 `min_widths` 键，`int(k)` 化；缺文件/无键时用 `MIN_WIDTHS` 写回创建；返回默认副本）；`extract_numbers(string) -> int|None`（拼接所有数字位） |

**测试要点**：raw_data 逐字段回退（已有测试覆盖的细节不重复，重点补 ❁ 前缀 / `'简'` 终止 / 演员 cap=5）；`get_video_info` 用 `MediaInfo` 假 track 对象断言 9 元素与 x264 覆盖；`get_name_from_template` **喂真实 settings 模板键**（`main_title_tv` 等）断言替换与三套后处理；`rename_folder` 的 `ValueError`；`create_hard_link` 文件/文件夹两个形状与 `EXDEV`。

### 2.5 ptgen.py —— PT-Gen 接口调用

| 项 | 内容 |
|---|---|
| `get_pt_gen_description(pt_gen_api_url, resource_url) -> (bool, (str, dict))` | 网络 GET `timeout=30`。URL 归一：`tt+数字`→IMDb 链接、纯数字→豆瓣 `subject/{id}/`；去 `?` 后缀。新旧 API 识别：`_is_new_pt_gen_api`（路径含 `/api` 或主机在 `{'pt-gen.hares.dpdns.org'}`）；`_norm_ptgen_url` 新版统一到 `<scheme>://<host>/api/getData`；`_auth_signature(secret)` 生成 `(X-Timestamp毫秒, HMAC-SHA256→base64url)`（`+`→`-`、`/`→`_`、去 `=` 填充）；新服务带 `X-Timestamp/X-Signature` 头 + `requestId=req_publish_helper_{ts}`。**成功返回 `(True, (format_data, data))` 嵌套元组**。错误串：非 200 → `'PT-Gen接口请求失败，状态码：{code}'`；JSON 无效 → `'PT-Gen接口响应不是有效的JSON格式，请检查PT-Gen接口是否正常'`；format 空 → `'获取到的PT-Gen简介为空，可能是资源链接有误或PT-Gen接口出错，请检查后重试'`；`requests.Timeout` → `'PT-Gen接口请求超时'`；`RequestException` → `'PT-Gen接口响应发生错误：{e}'`；其它 → `'PT-Gen接口请求发生错误：{e}'`。**后处理**：`&#39;`→`'`；把 `译名` 行重构为 `chinese_title`（◎/❁ 两种格式，原内容移到 `别名` 行）；`personalized_signature` 非空时**前插**为第一行；末尾补 `'\n'`；`img1`→`img2` |
| `get_playlet_description(original_title, year, area, category, language, season_number) -> str` | `season_number != '1'` 时标题追加 `' 第' + int_to_chinese(N) + '季'`；返回固定模板 `'\n◎片　　名　{...}\n◎年　　代　{...}\n◎产　　地　{...}\n◎类　　别　{...}\n◎语　　言　{...}\n◎简　　介　\n'` |
| `get_data_from_pt_gen_description(main_title, description, media_info, source, category) -> 8元组` | `(imdb_url, douban_url, category, area, video_format, audio_codec, video_codec, medium)`。IMDb 正则 `https://www\.imdb\.com/title/tt\d+/`、豆瓣 `https://movie\.douban\.com/subject/\d+/`；category 关键词表（纪录/体育/动画/综艺/短剧）；area 表（美英德法→欧美、大陆→大陆、港台→港台、日本/韩国/印度）；分辨率按 `3840/2160/1080p/1080i/720p/720i/480p` 关键字；audio 表（AAC/AC3/EAC3/DTS/DTS-HDMA/Atmos/TrueHD/Flac）；video 表（H264/H265/H266/X264/X265/X266/AV1）；medium 表（WEB-DL/Encode/Remux/HDTV/DVD，Blu-ray 且 `X26`→Encode、含 Remux 或 media_info 含 mkv→Remux） |

**测试要点**：mock `requests.get` 断言头/参数/超时；`tt1234567` 与 `1234567` 的 URL 改写；新老 API 探测；`_auth_signature` 用 `monkeypatch` 固定 time 断言 `-`/`_`/无 `=`；嵌套元组返回；`&#39;`、译名重构、签名前插、`img1→img2`；`get_playlet_description` season='2'→`'第二季'`；映射表边界（如 `1080i` vs `720i→480i` 的 bug 行为按现状记录）。

### 2.6 picturebed.py —— 图床上传（6 家）

| 项 | 内容 |
|---|---|
| `upload_picture(api_url, token, path) -> (bool, bbcode)` | 图片不存在→`(False, '图片文件路径不存在')`；去 URL 中空格/全角空格/换行；`get_picture_bed_type` 分发到 6 家：`lsky-pro/bohe/chevereto/freeimage/imgbb/pixhost`；类型未识别→`(False, '你错误更改了图床配置文件？冒号前面的类型是不能随便改的！...')` |
| 各 provider 契约 | **lsky-pro**：`data.data.links.bbcode`；**bohe**：读 `statusCode == '200'` 才成功取 `bbsurl`（否则 `'未接受到响应'` / `f'API响应出错了，错误码：{code}，错误提示：{result_data}'`）；**chevereto**：`data.image.url`→`[img]url[/img]`；**freeimage**：`format='txt'`，`res.text[:4]=='http'` 才成功→`[img]text[/img]`，否则 `(False, res.text)`；**imgbb**：`data.data.image.url`→`[img][/img]`；**pixhost**：`data.th_url` 先 `//t`→`//img`、`/thumbs/`→`/images/` 再包 `[img]`。每家都有 `requests.RequestException` / `KeyError` / `json.JSONDecodeError` → 中文错误 |
| `get_picture_bed_type(url) -> (bool, str)` / `find_picture_bed_type(url, data) -> (bool, str)` | 读取 `static/picture-bed-data.json`，缺键补默认并写回；`http://`→`https://`、去末尾 `/`；找不到→`(False, f'您使用的图床上传接口{url}暂未配置，请检查static/picture-bed-data.json文件，...')` |
| `generate_image_filename(base_path) -> str` | `datetime '%Y%m%d-%H%M%S'` + `-` + `random.sample('0123456789',6)` + `'.png'`，拼 `base_path/filename` |

**测试要点**：mock `requests.post`，逐家断言响应解析与 bbcode 包装；bohe 的 `statusCode=='200'` 分支；freeimage 必须以 `http` 开头才算成功；`find_picture_bed_type` 的 http→https 与去斜杠；`generate_image_filename` 的 6 位随机数与 `.png` 后缀。

### 2.7 torrent.py —— 制作种子

| 项 | 内容 |
|---|---|
| `make_torrent(path, torrent_storage_path) -> (bool, str)` | 不存在→`(False, '提供的路径不存在')`；目录且为空→`(False, '路径指向一个空目录')`；`Torrent(path=..., trackers=['https://tracker.example.com/announce'], created_by='Publish Helper', creation_date=now)`；**先删除已存在的同名目标种子**再 `generate()+write()`；`(True, torrent_path)`；所有异常捕获为 `(False, str(e))` |

**测试要点**：`tmp_path` 构造文件/目录；断言 `trackers`、`created_by` 精确值；**预置同名种子文件验证先删后写**；两条中文错误。

### 2.8 poster.py —— 海报下载上传

| 项 | 内容 |
|---|---|
| `get_poster_url_from_data(data: dict) -> str` | 依次尝试字段 `poster, img, image, cover, posterUrl`，再到嵌套 `data.<field>`；全无→`''` |
| `download_poster(poster_url, save_path) -> (bool, str)` | 空 URL→`(False,'Poster URL is empty')`；请求头含 Chrome UA + `Referer: https://movie.douban.com/`，`timeout=30, stream=True`；非 200→`(False, f'Failed to download poster, status code: {code}')`；按 chunk 写盘；`(True, save_path)`；`Timeout→'Poster download timeout (30s)'` |
| `process_poster(poster_url, api_url, token, temp_dir=None) -> (bool, str)` | 临时文件 `{temp_dir}/poster_{id(poster_url)}.jpg`；下载失败即返回；上传失败时**临时文件保留**（调试用）；上传成功后剥 `[img]...[/img]` 返回 `(True, uploaded_url)`；`finally` 中**仅上传成功**才删除临时文件 |
| `get_poster_from_pt_gen_response(pt_gen_data, ...)` | 取 URL 为空→`(False,'No poster URL found in PT-Gen response')`；否则转 `process_poster` |

**测试要点**：mock `requests.get` 断言 UA/Referer 头；上传失败时临时文件仍在、成功时被删；`[img]` 剥离；5 字段 + 嵌套 `data.*`。

### 2.9 autofeed.py —— auto_feed 链接生成

| 项 | 内容 |
|---|---|
| `get_auto_feed_link(main_title, second_title, description, media_info, file_name, team, source, category, torrent_url) -> (bool, str)` | 内部先调 `get_data_from_pt_gen_description`；取 settings `auto_feed_link` 模板；逐占位符 `{主标题}{副标题}{IMDB}{豆瓣}{简介}{MediaInfo}{种子名称}{类型}{地区}{分辨率}{音频编码}{视频编码}{媒介}{小组}{种子链接}` 用 `urllib.parse.quote` 替换；**存在 `#separator#`** 时把分隔符后的整段 `base64encoding`（UTF-8 base64）替换回去，得到 `(True, link)`；**不含 `#separator#` → `(False, '您设置的auto_feed_link不符合规则')`**。注意 `#seperator#` 错拼不会触发替换（`replace` 结果被丢弃，是历史遗留坑） |

**测试要点**：用**真实 settings 键**喂默认模板；断言 `quote` 化与尾部 base64（`base64.b64encode(tail.encode())` 相等）；无分隔符错误串。

### 2.10 settings_tool.py —— 统一设置（另含 text.py 工具）

| 项 | 内容 |
|---|---|
| `SettingsManager` | `__init__(settings_file=None)`（默认 `config.STATIC_DIR/settings.json`）；`_ensure_settings_file` 不存在则写默认；`_get_default_settings` 返回 **38 键**默认表；`_read_settings`（损坏/IO → `raise ConfigurationError`）；`_write_settings`（不可写 → `raise ConfigurationError`，写后清缓存）；`get_setting(key, default)`（**env 大写优先 → 文件 → default**，布尔归一，`_handle_legacy_keys` 做 `{category}→{categories}`、`{total_episode}→{total_episodes}`）；`update_setting`；`get_all_settings`（返回副本）；`update_all_settings`；`reset_to_defaults` |
| 模块便捷函数 | `get_settings/update_settings/get_settings_json/update_settings_json/combine_directories`（`str(Path.cwd()/relative_path)`） |

**text.py 补充**（重命名/解析依赖，无元组）：`natural_keys`（`re.split(r'(\d+)')`，数字段转 int）；`int_to_roman / int_to_special_roman(Ⅰ..Ⅹ) / int_to_chinese / chinese_to_int`（反向遍历 + 十百千万单位，非法字符 `raise ValueError` 但被捕获返回 `None`）；`base64encoding`（UTF-8 base64）；`validate_and_convert_to_int(value, name) -> int`（空/非数字 `raise ValueError`）；`chinese_name_to_pinyin`（xpinyin）；`convert_chinese_punctuation_to_english`。

### 2.11 data.py —— 下拉框数据与缩写

| 项 | 内容 |
|---|---|
| `get_combo_box_data(data_name) -> (bool, list)` | **白名单 `playlet-source|source|team`**；默认内容硬编码（playlet-source 5 项、source 8 项、team 6 项，末尾含 `''`）；经 `load_or_initialize_json(..., backfill=True)` 读写 `static/combo-box-data.json`；`(True, data[data_name])`；异常→`(False, [str(e)])` |
| `update_combo_box_data(configuration_data: str, configuration_name: str) -> (bool, str)` | 按 `'\n'` 分割；写回 `static/combo-box-data.json`；`(True,'更新成功')`；文件不存在→`(True,'文件不存在，已创建新文件并更新')`；`JSONDecodeError→(False,'JSON解码错误，文件内容可能损坏')`；其它→`(False, f'更新失败，错误：{str(e)}')` |
| `get_abbreviation(original_name, json_file_path='static/abbreviation.json') -> str` | `load_or_initialize_json` 读 `min_widths` + 一堆像素/编解码映射；命中返回缩写，否则**原样返回**；`FileNotFoundError/JSONDecodeError→original_name` |
| `load_names(file_path, name)` | `json.load` 后返回 `data[name]` |

---

## 3. 设置与数据文件清单

### 3.1 static/settings.json —— 38 键全表

键集合 = `SettingsManager._get_default_settings()` 并集（`auto_download_upload_poster` 可能不在旧文件里，读不到时回退默认 `False`）。示例值取自当前 `static/settings.json`。

| 键 | 示例值 | 控制内容 |
|---|---|---|
| api_port | "5372" | API 监听端口（**`start_api()` 实际用 `get_settings('api_port')`，而非 `config.API_PORT`**） |
| enable_api | "True"/"" | 是否启用 API（bool） |
| pt_gen_api_url | "https://pt-gen.hares.dpdns.org/api/getData" | PT-Gen 主接口 |
| pt_gen_api_url_backup | "https://ptgen.agsvpt.work/" | 备用 PT-Gen 接口 |
| pt_gen_auth_secret | "hares.23663" | PT-Gen HMAC-SHA256 签名密钥 |
| picture_bed_api_url | "https://freeimage.host/api/1/upload" | 图床上传接口 |
| picture_bed_api_token | "6d207e02198a847aa98d0a2a901485a5" | 图床 token |
| screenshot_storage_path | "temp/pic" | 截图/缩略图输出目录 |
| screenshot_number | "3" | 截图张数 |
| screenshot_threshold | "30.00" | 关键帧复杂度阈值 |
| screenshot_start_percentage | "0.10" | 截图起始帧占比 |
| screenshot_end_percentage | "0.90" | 截图结束帧占比 |
| auto_upload_screenshot | "True" | 自动上传截图（bool） |
| paste_screenshot_url | "True" | 截图 URL 粘贴进简介（bool） |
| delete_screenshot | "True" | 上传后删除本地截图（bool） |
| auto_download_upload_poster | False（默认） | 自动下载上传海报（bool） |
| do_get_thumbnail | "True" | 生成并上传缩略图（bool） |
| thumbnail_rows | "3" | 缩略图行数 |
| thumbnail_cols | "3" | 缩略图列数 |
| thumbnail_delay | "2.0" | 缩略图上传前延迟秒数 |
| torrent_storage_path | "temp/torrent" | 种子输出目录 |
| media_info_suffix | "True" | MediaInfo 追加 'Created by Publish Helper'（bool） |
| make_dir | "True" | 视频移入同名文件夹（bool） |
| rename_file | "True" | 执行重命名（bool） |
| create_hard_link | "True"/"" | 创建硬链接（bool） |
| second_confirm_file_name | "True" | 二次确认文件名（bool） |
| main_title_movie | "{en_title} {year} {video_format} {source} {video_codec} {bit_depth} {hdr_format} {frame_rate} {audio_codec} {channels} {audio_num}-{team}" | 电影主标题模板 |
| second_title_movie | "{original_title} / {other_titles} \| 类型：{categories} \| 演员：{actors}" | 电影副标题模板 |
| file_name_movie | "{original_title}.{en_title}.{year}.{video_format}..." | 电影文件名模板 |
| main_title_tv | "{en_title} S{season} {year} ..." | 剧集主标题模板 |
| second_title_tv | "{original_title} / {other_titles} \| {total_episodes} \| ..." | 剧集副标题模板 |
| file_name_tv | "{original_title}.{en_title}.S{season}E{episode}..." | 剧集文件名模板 |
| main_title_playlet | "{en_title} S{season} {year} ..." | 短剧主标题模板 |
| second_title_playlet | "{original_title} \| {total_episodes} \| {year}年 \| {playlet_source} \| 类型：{categories}" | 短剧副标题模板 |
| file_name_playlet | "{original_title}.{en_title}.S{season}E{episode}..." | 短剧文件名模板 |
| auto_feed_link | "https://example.com/upload.php#separator#name#linkstr#..." | auto_feed 模板（**必须以 `#separator#` 分隔**） |
| open_auto_feed_link | "True" | 生成后自动打开链接（bool） |
| personalized_signature | "" | 追加到 PT-Gen 简介开头的个性签名 |

### 3.2 其它数据文件

| 文件 | 结构 | 说明 |
|---|---|---|
| `static/combo-box-data.json` | `{team:[...], source:[...], playlet-source:[...]}` | 下拉框候选；由 `get_combo_box_data/update_combo_box_data` 维护，`backfill=True` 会补齐缺失键并写回 |
| `static/abbreviation.json` | `min_widths`（分辨率分段，键为字符串数字）+ `'7 680 pixels':'4320p'` 等缩写映射 | `get_abbreviation`、`load_min_widths_from_json` 使用；缺文件/缺键会被**写回创建** |
| `static/picture-bed-data.json` | `{provider: [url...]}`，6 家：lsky-pro/bohe/chevereto/freeimage/imgbb/pixhost | `get_picture_bed_type` 按 URL 匹配类型；缺键补默认并写回 |

### 3.3 src/config/settings.py —— Config 类

- 路径：`BASE_DIR`（`Path(__file__).parent.parent.parent`）、`SRC_DIR/STATIC_DIR/TEMP_DIR/MEDIA_DIR/LOGS_DIR`。
- 环境变量旋钮：`API_HOST("0.0.0.0")/API_PORT(15372)/API_DEBUG`、`GUI_TITLE/GUI_VERSION`、`PTGEN_API_URL/PTGEN_API_KEY`、`IMAGE_HOST_TYPE(freeimage)/IMAGE_HOST_API_URL/IMAGE_HOST_API_KEY`、`MEDIAINFO_PATH`、`LOG_LEVEL/LOG_FILE`。
- `_create_directories()` 创建：`STATIC_DIR, TEMP_DIR, TEMP_DIR/pic, TEMP_DIR/torrent, MEDIA_DIR, LOGS_DIR`。
- 模块级单例 `config = Config()`（import 即读 env）。
- `ImageHostConfig.SUPPORTED_HOSTS` 7 家静态描述（freeimage/imgbb/imagehub/pixhost/bohe/lsky-pro/chevereto）——与 picturebed 的 6 家实际实现**不完全一致**（imagehub 未实现上传），仅作配置参考。

---

## 4. GUI 业务流程（src/gui/startgui.py，2334 行）

> **GUI 无法 headless 运行**（`start_gui()` 创建 `QApplication` 进入事件循环）。测试方案二选一：① `QT_QPA_PLATFORM=offscreen` 冒烟；② **绕过 Qt，直接调用 handler/流水线函数并 mock 线程与网络**。`import startgui` 会 `import PyQt6`，测试环境需装 PyQt6。

### 4.1 三个页签与按钮驱动

| 页签 | 按钮（槽函数） | 业务 |
|---|---|---|
| Movie / TV / Playlet 通用 | `getPtGenButton` → `get_pt_gen_button_*_clicked` | 启 **主+备用两个 `GetPtGenThread`** 竞速，首个成功置 `self.get_pt_gen_success=True`，后到者忽略 |
| | `getPictureButton` → `get_picture_button_*_clicked` | `get_screenshot` 出图后逐图开 `UploadPictureThread`（见 4.3） |
| | `getMediaInfoButton` | `get_media_info` 填 mediainfo 文本框 |
| | `getNameButton` → `get_name_button_*_clicked` | 完整重命名流水线（见 4.2） |
| | `makeTorrentButton` → `MakeTorrentThread` | 异步 `make_torrent`，成功后填 `torrent_url` |
| | `startButton` → 一键启动 | 见 4.4 |
| | `autoFeedButton` | `get_auto_feed_link` → `pyperclip.copy`；若 `open_auto_feed_link` 用临时 HTML 触发 `webbrowser.open` |
| Movie/TV 专属 | `selectVideoButton / selectVideoFolderButton` | 取文件/文件夹路径 |
| Playlet 专属 | `getDescriptionButton` → `get_description_playlet_clicked` | 用 `get_playlet_description` 生成固定格式简介 |
| | `uploadCoverButton` → `upload_cover_button_playlet_clicked` | **独立单线程** `UploadPictureThread(is_cover=True)`，成功后把封面 URL **前插**到简介，**绕过槽位收集** |
| | `selectCoverFolderButton` | 选封面图 |

### 4.2 get_name 重命名流水线（以 Movie 为例，TV/Playlet 同理 + 季集处理）

`get_name_button_movie_clicked` → 重置全局 `get_name_movie_success=False / failure_number=0` → 校验 URL/PT-Gen 配置 → 启主/备 `GetPtGenThread`。结果回调 `handle_get_pt_gen_for_name_movie_result`：

1. 首胜去重；`_process_poster_in_description`（`auto_download_upload_poster` 开启时，见 4.5）；
2. `check_path_and_find_video(path)`；
3. `get_pt_gen_info(description, raw_data=json.loads(raw_data_json))`；
4. **year 为空 → 失败计数 +1**；
5. actors/other_titles 拼接（`' / '`，别名去尾 `' / '`）；
6. `second_confirm_file_name` 流程：英文名缺失时弹框（拼音 `chinese_name_to_pinyin` 兜底 / `QInputDialog` 手输，非法字符则失败）；
7. `get_video_info(video_path)`；
8. `get_name_from_template × 3`（`main_title_movie / second_title_movie / file_name_movie`）；
9. 文件名二次确认 + `is_filename_too_long` 检查（>250 弹框，改后仍长则失败）；
10. 按设置顺序副作用：`create_hard_link`（若开，`path` 指向硬链接结果）→ `make_dir && is_video_path==1` 时 `move_file_to_folder` → `rename_folder`（目录型）→ `rename_file`；
11. 全部成功 → `get_name_movie_success=True`。任何一步失败 → `get_name_movie_failure_number += 1` 并提前 return。

### 4.3 截图并发上传（槽位有序回填）

- `get_picture_button_*_clicked`：每张图开一个 `UploadPictureThread(..., index=idx)`，`is_thumbnail = do_get_thumbnail and idx == len(pictures)-1`（缩略图天然最后）；维护 `self._upload_slots[index]=url`、`self._slots_to_path[index]=本地路径`、`self._upload_total=总数`。
- `handle_upload_picture_*_result`：按 index 收集，`len(_upload_slots) < _upload_total` 则继续等；**全部完成后**按 `pictures` 顺序重建并 `setText`；`paste_screenshot_url` 为真则追加到简介；`delete_screenshot` 为真则按序删除本地图；结束后清空槽位。
- `UploadPictureThread.run`：`is_thumbnail` 先 `time.sleep(thumbnail_delay)`，再 `upload_picture(...)`，信号 `(success, response, path, is_cover, is_thumbnail, index)`。

### 4.4 一键启动编排

- **Movie/TV**：`start_button_*_clicked` 调 `get_name_button_*_clicked()` 后启动 `WaitForRenameThread(is_movie)`；`WaitForRenameThread.run` **轮询模块全局**（Movie：`get_name_movie_success / get_name_movie_failure_number`；TV 同名 TV 变量），每 0.5s 一次，条件 `success is False and failure_number <= 1 and wait_time <= 60`（最长 60s）；完成后 `handle_process_after_rename_*`：成功则依次 `get_media_info → get_picture → make_torrent`（各带 `QApplication.processEvents()`），失败则 toast 终止。
- **Playlet**：`start_button_playlet_clicked` **无 WaitForRenameThread**（`second_confirm_file_name` 必须为 False），串行：`get_name → get_picture → upload_cover → sleep(2) → get_media_info → sleep(2) → make_torrent`。

### 4.5 海报自动处理

`_process_poster_in_description(description)`：`auto_download_upload_poster` 开启时，用 `re` 提取简介中首个 `[img](https?://[^]]+)[/img]`，调 `process_poster(url, picture_bed_api_url, picture_bed_api_token, screenshot_storage_path)`，成功后用上传结果替换原 `[img]` 标签。

### 4.6 关键全局与线程

| 项 | 说明 |
|---|---|
| 模块全局 | `get_name_movie_success/failure_number`、`get_name_tv_success/failure_number`（Playlet 无全局——串行） |
| 实例状态 | `_upload_slots/_slots_to_path/_upload_total`、`get_pt_gen_success`、`path_movie/path_tv`、`torrent_url`、`wait_for_rename_thread` 等 |
| 线程 | `GetPtGenThread(bool,str,str)`、`UploadPictureThread(bool,str,str,bool,bool,int)`、`MakeTorrentThread(bool,str)`、`WaitForRenameThread(bool)`、`apiThread(str)`（`start_api()` 阻塞） |

**测试要点**：槽位收集的"乱序完成 → 按序回填"逻辑（可直接 mock handler 入参顺序）；`WaitForRenameThread` 轮询退出条件；Playlet 封面 `is_cover` 前插与绕过槽位；失败计数递增路径。

---

## 5. API 接口清单（src/api/startapi.py，26 路由）

### 5.1 响应封装约定（测试必须先建立）

- 统一 JSON 包络 `{data, message, statusCode}`：**`statusCode` 是 JSON 体内的字符串**，与 HTTP 状态码是两个维度（例如 HTTP 401 + `statusCode='UNAUTHORIZED_ACCESS_ERROR'`；HTTP 422 + `statusCode='MISSING_REQUIRED_PARAMETER'`）。
- `_ok(data=None, message='成功', status_code='OK', http_status=200)`；`_error(status_code, message, http_status=400, exc=None)`（`exc` 只写服务端日志，不外泄）。
- 参数读取统一走 `_payload()`：**JSON body 优先 → form → URL query**，返回 werkzeug `ImmutableMultiDict`（支持 `.get(key, default, type=str)` 类型转换）。
- 可选鉴权：设 `API_AUTH_TOKEN` 后全端点 `Authorization: Bearer <token>`，否则放行；CORS 白名单 `API_CORS_ORIGINS`（默认 `*`）。

### 5.2 路由清单（按域分组）

**截图 / 缩略图**

| 方法+路径 | 参数（`_payload`） | 副作用 | 成功 | 失败 |
|---|---|---|---|---|
| GET `/api/getScreenshot` | path*、screenshotStoragePath、screenshotNumber、screenshotThreshold、screenshotStartPercentage、screenshotEndPercentage、screenshotMinIntervalPercentage | 写截图文件 | 200 `{screenshotNumber,screenshotPath,videoPath}`，screenshotPath 为**相对 media/ 的列表** | 401 越域；422 空路径（死分支）/不存在/张数<1 或 >5/起止不在(0,1)/起>止；400 `BACKEND_PROCESSING_ERROR`；500 `GENERAL_ERROR` |
| GET `/api/getThumbnail` | path*、screenshotStoragePath、thumbnailRows、thumbnailCols、screenshotStartPercentage、screenshotEndPercentage | 写缩略图 | 200 `{thumbnailPath,videoPath}` | 同上（行列需>0） |

**图片上传**

| 方法+路径 | 参数 | 副作用 | 成功 | 失败 |
|---|---|---|---|---|
| POST `/api/uploadPicture` | picturePath*、pictureBedApiUrl、pictureBedApiToken | 调图床 API | 200 `{pictureBbCode, pictureUrl}`（pictureUrl = bbcode `[5:-6]`） | 422 缺路径/路径不存在；400 `BACKEND_PROCESSING_ERROR`；500 |

**媒体信息**

| 方法+路径 | 参数 | 成功 | 失败 |
|---|---|---|---|
| GET `/api/getMediaInfo` | path* | 200 `{mediaInfo, videoPath}` | 401/422/400/500 |
| GET `/api/getVideoInfo` | path* | 200 `{videoPath, videoFormat, videoCodec, bitDepth, hdrFormat, frameRate, audioCodec, channels, audioNum}` | 同上 |

**PT-Gen**

| 方法+路径 | 参数 | 成功 | 失败 / 备注 |
|---|---|---|---|
| GET `/api/getPtGenDescription` | resourceUrl*、ptGenApiUrl | 200 `{description, posterUrl}`；`auto_download_upload_poster` 时调 poster 流程 | 422 缺链接；400 `BACKEND_PROCESSING_ERROR`；500 |
| GET/POST `/api/getPlayletDescription` | originalTitle*、year、area、category、language、seasonNumber | 200 `{playletDescription}` | 422 缺名称；500 |
| GET/POST `/api/getPtGenInfo` | description* | 200 `{originalTitle, englishTitle, year, otherTitles, category, actors}`（otherTitles 用 `' / '` 连接、演员同） | **Bug：缺 description 时 message='MISSING_REQUIRED_PARAMETER'、statusCode='缺少PT-Gen简介内容。' 互换**；500 |
| GET `/api/getPTGenInfoByResourceUrl` | resourceUrl*、ptGenApiUrl | 200 `{originalTitle,...,description}` | **Bug：`description` 返回的是 `(format_data, full_data)` 元组**（`response` 未解包）；400/500 |

**种子**

| 方法+路径 | 参数 | 成功 | 失败 |
|---|---|---|---|
| POST `/api/makeTorrent` | path*、torrentStoragePath | 200 `{torrentPath}` | 401/422/400/500（`test_api_restful.py` 已覆盖 body/query 双栈） |

**命名模板**

| 方法+路径 | 参数 | 成功 | 失败 |
|---|---|---|---|
| GET/POST `/api/getNameFromTemplate` | template*（**白名单 9 个**：`main_title_/second_title_/file_name_` × movie/tv/playlet）、englishTitle、originalTitle、season、year、videoFormat、source、videoCodec、bitDepth、hdrFormat、frameRate、audioCodec、channels、audioNum、team、otherTitles、seasonNumber、totalEpisode、playletSource、category、actors | 200 `{name}`；**先 `delete_season_number(english_title, season_number)`** | 422 缺模板/模板不在白名单；500 |

**文件操作**

| 方法+路径 | 参数 | 成功 | 失败 / 备注 |
|---|---|---|---|
| POST `/api/renameFolder` | folderPath*、newFolderName* | 200 `{newFolderPath}`（相对 media/） | 401/422/400/500 |
| POST `/api/renameFile` | filePath*、newFileName* | 200 `{newFilePath}` | 401/422/400/500 |
| POST `/api/createHardLink` | path* | 200 `{hardLinkPath}` | 401/422/400/500 |
| POST `/api/moveFileToFolder` | filePath*、folderName* | 200 `{newFilePath}` | **Bug：401 越域检查用的是原始参数 `path`（未 join 的 filePath）而非 `file_path`**，导致空路径/相对路径 `''.startswith(media)` 为 False → **空路径命中 401 而非 422**；422/400/500 |
| POST `/api/renameEpisode` | folderPath*、newFileName*、episodeStartNumber | 200 `{newFolderPath}` | **要求 `check_path_and_find_video==2`（文件夹）**；文件路径 → 400 `'不支持文件路径：...'`；逐文件 `rename_file`（`{集数}` 补零）+ 末尾 `rename_folder`；500 |
| GET `/api/getTotalEpisode` | folderPath*、episodeStartNumber | 200 `{totalEpisode}`（`全N集` / `第N集` / `第N-M集`） | **同上要求文件夹**；400/500 |

**数据 / 设置**

| 方法+路径 | 参数 | 成功 | 失败 |
|---|---|---|---|
| GET `/api/getComboBoxData` | configurationName*（白名单 playlet-source/source/team） | 200 `{configurationData}` | 422 缺名/不在白名单 `PARAMETER_RANGE_ERROR`；400/500 |
| POST `/api/updateComboBoxData` | configurationName*、configurationData* | 200 `{}` | 同上 + 缺内容 422 |
| GET `/api/getSettings` | settingsName* | 200 `{settingsData}` | 422 缺名；500 |
| POST `/api/updateSettings` | settingsName*、settingsData* | 200 `{}` | 422 缺名/缺值；500 |
| GET `/api/settings` | 无 | 200 `{settings}`（全部） | 500 |
| POST `/api/settings/update` | **`request.json` 原始 body**（不走 `_payload`） | 200 `{}` | 500 |

**文件下载 / 浏览**

| 方法+路径 | 参数 | 成功 | 失败 / 备注 |
|---|---|---|---|
| GET `/api/getFile` | filePath* | `send_file` 附件下载（200） | **安全基准为 `config.TEMP_DIR`（非 media/）**：`Path.resolve()` + `temp_root not in target_path.parents` 严格边界；temp 根本身 → 401；文件不存在 → 404 `FILE_NOT_FOUND`；缺参数 422 |
| GET `/api/media/file/list` | path* | 200 `{fileList}`（`{name,size,type}`，`type` 为 '文件'/'文件夹'） | media 越域 401；500 |

**自动化（大杂烩）**

| 方法+路径 | 参数 | 成功 | 失败 / 备注 |
|---|---|---|---|
| POST `/api/autoHandleVideo` | resourceUrl*、path*、source*、team*、category*、season、episodesStartNumber | 200 全量 Data（camelCase 化：area/audio_codec/.../torrent_file_url/tags） | 422 `RUNTIME_ERROR`（`ValueError` 分支）/500 `RUNTIME_ERROR`（`RuntimeError`）/500 `GENERAL_ERROR`。流程：PT-Gen（失败重试一次）→ 截图（5 张内校验）→ 上传 → 缩略图 → get_video_info → get_pt_gen_info → 集数 → 三个模板 → 重命名 → MediaInfo → get_data_from_pt_gen_description → make_torrent → `torrent_file_url` 用 `request.base_url` 拼 `/getFile?filePath=` |

### 5.3 已知 7 处不一致 / Bug（写测试时按现状断言）

1. **getPtGenInfo 互换**：缺 `description` 时 `message='MISSING_REQUIRED_PARAMETER'`、`statusCode='缺少PT-Gen简介内容。'`（HTTP 仍 422）。
2. **moveFileToFolder 的 401 检查用原始变量**：`if not path.startswith(media_path)` 用的是未 join 的 `filePath` 参数（其它路由都检查 join 后的绝对路径）。
3. **getPTGenInfoByResourceUrl 返回 tuple**：`data.description` 是 `(format_data, full_data)` 元组而非字符串。
4. **鉴权 statusCode 不一致**：`_require_auth` 失败返回 `statusCode='UNAUTHORIZED'`，路由级越域返回 `'UNAUTHORIZED_ACCESS_ERROR'`。
5. **空路径命中 401 而非 422**：moveFileToFolder 因上述原始变量检查，空 `filePath` → `''.startswith(media)` False → 401；多数媒体类路由的空路径 422 分支是**死代码**（join 后恒为 media_path，检查必然通过）。
6. **getFile 安全加固**：基准为 `TEMP_DIR`（其它文件路由为 `media/`），`Path.resolve()` 解析符号链接/`..`，`parents` 成员判断防前缀绕过；temp 根目录本身不可作为文件目标（401）。
7. **getTotalEpisode / renameEpisode 要求文件夹**：传入文件路径 → 400 `'不支持文件路径：...'`（`check_path_and_find_video` 为 1 时）。

---

## 6. 测试覆盖矩阵（中心章节）

> 注意：`docs/DEVELOPMENT.md` 的「测试策略」已过时——其声称 `test_core.py / test_api.py / test_gui.py` 存在，**实际并不存在**。真实测试集为以下 **7 个文件**。

### 6.1 现有测试明细（7 个文件）

| 文件 | 覆盖内容（函数 + 关键断言） | 未覆盖 |
|---|---|---|
| `tests/test_config.py`（80 行） | `Config()`：`API_HOST=='0.0.0.0'`、`API_PORT==15372`、`BASE_DIR` 是 Path；`_create_directories` 生成 STATIC/TEMP/MEDIA/LOGS；`SettingsManager`：init 建文件、`get_setting('api_port', default)` 回退 `'15372'`、`update_setting` 往返、`monkeypatch.setenv('API_PORT')` 环境变量优先、legacy `{category}`→`{categories}` | 其它 env 旋钮（API_DEBUG/GUI_TITLE/PTGEN/IMAGE_HOST/MEDIAINFO/LOG）；`int()` 端口解析；`get_all_settings/update_all_settings/reset_to_defaults`；`_read_settings/_write_settings` 的 `ConfigurationError` 分支；`_BOOL_KEYS` 归一 |
| `tests/test_utils.py`（91 行） | `ensure_directory`（嵌套创建）；`safe_filename`（9 个非法字符清除、`max_length` 截断保留扩展名）；`get_file_hash`（md5 长度 32、缺失文件 `pytest.raises(FileNotFoundError)`）；`get_file_size_human`（0/1KB/1MB/1GB）；`setup_logger`（文件写入、无文件模式、INFO 级别） | `copy_with_structure`、`create_hardlink`、`find_files`、`combine_directories`（cwd 相对）、sha1/sha256、`load_or_initialize_json`（另见下） |
| `tests/test_settings_tool.py`（120 行） | `_BOOL_KEYS`：`'True'→True`、`'False'→False`、`''→False`、真 bool 直通、非布尔键保持字符串；`_get_default_settings` 12 个布尔键都是真 bool；pt_gen 默认值；`get_setting` 默认回退、update 往返、`{category}` 迁移、env 覆盖 | `reset_to_defaults`；`get_all_settings` 副本语义；模块级 `get_settings/update_settings/get_settings_json/update_settings_json`；`ConfigurationError`（损坏 JSON / 不可写路径）；`{total_episode}→{total_episodes}` 迁移 |
| `tests/test_file_utils_json.py`（87 行） | `load_or_initialize_json`：缺失创建并返回副本（不改 defaults 源）；`backfill=False` 只读、缺失键不补、**字节级不变**；`backfill=True` 补缺失键并写回、保留已有值、**保留 2 空格缩进**；损坏文件 → `ValueError` | `ensure_ascii` 参数；嵌套默认；父目录自动创建；`backfill=False` 遇损坏文件行为（读路径同样抛 ValueError） |
| `tests/test_api_getfile.py`（98 行） | `/api/getFile` 安全边界：temp 内文件 200 + 字节内容；前缀 lookalike 目录（`temp_evil`）401；`../` 穿越 401；temp 外绝对路径 401；**temp 根本身 401**；缺文件 404；缺 `filePath` 422；symlink 逃逸 401（无 symlink 平台跳过） | `send_file` 附件头/Content-Type；`GENERAL_ERROR` 500 分支；与 `API_AUTH_TOKEN` 的叠加行为 |
| `tests/test_api_restful.py`（74 行） | `_payload()` 双栈：`/api/makeTorrent` POST+JSON body 读到 `path`（422 `FILE_PATH_ERROR`）；query 兼容；body 带 type 转换；可选鉴权矩阵（无 token 200 / wrong 401 / secret 200）；`autoHandleVideo` GET→405、POST 缺参→422；`getPtGenInfo` 支持 POST body 与 GET query（非 405） | form 编码 body；**其余 24 个路由**；media 越域 401；空路径 422 分支；包络 `{data,message,statusCode}` 形状全量校验；7 处 bug 断言 |
| `tests/test_rename_info.py`（164 行） | `get_pt_gen_info`：raw_data 优先（标题/年份/aka 过滤主标题/类别 `' / '` 拼接/演员 **cap=5**/episodes/season）；返回 8 元组；纯正则回退（◎ 格式）；部分 raw_data 逐字段回退（缺 chinese_title、缺 year、空 genre、空 dict==None）；season 从 `chinese_title` 数字/汉字解析；episodes 从 raw_data | ❁ 前缀格式；多别名排序；`'简'` 演员终止；`暂无分类`；其它全部 rename 函数 |

### 6.2 未覆盖（gap）清单 —— 按模块 + 函数 + 建议首个断言点

**video.py**
| 函数 | 建议首个断言点 |
|---|---|
| `check_path_and_find_video` | tmp 文件 `.mkv`→`(1,path)`；目录含视频→`(2, path+'/'+file)`；目录无视频→`(0,'文件夹中没有符合类型的视频文件')`；`file:///` 前缀与末尾 `/` 归一；非视频扩展名文件→`(0, 消息含'不符合视频类型')` |
| `get_video_files` | 构造 `EP1/EP2/EP10` 断言自然序；无效目录→`(False, [f'错误：{e}'])`（列表形状） |
| `is_filename_too_long` | 251→True、250→False |
| `delete_season_number` | `"Ni Hao 1983"`+season='1' **原样**；`"Movie Season 2"`→`"Movie"`；`' Season 1'` 最长后缀优先于 `' 1'`；罗马 `'Ⅰ'` 后缀移除 |

**screenshot.py**（全部 mock `cv2`/`random`/`np`/`PIL`）
| 函数 | 建议首个断言点 |
|---|---|
| `get_screenshot` | mock `VideoCapture`+`random.sample`：成功返回 `(True, list)` 且 `len==number`；`PermissionError/FileExistsError` 建目录→对应中文元组；`std<=threshold` 走随机帧兜底（断言仍返回 number 张）；`sample>population` 的 `ValueError`→`(False, ['截图出错：...'])`；`cap.isOpened()==False`→`'无法加载视频'` |
| `get_thumbnail` | mock：空 `images` 时 `resized_images[0]` IndexError 被兜底为 `(False, str)`；rows×cols 网格与 `fx=fy=1/rows`；成功 `(True, path)` |

**mediainfo.py**
| 函数 | 建议首个断言点 |
|---|---|
| `get_media_info` | 不存在→`(False,'视频文件路径不存在')`；mock `MediaInfo.parse`：`f'{label:36}'` 对齐（`'Format' + 28 空格`）；Menu 章节正则 `'00_00_00000'→'00:00:00.000'`；`media_info_suffix` False 无后缀 / True 含 `'Created by Publish Helper'` |

**rename.py**
| 函数 | 建议首个断言点 |
|---|---|
| `get_pt_gen_info` | 补 ❁ 前缀、`'简'` 停止、演员 cap=5、`暂无分类`、`chinese_to_int('第五季')==5` |
| `get_video_info` | 假 MediaInfo track 断言 9 元素顺序；`writing_library` 含 x264→`'x264'`；双音轨→`audio_num=='2Audio'`；`' 1920 pixels'`→`'1080p'`；缺失文件→`(False,['视频文件路径不存在'])` |
| `get_name_from_template` | **喂真实 settings 模板键**（`main_title_movie` 等）：占位符全替换；`main_title_` 下划线→空格、`' -'→'-'`；`second_title_` `' /  \| '→' \| '`；`file_name_` 非法字符→`.`、连续点压缩；首字符 `.`/空格裁剪 |
| `rename_file` | 清洗非法字符；扩展名保留；缺失文件→`(False,'未找到文件：...')` |
| `rename_folder` | **`pytest.raises(ValueError, match='提供的路径不是一个目录或不存在')`** |
| `move_file_to_folder` | 已在该目录→`(True, 原路径)`；自动建目录 + `shutil.move` |
| `create_hard_link` | 文件→`{name}-hardlink{ext}` 同目录；文件夹→`-hardlink/` 整树 + 逐文件 `-hardlink`；`EXDEV`→`'Hard link cannot be created across different file systems'` |
| `approximate_resolution_by_width` / `load_min_widths_from_json` / `extract_numbers` | 1600→`'1080p'`、0→`'240p'`；缺文件写回创建；`extract_numbers('3840x2160')==3840`、无数字→None |

**ptgen.py**
| 函数 | 建议首个断言点 |
|---|---|
| `get_pt_gen_description` | mock `requests.get`：非 200→`'PT-Gen接口请求失败，状态码：...'`；JSON 无效→`'...不是有效的JSON格式...'`；format 空→`'获取到的PT-Gen简介为空...'`；`requests.Timeout`→`'PT-Gen接口请求超时'`；`RequestException`→`'...响应发生错误：...'`；`tt123`/`123` URL 改写；新 API 断言请求头含 `X-Signature`；`_auth_signature` 固定 time 断言 `-`/`_`/无 `=`；后处理：`&#39;`→`'`、译名重构含 `别名` 行、`personalized_signature` 前插、`img1`→`img2`；成功 `(True,(format_data,data))` |
| `get_playlet_description` | season `'1'` 不追加 / `'2'`→`' 第二季'`；固定模板逐行断言 |
| `get_data_from_pt_gen_description` | IMDb/豆瓣正则；area 表（`'美国'`→`'欧美'`、`'大陆'`）；category 表；分辨率 `2160p`→`'4K'`；audio/video/medium 表各一例 |

**picturebed.py**
| 函数 | 建议首个断言点 |
|---|---|
| `upload_picture` | 不存在→`(False,'图片文件路径不存在')`；按 URL 分发到 6 家 |
| 各 provider | mock `requests.post`：lsky `data.data.links.bbcode`；bohe `statusCode=='200'`→`bbsurl`（否则 `'未接受到响应'`）；chevereto `image.url`→`[img]...[/img]`；freeimage `res.text[:4]=='http'`→包装（否则 `(False, text)`）；imgbb `data.data.image.url`；pixhost `th_url` 的 `//t→//img` 替换 |
| `get_picture_bed_type` / `find_picture_bed_type` | `http://`→`https://`、去末尾 `/`；未配置→含 `'暂未配置'` 的中文消息 |
| `generate_image_filename` | 断言 `%Y%m%d-%H%M%S-6位数字.png` |

**torrent.py**
| 函数 | 建议首个断言点 |
|---|---|
| `make_torrent` | `tmp_path`：**断言 `t.trackers == ['https://tracker.example.com/announce']`、`t.created_by == 'Publish Helper'`**；预置同名种子验证**先删后写**；`(False,'提供的路径不存在')`；空目录→`(False,'路径指向一个空目录')` |

**poster.py**
| 函数 | 建议首个断言点 |
|---|---|
| `get_poster_url_from_data` | 5 字段命中顺序 + 嵌套 `data.*`；无→`''` |
| `download_poster` | mock `requests.get` **断言 headers 的 Chrome UA 与 `Referer: https://movie.douban.com/`**；`(True, save_path)`；超时消息 |
| `process_poster` | 上传失败时临时文件**保留**；成功时被删；`[img]` 剥成裸 URL |
| `get_poster_from_pt_gen_response` | 无海报→`(False,'No poster URL found in PT-Gen response')` |

**autofeed.py**
| 函数 | 建议首个断言点 |
|---|---|
| `get_auto_feed_link` | 真实 settings `auto_feed_link` 键；结果含 `#separator#`；尾部 `== base64encoding(原始尾部)`；无 `#separator#`→`(False,'您设置的auto_feed_link不符合规则')` |

**settings_tool.py / text.py**
| 函数 | 建议首个断言点 |
|---|---|
| `SettingsManager` 错误路径 | 损坏 JSON→`ConfigurationError`；`/` 不可写路径→`ConfigurationError`；`reset_to_defaults` 回 38 键 |
| `text.py` | `natural_keys('EP10')` 序；`int_to_roman(4)=='IV'`、`int_to_special_roman(2)=='Ⅱ'`、`int_to_chinese(11)=='十一'`、`chinese_to_int('第五季')==5`、`chinese_to_int('十')==10`；`base64encoding('中文')` 往返；`validate_and_convert_to_int` 空值/非数字 `ValueError` |

**data.py**
| 函数 | 建议首个断言点 |
|---|---|
| `get_combo_box_data` | 白名单 3 名；`backfill` 后写回；`(False,[str(e)])` |
| `update_combo_box_data` | `'\n'` 分割；文件不存在分支 `'文件不存在，已创建新文件并更新'`；损坏 JSON |
| `get_abbreviation` / `load_names` | 命中缩写 / 未命中原样返回；`data[name]` |

**API 路由（除 makeTorrent/getFile 外的 24 个）**
| 函数 | 建议首个断言点 |
|---|---|
| `getScreenshot/getThumbnail` | media 越域 401（statusCode `UNAUTHORIZED_ACCESS_ERROR`）；张数 <1/ >5 422 `VALUE_RANGE_ERROR`；起>止 422 `VALUE_RELATIONSHIP_ERROR`；mock `get_screenshot` 成功后相对路径替换 |
| `getMediaInfo/getVideoInfo` | mock 核心函数；401 越域；422 路径不存在 |
| `getPtGenDescription/getPTGenInfoByResourceUrl` | mock `get_pt_gen_description`；**断言 `description` 元组 bug**；poster 分支 |
| `getPtGenInfo` | **断言互换的 message/statusCode**；mock `get_pt_gen_info` |
| `getNameFromTemplate` | 模板白名单 9 个；越界 422 `PARAMETER_RANGE_ERROR`；`delete_season_number` 应用 |
| `renameFolder/renameFile/createHardLink` | 401 越域；422 缺参；mock 返回 |
| `moveFileToFolder` | **原始变量 401 bug（空 filePath→401 非 422）** |
| `renameEpisode/getTotalEpisode` | **文件路径→400 `'不支持文件路径：...'`**；文件夹正常；`全N集/第N-M集` 逻辑 |
| `getComboBoxData/updateComboBoxData` | 白名单；缺参 422 |
| `getSettings/updateSettings/settings/settings/update` | `settings/update` 走 `request.json`；状态码 |
| `media/file/list` | 越域 401；`{name,size,type}` 结构 |
| `autoHandleVideo` | **全部 mock**（pt_gen/screenshot/upload/thumbnail/video_info/template/rename/mediainfo/torrent）：缺参 422；`category='Movie'`→`'电影'`；`team` 含 `AGSV`→tags `['官方','冰种']`；Season 补零（`season='2'`→`'02'`） |

**GUI（src/gui/startgui.py）**
| 关注点 | 建议首个断言点 |
|---|---|
| offscreen 冒烟 | `QT_QPA_PLATFORM=offscreen` 下 `import` + `mainwindow()` 构造不崩 |
| 槽位收集回填 | mock `handle_upload_picture_*_result` 以乱序 index 入参，断言 `_upload_slots` 按序重建、失败置空、`delete_screenshot` 按序删除 |
| `WaitForRenameThread` | 直接调 `run`（不 start），mock 全局 `get_name_movie_success/failure_number` 断言轮询退出与 `(True/False)` 信号 |
| `_process_poster_in_description` | `auto_download_upload_poster` 关闭→原样；开启→`[img]` 被替换 |
| Playlet 封面 | `is_cover=True` 时 URL 前插、绕过槽位 |

---

## 7. 测试环境注意事项（写给测试实现）

1. **cwd 敏感**：`combine_directories` 基于 `os.getcwd()`，测试用 `monkeypatch.chdir(tmp_path)` 或传绝对路径；`config` 单例在 import 时初始化，测试改属性用 `monkeypatch.setattr(config, ...)`。
2. **settings 单例**：`SettingsManager()` 模块级实例在 import 时读 `static/settings.json`；隔离测试请构造 `SettingsManager(tmp_path/.../settings.json)`，不要污染真实文件（`get_abbreviation`、`get_combo_box_data`、`get_picture_bed_type` 会**写回** static 文件——需指向 tmp）。
3. **非确定性**：screenshot 的 `random.sample`、图片文件名随机 6 位 → mock；网络全部 mock（requests）。
4. **外部依赖**：`get_media_info/get_video_info` 依赖 `pymediainfo`；重命名/硬链接测试用 `tmp_path`；`create_hard_link` 跨盘 `EXDEV` 需 mock `os.link`。
5. **PyQt6**：GUI 测试需装 PyQt6 并用 offscreen 平台或直接调用 handler（绕过 `QApplication`）。
6. **开发文档纠正**：`docs/DEVELOPMENT.md` 中 `test_core.py/test_api.py/test_gui.py` 的文件树描述已过时，本文档 §6 才是真实矩阵。

---

## 8. 建议提交信息

```
[docs]:[docs][新增 docs/BUSINESS_LOGIC.md 业务逻辑契约与函数级测试覆盖矩阵文档]
```
