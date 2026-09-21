# Publish Helper 业务逻辑与测试要点

> 目标读者：后续编写与维护测试的开发者。
> 本文以「业务逻辑契约 + 函数级断言点」为核心，覆盖 `src/core/*`（11 个核心模块）、`src/utils/*`、`src/config/*`、`src/api/startapi.py`（26 个路由）、`src/gui/startgui.py`（3 个页签）、`src/main_cli.py`（3 条交互式管线）、`static/` 数据文件，并给出测试覆盖矩阵与测试环境注意事项。
>
> **本文档描述的是代码的当前真实行为，包括其中的缺陷。** 凡属 bug 的行为都明确标注为「bug / 现状」并给出行号——不是把它写成正确行为，也不是建议照此实现。改动代码后请同步本文（见文末「维护约定」）。
>
> 约定：测试一律断言**返回元组**，不依赖领域层异常（例外见 §1.2）。全部行号以 2026-09-21 的 `dev` 分支为准。

---

## 1. 横切契约（所有测试的地基，先读这一节）

### 1.1 返回约定：**约一半**函数返回 `(success, payload)` 二元组

先说结论，避免误判：`src/core/*.py` 中**模块级公开函数共 54 个，只有 27 个**在至少一条路径上 `return (a, b)` 形状的二元组。写测试前必须先确认目标函数的真实形状，不能默认全树统一。

**返回二元组的 27 个**（`文件.函数`）：

| 模块 | 函数 |
|---|---|
| `video.py` | `check_path_and_find_video`、`get_video_files` |
| `screenshot.py` | `get_screenshot`、`get_thumbnail` |
| `mediainfo.py` | `get_media_info` |
| `picturebed.py` | `upload_picture`、`get_picture_bed_type`、`find_picture_bed_type`、6 家 provider（`lsky_pro_/bohe_/chevereto_/freeimage_/imgbb_/pixhost_picture_bed`） |
| `torrent.py` | `make_torrent` |
| `rename.py` | `get_video_info`、`rename_file`、`rename_folder`、`move_file_to_folder`、`create_hard_link` |
| `ptgen.py` | `get_pt_gen_description` |
| `poster.py` | `download_poster`、`process_poster`、`get_poster_from_pt_gen_response` |
| `autofeed.py` | `get_auto_feed_link` |
| `data.py` | `get_combo_box_data`、`update_combo_box_data` |

**不返回二元组的 27 个**（旧文档漏列严重，此处补全）：

| 模块 | 函数 | 真实返回 |
|---|---|---|
| `video.py` | `is_filename_too_long` | `bool` |
| `video.py` | `delete_season_number` | `str` |
| `mediainfo.py` | （无例外） | — |
| `picturebed.py` | `generate_image_filename` | `str`（相对路径，见 §1.4） |
| `rename.py` | `get_pt_gen_info` | 8 元组（无 success 位） |
| `rename.py` | `get_name_from_template` | `str` |
| `rename.py` | `approximate_resolution_by_width` | `str` |
| `rename.py` | `load_min_widths_from_json` | `Dict` |
| `rename.py` | `extract_numbers` | `int \| None` |
| `ptgen.py` | `get_playlet_description` | `str` |
| `ptgen.py` | `get_data_from_pt_gen_description` | 8 元组 |
| `poster.py` | `get_poster_url_from_data` | `str`（空串 = 未找到） |
| `data.py` | `get_abbreviation` | `str`（未命中原样返回） |
| `data.py` | `load_names` | `json.load(...)[name]` |
| `settings_tool.py` | `get_settings` / `update_settings` / `get_settings_json` / `update_settings_json` / `combine_directories` | 值 / `None` / `Dict` / `None` / `str` |
| `text.py` | 全部 9 个公开函数（`natural_keys`、`int_to_roman`、`int_to_special_roman`、`int_to_chinese`、`chinese_to_int`、`base64encoding`、`validate_and_convert_to_int`、`chinese_name_to_pinyin`、`convert_chinese_punctuation_to_english`） | 值 |

**`src/core/` 之外没有任何函数返回二元组**——这条是测试 mock 的边界：

- `src/utils/file_utils.py` 9 个公开函数（`combine_directories`/`ensure_directory`/`safe_filename`/`get_file_hash`/`copy_with_structure`/`create_hardlink`/`find_files`/`get_file_size_human`/`load_or_initialize_json`）全部返回裸值或抛异常（`FileNotFoundError`/`ValueError`，`src/utils/file_utils.py:97,128,167,170,202,282`）；
- `src/utils/logger.py` 3 个（`ColoredFormatter.format`、`setup_logger`、`get_logger`）返回 `str`/`logging.Logger`；
- `src/config/settings.py` 5 个公开方法（`Config.get_temp_pic_dir`/`get_temp_torrent_dir`/`is_development` 与 `ImageHostConfig.get_host_config`/`get_supported_hosts`，`src/config/settings.py:68,72,76,126,131`）返回 `Path`/`bool`/`dict|None`/`list`。

`payload` 类型也不统一，测试断言形状时必须按函数逐个确认：

- `(True, [str, ...])`：`get_video_files`、`get_screenshot`（**相对** PNG 路径列表）；`get_combo_box_data`（列表）；
- `(True, str)`：`get_thumbnail`、`get_media_info`、`rename_*`/`move_file_to_folder`/`create_hard_link`、`make_torrent`、`upload_picture`、`get_auto_feed_link`、`download_poster`；
- `(True, (str, dict))` **嵌套元组**：`get_pt_gen_description`；
- 失败时 `payload` 大多为中文 `str`，但 `get_video_files` / `get_screenshot` / `get_thumbnail` 的 mkdir 分支是**单元素 `list`**，而 `get_thumbnail` 的运行期异常分支是**裸 `str`**（同一函数内两种形状，见 §2.2）。

### 1.2 异常层级：9 个类里只有 2 个是活的

`src/utils/exceptions.py` 定义 `PublishHelperError(Exception)` 与 8 个子类。全树 grep 后事实如下：

| 类 | 真实状态 | 证据 |
|---|---|---|
| `PublishHelperError` | **被 except** | `src/main_api.py:46`、`src/main_gui.py:61` 入口兜底 |
| `ConfigurationError` | **被 raise** | `src/core/settings_tool.py:120`（`_read_settings` JSON 损坏/IO）、`:132`（`_write_settings` 不可写） |
| `MediaInfoError` | 无 raise、无 except | 死类 |
| `ScreenshotError` | 无 raise、无 except | 死类 |
| `ImageUploadError` | 无 raise、无 except | 死类 |
| `TorrentError` | 无 raise、无 except | 死类 |
| `PTGenError` | 无 raise、无 except | 死类 |
| `RenameError` | 无 raise、无 except | 死类 |
| `ValidationError` | 无 raise、无 except | 死类 |

结论：**测试只许 `assert isinstance(payload, ...)` 或 `pytest.raises(ConfigurationError)`（仅 settings 文件损坏场景）**。不要写 `pytest.raises(MediaInfoError/ScreenshotError/TorrentError/...)`——那些类型永不会被抛出。

领域函数里真实的「主动抛」只有三处，注意它们的行为不对称：

- `rename_folder` 路径非目录 → `raise ValueError('提供的路径不是一个目录或不存在')` **穿透到调用方**（API 路由靠它走 500）；
- `make_torrent` 内部 `raise ValueError(...)` 但**同函数内被捕获**，对外仍是 `(False, str(e))`；
- `validate_and_convert_to_int` 空值/非数字 → `ValueError`（`src/core/text.py`）。

### 1.3 设置读取：优先级、`_BOOL_KEYS` 与两个陷阱

优先级（`src/core/settings_tool.py:136`）：**环境变量（key 大写） > `static/settings.json` > 调用方 `default`**。

`_BOOL_KEYS`（`src/core/settings_tool.py:27`，12 键，正确）：

```python
_BOOL_KEYS = frozenset({
    'auto_upload_screenshot', 'delete_screenshot', 'do_get_thumbnail',
    'enable_api', 'make_dir', 'media_info_suffix', 'open_auto_feed_link',
    'paste_screenshot_url', 'rename_file', 'create_hard_link',
    'second_confirm_file_name', 'auto_download_upload_poster',
})
```

命中该集合且值 `isinstance(value, str)` 时归一为 `value.lower() == 'true'`（`src/core/settings_tool.py:163`）。实测：`''` → `False`，`'false'` → `False`，`'True'` → `True`。非布尔键保持字符串原样（`'api_port'` 读出 `'15372'`）。legacy 键迁移 `_handle_legacy_keys` 只做两处替换：`{category}`→`{categories}`、`{total_episode}`→`{total_episodes}`（`src/core/settings_tool.py:169-189`）。

**陷阱 A —— 环境变量分支直接返回裸字符串，不做任何归一。** `src/core/settings_tool.py:148-151` 在读取缓存**之前**返回 `os.environ` 原始值，于是既跳过布尔归一、也跳过 legacy 迁移。实测：

```bash
ENABLE_API=false python -c "from src.core.settings_tool import get_settings; \
  print(repr(get_settings('enable_api')))"   # -> 'false'（str，不是 bool）
```

所以 `is False` 为假、`bool('false')` 为真。**测试若用 `monkeypatch.setenv` 控布尔开关，必须预期拿到字符串**，断言要写 `get_settings('enable_api') == 'false'` 而不是 `is False`。

**陷阱 B —— `_settings_cache` 让直接改文件不生效。** `SettingsManager._settings_cache`（`src/core/settings_tool.py:46`）一旦被 `get_setting`/`get_all_settings` 填充，后续只读缓存；只有 `_write_settings`（`:129`）会清缓存。实测：manager 读到 `True` 后，外部把 settings.json 改成 `False`，同一 manager 仍返回 `True`，新建 manager 才返回 `False`。**测试隔离必须构造独立 `SettingsManager(tmp_path/'settings.json')`，或写完文件后新建 manager。**

### 1.4 路径解析：cwd 相对，`MEDIA_DIR`/temp helper 全是死代码

`combine_directories` 有**两份实现，且不等价**（旧文档称「等价」有误）：

| 位置 | 实现 | 生效情况 |
|---|---|---|
| `src/utils/file_utils.py:32` | `os.path.join(os.getcwd(), path)` | **唯一被实际调用的一份** |
| `src/core/settings_tool.py:289` | `str(Path.cwd() / relative_path)` | **模块内零调用，死代码** |

实测三种不相等情形（Windows）：

```text
'media'    -> file_utils: '...\publish-helper\media'   settings_tool: '...\publish-helper\media'   相等
'temp/pic' -> file_utils: '...\publish-helper\temp/pic' settings_tool: '...\publish-helper\temp\pic' 不等
''         -> file_utils: '...\publish-helper\'        settings_tool: '...\publish-helper'         不等
'/abs/x'   -> file_utils: 'C:/abs/x'                    settings_tool: 'C:\abs\x'                   不等
```

差异点：分隔符（`os.path.join` 不归一化已有 `/`，`Path` 会）、空串尾分隔符、绝对路径入参（`os.path.join` 丢弃前面的 cwd，`/` 运算符也丢弃但改写分隔符）。**断言路径字符串时不要混用这两份。**

**`config.MEDIA_DIR` 在 `src/` 内零消费**，只在 `src/config/settings.py:23` 定义、`:61` 建目录。API 的真实资源根是 `src/api/startapi.py` 里 **13 处 `combine_directories('media')`**（行号：111, 295, 509, 588, 904, 1043, 1106, 1181, 1245, 1320, 1454, 1902, 2003），即 **cwd 相对**。测试必须 `monkeypatch.chdir(tmp_path)`；改 `config.MEDIA_DIR` 对 API 越域判定**无效**。（第 14 处 `combine_directories` 调用在 `:746`，作用于 `screenshot_storage_path`。）

同理 `Config.get_temp_pic_dir()` / `get_temp_torrent_dir()`（`src/config/settings.py:68,72`）在 `src/` 内**零调用**：截图目录取自 settings 键 `'screenshot_storage_path'`（当前值 `'temp/pic'`），种子目录取自 `'torrent_storage_path'`（当前值 `'temp/torrent'`），两者都是**相对路径**，同样走 cwd。

其余约定：`config.STATIC_DIR = BASE_DIR/"static"`（仓库根 `static/`，非 `src/static/`）；`static/` 下实际文件为 `settings.json`、`abbreviation.json`、`combo-box-data.json`、`picture-bed-data.json`、`ph-bjd.ico`。注意 `data.py`、`picturebed.py` 也走 `combine_directories('static/...')`（`src/core/data.py:12,71,109`、`src/core/picturebed.py:279`），即**同样 cwd 相对**，不是 `STATIC_DIR`。

截图/缩略图返回的路径是**相对路径**：`generate_image_filename`（`src/core/picturebed.py:374-381`）只做 `base_path + '/' + filename`，从不 `os.path.abspath`。GUI（`src/gui/startgui.py:330,371,990,1031,1619,2058`）与 API（`src/api/startapi.py:144,326`）传入的都是 settings 的相对值 `'temp/pic'`（API `:2129` 更直接硬编码 `screenshot_storage_path = 'temp/pic'`）——**无一处 abspath**；`src/api/startapi.py:746` 唯一例外地做了 `combine_directories(get_settings('screenshot_storage_path'))`，但那只用于 poster 分支。实测 `os.path.isabs(generate_image_filename('temp/pic')) is False`。API 侧的 `imagePath.replace(media_path, '')`（`src/api/startapi.py:205,210`）对这种相对路径**不产生效果**（前缀不匹配）。

### 1.5 logger 的双 `config` 陷阱（必须写进测试注意事项）

`src/utils/logger.py:8` 是**扁平导入 `from config.settings import config`，且没有 import 兼容桥**——对比 `src/core/settings_tool.py:12-22`、`src/utils/file_utils.py:13-17` 都有 `try/except ModuleNotFoundError` + `sys.path` 插入。后果可实测：

```bash
python -c "import src.utils.logger"
# ModuleNotFoundError: No module named 'config'
```

当 `src/` 被入口自举到 `sys.path` 后它能 import 成功，但此时 `config.settings` 与 `src.config.settings` 是**两个不同模块对象**，各自持有一个 `Config` 实例：

```text
logger.config 的类来自模块:  config.settings
src.config.settings 的类:    src.config.settings
logger.config is src.config.settings.config -> False
```

于是 `monkeypatch.setattr(config, 'LOG_LEVEL', ...)`（操作 `src.config.settings.config`）**控不到 logger 的级别与文件路径**；`get_logger()` 调用 `setup_logger(level=config.LOG_LEVEL, log_file=config.LOG_FILE)`（`src/utils/logger.py:101-105`），用的永远是另一份实例。实测默认落地 `logs/app.log`，且每个 logger 装两个 handler：`FileHandler(app.log, level=20)` + `ColoredStreamHandler(stdout, level=20)`。**测试要么 monkeypatch `src.utils.logger.config` 上对应的属性名，要么接受日志写真实 `logs/app.log`（不要断言日志文件内容）。**

### 1.6 断言模板

```python
from src.core.video import check_path_and_find_video

def test_xxx(tmp_path):
    ok, payload = check_path_and_find_video(str(tmp_path))   # 先读源码确认形状
    assert ok is False
    assert payload == '文件夹中没有符合类型的视频文件'          # 错误串逐字
```

---

## 2. 核心模块业务逻辑（src/core）

### 2.1 video.py —— 视频路径判定与文件列举

| 项 | 内容 |
|---|---|
| 常量 | `VIDEO_EXTENSIONS`（`src/core/video.py:7`）11 种：`['.mp4','.m4v','.avi','.flv','.mkv','.mpeg','.mpg','.rm','.rmvb','.ts','.m2ts']`，匹配前统一 `.lower()`，故大小写不敏感；`MIN_WIDTHS`（`:9-17`）7 项：`{'9600':'8640p','4608':'4320p','3200':'2160p','2240':'1440p','1600':'1080p','900':'720p','533':'480p'}`。两个常量都被函数内**复用**而非重复定义（`:21`、`:55` 有注释说明） |
| `check_path_and_find_video(path) -> (int, str)` | 前置清理：先去末尾 `/`（`:24-25`），再去开头 `file:///`（`:28-29`，只替换第一处）。**三态码**：`1` = 文件且扩展名匹配 → `(1, path)`；`2` = 目录内首个匹配 → `(2, path + '/' + file)`（用 `/` 硬拼，非 `os.path.join`）；`0` = 全部错误分支 |
| 三条错误消息（逐字） | `f'路径下获取到文件{path}，但该文件不符合视频类型'`（`:36`）；`'文件夹中没有符合类型的视频文件'`（`:45`）；`f'您提供的路径{path}既不是文件也不是文件夹'`（`:49`）。注意前两条带 `print`，且第三条的 `path` 是**清理后**的值（实测输入 `'C:/nope'` → `'您提供的路径C:/nope既不是文件也不是文件夹'`） |
| `get_video_files(folder_path) -> (bool, list)` | 无效目录（不存在或非目录）抛内部 `ValueError(f'您提供的路径"{folder_path}"不是一个有效的目录。')` 并被捕获 → `(False, [f'错误：{e}'])`，即**错误串包在单元素列表里且带 `"` 引号**（实测 `['错误：您提供的路径"C:/nope"不是一个有效的目录。']`）。成功 `(True, video_files)`，路径由 `os.path.join` 拼接，排序键 `natural_keys`（自然序，`EP2 < EP10`） |
| `is_filename_too_long(filename) -> bool` | `len(filename) > 250` → `True`（`:81`，边界 250 False / 251 True） |
| `delete_season_number(title, season_number) -> str` | 先 `title.rstrip()`（`:91`）；候选后缀 7 个（`:92-100`）：`' Season N'`、`' season N'`、`' SeasonN'`、`' seasonN'`、`' N'`、`' ' + int_to_roman(N)`、`' ' + int_to_special_roman(N)`；**按长度降序匹配**（`:102` `sorted(suffixes, key=len, reverse=True)`）避免 `' Season 1'` 被 `' 1'` 抢先，命中即 `break`；末尾 `title.strip()`。实测：`('Ni Hao 1983','1') -> 'Ni Hao 1983'`（不误伤）、`('Movie Season 1','1') -> 'Movie'`、`('Movie II','2') -> 'Movie'` |

**测试要点**：三态码三分支 + 三条中文消息逐字；`file:///` 与末尾 `/` 归一（注意归一后的 `path` 会进入错误串）；空目录的 `(0, '文件夹中没有符合类型的视频文件')`；自然排序；`['错误：...']` 列表形状；250 边界；`delete_season_number` 的降序匹配优先级与罗马数字两支。

### 2.2 screenshot.py —— 截图与缩略图（非确定性，必须 mock）

| 项 | 内容 |
|---|---|
| `get_screenshot(video_path, screenshot_path, screenshot_number, screenshot_threshold, screenshot_start, screenshot_end, screenshot_min_interval=0.01) -> (bool, list)`（`src/core/screenshot.py:15`） | 目录先建（`:19-31`），`VideoCapture` 打不开 → `(False, ['无法加载视频'])`（`:36-38`）；`total_frames = int(CAP_PROP_FRAME_COUNT)`、`fps = CAP_PROP_FPS`、`duration = total_frames / fps`（`:40-42`）；`start_frame = int(total * screenshot_start)`、`end_frame = int(total * screenshot_end)`（`:46-47`）；**`screenshot_min_interval = duration * screenshot_min_interval`（分数→秒，`:48`，变量被原地覆盖）**；`timestamps = sorted(random.sample(range(start_frame, end_frame), screenshot_number))`（`:56`，**`number > 区间长度` 会抛 `ValueError`**）；`last_keyframe_time` 初值 `-screenshot_min_interval`（`:53`） |
| 关键帧两条件 | `current_time = timestamp / fps`（`:65`），只有 `current_time >= last_keyframe_time + screenshot_min_interval`（`:66`）**且** `np.std(frame) > screenshot_threshold`（`:70`，严格大于）才取为关键帧并更新 `last_keyframe_time = current_time`（`:75`）。**两个条件不满足各有独立兜底分支**：复杂度不足（`:76-84`）与间隔不足（`:85-93`）都走 `random.sample(range(start_frame, end_frame), 1)[0]` 重取一帧，且**兜底帧不校验、不更新 `last_keyframe_time`**。`cap.read()` 返回 `not ret` 时 `continue`（`:62-63`） |
| 成功/失败形状 | 成功 `(True, extracted_images)`（`:98`，**相对路径列表**，见 §1.4）；运行期任何异常 → `(False, [f'截图出错：{e}'])`（`:99-101`，**单元素列表**）。实测 `random.sample` 抛 `ValueError('sample>pop')` → `(False, ['截图出错：sample>pop'])` |
| **资源释放不对称** | `cap.release()` 只在**成功路径** `:95`，异常路径（含 `sample` 越界、`Image.save` 失败）**不 release，句柄泄漏**。旧文档未记。 |
| mkdir 三种错误消息 | `PermissionError` → `print('权限不足，无法创建目录')` + `(False, ['权限不足，无法创建目录'])`（`:23-25`，**注意 print 带句号、payload 不带**）；`FileExistsError` → `(False, ['路径已存在，且不是目录'])`（`:26-28`）；其它 → `(False, [f'创建目录时出错：{e}'])`（`:29-31`） |
| `get_thumbnail(video_path, screenshot_storage_path, thumbnail_rows, thumbnail_cols, screenshot_start_percentage, screenshot_end_percentage) -> (bool, str)`（`:104`） | mkdir 同上三种（`:107-118`，print 文案**带句号**：`'已创建输出路径。'`/`'权限不足，无法创建目录。'`/`'路径已存在，且不是目录。'`，但 payload 串仍是上面三句、不带句号）。`interval = (end_frame - start_frame) // (cols * rows)`（`:133`，**整除，可能为 0**） |
| 「打不开视频」形状与 `get_screenshot` **不一致** | `raise Exception('Error: 无法打开视频文件')`（`:124`），被 `:174-176` 兜底 → `(False, 'Error: 无法打开视频文件')`（**裸 `str`，不是列表**）。`get_screenshot` 是直接 `return False, ['无法加载视频']`（列表、中文、无 `Error:` 前缀）。**同一模块两种形状必须分别断言。** |
| 取帧与拼接怪癖 | 按 `cols * rows` 次循环，`frame_number >= end_frame` 时 `break`（`:139-140`）；`read()` 失败 → `raise Exception(f'Error: 无法读取第 {i + 1} 张图像')`（`:146`）；图像数不足仅 `print` 警告（`:151-152`）；`cv2.resize(image, (0, 0), fx=1.0/thumbnail_rows, fy=1.0/thumbnail_rows)`（`:154-155`，**fx 与 fy 都用 `thumbnail_rows`，与 `thumbnail_cols` 无关——row/col 不对称的怪癖**）；白底画布 `np.ones((cols*(h+2*5), rows*(w+2*5), 3), uint8) * 255`（`:156-159`，**外圈 rows、内圈 cols**，与 resize 的 rows 分母配合）；`border_size = 5` |
| `get_thumbnail` 失败形状 | `except Exception` → `(False, str(e))`（`:174-176`，**裸 `str`**）。`len(images) == 0` 时 `resized_images[0]` 抛 `IndexError`（`:157`）被兜成 `(False, 'list index out of range')`；实测 `read()` 恒 False → `(False, 'Error: 无法读取第 1 张图像')` |
| **`get_thumbnail` 更严重的资源陷阱** | `video_capture = None`（`:119`），`finally: video_capture.release()`（`:178-179`）。若 `cv2.VideoCapture(...)` **构造函数自身抛异常**，`video_capture` 仍是 `None`，`finally` 抛 `AttributeError: 'NoneType' object has no attribute 'release'`，**且它抛在 `except` 之外**，异常直接穿透到调用方（实测确实如此）。而正常运行时 `finally` 保证 release，与 `get_screenshot` 相反 |
| 成功返回 | `(True, thumbnail_path)`（`:182`，在 `finally` 之后，**相对路径**）；成功时 `print(f'拼接后的图像已保存到{thumbnail_path}')` |
| `generate_image_filename(base_path) -> str`（`src/core/picturebed.py:374-381`） | `datetime.now().strftime('%Y%m%d-%H%M%S')` + `'-'` + `''.join(random.sample('0123456789', 6))` + `'.png'`；拼 `base_path + '/' + filename`（**手拼 `/`，不 abspath**） |

**测试要点**：mock `cv2.VideoCapture`（**同时 mock `isOpened` 与 `get`**）、`random.sample`、`np.std`、`PIL.Image`、`generate_image_filename`；分别断言 `get_screenshot` 的 `['无法加载视频']` 列表与 `get_thumbnail` 的 `'Error: 无法打开视频文件'` 裸串；两个函数的 **mkdir 三种失败分支**（各自的 `PermissionError`/`FileExistsError`/其它）与「打不开视频」分支（形状不同，见上）；`screenshot_min_interval == duration * 分数`；关键帧两条件的**同时满足**与两条兜底分支；`fx=fy=1/rows`；`get_thumbnail` 的 `IndexError`/读帧失败兜底与「构造函数抛异常 → `AttributeError` 穿透」；`sample > population` 的 `(False, [...])`；返回图片数 == `screenshot_number`；`generate_image_filename` 的 6 位数字与 `.png` 后缀与相对路径（`os.path.isabs(...) is False`）。

### 2.3 mediainfo.py —— MediaInfo 论坛文本

| 项 | 内容 |
|---|---|
| `get_media_info(file_path) -> (bool, str)`（`src/core/mediainfo.py:10`） | 路径不存在 → `print('文件路径不存在')` + `(False, '视频文件路径不存在')`（`:11-13`）。成功 `(True, output)`（`:200`）。**注意路径检查在 `try` 之外**，`file_path` 为 `None` 时 `os.path.exists(None)` 会先抛 `TypeError` |
| 字段取值规则 | `value = track[key][0] if isinstance(track.get(key), list) else track.get(key)`（四处：`:57`、`:112`、`:151`、`:179`）。**mock 假 track 时必须把值写成单元素列表**才能取到，写成裸标量也能取（走 `else` 分支），但 `[]` 空列表会 `IndexError`。仅 `value is not None` 才输出（`:58,113,152,180`） |
| 文本对齐 | 一律 `f'{label:36}: {value}\n'`——label 左对齐补空格到 36 列，实测 `f'{"Format":36}: X'` == `'Format' + ' '*30 + ': X'` |
| track 分段文案 | General：`'General\n'`（`:34`）；Video：`'\nVideo\n'` **前置换行**（`:65`）；Audio：`f'\nAudio #{audio_count}\n'`（`:118`）；Text：`f'\nText #{text_count}\n'`（`:159`）；Menu：`f'\nMenu\n'`（`:184`，f-string 无占位符）。计数器 `audio_count, text_count` **均从 1 起、每遇到一条同类 track 自增**（`:27`、`:119`、`:160`），实测两条 Audio → `Audio #1`、`Audio #2`，Text 独立计数也从 `#1` 起 |
| General 独有处理 | `label == 'Complete name'` 时 `value = os.path.basename(value)`（`:59-60`，只留文件名去路径） |
| Audio 独有的跳过 | `label == 'Delay relative to video' and value == '00:00:00.000'` → `continue`（`:153-154`）。实测 `'00:00:00.000'` 不输出，`'00:00:00.001'` 正常输出 |
| Menu 解析 | 遍历 `track.items()`，`re.match(r'(\d{2})_(\d{2})_(\d{5})', key)`（`:188`）匹配后 `divmod(int(seconds_millis), 1000)` 拆秒/毫秒，格式化为 `f'{hours}:{minutes}:{seconds:02}.{millis:03}'`（`:193`），输出 `f'{timestamp:36}: {value}\n'`（`:195`）。实测 `'00_00_00000'` → `00:00:00.000` |
| suffix 文案 | `if get_settings('media_info_suffix'): output += '\nCreated by Publish Helper'`（`:197-198`）——**前置换行、无尾换行**，精确串 `'Created by Publish Helper'`（无句号） |
| 错误分流 | 异常顺序是 **`except OSError`（`:202-205`）在前，`except Exception`（`:206-209`）在后**。`OSError` → `(False, f'文件路径错误：{e}')`；其余 → `(False, f'无法解析文件：{e}')`。实测 mock 抛 `PermissionError('denied')`（`OSError` 子类）走「文件路径错误」，抛 `RuntimeError('oops')` 走「无法解析文件」 |
| 隐性 `KeyError` 兜底 | `data['tracks']`（`:31`）与 `track['track_type']`（`:32` 等）都用**下标**取键。`to_json()` 缺 `tracks` 键 → `KeyError('tracks')` → 兜成 `(False, "无法解析文件：'tracks'")`（实测）；track 缺 `track_type` → `(False, "无法解析文件：'track_type'")`。`json.loads` 失败（如 `to_json()` 返回非 JSON）→ `(False, '无法解析文件：Expecting value: line 1 column 1 (char 0)')` |

**测试要点**：mock `pymediainfo.MediaInfo.parse`（**返回值只需实现 `to_json()`**）与 `src.core.mediainfo.get_settings`（**必须 mock，否则读真实 settings 的 `media_info_suffix`**）；用**真实存在的临时文件路径**喂 `file_path`，否则会在 `:11` 提前返回；假 track 字段用列表形状；断言 `{label:36}` 对齐、`Complete name` 剥路径、`Delay relative to video` 跳过、`Audio #N`/`Text #N` 自增、Menu 时间戳正则、`OSError` vs 其它异常的两条消息、suffix 开/关（精确串 `'\nCreated by Publish Helper'`）。

---

### 2.4 rename.py —— 命名流水线（623 行）

模块导入：`src/core/data.py::get_abbreviation`、`src/core/settings_tool.py::get_settings`、`src/core/text.py::chinese_to_int`、`src/core/video.py::MIN_WIDTHS`、`pymediainfo.MediaInfo`（`src/core/rename.py:8-13`）。

**测试隔离要点**：`get_abbreviation` 与 `approximate_resolution_by_width` 读的是 **cwd 相对的 `static/abbreviation.json`**（`combine_directories = os.path.join(os.getcwd(), path)`，`src/utils/file_utils.py:32`），不是 `config.STATIC_DIR`。已实测：把 cwd 切到一个含自定义 `static/abbreviation.json` 的临时目录后，两个函数都读到该临时文件。测试必须 `monkeypatch.chdir` 或隔离 `static/`，否则会读真实仓库表。

**另一条隐蔽陷阱**：本模块不做 `sys.stdout` 编码兜底（`ptgen.py` 才做，见 §2.5），但 `get_pt_gen_info` 单函数就有 **19 处 `print`**（`rename.py:33,35,53,57,61,69,75,89,98,113,153,237,252-257,259`），会原样打印 description / 标题等内容。在 Windows `cp936` 控制台下，输入含 `❁`、`◎` 等字符时 `print` 抛 `UnicodeEncodeError` 并从函数中逃逸（已实测：`python -c "get_pt_gen_info('❁ 片　　名: X…')"` 在 gbk stdout 下抛 `UnicodeEncodeError: 'gbk' codec can't encode character '❁'`）。测试须 `-X utf8` / `PYTHONIOENCODING=utf-8`，或 `redirect_stdout` 到 `io.StringIO`。

#### 2.4.1 `get_pt_gen_info(description, raw_data=None) -> 8 元组`（`rename.py:17-260`）

签名与返回（`rename.py:17-32`、`260`）：

```
(description: str, raw_data: Optional[Dict[str, Any]] = None)
 -> Tuple[str, str, Union[str,int], List[str], str, List[str], Optional[int], Optional[int]]
返回 (original_title, english_title, year_result, other_titles, categories, actors, episodes, season)
```

**入口预处理**（`37-38`）：`description.replace('\\n', '\n')` 再 `description.replace('\\\n', '\\n')`。即「反斜杠+字母 n」被还原为真换行；而「反斜杠+真换行」被还原成字面 `\n`。已实测：把 `◎译　　名　中文名\n◎片　　名　Movie EN\n`（反斜杠是字面量）喂进去，能正确解析出 `('中文名', 'Movie EN', '2020', '动作')`。

**raw_data 分支——只读 7 个 JSON 键**（`50-113`）

| 键 | 行为 | 行号 |
|---|---|---|
| `chinese_title` | `raw_data.get(...) or ''`，空则回落正则 | 52 |
| `foreign_title` | 同上 | 56 |
| `year` | `str(raw_data.get('year','') or '')`；`year=0` 因 `or` 被当作空 → 回落正则（已实测 `{'year':0}` → `''`）。**注意 `raw_year` 是 `str`**，与正则分支同为 str | 60 |
| `aka` | 仅当 `isinstance(list)`；逐项 `strip()`，非空 **且 `!= raw_original_title` 且 `!= raw_english_title`** 才保留 | 64-69 |
| `genre` | 仅当 `isinstance(list) and genre_list`；`' / '.join(...)`（空列表→`''`→回落正则） | 72-75 |
| `cast` | 仅当 `isinstance(list)`；逐项 `re.search(r'([一-龥·]+)', str(name))`（**源码用 `一-龥` 转义形式，不是字面量汉字区间**），命中就 append；`len>=5` break | 78-89 |
| `episodes` | `int()` 强转，`(ValueError, TypeError)` 静默吞 | 92-98 |

**`season` 不是 raw_data 字段**（`100-113`）：raw_data 分支里**不读** `raw_data['season']`，也**不打印**它的值。`raw_season` 只在 `raw_original_title`（即 `chinese_title`）非空时，从该标题用正则派生：

```
第(\d+)季|第([零一二三四五六七八九十百千万]+)季|Season (\d+)
```
（`102`；汉字分支的 `chinese_to_int` 包着 `except ValueError: pass`——**死代码**，`text.chinese_to_int` 内部已 `except ValueError: return None`，永不抛，见 `src/core/text.py:181-182`）

已实测：`{'chinese_title':'双面女间谍 第五季','season':3}` → `season=5`（标题派生的覆盖语义，实际是只认标题）；`{'chinese_title':'无季','season':3}` → `None`（**显式传入的 `season=3` 被静默忽略**）；`{'chinese_title':'','season':3}` → `None`。API 路由若单独回传 `season` 键，**完全无效**。

**`cast` 分支无 `'简'` 判断**：raw_data 的 `cast` 逐项提取中文，没有任何 `'简'` 特判（对比正则回退分支 `206`）。已实测 `{'cast':['Tom Hanks (汤姆·汉克斯)','英文only','张三']}` → `['汤姆·汉克斯','英文','张三']`——第二项取到的是字符串里的乱入汉字「英文」，说明纯英文串若含任意汉字仍会被收进来。

**非 dict 的 `raw_data` 会在打印处崩溃**（`34-35`）：`if raw_data:` 只做真值判断，随后 `list(raw_data.keys())`。已实测 `get_pt_gen_info(desc, ['x'])` → `AttributeError: 'list' object has no attribute 'keys'`。测试若传非 dict 需预期该异常。

**正则回退分支（`115-240`）**

字段正则表（`◎` 格式为主，`❁` 为备用）：

| 字段 | 首选正则 | `❁` 备用正则 | 行号 |
|---|---|---|---|
| categories | `◎类　　别\s*([^\n]*)` | `❁[\s　]*类[\s　]*别[\s　：:]*([^\n]*)` | 118, 126 |
| episodes | `◎集　　数\s*(\d+)` | `❁[\s　]*集[\s　]*数[\s　：:]*(\d+)` | 119, 128 |
| year | `◎年　　代\s*(\d{4})`；失败回落 `◎上映日期\s*(\d{4})` | `❁…年…代…(\d{4})`；再失败 `❁…上映日期…(\d{4})` | 120-122, 130-132 |
| 片名/译名 | `◎片　　名　(.*?)\n\|◎译　　名　(.*?)\n` | `❁[\s　]*片[\s　]*名[\s　：:]+([^\n]+)\|❁[\s　]*译[\s　]*名[\s　：:]+([^\n]+)` | 135, 142 |
| 演员 | `(◎主　　演｜◎演　　员)\s*((?:[\s　]*.*?(?:\n\|$))*)`，`MULTILINE\|DOTALL` | `(❁…主…演｜❁…演…员)[\s　：:]*((?:[\s　]*.*?(?:\n\|$))*)` | 177-180, 186-189 |

**`◎` 格式要重排、`❁` 格式不重排**（`137`、`147-148`）：`used_circle_prefix = bool(matches)` 在首次 `findall` 后立即固化；只有它为真（走 `◎` 分支）才 `matches.insert(0, matches.pop())`。因为 `◎` 格式里 `译名` 行在 `片名` 行之前，重排后「原片名」才在第 0 位。已实测两种行序（`◎片` 在前 / `◎译` 在前）都得到 `original_title='中文名'`、`english_title='Movie EN'`。

**英文/中文标题判定**（`152`、`156-169`）：先 `separated_titles = [t.strip() for 组 in titles for t in 组.split('/')]`——**标题按 `/` 切分**；`english_pattern` 为纯 ASCII/罗马数字白名单（`^[A-Za-z\-\—\:\s\(\)…\dⅠ-ↈ]+$`），首个 `re.match` 命中者即 `regex_english_title`；`original_pattern` 是含 `一-龥` 等大字符集的正则（`163-165`，**同理为转义形式**），命中**且 `not re.match(english_pattern, title)`** 者为首个 `regex_original_title`。其余全部进 `regex_other_titles`（`171`）。

已实测：`◎译　　名　中文名 / 别名A` + `◎片　　名　English Title` → `other_titles=['别名A']`；`❁ 译　　名:　中文名1 / 中文名2` + `❁ 片　　名:　English Title` → `other_titles=['中文名2']`。

**演员行终止条件（`192-213`）——范围远宽于「遇到 `'简'` 才停」，且只存在于正则分支**

```python
cleaned_actor = re.search(r'([一-龥·]+)', cleaned_line)
if cleaned_actor and cleaned_actor.group() != '简':
    regex_actors.append(cleaned_actor.group())
else:
    break
```

- `cleaned_actor is None`（**该行完全不含汉字**，例如纯英文演员行）走 `else` → **立即 break**。已实测：`◎主　　演　Tom Hanks\n张　三\n李　四…` → `actors=[]`（纯英文首行直接终结采集）；把首行换成 `张　三` 后正常取到 5 个。
- 含汉字但 `group() == '简'` 同样 break。
- 上限 5（`len(regex_actors) == 5`，`212-213`），**写在 `append` 之后**，所以每轮最多入列 1 个。
- 清洗：每行先 `re.sub(r'[\s　]+', ' ', line.strip())` 压空白，再提取首个连续汉字串。**这是「取每行首个汉字串」而非「去除非汉字」**——`张　三` → `张`（已实测）。
- 两个演员行前缀都认：`◎主　　演` 与 `◎演　　员`（`177-178`）。已实测 `◎演　　员　张　三\n李　四` → `['张','李']`。

**类别被改写为 `'暂无分类'` 的三条件（`215-216`）**

```python
if '◎语　　言' in regex_categories or '❁' in regex_categories or (regex_categories and '语' in regex_categories[:5]):
```

- 条件 1：**类别串内部**含字面量 `◎语　　言`；
- 条件 2：类别串内部出现任意 `❁`（错位解析的典型残留）；
- 条件 3：**类别串前 5 个字符内任意位置含 `语`**（不是「以语开头」）。

已实测（皆为 `'暂无分类'`）：`语`、`语言`、`剧情 语言`、`剧情❁`、`动作语`、`xxx语`；不命中：`剧情`、`剧情 / 语言`（`语` 在第 8 个字符处）。

**季数正则回退版比 raw 版更宽（`223`）**

```
Season (\d+)|season (\d+)| (\d+)st|第(\d+)季|第([零一二三四五六七八九十百千万]+)季
```

- 多出 `season` 小写、` (\d+)st`（**前置一个半角空格**），少了 raw 版的 `Season (\d+)` 之外不区分大小写的能力（实际靠并列小写分支补齐）。
- 已实测：`第5季`→5、`第五季`→5、`Season 3`→3、`season 3`→3、` 3st`→3、`第五十五季`→55；**不命中**：`2nd`（正则只认 `st`）、`第 5 季`（数字与「季」之间不允许空格）。
- `group(5)` 的汉字分支有 `except ValueError: print(e); regex_season = None`（`234-238`），同样是死代码（`chinese_to_int` 永不抛）。

**`episodes` 的 `int()` 失败被静默吞掉**（`219`）：`int(episodes_match.group(1)) if episodes_match else None`。因正则本身只匹配 `\d+`，理论上只在超长数字场景触发；`◎集　　数　abc` 实测得 `None`（正则未命中）。

**`◎片　　名` 行末必须有 `\n`**（`135`）：末行为 `◎片　　名　EN`（无换行）时 `english_title` 为 `''`；补上 `\n` 后得 `'EN'`。`❁` 备用正则用的是 `([^\n]+)`，不要求行尾换行——已实测 `❁ …片名: EN`（无换行）仍能取到。

**逐字段合并（`243-250`）**：`raw_*` 与 `regex_*` 一一对应，raw 侧「非空 / 非 None」优先：

| 输出位 | 判定 |
|---|---|
| `original_title` | `raw_original_title if raw_original_title else regex_original_title` |
| `english_title` | 同上 |
| `year_result` | 同上（`raw_year` 是 str，`'0'` 为真值但 `0` 在 raw 侧已被 `or ''` 变空） |
| `other_titles` | `raw_other_titles if raw_other_titles else regex_other_titles` |
| `categories` | 同上 |
| `actors` | 同上 |
| `episodes` | `raw_episodes if raw_episodes is not None else regex_episodes` |
| `season` | `raw_season if raw_season is not None else regex_season` |

**若只想测正则分支，`raw_data` 必须传 `None` 或 `{}`**——传 `{}` 会跳过 `if raw_data and isinstance(...)` 整块，等价于纯正则。

#### 2.4.2 `get_video_info(file_path) -> (bool, 9 元素 list)`（`rename.py:264-356`）

| 项 | 内容 |
|---|---|
| 路径不存在 | `(False, ['视频文件路径不存在'])`（`266-267`），**先于 try**，不打印 JSON |
| 路径相关异常 | `except OSError` → `(False, [f'文件路径错误：{e}。'])`（`349-352`，**末尾全角句号**） |
| 解析失败 | `except Exception` → `(False, [f'无法解析文件：{e}。'])`（`353-356`，同上） |
| 成功 | `(True, [video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num, tags])`（`346-348`），**全部经过 `get_abbreviation`**，只有 `audio_num`/`tags` 原样 |

**track 聚合规则（含容易漏记的累加点）**

| track | 字段 | 赋值方式 | 行号 |
|---|---|---|---|
| General | `other_frame_rate[0]` | `=`（覆盖） | 285-287 |
| Video | `other_width` / `other_height` / `other_format` / `other_hdr_format` / `other_bit_depth` | 全部 `+=`（**跨多条 Video track 字符串拼接**） | 291-300 |
| Video | `writing_library` | 含 `x264`/`x265`/`x266` 时**覆盖** `video_codec`（值为小写 `'x264'` 等） | 301-307 |
| Audio | `commercial_name` / `channel_layout` | 仅 `audio_count == 0` 时取（**首条 Audio**） | 310-315 |
| Audio | `other_language` | `'Chinese'`→`国语`，`'English'`→`英语`，**append 前有 `not in tags` 去重守卫** | 316-319 |
| Text | `other_language` | `'Chinese'`→`中字`，`'English'`→`英字`，同样带去重守卫 | 323-327 |

已实测多 track 的后果：两条 Video（`1 920 pixels` + `1 280 pixels`）→ `width` 变成 `'1 920 pixels1 280 pixels'`、`video_codec` 变成 `'AVCHEVC'`，`extract_numbers` 拼出 `19201280`，分辨率落到 `8640p`（两条 track 全部数据被当成一个数）。**测试应覆盖「两条 Video track」这一失真路径**。

**`writing_library` 的三个 `if` 是并列的**（`302-307`）：同时含 `x264` 与 `x265` 时后者胜；写的是小写。

**末位兜底链**（`329-345`）

```python
width_num = extract_numbers(width); height_num = extract_numbers(height)
if (width_num or 0) > (height_num or 0):   # 取较长边
    video_format += width
else:
    video_format += height
video_format = get_abbreviation(video_format)
if video_format[-7:] == ' pixels':
    video_format = approximate_resolution_by_width(extract_numbers(video_format) or 0)
```

- 判定是**严格大于**；相等（如两条都 `None`）走 else。
- **兜底只在 `get_abbreviation` 结果仍以 `' pixels'` 结尾时触发**——即表里没有该键，`get_abbreviation` 原样返回。表里已有的键（`'7 680 pixels'→'4320p'`、`'1 920 pixels'→'1080p'` 等，`data.py:116-123`）直接命中，永不进兜底。已实测：`'1 920 pixels'`→`'1080p'`（不走兜底）、`'8 192 pixels'`→仍为 `'8 192 pixels'`→兜底 `approximate_resolution_by_width(8192)`→`'4320p'`、`'4 320 pixels'`→兜底。
- 兜底后**不再二次查表**：`5 000 pixels` → 兜底返回 `'4320p'`（直接落字符串）。
- 竖屏资源取较长边：`720x1280` → `'720p'`（`height` 侧）。

**`audio_num`**（`342-345`）：`audio_count == 1` → `''`；否则 `str(audio_count) + get_abbreviation('Audio')`，而 `'Audio'` 在表里映射为 `'Audio'`，所以常见输出 `'2Audio'`；`audio_count == 0`（无 Audio track）同样走 else → **实测得 `'0Audio'`**。

#### 2.4.3 分辨率辅助（`rename.py:359-412`）

| 函数 | 契约 | 行号 |
|---|---|---|
| `approximate_resolution_by_width(width: int) -> str` | 读 `load_min_widths_from_json('static/abbreviation.json')`；对 `sorted(midpoints.keys(), reverse=True)` 取首个 `width >= k` 的 `midpoints[k]`；全不命中 → `'240p'`。已实测 `1920→'1080p'`、`0→'240p'`（无 `>= 0` 的键）、`8192→'4320p'`、`9600→'8640p'` | 360-366 |
| `load_min_widths_from_json(filepath='static/abbreviation.json') -> Dict[int,str]` | 默认表 `MIN_WIDTHS`（`src/core/video.py:9-17`，键为字符串）。**只捕 `FileNotFoundError` / `JSONDecodeError`**：`PermissionError` / `IsADirectoryError` / `UnicodeDecodeError` 会向上抛（已实测：目录 → `PermissionError`，坏 UTF-8 → `UnicodeDecodeError`）。命中 `min_widths` 键 → `{int(k): v}` 返回。缺键/异常 → 走写回块：`data['min_widths'] = default_min_widths`、**`os.makedirs(os.path.dirname(filepath), exist_ok=True)`**、`json.dump(indent=4)`；写回整块被 `except Exception: print(...)` 包住。末行统一 `return {int(k): v for k,v in default_min_widths.items()}`（注意**返回的是默认表，不是刚读到的 data**，只影响「读到了别的键」的场景） | 370-400 |
| `extract_numbers(string) -> int \| None` | 逐字符 `isdigit()` 拼接**所有**数字位再 `int()`；无数字 → `None`。已实测 `'8 192 pixels' → 8192`、`'1 920 pixels1 280 pixels' → 19201280` | 404-412 |

`min_widths` 实测表（`static/abbreviation.json` 与 `MIN_WIDTHS` 一致）：`9600→8640p`、`4608→4320p`、`3200→2160p`、`2240→1440p`、`1600→1080p`、`900→720p`、`533→480p`。

#### 2.4.4 `get_name_from_template(...) -> str`（`rename.py:415-458`）

**形参顺序即坑**：21 个业务参数之后，`template` 是**最后一个位置参数**（`417`）：

```
(english_title, original_title, season, episode, year, video_format, source, video_codec,
 bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num, team, other_titles,
 season_number, total_episodes, playlet_source, categories, actors, template)
```

**第 1 个形参 `english_title` 对应占位符 `{en_title}`**（不是 `{english_title}`）；`template` 传入的是 **settings 键名**（`get_settings(template)`，`418`），不是模板串本身。

21 个占位符（`420-440`，逐一对应上面 21 个参数，拼写如下表）：

| 占位符 | 形参 | 占位符 | 形参 |
|---|---|---|---|
| `{en_title}` | `english_title` | `{audio_codec}` | `audio_codec` |
| `{original_title}` | `original_title` | `{channels}` | `channels` |
| `{season}` | `season` | `{audio_num}` | `audio_num` |
| `{episode}` | `episode` | `{team}` | `team` |
| `{year}` | `year`（`str(year)` 包裹，`424`） | `{other_titles}` | `other_titles` |
| `{video_format}` | `video_format` | `{season_number}` | `season_number` |
| `{source}` | `source` | `{total_episodes}` | `total_episodes` |
| `{video_codec}` | `video_codec` | `{playlet_source}` | `playlet_source` |
| `{bit_depth}` | `bit_depth` | `{categories}` | `categories` |
| `{hdr_format}` | `hdr_format` | `{actors}` | `actors` |
| `{frame_rate}` | `frame_rate` | | |

**两处必崩**（测试要显式覆盖）：

| 场景 | 异常 | 行号 |
|---|---|---|
| `get_settings(template)` 返回 `None`（模板键不存在） | `AttributeError: 'NoneType' object has no attribute 'replace'` —— `None.replace('{en_title}', ...)` | 418, 420 |
| 模板串为 `''`（空串） | `IndexError: string index out of range` —— 末行 `name[0]` | 456 |

已实测：`get_name_from_template(..., 'no_such_key_xyz')` → `AttributeError`；把 `main_title_tv` 临时置为 `''` → `IndexError`。API 路由 `/api/getNameFromTemplate` 先把 `template` 限定在白名单 9 个键内（`src/api/startapi.py:973-989`），所以实际走的是 `IndexError` 分支（模板被用户清空时）。

**三套后处理是「模板名做子串匹配」而非严格前缀**（`441`、`446`、`451`）：判定条件分别是 `'main_title' in template`、`'second_title' in template`、`'file_name' in template`。三种后处理都在 `name`（已替换完的结果）上做**字符串替换**，与模板键的语义无关。

| 分支 | 操作（逐条照抄） | 行号 |
|---|---|---|
| `main_title` | ① `name.replace('_', ' ')`；② `re.sub(r'\s+', ' ', name)`；③ `re.sub(r' -', '-', name)`；④ `re.sub(r' @', '@', name)` | 442-445 |
| `second_title` | ① `name.replace(' /  \| ', ' \| ')`；② `name.replace('标 / 简', '')`；③ `name[:3] == ' \| '` 时 `name = name[3:]` | 447-450 |
| `file_name` | ① `re.sub(r"[<>:\'/\\|?*\s]", '.', name)`；② `re.sub(r'\.{2,}', '.', name)`；③ `re.sub(r'\.-', '-', name)`；④ `re.sub(r'\.@', '@', name)` | 452-455 |

**统一末处理**（`456-457`）：`if name[0] == '.' or name[0] == ' ': name = name[1:]`——**只去一次**，且首字符为空串时抛 `IndexError`。

已实测（`static/settings.json` 真实模板）：

| 调用 | 结果 |
|---|---|
| `main_title_tv`（`{en_title} S{season} {year}…-{team}`） | `'EN S1 2020 1080p WEB-DL x265 AAC-Team'` |
| `second_title_movie` | `'CN / A / B \| 类型：剧情 \| 演员：张三'` |
| `file_name_tv`（`original_title='中文 名'`, `episode='1'`） | `'中文.名.En.Title.SE1.2020-'` |
| `main_title_tv` + `english_title='.EN'` | `'EN S-'`（前导 `.` 被 `456` 去掉） |
| `second_title_tv` 全空 | `'\| 类型： \| 演员：'`：替换后为 `' /  \|  \| 类型： \| 演员：'`，`' /  \| '→' \| '` 得 `' \|  \| 类型：…'`，`[:3]` 命中 `' \| '` 并裁剪 3 字符，落到 `'\| 类型： \| 演员：'`（实测复算一致） |

`second_title` 的 `'标 / 简'` 与 `' /  | '` 两条替换**是对模板字面量的**：模板里原文是 `' / '`（original_title 与 other_titles 之间）加 `' | '`（other_titles 与后续之间），中间因 other_titles 渲染为空才出现 `' /  | '`。

#### 2.4.5 文件/目录操作四函数

| 函数 | 契约（错误串逐字） | 行号 |
|---|---|---|
| `rename_file(file_path, new_file_name) -> (bool, str)` | 先 `re.sub(r"[<>:\'/\\\|?*]", '.', new_file_name)`（**注意不替换空白**）；`os.path.split` 取目录，`os.path.splitext` 保留原扩展名；新路径 = `file_dir + '/' + new_file_name + file_extension`（**硬编码 `/` 拼接**）。成功 `(True, new_name)`；`FileNotFoundError` → `(False, f'未找到文件：{file_path}')`；`OSError` → `(False, f'重命名文件时出错：{e}')`。无 `except Exception` 兜底 | 461-482 |
| `rename_folder(current_folder_path, new_name) -> (bool, str)` | 同样清洗 `new_name`；`not os.path.isdir(...)` → `raise ValueError('提供的路径不是一个目录或不存在')`（**唯一故意抛出的领域异常**，API 路由靠它走 500）。成功 `(True, new_dir)`（`parent_dir + '/' + new_name`，硬编码 `/`）；`OSError` → `(False, f'重命名目录时发生错误：{e}')` | 485-517 |
| `move_file_to_folder(file_path, folder_name) -> (bool, str)` | `os.path.basename(file_dir) == folder_name` → `(True, file_path)` 原样返回（**不比较文件名**）。目标目录不存在 → `os.makedirs(target_folder)` —— **这一句在 try 之外**（`542-543`），目录创建失败（权限/同名文件）抛未捕获异常而非返回元组（已实测 monkeypatch `os.makedirs` 抛 `PermissionError` → 直接冒泡）。`shutil.move` 成功 `(True, target_file)`；失败 `(False, f'移动文件时出错：{e}')`（`except Exception`） | 520-556 |
| `create_hard_link(path) -> (bool, str)` | 六条返回分支，**必含容易漏掉的第 4 条**（路径存在但既非文件也非目录） | 559-623 |

`create_hard_link` 全部分支：

| 条件 | 返回 | 行号 |
|---|---|---|
| `not os.path.exists(path)` | `(False, f'Path does not exist: {path}')` | 562-563 |
| `os.path.isfile(path)` | 建 `os.path.join(file_dir, f'{name}-hardlink{ext}')`，`os.link` 后 `(True, link_path)` | 566-576 |
| `os.path.isdir(path)` | 目标 `path + '-hardlink'`，`os.walk` 保留整树，每个文件 `f'{name}-hardlink{ext}'`，返回 `(True, link_path)` | 579-604 |
| **路径存在但既非文件也非目录** | **`(False, f'Unsupported path type: {path}')`** | 606-607 |
| `FileExistsError` | `(False, 'Hard link already exists')` | 609-610 |
| `PermissionError` | `(False, 'Permission denied, unable to create the hard link')` | 612-613 |
| `OSError` 且 `errno == errno.EXDEV` | `(False, 'Hard link cannot be created across different file systems')` | 617-618 |
| 其它 `OSError` | `(False, f'OS error occurred: {str(e)}')` | 619 |
| 其它 `Exception` | `(False, f'Unexpected error: {str(e)}')` | 621-623 |

已实测：文件 → `(True, '…\\h-hardlink.mkv')`；同路径再来一次 → `(False, 'Hard link already exists')`；目录 → `(True, '…\\sdir-hardlink')`；`exists=True` 但 `isfile/isdir` 均 False（monkeypatch）→ `(False, 'Unsupported path type: weird://thing')`。

**注意**：目录分支对已存在的目标目录是**幂等跳过**的（`if not os.path.exists(link_path)` / `if not os.path.exists(new_dir)`，`583`、`593`），但**源文件的硬链接不检查是否存在**——`os.link` 撞到同名文件抛 `FileExistsError`，被 `609` 统一转成 `'Hard link already exists'`。已实测：同一目录连做两次 → 第二次 `(False, 'Hard link already exists')`；删掉其中一个内部硬链接后再做第三次 → `(True, …)`（已存在的目录被跳过，只补缺失的那一个文件）。

---

### 2.5 ptgen.py —— PT-Gen 接口调用（319 行）

**模块导入期副作用**（`ptgen.py:17-19`）：`hasattr(sys.stdout,'reconfigure')` 为真时执行 `sys.stdout.reconfigure(errors='replace')` 与 `sys.stderr.reconfigure(errors='replace')`。**任何 `import src.core.ptgen`（含间接 import）都会改动进程级 stdout/stderr 的编码错误策略**——测试里 `capsys`/`capfd` 会看到被 replace 后的输出，且该副作用不可逆。模块另有 **20 处 `print`**（含 `[DEBUG] …` 系列）会污染捕获输出，断言前建议 `capsys.readouterr()` 清空。

#### 2.5.1 新旧 API 识别与 URL 归一

| 函数 | 契约 | 行号 |
|---|---|---|
| `_is_new_pt_gen_api(api_url)` | 先 `(api_url or '').split('?')[0]`；`'/api' in api_url` → `True`；否则 `urlsplit(api_url).hostname in _NEW_PTGEN_HOSTS`，异常 → `False`。`_NEW_PTGEN_HOSTS = {'pt-gen.hares.dpdns.org'}` | 22, 25-37 |
| `_norm_ptgen_url(api_url)` | `api_url = (api_url or '').split('?')[0]`；非新服务 → `return api_url.rstrip('/')`（**老服务去尾斜杠**）；新服务 → `parts = urlsplit(api_url)`、`host = parts.netloc or parts.path`、`urlunsplit((parts.scheme or 'https', host, '/api/getData', '', ''))` | 40-51 |

**缺 scheme 会产生双路径（必然 404）**：`urlsplit` 对无 scheme 的输入把整串当 `path`，于是 `host = parts.path` 得到 `'pt-gen.hares.dpdns.org/api/getData'`，再拼 `/api/getData`：

| 输入 | 输出 | 备注 |
|---|---|---|
| `pt-gen.hares.dpdns.org/api/getData` | `https://pt-gen.hares.dpdns.org/api/getData/api/getData` | **双路径，已实测** |
| `pt-gen.hares.dpdns.org` | `pt-gen.hares.dpdns.org`（原样） | 无 scheme 且不含 `/api` → `_is_new` 靠 hostname 判定也失败（`urlsplit('pt-gen.hares.dpdns.org').hostname is None`），**不进新版分支**；已实测 |
| `https://pt-gen.hares.dpdns.org/api/getData` | 原样 | 幂等 |
| `https://pt-gen.hares.dpdns.org` | `https://pt-gen.hares.dpdns.org/api/getData` | 补全端点 |
| `https://pt-gen.hares.dpdns.org/api/getData?x=1` | `https://pt-gen.hares.dpdns.org/api/getData` | `?` 被切掉 |
| `https://old.example.com/ptgen/` | `https://old.example.com/ptgen` | 老服务 `rstrip('/')` |
| `''` / `None` | `''` | 已实测 |

#### 2.5.2 `_auth_signature(secret) -> (ts, sig)`（`ptgen.py:54-64`）

- `ts = str(int(time.time() * 1000))`——**13 位毫秒字符串**。
- `digest = hmac.new(secret.encode(), ts.encode(), hashlib.sha256).digest()`——**HMAC 只对时间戳字符串签名，不覆盖 URL/params/body**。
- `sig = base64.b64encode(digest).decode()`，再 `sig.replace('+','-').replace('/','_').rstrip('=')`。

已实测：sig 长度 43（SHA-256 → base64 44 字符去 1 个 `=`），不含 `=`/`+`/`/`。测试 `monkeypatch` 固定 `time.time()` 即可断言完整签名串。

`_get_auth_secret()`（`67-72`）：`get_settings('pt_gen_auth_secret') or 'hares.23663'`，整段包 `except Exception: return 'hares.23663'`。空串/异常都回退常量。已实测默认返回 `'hares.23663'`。

#### 2.5.3 `get_pt_gen_description(pt_gen_api_url, resource_url) -> (bool, (str, dict))`（`ptgen.py:75-179`）

**resource_url 预处理顺序**（`78-89`）：

1. `resource_url.replace(' ', '')` —— **半角空格**（`78`）
2. `resource_url.replace('　', '')` —— **全角 U+3000 空格**（`79`）。这两条是近期修的回归点，容易漏记。
3. `tt` + 纯数字 → `f'https://www.imdb.com/title/{resource_url}/'`（`82-83`）
4. 纯数字 → `f'https://movie.douban.com/subject/{resource_url}/'`（`85-86`）
5. `resource_url = resource_url.split('?')[0]` —— **去查询串在 tt/豆瓣改写之后**（`89`），所以 `'1234?from=x'` 不会走豆瓣分支（`isdigit()` 为假）

**请求构造**（`92-100`）：

| 项 | 值 | 行号 |
|---|---|---|
| `api_url` | `_norm_ptgen_url(pt_gen_api_url)` | 92 |
| `params` | **始终含** `{'url': resource_url}` | 94 |
| 新服务判定 | `_is_new_pt_gen_api(pt_gen_api_url)`（**用原始未归一的 URL 判定**） | 95 |
| 新服务附加 | `headers = {'X-Timestamp': ts, 'X-Signature': sig}`；`params['requestId'] = f'req_publish_helper_{ts}'` —— **`requestId` 在 params 里，不在 header** | 97-98 |
| timeout | **`timeout=30`**（注释：新服务首次抓豆瓣较慢） | 100 |

已实测新服务请求：`url='https://pt-gen.hares.dpdns.org/api/getData'`、`params={'url':'https://www.imdb.com/title/tt1234567/','requestId':'req_publish_helper_1789953485328'}`、`headers={'X-Timestamp':'1789953485328','X-Signature':'qVdMYO2hbHm0pohv2Y3cwr50ue8J36cq8O1PWHBP5Qs'}`、`timeout=30`。老服务：`headers={}`、`params` 只有 `url`、老 URL 已 `rstrip('/')`。

已实测半角+全角混排输入 `' 123 456　7 '` → 归一为 `'1234567'` → `https://movie.douban.com/subject/1234567/`。

**响应体两种形状**（`120`）：

```python
format_data = data.get('format') if 'format' in data else data.get('data', {}).get('format', '')
```

用 `'format' in data` 判定（键存在即取，**值为 `None`/`''` 也取**），否则钻 `data['data']['format']`。`data` 不是 dict 时 `'format' in data` 仍可能成立（如 list），后续 `.replace` 会炸。

**成功判定与后处理顺序**（`123-162`）：`format_data != '' and format_data is not None` 才继续，顺序严格为：

1. `format_data.replace('&#39;', "'")`（`125`）—— **只处理这一个 HTML 实体**
2. 译名行重构（`129-153`，条件见下）
3. `personalized_signature` **前插**：`get_settings("personalized_signature")`，`!= '' and format_data is not None` 时 `format_data = personalized_signature + '\n' + format_data`（`155-158`）
4. `format_data += '\n'` —— **末尾补换行**（`159`）
5. `format_data.replace('img1', 'img2')`（`160`）
6. `return True, (format_data, data)` —— **嵌套元组：处理后的文本 + 原始 JSON dict**

已实测含 `personalized_signature='【签名】'` + 正文含 `img1` → `'【签名】\n◎片　　名　X\n◎译　　名　Y\nimg2 here\n'`。

**译名行重构——仅在 `data.get('chinese_title','')` 非空时执行**（`129-130`），且正则要求**行尾有 `\n`**：

```python
trans_pattern = _re.compile(r'(([◎❁])\s*译\s*名\s*[:：]?\s*)(.*?)(\n)', _re.DOTALL)
```

- `.*?` 非贪婪 + `DOTALL`，所以 `(.*?)` 会跨行吞到**第一个 `\n`**——即「译名」行的原始内容（别名）。
- `match.group(2)` 是前缀字符 `◎` 或 `❁`，决定重构行样式：

| 前缀 | 新「译名」行 | 「别名」行（仅 `aka_content` 非空时追加） |
|---|---|---|
| `❁` | `f'❁ 译　　名:　{chinese_title}\n'` | `f'❁ 别　　名:　{aka_content}\n'` |
| 其它（含 `◎`） | `f'◎译　　名　{chinese_title}\n'` | `f'◎别　　名　{aka_content}\n'` |

- 替换用 `format_data[:match.start()] + new_trans_line + format_data[match.end():]`（`152`）——**只替换第一处匹配**。

已实测 7 种场景：

| 输入 | 输出 `format_data` |
|---|---|
| `…◎译　　名　OldName`（**末行无 `\n`**） | 原样 + `\n`，**不重构**（正则未命中，静默跳过） |
| `…◎译　　名　OldName\n` | `…◎译　　名　新译名\n◎别　　名　OldName\n\n` |
| `…◎译　　名　\n`（aka 为空） | `…◎译　　名　新译名\n\n`（**无别名行**） |
| `❁ 译　　名: OldName\n` | `❁ 译　　名:　新译名\n❁ 别　　名:　OldName\n\n` |
| `❁ 译　　名: AkaOne / AkaTwo\n` | `…❁ 别　　名:　AkaOne / AkaTwo\n` |
| 无 `chinese_title` | 原样 + `\n`（**不重构**） |
| 正文含 `It&#39;s me` | `&#39;`→`'` 先生效，别名行拿到 `It's me` |

**六条错误返回（逐字，含全角标点）**

| 场景 | 返回 | 行号 |
|---|---|---|
| `response.status_code != 200` | `(False, f'PT-Gen接口请求失败，状态码：{str(response.status_code)}')` | 103-105 |
| `response.json()` 抛 `ValueError` | `(False, 'PT-Gen接口响应不是有效的JSON格式，请检查PT-Gen接口是否正常')` | 108-117 |
| `format_data` 为空/None | `(False, '获取到的PT-Gen简介为空，可能是资源链接有误或PT-Gen接口出错，请检查后重试')` | 163-164 |
| `requests.Timeout` | `(False, 'PT-Gen接口请求超时')` | 166-169 |
| `requests.RequestException` | `(False, f'PT-Gen接口响应发生错误：{e}')` | 171-174 |
| 其它 `Exception` | `(False, f'PT-Gen接口请求发生错误：{e}')` | 176-179 |

注意 `requests.Timeout` 是 `RequestException` 子类，必须排在前面（`166` 在 `171` 之前），已实测两条分支各自命中。

#### 2.5.4 `get_playlet_description(...) -> str`（`ptgen.py:182-185`）

```python
if season_number != '1':
    original_title += ' 第' + int_to_chinese(int(season_number)) + '季'
return f'\n◎片　　名　{original_title}\n◎年　　代　{year}\n◎产　　地　{area}\n◎类　　别　{category}\n◎语　　言　{language}\n◎简　　介　\n'
```

- 参数为**位置参数**：`(original_title, year, area, category, language, season_number)`。注意第 4 个是 `category`（对应 `◎类　　别`）、第 5 个是 `language`（对应 `◎语　　言`）；GUI 调用点的实参名是 `categories`，语义相同（`src/gui/startgui.py:1589`）。
- 模板**以 `\n` 开头、以 `\n` 结尾**，`◎简　　介　` 后为空。
- `int(season_number)` **未捕获异常**：`season_number=''`（API 默认值）、`'abc'`、`'1.5'` 都抛 `ValueError: invalid literal for int() with base 10: …`（已实测三种）。API 路由 `/api/getPlayletDescription` 会因此走通用 `except Exception` → HTTP 500 `statusCode='GENERAL_ERROR'`（`src/api/startapi.py:819-824`）。
- `int_to_chinese` 对 `> 9999` 返回 `'数字超出范围'`（`src/core/text.py:115-116`），所以 `season_number='10000'` → 标题变成 `'片名 第数字超出范围季'`（已实测，**不抛异常**）。
- 已实测：`season_number='1'` → 标题原样；`'2'` → `'片名 第二季'`；`'11'` → `'片名 第十一季'`。

#### 2.5.5 `get_data_from_pt_gen_description(...) -> 8 元组`（`ptgen.py:188-319`）

```
(main_title, description, media_info, source, category)
 -> (imdb_url, douban_url, category, area, video_format, audio_codec, video_codec, medium)
```

**输入 `category` 是「默认值」**：只有当 `◎类　　别　` 行命中关键词时才被覆盖，否则原样返回（已实测 `category='输入类别'` 且描述无匹配 → `'输入类别'`）。`source` 同样只作为媒介判定的一条输入。

**六张映射表全部是并列 `if`，最后命中者胜，不是互斥查表**——这是本函数最重要的结构性事实，测试不要按「查表命中即返回」来写。

**IMDb / 豆瓣正则**（`199-210`）：`r'https://www\.imdb\.com/title/tt\d+/'`、`r'https://movie\.douban\.com/subject/\d+/'`；用 `re.search(...).group(0)`，命中即 `imdb_url += …`（`+=` 到空串，等价赋值）。**要求行尾斜杠**：`https://www.imdb.com/title/tt1234567`（无 `/`）实测两个 URL 都是 `''`。

**category 表**（`213-227`；匹配文本 `t = match.group(0)`，即**含 `◎类　　别　` 前缀的整行**，不是 `group(1)`；未命中时 `t=''`）

| 判定 | 输出 | 行号 |
|---|---|---|
| `'纪录' in t` | `纪录` | 217-218 |
| `'体育' in t` | `体育` | 219-220 |
| `'动画' in t` | `动画` | 221-222 |
| `'综艺' in t or '脱口秀' in t` | `综艺` | 223-224 |
| `'短片' in t` | **`短剧`**（关键词是「短片」，输出是「短剧」） | 225-226 |

已实测：`纪录片 / 动画` → `动画`；`纪录 / 体育 / 动画` → `动画`；`纪录 体育` → `体育`；`综艺 / 短片` → `短剧`；`脱口秀` → `综艺`；`剧情` → `''`。

**area 表**（`230-246`；`s = match.group(1)`，未命中 `''`）

| 判定 | 输出 | 行号 |
|---|---|---|
| `'美国' or '英国' or '德国' or '法国' in s` | `欧美` | 234-235 |
| `'大陆' in s` | `大陆` | 236-237 |
| `'香港' or '台湾' in s` | `港台` | 238-239 |
| `'日本' in s` | `日本` | 240-241 |
| `'韩国' in s` | `韩国` | 242-243 |
| `'印度' in s` | `印度` | 244-245 |

已实测：`美国 / 香港` → `港台`；`大陆 / 香港` → `港台`（**后命中者胜**）；`德国` → `欧美`；`韩国 / 印度` → `印度`。

**video_format 表**（`249-264`；只看 `main_title`）

| 关键字 | 输出 | 行号 |
|---|---|---|
| `3840p` / `3840P` / `3840i` | **`8K`** | 249-250 |
| `2160p` / `2160P` / `2160i` | `4K` | 251-252 |
| `1080p` / `1080P` | `1080p` | 253-254 |
| `1080i` | `1080i` | 255-256 |
| `720p` / `720P` | `720p` | 257-258 |
| `720i` | `720i` | 259-260 |
| `480p` / `480P` | `480p` | 261-262 |
| `480i` / **`480P`** | **`480i`** | 263-264 |

**`480P` 被判成 `480i` 是 bug**：`263` 的第二个条件多写了 `'480P'`，紧跟 `261` 之后必然覆盖。已实测 `'Movie.2020.480P.x264'` → `480i`，`'Movie.2020.480p.x264'` → `480p`。**测试必须按现状断言 `480P → 480i`**，不要写成正确行为。

其余同名覆盖：`1080p.1080i` → `1080i`、`720p.720i` → `720i`（皆已实测）。**`8K` 这个输出值最易被漏记**（只有 `3840p/3840P/3840i` 三个关键字能触发）。

**audio_codec 表**（`268-285`；只看 `main_title`）

| 关键字 | 输出 | 行号 |
|---|---|---|
| `AAC` | `AAC` | 268-269 |
| `AC3` **或 `DD`** | `AC3` | 270-271 |
| `EAC3` / `E-AC3` / `DDP` / `DD+` | `EAC3` | 272-273 |
| `DTS` **且同时**含 `HD` 与 `MA` | `DTS-HDMA` | 274-276 |
| `DTS`（其余情形） | `DTS` | 277-278 |
| `Atmos` / `ATMOS` | `Atmos` | 279-280 |
| `TrueHD` / `TRUEHD` | `TrueHD` | 281-282 |
| `Flac` / `FLAC` | `Flac` | 283-284 |

`DTS-HDMA` 的判定是**两个条件同时成立**（`'HD' in main_title and 'MA' in main_title`），已实测 `DTS.HD`（有 HD 无 MA）→ `DTS`、`DTS.MA`（有 MA 无 HD）→ `DTS`、`DTS-HD.MA` → `DTS-HDMA`。

并列覆盖实测：`AAC,DD` → `AC3`（`AC3` 分支的 `'DD'` 命中并覆盖）；`AAC.DDP` → `EAC3`；`TrueHD.Atmos` → `TrueHD`（**`Atmos` 在前、`TrueHD` 在后，TrueHD 胜**）；`ATMOS` 单独 → `Atmos`。若 `main_title` 同时含 `AAC` 与 `DTS`，`DTS` 分支在后（`274`）会胜出。

**video_codec 表**（`288-302`；只看 `main_title`）

| 关键字 | 输出 | 行号 |
|---|---|---|
| `H264` / `H.264` / `h264` / `h.264` / `AVC` / `avc` | `H264` | 288-289 |
| `H265` / `H.265` / `h265` / `h.265` / `HEVC` / `hevc` | `H265` | 290-291 |
| `H266` / `H.266` / `h266` / `h.266` / `VVC` / `vvc` | `H266` | 292-293 |
| `X264` / `x264` | `X264` | 294-295 |
| `X265` / `x265` | `X265` | 296-297 |
| `X266` / `x266` | `X266` | 298-299 |
| `AV1` / `av1` | `AV1` | 300-301 |

已实测：`HEVC` → `H265`、`AVC` → `H264`、`VVC` → `H266`、`H264.x265` → `X265`（后命中者胜）、`Movie.1080p.Blu-ray.x264` → `X264`（大写形式）。AV1 表里**没有 `H.264` 之外的乱序**，且 `X264` 排在 `H264` 之后——`Movie.H264` 不含 `x264` 所以不冲突。

**medium 表**（`305-316`）——本函数最复杂的一张，同时看 `source` 与 `main_title`（以及 `media_info`）

```python
if source == 'WEB-DL' or 'WEB-DL' in main_title or source == 'Web-DL' or 'Web-DL' in main_title or source == 'web-dl' or 'web-dl' in main_title or source == 'WEBDL' or 'WEBDL' in main_title or source == 'WebDL' or 'WebDL' in main_title or source == 'webdl' or 'webdl' in main_title:
    medium = 'WEB-DL'
```

| 分支 | 命中条件 | 输出 | 行号 |
|---|---|---|---|
| WEB-DL | `source` 或 `main_title` 含以下 **6 种**之一：`WEB-DL` / `Web-DL` / `web-dl` / `WEBDL` / `WebDL` / `webdl` | `WEB-DL` | 305-306 |
| Blu-ray | `source` == 以下 **3 种**之一（**不检查 `main_title`**）：`Blu-ray` / `Blu-Ray` / `BluRay`；或 `source` ∈ {`UHD Blu-ray`, `UHD Blu-Ray`, `UHD BluRay`}（**仅 `source` 侧 3 种，`main_title` 里的 UHD 写法不生效**） | 见下两行 | 307 |
| ↳ 子判定 1 | `'X26' in video_codec`（**大写 X26**，而 `video_codec` 的值是大写 `X264/X265/X266`） | `Encode` | 308-309 |
| ↳ 子判定 2 | 否则：`'Remux' / 'REMUX' / 'remux' in main_title` **或 `'mkv' in media_info`**（**小写 `mkv`，`MKV` 不认**） | `Remux` | 311-312 |
| ↳ 否则 | 以上都不满足 | `medium` 保持原值（通常是 `''`） | — |
| HDTV | `source == 'HDTV' or 'HDTV' in main_title` | `HDTV` | 313-314 |
| DVD | `source == 'DVD' or 'DVD' in main_title` | `DVD` | 315-316 |

**并列覆盖实测**：

| 输入 | 输出 | 说明 |
|---|---|---|
| `source='Blu-ray'`, `main_title` 含 `WEB-DL`, 无 REMUX/x26 | `WEB-DL` | Blu-ray 分支进去但两个子判定都不满足，**不改写 `medium`** → 保留 WEB-DL |
| `source='Blu-ray'`, `main_title='Movie.WEB-DL.Blu-ray.REMUX'` | `Remux` | 同上，进 Blu-ray 子判定 2 |
| `source='Blu-ray'`, `main_title='Movie.WEB-DL.Blu-ray.x265'` | `Encode` | 子判定 1 |
| `source='Blu-ray'`, `main_title='Movie.x264'` | `Encode` | **H264 编码拿不到 Encode**：`video_codec='H264'` 不含 `X26`，且无 Remux/mkv → 返回 `''`（已实测空串） |
| `source='Blu-ray'`, `main_title` 含 `H.264` 与 `x264` 两者 | `Encode` | `video_codec` 被后置的 `X264` 覆盖 |
| `source='Blu-ray'`, `main_title='Movie.Blu-ray.REMUX'` | `Remux` | |
| `source='Blu-ray'`, `media_info='mkv container'` | `Remux` | `media_info` 侧兜底 |
| `source='Blu-ray'`, `media_info='MKV container'` | `''` | **大写 `MKV` 不认** |
| `source='Blu-ray'`, `main_title='Movie.Blu-ray'`（无 Remux/mkv/X26） | `''` | 三个条件全不满足 |
| `source='Blu-ray'`, `main_title='Movie.Blu-ray.HDTV'` | `HDTV` | HDTV 分支在下，覆盖 |
| `source='Blu-ray'`, `main_title='Movie.Blu-ray.HDTV'`, `media_info='mkv'` | `HDTV` | 同上（HDTV 最后命中） |
| `source=''`, `main_title='UHD Blu-ray 1080p'` | `''` | **UHD 写法只在 `source` 侧生效** |
| `source='UHD Blu-ray'`, `main_title='Movie.REMUX'` | `Remux` | |
| `source='UHD Blu-ray'`, `main_title='Movie.x264'` | `Encode` | |
| `source=''`, `main_title='Movie.DVD'` | `DVD` | |

`medium` 为 `''` 是合法且常见的返回（`source` 为空、`main_title` 无媒介关键字时）；调用方 `src/core/autofeed.py:17` 直接解包 8 元组。

---

### 2.6 picturebed.py —— 图床上传（6 家 provider）

源码 381 行。核心是 `upload_picture` 的**类型分发**，6 个 provider 各自独立实现，签名、参数、异常处理**互不相同**——这是本节最容易写错的地方，写测试前请逐家对照下表。

#### 2.6.1 `upload_picture(picture_bed_api_url, picture_bed_api_token, picture_path) -> (bool, str)`

`src/core/picturebed.py:13`。执行顺序：

1. `os.path.exists(picture_path)` 为假 → `(False, '图片文件路径不存在')`（`:15-17`）。
2. URL 清理：依次 `replace(' ','')`、`replace('　','')`（全角空格）、`replace('\n','')`（`:21-23`）。**注意顺序**：先删半角空格，再删全角，最后删换行。
3. `get_picture_bed_type(cleaned_url)`（`:24`）。失败时把它的 `str` 原样透传为 `(False, payload)`（`:41-42`）。
4. 按类型分发（`:27-38`）。**`pixhost` 是唯一不接收 token 的分支**：`pixhost_picture_bed(api_url, picture_path)`（`:38`），其余 5 家都是 `(api_url, api_token, picture_path)`。
5. 落到 `else` → 未识别类型文案（`:40`，逐字）：
   `你错误更改了图床配置文件？冒号前面的类型是不能随便改的！如果需要支持更多新类型的图床请提Issues，前提是图床支持API上传！`

**mock 断言要点**：`upload_picture` 开头 `print` 了 token（`:14`），不影响契约，但意味着测试不必 mock print。

#### 2.6.2 六家 provider 的请求参数与响应解析（逐家）

| provider | 函数:行 | 请求体 `data` | 文件字段 / MIME | headers | 成功条件 | 成功返回 |
|---|---|---|---|---|---|---|
| `lsky-pro` | `:46` | `{}`（空 dict） | `file` / `image/png`（`:49`） | `Authorization: <token>`（**裸值，无 `Bearer ` 前缀**）、`Accept: json`（`:50`） | HTTP 200 **且**五道前置校验全过 | `data['data']['links']['bbcode']` 原文（`:104-106`） |
| `bohe` | `:116` | `api_token`、`image_compress=0`、`image_compress_level=80`（`:120`） | `uploadedFile` / `image/png`（`:119`） | 无 | `str(api_response.get('statusCode','')) == '200'`（`:141,144`） | `str(bbsurl)`（`:145-146`，**不包 `[img]`**） |
| `chevereto` | `:154` | `expiration='PT5M'`、`X-API-Key=<token>`、`key=<token>`（`:157`） | `source` / `image/png`（`:158`） | 无 | `data['image']['url']` 命中 | `f'[img]{url}[/img]'`（`:176`） |
| `freeimage` | `:186` | `key=<token>`、`format='txt'`（`:189`） | `source` / `image/png`（`:190`） | 无 | `res.text[:4] == 'http'`（`:203`） | `'[img]' + res.text + '[/img]'`（`:204-206`）；否则 `(False, res.text)`（`:208`，**原样透传响应文本**） |
| `imgbb` | `:212` | `expiration='600'`、`key=<token>`（`:215`） | `image` / `image/png`（`:216`） | 无 | `data['data']['image']['url']` 命中 | `f'[img]{url}[/img]'`（`:233`） |
| `pixhost` | `:243` | `content_type=0`、`max_th_size=420`（`:247`） | `img` / **`image/jpeg`**（`:246`） | `Accept: application/json`（`:248`） | `data['th_url']` 命中 | 见下 |

`pixhost` 的 URL 二次加工（`:263-267`）：取 `th_url` → `replace('//t','//img')` → `replace('/thumbs/','/images/')` → 包 `[img]`。实测 `//t.thumbs/x/thumbs/a.jpg` → `[img]//img.thumbs/x/images/a.jpg[/img]`（注意第一次 `//t` 替换只命中前缀，`thumbs` 里的 `t` 不受影响）。

`pixhost` 的文件 MIME 写死 `image/jpeg`，与其余 5 家的 `image/png` 不同；且 `pixhost_picture_bed` 的形参顺序是 `(api_url, frame_path)`（无 token）。

#### 2.6.3 每家实际捕获的异常类型（**不是**「每家都有三种」）

| provider | `RequestException` | `KeyError` | `JSONDecodeError` | 备注 |
|---|---|---|---|---|
| `lsky-pro` | 有 `:68-70` | 有 `:107-109` | 有 `:110-112` | 三条消息都带 `res.text` |
| `bohe` | 有 `:126-128` | **无** | 有 `:134-138` | 走 `api_response.get(...)`，**不会** KeyError |
| `chevereto` | 有 `:166-168` | 有 `:177-179` | 有 `:180-182` | 消息里是 `str(res)`（整个 Mock 的 repr），不是 `res.text` |
| `freeimage` | 有 `:198-200` | **无** | **无** | 不做 JSON 解析，纯文本判断 |
| `imgbb` | 有 `:224-226` | 有 `:234-236` | 有 `:237-239` | |
| `pixhost` | 有 `:256-258` | 有 `:268-270` | 有 `:271-273` | |

对测试的直接后果：

- **不要给 `freeimage` 断言 `KeyError`/`JSONDecodeError` 分支**——不存在；
- **不要给 `bohe` 断言 `KeyError` 分支**——不存在；
- `freeimage`/`imgbb`/`pixhost` 的 `RequestException` 文案是 **`'请求过程中出现错误：' + str(e)`（字符串拼接）**（`:200`/`:226`/`:258`）；`lsky-pro`/`bohe`/`chevereto` 用的是 **f-string `f'请求过程中出现错误：{str(e)}'`**（`:70`/`:128`/`:168`）。结果字符串相同，但 monkeypatch 方案的差异在此：前者根本不会经过 f-string。

**七条异常消息逐字对照**（前三条三家共用，后四条各一家）：

| 场景 | 逐字文案 | 出现处 |
|---|---|---|
| 请求异常（f-string 版） | `f'请求过程中出现错误：{str(e)}'` | lsky `:70`、bohe `:128`、chevereto `:168` |
| 请求异常（拼接版） | `'请求过程中出现错误：' + str(e)` | freeimage `:200`、imgbb `:226`、pixhost `:258` |
| `KeyError`（带 `res.text`） | `f'图床响应结果缺少所需的值：{str(e)}，响应内容：{res.text}'` | **仅 lsky** `:109` |
| `KeyError`（带 `str(res)`） | `f'图床响应结果缺少所需的值：{str(e)}，{str(res)}'` | chevereto `:179`、imgbb `:236`、pixhost `:270` |
| `JSONDecodeError`（带 `res.text`） | `f'处理返回的JSON过程中出现错误：{str(e)}，响应文本：{res.text}'` | **仅 lsky** `:112` |
| `JSONDecodeError`（带 `str(res)`） | `f'处理返回的JSON过程中出现错误：{str(e)}，{str(res)}'` | chevereto `:182`、imgbb `:239`、pixhost `:273` |
| `bohe` 非 JSON 响应 | `'响应不是有效的JSON格式'`（**定值串，不带原始响应**） | bohe `:138` |

注意后两组的**分隔符与承载字段不同**：lsky 用中文逗号 `，` + `响应内容：`/`响应文本：`，其余三家用中文逗号 `，` + `str(res)`（**整个 response 对象的 repr**，实测形如 `图床响应结果缺少所需的值：'image'，<Mock id='1824472795024'>`）。写断言时**不要把 `str(res)` 段写成 `res.text`**。

六家响应解析的**字符串解析路径**已独立复核为正确：`lsky data.data.links.bbcode`、`bohe statusCode=='200'→bbsurl`、`chevereto data.image.url`、`freeimage res.text[:4]=='http'`、`imgbb data.data.image.url`、`pixhost //t→//img 与 /thumbs/→/images/`。

#### 2.6.4 `lsky-pro` 的五道前置校验（**覆盖面最大的分支集合，必须逐个补测**）

`lsky_pro` 是唯一做了完整响应结构校验的 provider（`:73-101`），按**检查顺序**：

| 序 | 条件 | 行 | 返回的错误串（逐字） |
|---|---|---|---|
| 1 | `res.status_code != 200` | `:73-75` | `f'图床API返回错误状态码：{res.status_code}，响应内容：{res.text}'` |
| 2 | `json.loads(res.text)` 结果 `is None` | `:80-82` | `f'图床API返回了空数据，响应文本：{res.text}'` |
| 3 | `'status' in data and data['status'] is False` | `:85-88` | `f'图床API返回错误：{error_msg}'`，`error_msg = data.get('message','未知错误')` |
| 4 | `'data' not in data or data['data'] is None` | `:91-93` | `'图床API响应格式错误：缺少data字段'`（注意是**定值串**，不带响应内容；且 f-string 前缀 `f` 冗余） |
| 5 | `'links' not in data['data'] or data['data']['links'] is None` | `:95-97` | `'图床API响应格式错误：缺少links字段'` |
| 6 | `'bbcode' not in data['data']['links']` | `:99-101` | `'图床API响应格式错误：缺少bbcode字段'` |

实测（`mock.patch('requests.post')`）：
`'null'` → 第 2 道；`'{"status":false,"message":"bad"}'` → 第 3 道；`'{}'` → 第 4 道；`'{"data":{"x":1}}'` → 第 5 道；`'{"data":{"links":{}}}'` → 第 6 道；`'{"data":{"links":{"bbcode":"[img]u[/img]"}}}'` → `(True,'[img]u[/img]')`。

**与其余五家的结构性差异**：只有 `lsky-pro` 检查 HTTP 状态码（其余五家只看 body）；只有它把 `data is None` 单独处理；`status is False` 用的是 **`is False` 恒等比较**，所以 `data['status'] == 0` 或 `'false'` **不会**触发第 3 道。

**未捕获的 `TypeError` 边界**（实测）：五道校验用的都是 `in` / 下标，当 `json.loads` 产出**非 dict 标量**时会抛 `TypeError`，而 `:107/:110` 只捕 `KeyError`/`JSONDecodeError`，**`TypeError` 会向上冒泡出 `lsky_pro_picture_bed`**：

| 响应文本 | 结果 |
|---|---|
| `'[1,2]'` | `(False, '图床API响应格式错误：缺少data字段')`（list 支持 `in`） |
| `'"str"'` | `(False, '图床API响应格式错误：缺少data字段')`（str 支持 `in`） |
| `'123'` | **抛 `TypeError: argument of type 'int' is not iterable`** |
| `'true'` | **抛 `TypeError: argument of type 'bool' is not iterable`** |

这是 `upload_picture` 链路唯一会把异常抛给调用方的入口（`upload_picture` 本身不包 try）。测试若要固化，用 `pytest.raises(TypeError)`；若要保「领域层不抛异常」的假设，需注意此处反例。

`bohe` 的三分支（`:144-150`）：`statusCode=='200'` → 成功；`statusCode==''`（含键缺失，因 `.get(...,'')`）→ `'未接受到响应'`；其余 → `f'API响应出错了，错误码：{status_code}，错误提示：{result_data}'`。`bohe` 还**显式关闭了文件句柄**（`files['uploadedFile'][1].close()`，`:131`）；其余五家**不关闭**，是资源泄漏（不影响契约断言，但要 mock `open` 时留意）。

#### 2.6.5 `get_picture_bed_type(picture_bed_api_url) -> (bool, str)`

`src/core/picturebed.py:276`。

1. `file_path = combine_directories('static/picture-bed-data.json')`（`:279`，**`file_utils` 版，cwd 相对**）。
2. `default_content`（`:282-299`）**只有 5 家**：`lsky-pro`（2 条 URL）、`bohe`、`freeimage`、`imgbb`、`pixhost` 各 1 条。**没有 `chevereto`**。
3. 文件存在则 `json.load` 读入（`:302-304`），不存在则 `existing_content = {}`（`:306`）。
4. 合并默认值（`:309-319`）：缺 key 则整段赋值；已存在则**逐 URL 判重后 append**（所以用户手工删掉的默认 URL 会被重新加回）。
5. `updated` 为真才写回（`:322-326`）：`os.makedirs(os.path.dirname(file_path), exist_ok=True)` + `json.dump(..., ensure_ascii=False, indent=4)`。
6. `find_picture_bed_type(...)` 后透传结果（`:329-336`）。
7. 外层 `except Exception as e: return False, str(e)`（`:338-340`）——**文件损坏时 `json.JSONDecodeError` 被此兜底吞掉**，返回的是原始英文 JSON 报错，实测：`(False, 'Expecting property name enclosed in double quotes: line 1 column 2 (char 1)')`。

**`chevereto` 的缺口是真实缺陷**：因为 `default_content` 没有它，若本地 `picture-bed-data.json` 缺 `chevereto` 键，该键**不会被补齐**。实测在只写了 `{'lsky-pro':[...]}` 的文件上调用，写回后文件 key 仍是 `['bohe','freeimage','imgbb','lsky-pro','pixhost']`，且 `https://www.imagehub.cc/api/1/upload` 返回「暂未配置」。**旧文档「缺键补默认并写回」的说法对 chevereto 不成立。**

当前仓库的 `static/picture-bed-data.json` 有 **6 键**（含 `chevereto → ['https://www.imagehub.cc/api/1/upload']`），且 `lsky-pro` 实际有 **3 条** URL，比代码默认的 2 条多一条 `https://picture.agsvpt.cn/api/v1/upload`。

#### 2.6.6 `find_picture_bed_type(picture_bed_api_url, picture_bed_api_data) -> (bool, str)`

`src/core/picturebed.py:343`。三步：

1. `startswith('http://')` → 换成 `'https://' + url[7:]`（`:358-359`）。
2. `endswith('/')` → 去掉末尾一个 `/`（`:362-363`）。**只去一个**，`https://x//` 会残留一个。
3. 遍历 `picture_bed_api_data.items()`，`url in urls` 命中即 `(True, identifier)`（`:366-368`）。**是精确全等匹配，非前缀/包含**。
4. 未命中 → `(False, f'您使用的图床上传接口{picture_bed_api_url}暂未配置，请检查static/picture-bed-data.json文件，如果您的图床符合其中的配置，可将上传接口URL按照格式添加到对应类型下')`（`:371`）。注意串里嵌的是**加工后的 URL**（已 https 化、已去尾斜杠）。

#### 2.6.7 `generate_image_filename(base_path) -> str`

`src/core/picturebed.py:374`。`datetime.now().strftime('%Y%m%d-%H%M%S')` + `'-'` + `random.sample('0123456789', 6)` 拼成的 6 位串 + `'.png'`，再以 **`base_path + '/' + filename` 字符串拼接**（`:380`，非 `os.path.join`）。实测 `generate_image_filename('/tmp/base')` → `/tmp/base/20260921-091637-670853.png`。

- 6 位是 `random.sample`，**六个数字互不相同**（无重复位）。
- 测试要固定随机时 mock `random.sample`（或 `random.seed`）；断言后缀 `.png` 与前缀日期格式 `%Y%m%d-%H%M%S-`。

---

### 2.7 torrent.py —— 制作种子

源码 51 行，只有 `make_torrent(path: str, torrent_storage_path: str) -> (bool, str)`（`src/core/torrent.py:8`）。

执行顺序（**顺序本身是测试断言点**）：

| 序 | 动作 | 行 | 说明 |
|---|---|---|---|
| 1 | `os.path.exists(path)` 为假 → `raise ValueError('提供的路径不存在')` | `:12-13` | 抛出后由 `:44` 捕获 |
| 2 | `os.path.isdir(path) and not os.listdir(path)` → `raise ValueError('路径指向一个空目录')` | `:16-17` | 仅"目录且**空**"才算错；空文件不报 |
| 3 | 推导种子文件名：`os.path.basename(path.rstrip('/\\')) + '.torrent'` | `:20` | `rstrip('/\\')` 同时去掉正反斜杠 |
| 4 | 拼路径：`torrent_file_path = torrent_storage_path + '/' + torrent_file_name` | `:21` | **字符串拼接，不是 `os.path.join`**，所以 `torrent_storage_path` 以 `/` 结尾时会产出双斜杠 |
| 5 | `os.makedirs(os.path.dirname(torrent_file_path), exist_ok=True)` | `:24` | **在删除旧种子之前** |
| 6 | 目标已存在则 `os.remove` | `:27-28` | **先删后写** |
| 7 | `Torrent(path=path, trackers=['https://tracker.example.com/announce'], created_by='Publish Helper', creation_date=datetime.now())` | `:31-35` | 固定占位 tracker，值必须逐字断言 |
| 8 | `t.generate()` → `t.write(torrent_file_path)` | `:38-39` | |
| 9 | `(True, torrent_file_path)` | `:42` | |

异常分两层：`:44-47` 捕 `(OSError, IOError, ValueError)` → `(False, str(e))`，即第 1/2 步的 `ValueError` 消息**原样成为 payload**；`:49-52` 捕其余 `Exception` → `(False, str(e))`。两层的 payload 形态相同，无法从返回值区分——需要区分时用 `print` 文案（`'Error occurred: '` vs `'An unexpected error occurred: '`）。

实测（Windows）：

```
make_torrent(<不存在路径>, d)      -> (False, '提供的路径不存在')
make_torrent(<空目录>, d)          -> (False, '路径指向一个空目录')
make_torrent(<含文件目录>, d)      -> (True, '<d>/MyMovie.torrent')
make_torrent('<同目录>\\', d)      -> (True, '<d>/MyMovie.torrent')   # 同一个目标文件
make_torrent(<单文件 solo.mkv>, d) -> (True, '<d>/solo.mkv.torrent')
```

`path.rstrip('/\\')` 让**带尾斜杠的目录与不带尾斜杠的目录产出同名种子**，可据此测幂等；单文件也会生成 `.torrent`（不报错），所以「文件」与「非空目录」都合法。

**测试要点**：`tmp_path` 造四类输入；预置同名 `.torrent` 文件验证「先删后写」（可断言旧文件内容被覆盖 / mtime 变化）；断言 `trackers` 与 `created_by` 精确值（用 `mock.patch('src.core.torrent.Torrent')` 拦构造参数最省事，否则会真的走 torf 哈希计算）。**不要**真跑到写盘那步做大数据量目录。

---

### 2.8 poster.py —— 海报下载与上传

源码 220 行。4 个函数，**模块内唯一的跨模块依赖是 `from src.core.picturebed import upload_picture`**（`src/core/poster.py:10`）——monkeypatch 时注意要打 `src.core.poster.upload_picture`。

#### 2.8.1 `get_poster_url_from_data(data: dict) -> str`

`src/core/poster.py:13`。

1. 先查**顶层** 5 个字段，**按此优先级顺序**：`['poster', 'img', 'image', 'cover', 'posterUrl']`（`:25`，列表顺序即优先级）。命中条件 `field in data and data[field]`——**空串/None/0 都视为未命中**（`:28`）。
2. 顶层全未命中，再查嵌套 **`data['data'][field]`**，同样顺序（`:34-39`）。
3. 全未命中 → `print` + 返回 `''`（`:41-42`）。

实测：`{}` → `''`；`{'cover':'c'}` → `'c'`；`{'data':{'posterUrl':'p'}}` → `'p'`。

注意：`'data' in data` 时若 `data['data']` 不是 dict，`field in data['data']` / `data['data'][field]` 会抛 `TypeError`（第 2 段**无** try 包裹）。实测四种输入：

| 输入 | 结果 |
|---|---|
| `{'data': None}` | `TypeError: argument of type 'NoneType' is not iterable`（`:36` 的 `field in data['data']`） |
| `{'data': 'poster'}` | `TypeError: string indices must be integers`（字符串能过 `in` 检查，在 `data['data'][field]` 下标处炸） |
| `{'data': ['poster']}` | `TypeError: list indices must be integers or slices, not str` |
| `{'data': 'x'}` | `''`（`'x'` 不含任何候选字段名，正常走完返回空串） |

这是可被测试固化的缺陷边界。

**`download_poster` 的请求参数与附加 header 全部列出**（`:63-76`，测试若断言 header 需逐项匹配）：

#### 2.8.2 `download_poster(poster_url, save_path) -> (bool, str)`

`src/core/poster.py:45`。

| 分支 | 行 | 返回值 |
|---|---|---|
| `not poster_url` | `:57-58` | `(False, 'Poster URL is empty')` |
| 非 200 | `:78-79` | `(False, f'Failed to download poster, status code: {response.status_code}')` |
| 成功 | `:90-91` | `(True, save_path)` |
| `requests.Timeout` | `:93-95` | `(False, 'Poster download timeout (30s)')` |
| `requests.RequestException` | `:97-99` | `(False, f'Poster download request error: {str(e)}')` |
| `IOError` | `:101-103` | `(False, f'Failed to save poster file: {str(e)}')` |
| 其它 `Exception` | `:105-107` | `(False, f'Unexpected error: {str(e)}')` |

`Timeout` 是 `RequestException` 的子类，**必须写在前面**才不会被吞掉（源码顺序正确）。

请求头（`:63-73`）9 项，**测试若断言 header 需全部列出**：

```
User-Agent     : Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36
Accept         : image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8
Accept-Language: en-US,en;q=0.9,zh-CN;q=0.8,zh-TW;q=0.7,zh;q=0.6
Referer        : https://movie.douban.com/
Cache-Control  : no-cache
Pragma         : no-cache
Sec-Fetch-Dest : image
Sec-Fetch-Mode : no-cors
Sec-Fetch-Site : cross-site
```

请求参数：`requests.get(poster_url, headers=headers, timeout=30, stream=True)`（`:76`，`stream=True`）。

**两处 `os.makedirs` 的位置差异**（都只建 `save_path` 的父目录，不建 `save_path`）：

| 函数 | 行 | 时机 |
|---|---|---|
| `download_poster` | `:82` | **非 200 短路之后、写盘之前**。所以「非 200 时不创建目录」可断言。写 `'x.jpg'` 这类无目录部分的路径时 `os.path.dirname` 返回 `''`，`makedirs('')` 抛 `FileNotFoundError`（`IOError` 在 Py3 即 `OSError` 的别名，故被 `:101` 捕获 → `(False, 'Failed to save poster file: ...')`） |
| `process_poster` | **无** | 它不建目录——目录由 `download_poster` 建；若 `temp_dir` 不存在且传入的是自定义路径，同样落到 `download_poster` 的 `makedirs` |

写盘用 `response.iter_content(chunk_size=8192)`，**跳过假值 chunk**（`:86-88`，`if chunk:`）——mock 的 `iter_content` 返回值里放一个 `b''` 可验证该判断。

#### 2.8.3 `process_poster(poster_url, picture_bed_api_url, picture_bed_api_token, temp_dir=None) -> (bool, str)`

`src/core/poster.py:110`。

1. `temp_dir` 为 `None` 时用 `tempfile.gettempdir()`（`:139-140`）。
2. 临时文件名 **`f'poster_{id(poster_url)}.jpg'`**（`:143`）——`id()` 是**对象内存地址**，同进程内同一字符串对象可能得到不同值（取决于驻留/新建）。**测试不要硬编码该文件名**，要么从 `download_poster` 的 mock 入参取，要么 monkeypatch `tempfile.gettempdir` 并用 `id()` 现算。扩展名写死 `.jpg`，与实际图片格式无关。
3. 下载失败 → `(False, f'Failed to download poster: {download_result}')`（`:152-153`，**前缀 + 内层消息拼接**）。
4. 上传（`upload_picture(api_url, token, temp_file_path)`，`:161-165`）失败 → 打印「Temp file kept for debugging」并 `(False, f'Failed to upload poster: {upload_result}')`（`:167-170`）。
5. 成功：若 `upload_result` 形如 `[img]...[/img]` → `upload_result[5:-6]` 剥壳（`:176-177`）；否则**原样返回**（`:179`）。实测 `'[img]http://img/x.png[/img]'` → `(True,'http://img/x.png')`，`'http://img/plain.png'` → `(True,'http://img/plain.png')`。
6. 外层 `except Exception` → `(False, f'Error during poster processing: {str(e)}')`（`:183-185`）。
7. `finally`（`:187-194`）：**仅当 `upload_success` 为真且文件存在**才 `os.remove`。删除失败只 `print` 警告，**不改返回值**。

`finally` 是这条流水线最关键的断言点：**上传失败时临时文件必须保留**（实测成立），上传成功时必须删除。另注意 `os.path.getsize(temp_file_path)`（`:156`）在下载成功后立刻调用——若 mock 的 `download_poster` 返回 `(True, ...)` 但**不真的写文件**，这里会抛 `FileNotFoundError`，被 `:183` 捕获成 `'Error during poster processing: [WinError 2] ...'`。**mock `download_poster` 时必须真的创建文件**，否则测不到上传分支。

#### 2.8.4 `get_poster_from_pt_gen_response(pt_gen_data, api_url, api_token, temp_dir=None) -> (bool, str)`

`src/core/poster.py:197`。`get_poster_url_from_data` 取空 → `(False, 'No poster URL found in PT-Gen response')`（`:217-218`）；否则直接转 `process_poster`（`:220`）。

---

### 2.9 autofeed.py —— auto_feed 链接生成

源码 81 行，只有 `get_auto_feed_link(main_title, second_title, description, media_info, file_name, team, source, category, torrent_url) -> (bool, str)`（`src/core/autofeed.py:9`）。

**参数名与内部变量名不一致，是常见误设点**：形参 `second_title` → 内部 `small_descr`，形参 `file_name` → `f'{file_name}.torrent'`（`:12`，**自动补 `.torrent` 后缀**）。

执行流程：

1. `auto_feed_link = str(get_settings('auto_feed_link'))`（`:11`）。
2. `get_data_from_pt_gen_description(main_title, description, media_info, source, category)` → 8 元组 `(url, dburl, category, source_sel, standard_sel, audiocodec_sel, codec_sel, medium_sel)`（`:17-18`）。注意 **`category` 被返回的第 3 个值覆盖**（入参 `category` 与出参重名）。
3. 逐占位符替换（`:39-53`），每个值都过 `urllib.parse.quote`。

**占位符实测共 15 个**（对默认模板 `get_settings('auto_feed_link')` 用正则 `\{[^}]+\}` 提取，去重后仍 15 个）：

| # | 占位符 | 来源变量 | 行 |
|---|---|---|---|
| 1 | `{主标题}` | `quote(name)`，`name=main_title` | `:39` |
| 2 | `{副标题}` | `quote(small_descr)` | `:40` |
| 3 | `{IMDB}` | `quote(url)` | `:41` |
| 4 | `{豆瓣}` | `quote(dburl)` | `:42` |
| 5 | `{简介}` | `quote(descr)` | `:43` |
| 6 | `{MediaInfo}` | `quote(media_info)` | `:44` |
| 7 | `{种子名称}` | `quote(torrent_name)` | `:45` |
| 8 | `{类型}` | `quote(category)` | `:46` |
| 9 | `{地区}` | `quote(source_sel)` | `:47` |
| 10 | `{分辨率}` | `quote(standard_sel)` | `:48` |
| 11 | `{音频编码}` | `quote(audiocodec_sel)` | `:49` |
| 12 | `{视频编码}` | `quote(codec_sel)` | `:50` |
| 13 | `{媒介}` | `quote(medium_sel)` | `:51` |
| 14 | `{小组}` | `quote(team)` | `:52` |
| 15 | `{种子链接}` | `quote(torrent_url)` | `:53` |

**`{MediaInfo}` 是唯一一个英文占位符**，其余 14 个是中文。旧文档写「16 个中文占位符」两处都不对。

4. **`#seperator#` 错拼坑**（`:60`）：`auto_feed_link.replace('#seperator#','#separator#')` 的返回值**被丢弃**，该行是死代码。语义后果：**旧模板里写错拼的 `#seperator#` 不会被自动修复**，而第 62 行的判定只认 `#separator#`，于是错拼模板直接走 `(False, '您设置的auto_feed_link不符合规则')`。当前代码默认模板与 `static/settings.json` 里都是正确拼写 `#separator#`（实测各 1 处）。

5. 尾部 base64（`:62-67`）：

```python
if '#separator#' in auto_feed_link:
    string_to_encode = auto_feed_link.split('#separator#')[-1]
    string_encoded = base64encoding(string_to_encode)          # UTF-8 → base64
    auto_feed_link = auto_feed_link.replace(string_to_encode, '') + string_encoded
    return True, auto_feed_link
else:
    return False, '您设置的auto_feed_link不符合规则'
```

**`replace(string_to_encode, '')` 是全局替换，不是「仅删尾部一次」**：若 base64 段（`#separator#` 之后的整个尾巴）的字符串值在模板前部也出现，前部会被一并删掉。实测模板 `'https://abc/abc#separator#abc'` → 输出 `'https:///#separator#YWJj'`（前段的 `abc/abc` 里两处 `abc` 全被删，只剩 `https://` + `#separator#`）。正常模板（尾部是 `#linkstr#0` 这类特征串）不会撞上，但用短尾串做测试时会踩到——**这是必须固化的边界**。

另：`split('#separator#')[-1]` 取**最后一段**，所以模板含多个 `#separator#` 时只用最后一段编码，前面的 `#separator#` 也会被 `replace` 一并删掉（与上条同源）。

**测试要点**：mock `src.core.autofeed.get_settings` 与 `get_data_from_pt_gen_description` 后逐项断言 `quote` 化；断言尾段 base64 等于 `base64.b64encode(tail.encode('utf-8')).decode()`；断言不含 `#separator#` 时的中文错误串；补 `replace` 全局删除的边界用例。

---

### 2.10 settings_tool.py —— 统一设置（附 text.py 工具）

#### 2.10.1 模块级单例（**测试隔离的关键点，旧文档遗漏**）

```python
# src/core/settings_tool.py:231
settings_manager = SettingsManager()
```

**这一行在 import 时立即执行**：`SettingsManager.__init__` → `_ensure_settings_file()` → 若 `config.STATIC_DIR / "settings.json"` 不存在则**创建并写入 38 键默认值**。因此：

- `import src.core.settings_tool` 就有**文件系统副作用**，会读到真实 `CONFIG` 决定的路径（`BASE_DIR/static/settings.json`，与 cwd 无关）；
- 所有便捷函数（`get_settings` / `update_settings` / `get_settings_json` / `update_settings_json`）都闭包在这个单例上，**只认 `config.STATIC_DIR`**，无法通过传参指向临时文件；
- 测试要用临时文件时，唯一途径是**自己 `SettingsManager(tmp_path/'s.json')`** 并 monkeypatch 目标模块里的 `get_settings`（`tests/conftest.py` 的 `mock_settings` fixture 正是这个套路）。**光靠 `chdir` 无法隔离**（`STATIC_DIR` 是绝对路径），这是与 `data.py`/`picturebed.py` 那套 cwd 相对路径的根本差异。

#### 2.10.2 `SettingsManager` 方法清单

| 成员 | 行 | 行为 |
|---|---|---|
| `__init__(settings_file=None)` | `:38` | 默认 `config.STATIC_DIR / "settings.json"`（`:45`）；`_settings_cache=None`；立即调 `_ensure_settings_file()` |
| `_ensure_settings_file()` | `:49-55` | 文件不存在 → `ensure_directory(parent)` + `_write_settings(_get_default_settings())`，写 38 键 |
| `_get_default_settings()` | `:57-109` | 返回**38 键** dict（全表见 §3.1），每次调用**新建** dict |
| `_read_settings()` | `:111-120` | `json.load`；`JSONDecodeError`/`IOError` → `raise ConfigurationError(f"Invalid settings file: {self.settings_file}")` |
| `_write_settings(settings)` | `:122-134` | `json.dump(..., indent=4, ensure_ascii=False)`；成功后 **`self._settings_cache = None`**（强制重载）；`IOError` → `raise ConfigurationError(f"Cannot write to settings file: {self.settings_file}")` |
| `get_setting(key, default=None)` | `:136-167` | 见下 |
| `_handle_legacy_keys(value)` | `:169-189` | str 时做 `{category}→{categories}`、`{total_episode}→{total_episodes}` 替换；**只在 `get_setting` 的返回值上做，不写回文件** |
| `update_setting(key, value)` | `:191-205` | `_read_settings()` → 改键 → `_write_settings()`；单键更新，**不 merge 默认值** |
| `get_all_settings()` | `:207-211` | 走缓存，返回 **`.copy()`（浅拷贝，顶层新 dict）** |
| `update_all_settings(settings)` | `:213-221` | 整体覆盖写盘 |
| `reset_to_defaults()` | `:223-227` | `_write_settings(_get_default_settings())` |

#### 2.10.3 `get_setting` 的三段结构与两处「不归一」陷阱

`src/core/settings_tool.py:136-167`：

```python
env_value = os.environ.get(key.upper())          # :148
if env_value is not None:                        # :149
    return env_value                             # :151  ← 直接返回，不做任何归一
if self._settings_cache is None:
    self._settings_cache = self._read_settings() # :154-155
value = self._settings_cache.get(key, default)   # :157
value = self._handle_legacy_keys(value)          # :160
if key in _BOOL_KEYS and isinstance(value, str): # :163-164
    value = value.lower() == 'true'
return value
```

**陷阱一（旧文档说法不准确）**：`get_setting` **从不查 `_get_default_settings()`**，只做 `self._settings_cache.get(key, default)`。所以「读不到时回退默认 `False`」是错的。实测：在只含 `{'enable_api':'True'}` 的文件上 `sm.get_setting('auto_download_upload_poster')`（**不传 default**）返回 **`None`**，只是调用方通常写 `if get_settings(k):`，`bool(None) == False` 才「看起来」对了。**测试应断言 `is None` 而不是 `is False`。**

**陷阱二（布尔键走 env 分支不归一）**：`:151` 的提前 `return` 在 `:163` 的布尔归一**之前**，所以经环境变量读到的布尔键返回**裸字符串**。实测：

```
ENABLE_API=false                 → get_settings('enable_api')                  == 'false'   # 字符串，不是 False
AUTO_DOWNLOAD_UPLOAD_POSTER=True → get_settings('auto_download_upload_poster') == 'True'    # 字符串
（文件里 'True'）                 → get_settings('enable_api')                  == True      # 归一过
```

`'false'` 是**真值**（非空字符串），所以 `if get_settings('enable_api'):` 在 env 设成 `false` 时**为真**——这是一个真实的反向缺陷，必须写进文档与测试。**经文件 / default 路径才归一。**

`_BOOL_KEYS` 共 **12 键**（`:27-32`）：
`auto_upload_screenshot, delete_screenshot, do_get_thumbnail, enable_api, make_dir, media_info_suffix, open_auto_feed_link, paste_screenshot_url, rename_file, create_hard_link, second_confirm_file_name, auto_download_upload_poster`。
归一规则只有一条：`value.lower() == 'true'`——所以 `'True'`→`True`、`'False'`→`False`、**`''`→`False`**、`'1'`→`False`。

#### 2.10.4 模块便捷函数与 `combine_directories`

| 函数 | 行 | 说明 |
|---|---|---|
| `get_settings(key, default=None)` | `:234-245` | `settings_manager.get_setting(key, default)` |
| `update_settings(key, value)` | `:248-256` | `settings_manager.update_setting` |
| `get_settings_json()` | `:259-266` | `settings_manager.get_all_settings()` |
| `update_settings_json(settings)` | `:269-276` | `settings_manager.update_all_settings` |
| `combine_directories(relative_path)` | `:279-289` | `str(Path.cwd() / relative_path)` |

**`settings_tool.combine_directories` 与 `file_utils.combine_directories` 不等价**，且写测试时不能互相替换：

| 输入 | `settings_tool`（`Path.cwd() / p`） | `file_utils`（`os.path.join(os.getcwd(), p)`） |
|---|---|---|
| `'static/x.json'` | `...\static\x.json`（**反斜杠**） | `...\static/x.json`（**保留正斜杠**） |
| `''` | `...\tmp38mt1ui4`（无尾分隔符） | `...\tmp38mt1ui4\`（**有尾分隔符**） |
| `'a/b'` | `...\a\b` | `...\a/b` |

差异根因是 `pathlib` 的 `/` 运算符会归一化分隔符，`os.path.join` 不会。

**`settings_tool.combine_directories` 是模块内零调用的死代码**（已 grep 确认：`settings_tool.py` 除定义处外无任何引用；`data.py` / `picturebed.py` 用的都是 `file_utils` 那份）。所以它只对「直接 import 本模块的测试」有意义。

#### 2.10.5 text.py —— 文本/数字工具

源码 197 行，无元组返回，全部是纯函数。

| 函数 | 行 | 契约（**已实测**） |
|---|---|---|
| `chinese_name_to_pinyin(chinese_name)` | `:7` | xpinyin 逐段 `capitalize()` 后拼空格，再过 `convert_chinese_punctuation_to_english` + 一组 `' ,'→','`/`'( '→'('` 等收尾替换 + `re.sub(r'\s+',' ')`。**返回值末尾保留一个空格**：`'你好，世界'` → `'Ni Hao, Shi Jie '` |
| `convert_chinese_punctuation_to_english(text)` | `:33` | **18 条**映射键，但**字典字面量在 `‘` 处被打断**（见下），实际生效 17 条。每条都是 `str.replace(chinese, english)`（`:59-60`，顺序遍历，无边界处理）。生效映射：`，→', '`、`。→'. '`、`！→'! '`、`？→'? '`、`：→': '`、`；→'; '`、`“→"'"`、`”→"'"`、`（→' ('`、`）→') '`、`【→' ['`、`】→'] '`、`《→' <'`、`》→'> '`、`、→', '`、`——→'--'`、`…→'...'`。注意 `“`/`”` **都映射成同一个半角单引号**（不区分开闭）。实测 `'你好，世界。'` → `'你好, 世界. '` |
| `natural_keys(text)` | `:65` | `[int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]`。`'a10b2'` → `['a', 10, 'b', 2, '']`（**首尾空串也会保留**） |
| `int_to_roman(num)` | `:72` | 标准贪心减法表。`0` → `''`（while 不进循环）；`4`→`'IV'`；`1994`→`'MCMXCIV'` |
| `int_to_special_roman(num)` | `:95` | 查 `{1:'Ⅰ'…10:'Ⅹ'}`；**不在 1-10 内返回 `str(num)`**（`0`→`'0'`、`11`→`'11'`，不抛错） |
| `int_to_chinese(num)` | `:114` | 见下 |
| `chinese_to_int(chinese_num)` | `:142` | 见下 |
| `base64encoding(string)` | `:185` | `base64.b64encode(s.encode('utf-8')).decode('utf-8')` |
| `validate_and_convert_to_int(value, value_name)` | `:189` | `None`/`''` → `raise ValueError(f'{value_name} 不能为 None 或空字符串')`；`int(value)` 失败 → `raise ValueError(f'{value_name} 必须是数字，您提供的是：{value}') from e` |

**新发现的缺陷：`convert_chinese_punctuation_to_english` 的字典字面量在 `‘` 处被注释打断**（旧文档与历史测试都未发现）。

源码 `src/core/text.py:44-45` 的原文是：

```python
'‘': ''',  # Single quotation mark (opening)
'’': ''',  # Single quotation mark (closing)
```

这里 `''',` 被解析成「空串 `''` + 未闭合的三引号开头」，于是从 `''',  # Single quotation mark (opening)` 起、直到下一处 `'''`（即下一行的 `''',` 收尾）之间的内容**全部成为字符串字面量**。逐项实测的后果：

| 输入 | 输出 |
|---|---|
| `'’'`（右单引号 `’`） | **原样保留**（因为 `’` 从未成为字典键） |
| `'‘'`（左单引号 `‘`） | **被替换成** `",  # Single quotation mark (opening)\n        '’': "` 这串垃圾（`‘` 是键，值成了那两行注释文本） |

即：`convert_chinese_punctuation_to_english('A’B')` → `'A’B'`（无变化）；`convert_chinese_punctuation_to_english('‘A')` → `'",  # Single quotation mark (opening)\n        '’': "A'`。

影响面：`chinese_name_to_pinyin` 内部会调它，所以**中文名里含 `‘` 会把注释文本拼进文件名/标题**；含 `’` 则不会被转换。18 个键中实际只有 17 个生效，`‘`/`’` 这对是坏的。**这是可被测试固化的确定性行为**（不要写「`‘`→`'`」这种期望）。

**`int_to_chinese`（`:114-139`）—— 正序逐位实现，不是旧文档写的「反向遍历 + 十百千万单位」**：

1. `num < 0 or num > 9999` → **`'数字超出范围'`**（`:115-116`）。
2. `num == 0` → `'零'`（`:117-118`）。
3. 按 `str(num)` **正序**逐位取 `units = ['', '十', '百', '千']` 的 `units[len(s)-1-i]`，非零位拼 `digits[d] + unit`（`:124-133`）。
4. 零位的补零规则：`chars` 非空、末位不是 `'零'`、且**后面还有非零位**才补 `'零'`（`:129-131`）——所以尾部零与连续零都不补。
5. `10 <= num < 20` → `result = result[1:]` 去掉前导「一」（`:136-138`）。

实测：`0→'零'`、`10→'十'`、`11→'十一'`、`15→'十五'`、`19→'十九'`、`20→'二十'`、`25→'二十五'`、`99→'九十九'`、`100→'一百'`、`101→'一百零一'`、`110→'一百一十'`、`300→'三百'`、`999→'九百九十九'`、`1000→'一千'`、`1001→'一千零一'`、`9999→'九千九百九十九'`、`10000/-1→'数字超出范围'`。

**`chinese_to_int`（`:142-182`）—— 正序累加，`万` 进档有真实 bug**：

1. `not chinese_num` → `None`（`:144-145`）；`''` 与 `None` 都走这条。
2. 逐字符：数字字符写 `current`；单位字符 `total += current * unit` 后 `current = 0`；**`current` 为 0 时按 1 处理**（`:174`，故 `'十'`→10）。
3. 非数字非单位字符 → `raise ValueError`，被 `:181-182` `except ValueError: return None` 兜住 → 返回 `None`。
4. 末尾 `total += current`（`:179`）。

**`unit_map` 含 `'万': 10000`，但用「立即乘 unit 累加」的正序算法处理万位是错的**（万应该是「前面一段整体 ×10000」，不是「当前位 ×10000」）。实测确认：

```
'十二万' -> 20010      （正确值 120000）
'十万'   -> 10010      （正确值 100000）
'万'     -> 10000      （巧合正确）
'一亿'   -> None       （'亿' 不在 unit_map，抛 ValueError 被吞）
```

千以内正确：`'零'→0`、`'一'→1`、`'十'→10`、`'十一'→11`、`'十五'→15`、`'二十'→20`、`'二十五'→25`、`'九十九'→99`、`'一百'→100`、`'一百零一'→101`、`'一百一十'→110`、`'三百'→300`。非法字符 `'abc'` → `None`。

**注意 `chinese_to_int` 不处理多位数连写**（算法里 `current` 每次赋值而非累加），所以「十二」=10+2=12 正确只是因为它恰好是「十」+「二」。

---

### 2.11 data.py —— 下拉框数据与缩写

源码 173 行，4 个函数。`get_combo_box_data` / `update_combo_box_data` / `get_abbreviation` 走 **cwd 相对**路径（`file_utils.combine_directories`），`load_names` 走调用方传入路径。

#### 2.11.1 `get_combo_box_data(data_name) -> (bool, list)`

`src/core/data.py:9`。

1. `file_path = combine_directories('static/combo-box-data.json')`（`:12`）。
2. `default_content = {}`（`:14`），再按 `data_name` 三分支赋值（`:17-55`）。**未知 `data_name` 时保持 `{}`**。

| `data_name` | 行 | 代码默认列表（**含末尾 `''`，长度按下表**） |
|---|---|---|
| `playlet-source` | `:17-27` | `['网络收费短剧','网络免费短剧','抖音短剧','快手短剧','腾讯短剧','']` → **6 项**（5 个非空 + 末尾空串） |
| `source` | `:29-42` | `['WEB-DL','Remux','Blu-ray','UHD Blu-ray','Blu-ray Remux','UHD Blu-ray Remux','HDTV','DVD','']` → **9 项**（8 + 空串） |
| `team` | `:44-55` | `['AGSVWEB','AGSVMUS','AGSVPT','GodDramas','CatEDU','Pack','']` → **7 项**（6 + 空串） |

> 旧文档写「5 / 8 / 6 项」只在理解成「**非空**条目数」时才勉强成立；把 `list` 长度直接断言成 5/8/6 会失败。**按长度断言请用 6 / 9 / 7。**

3. `data = load_or_initialize_json(file_path, default_content, backfill=True)`（`:58`）——**`backfill=True`**，所以已存在的文件若缺该键会被补齐并**写回**（保留原缩进）。这与 `get_abbreviation` 的 `backfill=False` 形成对照。
4. `return True, data[data_name]`（`:59`）。**返回的是文件里的实际内容，不是代码默认值**——所以「代码默认 vs 文件内容」的漂移会直接体现在返回值上。
5. 外层 `except Exception as e: return False, [str(e)]`（`:61-63`）——**payload 是单元素列表**，与其他模块的中文错误串形态不同。

**未知 `data_name` 的完整路径（旧文档未描述）**：`default_content` 为 `{}` →
若文件不存在，`load_or_initialize_json` 会以 `{}` **创建文件**（`:270-275`）→ 之后 `data[data_name]` 抛 `KeyError("'bogus'")` → 被 `:61` 捕获。实测返回 **`(False, ["'bogus'"])`**（字符串里**带单引号**，是 `str(KeyError)` 的 `repr` 形态），并且 **`static/combo-box-data.json` 被创建成一个空 `{}`**。写测试时注意这是个「查询即建文件」的副作用。

**代码默认与实际文件的漂移（实测）**：`static/combo-box-data.json` 里 `playlet-source` 有 **7 项**且含 **`'哔哩哔哩短剧'`**——该值**不在代码默认列表里**，是手工加进文件的；`source`（9 项）与 `team`（7 项）与代码默认逐项一致。因为走 `backfill=True` 只补缺失键、**不删既有值**，这种漂移不会被自动收敛。

#### 2.11.2 `update_combo_box_data(configuration_data, configuration_name) -> (bool, str)`

`src/core/data.py:66`。

**第一行就是 bug**（`:68`）：

```python
sources_list = configuration_data.split('\\n')
```

Python 源码里写的是 `split('\n')` 吗？**不是**——源码是 `split('\\n')`，`'\\n'` 是**反斜杠 + 字母 n 两个字符**的字面量，**不是换行符**。所以它按「字面量反斜杠+n」切分，而**不按真换行切分**。实测（把源码表达式复原后跑）：

| 入参（用 `repr` 描述，避免转义歧义） | 结果写入值 |
|---|---|
| 真换行符连接：`'a' + chr(10) + 'b'` | `['a' + chr(10) + 'b']` —— **单元素列表，真换行从未被切分** |
| 字面量反斜杠+n 连接：`'a' + chr(92) + 'n' + 'b'` | `['a', 'b']` —— 只有字面量才切分 |

**这是真实功能 bug**：所有正常换行输入的调用方（GUI/API 的多行文本框）都只能写入**一整条**字符串，下拉框永远只有一项。旧文档把它写成了正确行为（「按换行分割」），必须改正。已有测试 `tests/test_core_data.py:50` 传的是 `"A\\nB\\nC"`（Python 字面量即 `A` + 反斜杠 + `n` + `B` + …，**不是真换行**），所以**恰好通过**——这掩盖了 bug。**修 bug 时要注意这条既有测试会一起变红。**

后续流程：

1. `file_path = combine_directories('static/combo-box-data.json')`（`:71`）。
2. `try`: 打开读 `existing_data`（`:75-76`）；`configuration_name not in existing_data` 则先置 `[]`（`:79-80`）；**无条件覆盖赋值** `existing_data[configuration_name] = sources_list`（`:83`，所以第 79-80 行的「先建空列表」是冗余的）；`json.dump(..., ensure_ascii=False, indent=4)` 写回（`:86-87`）；`(True, '更新成功')`（`:89`）。
3. `except FileNotFoundError`（`:91-96`）：`os.makedirs(os.path.dirname(file_path), exist_ok=True)` + 写 `{configuration_name: sources_list}`；返回 **`(True, '文件不存在，已创建新文件并更新')`**。
4. `except json.JSONDecodeError`（`:98-99`）：`(False, 'JSON解码错误，文件内容可能损坏')`。
5. `except Exception`（`:101-103`）：`(False, f'更新失败，错误：{str(e)}')`。

**四条消息逐字**（已复核）：`'更新成功'`、`'文件不存在，已创建新文件并更新'`、`'JSON解码错误，文件内容可能损坏'`、`f'更新失败，错误：{str(e)}'`。

注意第 3 步的 `except FileNotFoundError` 只能捕到 `open(file_path,'r')` 的失败；若目录也不存在，它自己 `os.makedirs` 补建（历史修复点，`tests/test_core_data.py:58` 有回归用例）。但**文件存在而目录不存在**不可能同时成立，所以 `makedirs` 只为覆盖「目录被外部删掉」的场景。

#### 2.11.3 `get_abbreviation(original_name, json_file_path='static/abbreviation.json') -> str`

`src/core/data.py:106`。**有两处独立缺陷。**

**缺陷一：形参 `json_file_path` 立刻被覆盖**（`:109`）：

```python
def get_abbreviation(original_name: str, json_file_path: str = 'static/abbreviation.json') -> str:
    print('开始对参数名称进行转化')
    try:
        json_file_path = combine_directories('static/abbreviation.json')   # :109  覆盖入参
```

所以**传入的路径是死的**，永远读 cwd 下的 `static/abbreviation.json`。测试不能靠传路径隔离，**必须 chdir**。

**缺陷二：损坏文件抛未捕获的 `ValueError`**（`:112-167`）：

- `load_or_initialize_json(..., backfill 不传 → False)`（`:112-158`）：`backfill=False` 意味着**只读，绝不改写已有文件**。这与旧文档「缺键会被写回创建」相反——**`get_abbreviation` 不做任何写回**。真正的写回只发生在 `rename.load_min_widths_from_json`（`src/core/rename.py:370`，它自己 `json.dump`）。
- 文件不存在时 `load_or_initialize_json` 会**以默认表创建文件**并返回（`:270-275`），所以「首次调用即建文件」是成立的，但这与「缺键回填」是两件事。
- 文件损坏时 `load_or_initialize_json` 抛 **`ValueError(f"JSON 解析失败，文件可能损坏: {path}")`**（`file_utils.py:282`）。而 `data.py` 只 catch `FileNotFoundError`（`:162-164`）和 `json.JSONDecodeError`（`:165-167`）。`ValueError` **不是** `JSONDecodeError` 的父类，所以：
  - **损坏文件 → `ValueError` 向上冒泡，未被任何分支捕获**。实测确认：`ValueError: JSON 解析失败，文件可能损坏: <路径>`。
  - **`except json.JSONDecodeError` 分支已是死代码**（`load_or_initialize_json` 内部已把 `JSONDecodeError` 转成 `ValueError`，不会再漏出来）。
  - `except FileNotFoundError` 也是**死的**（`load_or_initialize_json` 在文件缺失时走创建路径，不会抛 `FileNotFoundError`；创建路径里的 `mkdir` 失败是 `OSError`）。
- 命中逻辑：`str(abbreviation_map.get(original_name, original_name))`（`:161`）——**未命中原样返回**，且**强制 `str()`**（所以默认表里 `'8 bits': ''` 这类空值返回 `''`，`int`/`None` 值会被字符串化）。

**代码默认表 42 键 vs 文件 43 键（实测）**：

| 集合差 | 成员 |
|---|---|
| 代码有、文件无 | `'Audio'` |
| 文件有、代码无 | `'120.000 FPS'`（→`'120FPS'`）、`'C L R LS RS LFE Cb'`（→`'5.1'`） |

第三个差异在**同键不同值**：代码写 `'C L R Ls Rs LFE': '5.1'`，文件写 `'C L R LS RS LFE Cb': '5.1'`（大小写与多出的 `Cb` 都不同）——所以**文件里能匹配的声道串与代码默认表不重合**。由于 `backfill=False`，这些差异永远不会被补齐。

默认表还含一个特殊项：`'min_widths': MIN_WIDTHS`（`:115`，从 `src/core/video.py` import），实测与 `static/abbreviation.json` 的 `min_widths` **完全相等**（7 键，字符串数字 → 分辨率缩写）：

```
'9600':'8640p'  '4608':'4320p'  '3200':'2160p'  '2240':'1440p'
'1600':'1080p'  '900':'720p'    '533':'480p'
```

#### 2.11.4 `load_names(file_path, name) -> Any`

`src/core/data.py:170-173`：`with open(file_path,'r',encoding='utf-8') as file: data = json.load(file); return data[name]`。**无 try 包裹**——文件缺失抛 `FileNotFoundError`，键缺失抛 `KeyError`，损坏抛 `JSONDecodeError`，全部向上冒泡。是与本模块其余函数（一律 return 元组）风格相反的例外。

注意：`file_path` **不做 `combine_directories`**，所以是**原样使用调用方传入的路径**（cwd 相对与否取决于调用方），与同模块另三个函数内部自行拼接 `static/...` 的行为不同。测试请传绝对路径或先 `chdir`。

#### 2.11.5 本节结论速查（写测试时的断言清单）

| 断言点 | 正确期望 |
|---|---|
| `get_combo_box_data('playlet-source'/'source'/'team')` 的**列表长度** | **6 / 9 / 7**（不是 5/8/6） |
| `get_combo_box_data('bogus')` | `(False, ["'bogus'"])`，并**创建**空的 `static/combo-box-data.json` |
| `update_combo_box_data(真换行串, 键)` | 写入**单元素**列表（`'\\n'` 字面量 bug）；只有字面量反斜杠+n 才切分 |
| `get_abbreviation` 的第二个参数 | **无效**，永远读 cwd 下 `static/abbreviation.json` |
| `get_abbreviation` 遇损坏文件 | **抛 `ValueError`**（不是「原样返回」）；`JSONDecodeError`/`FileNotFoundError` 两个 except 都是死代码 |
| `get_abbreviation` 是否写回文件 | **不写回**（`backfill=False`） |
| `load_or_initialize_json` 的 `ensure_ascii` 默认 | **`False`**（中文不转义） |

---

## 3. 设置与数据文件清单

### 3.1 static/settings.json —— 38 键全表

键集合来自 `SettingsManager._get_default_settings()`（`src/core/settings_tool.py:57-109`），实测 **38 键**。示例值取自当前仓库的 `static/settings.json`（本地文件实测 **37 键**）。

**「示例值」列的含义**：当前文件中该键的实际内容。凡标为「(默认)」的表示文件里缺该键，实际运行时由调用方 default 兜底（**不**是 `get_setting` 兜底，见 §2.10.3）。

| 键 | 文件示例值 | 默认值 | 控制内容 |
|---|---|---|---|
| `api_port` | `"5372"` | `"15372"` | API 监听端口。**`start_api()` 实际用 `get_settings('api_port')`**（`src/api/startapi.py:71`），而非 `config.API_PORT`——env `API_PORT` 因此对实际监听端口无效 |
| `enable_api` | `""` | `True` | 是否启用 API（`_BOOL_KEYS`） |
| `pt_gen_api_url` | `"https://pt-gen.hares.dpdns.org/api/getData"` | 同 | PT-Gen 主接口 |
| `pt_gen_api_url_backup` | `"https://ptgen.agsvpt.work/"` | 同 | 备用 PT-Gen 接口 |
| `pt_gen_auth_secret` | **（密钥，本文不打印值）** | 密钥 | PT-Gen HMAC-SHA256 签名密钥 |
| `picture_bed_api_url` | `"https://freeimage.host/api/1/upload"` | 同 | 图床上传接口，同时决定 provider 类型 |
| `picture_bed_api_token` | **（token，本文不打印值）** | token | 图床 token |
| `screenshot_storage_path` | `"temp/pic"` | 同 | 截图/缩略图输出目录 |
| `screenshot_number` | `"3"` | 同 | 截图张数 |
| `screenshot_threshold` | `"30.00"` | `"30.0"` | 关键帧复杂度阈值（**值不同**） |
| `screenshot_start_percentage` | `"0.10"` | 同 | 截图起始帧占比 |
| `screenshot_end_percentage` | `"0.90"` | 同 | 截图结束帧占比 |
| `auto_upload_screenshot` | `"True"` | `True` | 自动上传截图（bool） |
| `paste_screenshot_url` | `"True"` | `True` | 截图 URL 粘贴进简介（bool） |
| `delete_screenshot` | `"True"` | `True` | 上传后删除本地截图（bool） |
| `auto_download_upload_poster` | **(文件缺此键)** | `False` | 自动下载上传海报（bool） |
| `do_get_thumbnail` | `"True"` | `True` | 生成并上传缩略图（bool） |
| `thumbnail_rows` | `"3"` | 同 | 缩略图行数 |
| `thumbnail_cols` | `"3"` | 同 | 缩略图列数 |
| `thumbnail_delay` | `"2.0"` | 同 | 缩略图上传前延迟秒数 |
| `torrent_storage_path` | `"temp/torrent"` | 同 | 种子输出目录 |
| `media_info_suffix` | `"True"` | `True` | MediaInfo 追加 `Created by Publish Helper`（bool） |
| `make_dir` | `"True"` | `True` | 视频移入同名文件夹（bool） |
| `rename_file` | `"True"` | `True` | 执行重命名（bool） |
| `create_hard_link` | `""` | `True` | 创建硬链接（bool） |
| `second_confirm_file_name` | `"True"` | `True` | 二次确认文件名（bool） |
| `main_title_movie` | `"{en_title} {year} {video_format} {source} {video_codec} {bit_depth} {hdr_format} {frame_rate} {audio_codec} {channels} {audio_num}-{team}"` | 同 | 电影主标题模板 |
| `second_title_movie` | `"{original_title} / {other_titles} \| 类型：{categories} \| 演员：{actors}"` | 同 | 电影副标题模板 |
| `file_name_movie` | `"{original_title}.{en_title}.{year}.{video_format}.{source}.{video_codec}.{bit_depth}.{hdr_format}.{frame_rate}.{audio_codec}.{channels}.{audio_num}-{team}"` | 同 | 电影文件名模板 |
| `main_title_tv` | `"{en_title} S{season} {year} {video_format} {source} {video_codec} {bit_depth} {hdr_format} {frame_rate} {audio_codec} {channels} {audio_num}-{team}"` | 同 | 剧集主标题模板 |
| `second_title_tv` | `"{original_title} / {other_titles} \| {total_episodes} \| 类型：{categories} \| 演员：{actors}"` | 同 | 剧集副标题模板 |
| `file_name_tv` | `"{original_title}.{en_title}.S{season}E{episode}.{year}.{video_format}.{source}.{video_codec}.{bit_depth}.{hdr_format}.{frame_rate}.{audio_codec}.{channels}.{audio_num}-{team}"` | 同 | 剧集文件名模板 |
| `main_title_playlet` | `"{en_title} S{season} {year} {video_format} {source} {video_codec} {bit_depth} {hdr_format} {frame_rate} {audio_codec} {channels} {audio_num}-{team}"` | 同 | 短剧主标题模板 |
| `second_title_playlet` | `"{original_title} \| {total_episodes} \| {year}年 \| {playlet_source} \| 类型：{categories}"` | 同 | 短剧副标题模板 |
| `file_name_playlet` | `"{original_title}.{en_title}.S{season}E{episode}.{year}.{video_format}.{source}.{video_codec}.{bit_depth}.{hdr_format}.{frame_rate}.{audio_codec}.{channels}.{audio_num}-{team}"` | 同 | 短剧文件名模板 |
| `auto_feed_link` | `"https://example.com/upload.php#separator#name#linkstr#..."` | 同 | auto_feed 模板（**必须以 `#separator#` 分隔**） |
| `open_auto_feed_link` | `"True"` | `True` | 生成后自动打开链接（bool） |
| `personalized_signature` | `""` | `""` | 追加到 PT-Gen 简介开头（**默认值是空串，不是非空**） |

**「读不到就回退默认」这句话要谨慎**：`get_setting` **不查** `_get_default_settings()`（§2.10.3 陷阱一）。实测 `auto_download_upload_poster` 缺失时 `get_setting(k)` 返回 **`None`**，`bool(None) == False` 才让行为「看起来对」。若某调用方写了 `get_settings('auto_download_upload_poster', True)`，就会得到 `True`——**与默认表里的 `False` 相反**。

**当前文件与默认表的实测差异（1 项缺失 + 13 项值不同）**：

- **缺键**（1 个）：`auto_download_upload_poster`。
- **值不同**（13 个），分两类：
  - 2 个字符串键：`api_port`（`'5372'` vs `'15372'`）、`screenshot_threshold`（`'30.00'` vs `'30.0'`）；
  - 11 个布尔键：`auto_upload_screenshot`、`create_hard_link`、`delete_screenshot`、`do_get_thumbnail`、`enable_api`、`make_dir`、`media_info_suffix`、`open_auto_feed_link`、`paste_screenshot_url`、`rename_file`、`second_confirm_file_name`。文件里存的是**字符串 `'True'`**（或 `''`，如 `create_hard_link` 与 `enable_api`），默认表里是**真 bool `True`**。
- 这 11 个布尔键的差异正是 `_BOOL_KEYS` 归一存在的原因：文件里是 `'True'`，读出来必须变 `True`；而 `''` 归一为 `False`（所以本地这份文件实际**关闭**了 API 与硬链接）。
- **写测试时不要硬编码这份文件的当前值**（`api_port='5372'`、`enable_api=''` 等随时可能被本地环境改动）。要断言默认表就用 `SettingsManager._get_default_settings()`（38 键、真 bool），要断言归一则用自己造的临时文件。

### 3.2 其它数据文件（`static/` 下 4 个 JSON）

| 文件 | 顶层结构 | 当前实际规模 | 维护者与读写语义 |
|---|---|---|---|
| `static/picture-bed-data.json` | `{provider: [url, ...]}` | **6 键**：`lsky-pro`(3)、`bohe`(1)、`chevereto`(1)、`freeimage`(1)、`imgbb`(1)、`pixhost`(1) | `picturebed.get_picture_bed_type`。**会写回**：缺默认 key 补默认、已有 key 缺默认 URL 则 append（`ensure_ascii=False, indent=4`）。但 `default_content` **只有 5 家、无 `chevereto`**，故 chevereto 缺失时不会被补 |
| `static/combo-box-data.json` | `{team:[...], source:[...], playlet-source:[...]}` | **3 键**：`team`(7)、`source`(9)、`playlet-source`(7，含 `'哔哩哔哩短剧'`) | `data.get_combo_box_data`（`backfill=True`，缺 key 会补齐**并写回**，保留原缩进）/ `data.update_combo_box_data`（整体覆盖某键，`indent=4`） |
| `static/abbreviation.json` | 扁平映射（`'3 840 pixels': '2160p'` 等）**外加**一个 `min_widths` 子字典 | **43 键**（42 个扁平映射 + `min_widths`） | `data.get_abbreviation`（`backfill=False`，**只读不改写**）与 `rename.load_min_widths_from_json`（**唯一会写回的文件使用者**，`src/core/rename.py:370-395`，缺 `min_widths` 时才 `json.dump(..., indent=4)`） |
| `static/settings.json` | 扁平 `{key: value}`（值多为字符串） | **37 键**（默认表 38，缺 `auto_download_upload_poster`） | `SettingsManager`；含 `pt_gen_auth_secret` / `picture_bed_api_token` **两个密钥字段**，**测试不得读取/打印其值，也不得把真实文件写坏** |
| `static/ph-bjd.ico` | 二进制图标 | — | GUI 图标资源，非 JSON |

对旧文档两处说法的更正：

1. **`abbreviation.json` 不会因为「缺键」被写回创建**。`get_abbreviation` 传的是 `backfill=False`（不传该参），`load_or_initialize_json` 在「文件存在」路径下**绝不改写**（实测 `unchanged: True`）；只有「文件不存在」时才以默认表创建。真正做**写回补齐**的是 `rename.load_min_widths_from_json`，且它只补 `min_widths` 这一个键。
2. **`get_abbreviation` 对损坏文件不是「原样返回」**，而是抛未捕获的 `ValueError`（§2.11.3 缺陷二）。

`load_or_initialize_json`（`src/utils/file_utils.py:242-304`）自身的契约：

| 项 | 值 | 行 |
|---|---|---|
| 签名 | `(path, defaults, ensure_ascii=False, backfill=False)` | `:242-247` |
| `ensure_ascii` 默认 | **`False`** → 中文**非转义**落盘（实测新建文件 `'{\n    "中文": "值"\n}'`） | `:246` |
| 新建时缩进 | 固定 **`indent=4`**，并 `mkdir(parents=True, exist_ok=True)` 建父目录 | `:270-275` |
| 新建返回值 | `dict(defaults)`（**浅拷贝**，调用方改它不影响原 `defaults`） | `:275` |
| `backfill=False` | 只读，**绝不写盘** | `:285-291` |
| `backfill=True` 且无缺失 | 也不写盘（`changed` 为假） | `:291` |
| `backfill=True` 且有缺失 | 写回，**探测原文件缩进**：取第一个以空格/制表符开头且非注释行的前导空白；**探测失败（如单行无缩进 JSON）回落 `4`** | `:292-302` |
| 文件损坏 | `raise ValueError(f"JSON 解析失败，文件可能损坏: {path_obj}")` | `:281-282` |

实测缩进探测：`'{\n  "a": 1\n}'` + `backfill=True` → 写回仍是 **2 空格**；`'{"a":1}'`（单行）+ backfill → 写回 **4 空格**。

### 3.3 src/config/settings.py —— Config 类

`config` 是模块级单例（`src/config/settings.py:82` `config = Config()`），**import 即执行**：`load_dotenv()`（读 `.env`）→ 建 6 个目录 → 读 env。

**路径属性**（`:19-24`，全部基于 `Path(__file__).parent.parent.parent`，即仓库根）：

| 属性 | 值 | 实际被谁用 |
|---|---|---|
| `BASE_DIR` | `Path(...)/publish-helper` | 仅作为其余路径的基 |
| `SRC_DIR` | `BASE_DIR / "src"` | 仅入口脚本 `sys.path` 自举（`main_gui.py:37` / `main_api.py:24` 插入；`main_cli.py:16` 只插项目根，靠 `src.` 前缀导入） |
| `STATIC_DIR` | `BASE_DIR / "static"` | 全仓 3 处引用：`settings_tool.py:45`（`settings.json` 的真实路径，**核心代码唯一使用点**）、`main_api.py:39` 与 `main_gui.py:54`（仅启动日志打印）。注意 `data.py`/`picturebed.py` 读 `static/` 下其它 JSON 时**不用它**，而是 cwd 相对拼接 |
| `TEMP_DIR` | `BASE_DIR / "temp"` | **`/api/getFile` 的安全根**（`src/api/startapi.py:1746`，注释明确「不用 cwd，避免服务以不同 cwd 启动时基准漂移」——是本模块唯一被 API 生产代码使用的路径属性） |
| `MEDIA_DIR` | `BASE_DIR / "media"` | **生产代码零引用**——API 的 media 根实际用 `combine_directories('media')`（**cwd 相对**，`src/api/startapi.py` 共 **13 处**），不是 `config.MEDIA_DIR` |
| `LOGS_DIR` | `BASE_DIR / "logs"` | `LOG_FILE` 的基 |

**方法**：`_create_directories()`（`:54-66`）建 `STATIC_DIR`、`TEMP_DIR`、`TEMP_DIR/pic`、`TEMP_DIR/torrent`、`MEDIA_DIR`、`LOGS_DIR`；`get_temp_pic_dir()`（`:68-70`）→ `TEMP_DIR/"pic"`；`get_temp_torrent_dir()`（`:72-74`）→ `TEMP_DIR/"torrent"`；`is_development()`（`:76-78`）→ `os.getenv("ENVIRONMENT","production").lower() == "development"`。

**env 旋钮清单（含旧文档漏掉的两个）**：

| 属性 | env 名 | 默认值 | 消费方 |
|---|---|---|---|
| `API_HOST` | `API_HOST` | `"0.0.0.0"` | `startapi:71`、`main_api:37` |
| `API_PORT` | `API_PORT` | `15372`（`int()`） | `main_api:37` 仅日志；**实际监听端口走 `get_settings('api_port')`** |
| `API_DEBUG` | `API_DEBUG` | `"false"`（`.lower()=="true"`） | `startapi:71`、`main_api:38` |
| `GUI_TITLE` | `GUI_TITLE` | `"Publish Helper"` | **代码零引用**（仅 `.env.example` 声明） |
| `GUI_VERSION` | `GUI_VERSION` | `"1.4.5"` | `main_gui:53` 仅日志 |
| `PTGEN_API_URL` | `PTGEN_API_URL` | `""` | **代码零引用**（PT-Gen 实际走 settings 的 `pt_gen_api_url`） |
| `PTGEN_API_KEY` | `PTGEN_API_KEY` | `""` | **代码零引用** |
| `IMAGE_HOST_TYPE` | `IMAGE_HOST_TYPE` | `"freeimage"` | **代码零引用** |
| `IMAGE_HOST_API_URL` | `IMAGE_HOST_API_URL` | `""` | **代码零引用** |
| `IMAGE_HOST_API_KEY` | `IMAGE_HOST_API_KEY` | `""` | **代码零引用** |
| `MEDIAINFO_PATH` | `MEDIAINFO_PATH` | `""` | **代码零引用** |
| `LOG_LEVEL` | `LOG_LEVEL` | `"INFO"` | `utils/logger.py:59,104` |
| `LOG_FILE` | `LOG_FILE` | `"app.log"` → `LOGS_DIR/"app.log"` | `utils/logger.py:104`。注意 `.env.example` 里写的是 `LOG_FILE=logs/app.log`，会得到 `LOGS_DIR/"logs/app.log"`（**嵌套一层**） |
| `AUTH_TOKEN`（模块级，非 Config 属性） | **`API_AUTH_TOKEN`** | `''`（`.strip()`） | `src/api/startapi.py:31-32`。**非 Config 属性，是 startapi 自己的模块级常量** |
| `_CORS_ORIGINS`（模块级） | **`API_CORS_ORIGINS`** | `'*'`（`.strip() or '*'`） | `src/api/startapi.py:34-35`。**同样非 Config 属性** |

**旧文档漏了 `API_AUTH_TOKEN` 与 `API_CORS_ORIGINS`。** 这两个虽在 `.env.example` 的「API Configuration」段落里，但**不由 `Config` 读取**——`Config` 无对应属性，它们是 `startapi.py` 直接 `os.getenv` 的模块级常量，且**在 import 时就固化**（之后改 `os.environ` 不影响已 import 的 `AUTH_TOKEN`）。语义：设了 `API_AUTH_TOKEN` 则全端点要求 `Authorization: Bearer <token>`（`startapi.py:38-48` 的 `before_request`），未设则放行；`API_CORS_ORIGINS` 为 `*` 时不限制，否则按逗号切分收窄。

**注意「零引用」的两层含义**：`GUI_TITLE`、`PTGEN_API_URL`、`PTGEN_API_KEY`、`IMAGE_HOST_TYPE`、`IMAGE_HOST_API_URL`、`IMAGE_HOST_API_KEY`、`MEDIAINFO_PATH` 共 **7 个** env 在 `Config.__init__` 里定义了属性，但**生产代码从不 `config.<X>`**——它们是**死配置**，写测试时不要期望改 env 会改变行为。真正有生产消费者的只有：`API_HOST`、`API_DEBUG`、`LOG_LEVEL`、`LOG_FILE`（4 个生效）+ `GUI_VERSION`（仅日志）。路径类属性里只有 `STATIC_DIR`（settings 文件）与 `TEMP_DIR`（`/api/getFile` 基准）有生产消费者。

另有两个 env 属于**同一类死配置**但更隐蔽——它们在 `Config` 里**连属性都没有**，只是 `.env.example` 提到了（`.env.example` 的 `TEMP_DIR`/`MEDIA_DIR`/`STATIC_DIR` 三行**无任何代码读取**）。改这三个 env 完全不影响 `Config` 的路径属性（那些路径由 `__file__` 硬推导）。

**`ImageHostConfig`**（`:85-134`）：`SUPPORTED_HOSTS` 静态表 **7 家**（`freeimage`/`imgbb`/`imagehub`/`pixhost`/`bohe`/`lsky-pro`/`chevereto`），带 `name`/`api_url`/`requires_key`；`get_host_config(host_type)`、`get_supported_hosts()`。**与 `picturebed.py` 实际实现的 6 家不一致**：`imagehub` 在表里有、在 `upload_picture` 的分发里**没有**（会落进未识别类型分支）；而 `picturebed` 支持的 6 家与表里除 `imagehub` 外的 6 家一一对应。该类**全仓无调用方**，仅作配置参考。

---

## 4. GUI 业务流程（src/gui/startgui.py，2334 行 + src/gui/ui_tools.py，40 行）

> **读者注意：GUI 层是整个仓库里 bug 密度最高的模块。** 它有大量跨页签复制粘贴出来的近重复实现（Movie/TV/Playlet 三套 `get_name` / `get_picture` / `handle_upload_picture`），彼此已经漂移；又混用了两套 UI 工具库（PyQt6 + tkinter）。写 GUI 测试时**必须先读源码确认目标页签那一份的实际行为**，不要假定三份等价。本节所有行号均已逐条核实。
>
> 测试方案见本节末尾 §4.9。核心结论：`import src.gui.startgui` 会拉起 PyQt6（`requirements.txt` 已含 `PyQt6==6.6.1`、`PyQt6-Qt6==6.6.2`），实例化 `mainwindow()` 需要 `QT_QPA_PLATFORM=offscreen`；线程类与纯逻辑方法可以绕开 `QApplication` 直接调用。

### 4.0 入口与模块级全局

| 项 | 位置 | 说明 |
|---|---|---|
| `start_gui()` | `:38` | 建 `QApplication(sys.argv)` → `mainwindow()` → `setWindowIcon(QIcon('static/ph-bjd.ico'))`（**cwd 相对路径**）→ `show()` → `sys.exit(gui.exec())`。测试**不要调用** |
| `git_clicked()` | `:47` | `webbrowser.open('https://github.com/bjdbjd/publish-helper')`，绑到菜单 `actiongit`（`:99`） |
| 模块全局 ×4 | `:32-35` | `get_name_movie_success=False`、`get_name_movie_failure_number=0`、`get_name_tv_success=False`、`get_name_tv_failure_number=0`。**Playlet 没有对应全局**（它不走重命名线程）。这四个既是重命名流水线的状态位，也是 `WaitForRenameThread` 的轮询变量，详见 §4.5 |
| `mainwindow` 类 | `:51` | `class mainwindow(QMainWindow, Ui_Mainwindow)`，注意类名全小写、与 Qt Designer 生成的 `Ui_Mainwindow` 多继承 |
| `settings` 类 | `:2029` | `class settings(QDialog, Ui_Settings)`（同样全小写），设置对话框，见 §4.7 |

### 4.1 三个页签与按钮驱动

页签真实名称由 `src/gui/ui/mainwindow.py` 的 `retranslateUi` 设定（`.py:1913` / `.py:1938` / `.py:1999`，三个 `addTab` 分别在 `.py:581` / `.py:1149` / `.py:1863`，窗口标题 `'Publish Helper'` 在 `.py:1889`），顺序即 `tabWiget` 索引 0/1/2：**「电影」/「剧集」/「短剧」**。控件对象名前缀分别是 `*Movie` / `*TV` / `*Playlet`（内部 widget 名 `tab` / `tab_2` / `tab_3`）。生成类的名字是 `Ui_Mainwindow`（`mainwindow.py:12`，`M` 大写），与 `src/gui/ui/settings.py` 的 `Ui_Settings` 风格一致。

#### 4.1.1 信号绑定全表（`mainwindow.__init__`，`:96-131`）

| 页签 | 控件 | 槽函数 | 绑定行 |
|---|---|---|---|
| 菜单 | `actionsettings.triggered` | `self.settings_clicked` | `:98`（**`:111` 又连了一次，同一信号连同一槽两次，触发时会打开两个设置窗口**） |
| 菜单 | `actiongit.triggered` | `git_clicked`（模块级裸函数） | `:99` |
| 电影 | `getPtGenButtonMovie` | `get_pt_gen_button_movie_clicked` | `:100` |
| 电影 | `getPictureButtonMovie` | `get_picture_button_movie_clicked` | `:101` |
| 电影 | `selectVideoButtonMovie` | `select_video_button_movie_clicked` | `:102` |
| 电影 | `selectVideoFolderButtonMovie` | `select_video_folder_button_movie_clicked` | `:103` |
| 电影 | `getMediaInfoButtonMovie` | `get_media_info_button_movie_clicked` | `:104` |
| 电影 | `getNameButtonMovie` | `get_name_button_movie_clicked` | `:105` |
| 电影 | `makeTorrentButtonMovie` | `make_torrent_button_movie_clicked` | `:106` |
| 电影 | `startButtonMovie` | **`start_button_movie_clicked`** | `:107` |
| 电影 | `autoFeedButtonMovie` | `auto_feed_button_movie_clicked` | `:108` |
| 剧集 | `getPtGenButtonTV` | `get_pt_gen_button_tv_clicked` | `:112` |
| 剧集 | `getPictureButtonTV` | `get_picture_button_tv_clicked` | `:113` |
| 剧集 | `selectVideoFolderButtonTV` | `select_video_folder_button_tv_clicked` | `:114`（**剧集没有「选文件」按钮，只有选文件夹**） |
| 剧集 | `getMediaInfoButtonTV` | `get_media_info_button_tv_clicked` | `:115` |
| 剧集 | `getNameButtonTV` | `get_name_button_tv_clicked` | `:116` |
| 剧集 | `makeTorrentButtonTV` | `make_torrent_button_tv_clicked` | `:117` |
| 剧集 | `startButtonTV` | **`start_button_tv_clicked`** | `:118` |
| 剧集 | `autoFeedButtonTV` | `auto_feed_button_tv_clicked` | `:119` |
| 短剧 | `getDescriptionButtonPlaylet` | `get_description_playlet_clicked` | `:122` |
| 短剧 | `getPictureButtonPlaylet` | `get_picture_button_playlet_clicked` | `:123` |
| 短剧 | `uploadCoverButtonPlaylet` | `upload_cover_button_playlet_clicked` | `:124` |
| 短剧 | `selectVideoFolderButtonPlaylet` | `select_video_folder_button_playlet_clicked` | `:125` |
| 短剧 | `selectCoverFolderButtonPlaylet` | **`select_cover_folder_button_playlet_clicked`** | `:126` |
| 短剧 | `getMediaInfoButtonPlaylet` | `get_media_info_button_playlet_clicked` | `:127` |
| 短剧 | `getNameButtonPlaylet` | `get_name_button_playlet_clicked` | `:128` |
| 短剧 | `makeTorrentButtonPlaylet` | `make_torrent_button_playlet_clicked` | `:129` |
| 短剧 | `startButtonPlaylet` | **`start_button_playlet_clicked`** | `:130` |
| 短剧 | `autoFeedButtonPlaylet` | `auto_feed_button_playlet_clicked` | `:131` |

**短剧没有「获取简介」以外的 PT-Gen 入口**：它不调 PT-Gen，`get_description_playlet_clicked` 用本地模板 `get_playlet_description` 拼简介（`:1577-1594`）。

#### 4.1.2 按钮业务

| 按钮 | 业务 | 关键位置 |
|---|---|---|
| 获取（PT-Gen） | 读 `pt_gen_api_url` / `pt_gen_api_url_backup` + `resourceUrl*` 文本框；空则写 debug 并 return。**同时启动主线程和备用线程竞速**（各自 `GetPtGenThread`），回调先判 `self.get_pt_gen_success` 去重 | 电影 `:256-283`，剧集 `:917-944` |
| 获取（截图） | `check_path_and_find_video` → `get_screenshot`(+`get_thumbnail`) → 按 `auto_upload_screenshot` 决定上传或直接回填本地路径。**三页签共用 `_upload_pictures` 抽象** | `:364-421` / `:1024-1081` / `:1611-1669`，见 §4.3 |
| 获取（MediaInfo） | `check_path_and_find_video` → `get_media_info` → `setText(media_info)` 后**再 `append('\n')`** | `:484-499` / `:1121-1136` / `:1726-1741` |
| 文件 / 文件夹 | `ui_tools.get_video_file_path()` / `get_folder_path()` 返回值直接 `setText`（**不做空值判断**，取消选择会把路径框清空） | `:476-482` / `:1117-1119` / `:1722-1724` |
| 选封面 | `ui_tools.get_picture_file_path()` → `coverPathPlaylet` | `:1718-1720` |
| 获取标准命名 | 见 §4.2 | `:501` / `:1138` / `:1743` |
| 制作种子 | 见 §4.4 | `:833` / `:1500` / `:1962` |
| 一键启动 | 见 §4.5 | `:195` / `:858` / `:1527` |
| auto feed | 读本页签 5 个文本框 + `team/source` 下拉 + 硬编码 `category`（电影 `'电影'` `:232`、剧集 `'剧集'` `:895`、短剧 `'短剧'` `:1555`）→ `get_auto_feed_link(..., self.torrent_url)` → `pyperclip.copy` → `open_auto_feed_link` 为真时写临时 HTML 并 `webbrowser.open` | `:223` / `:886` / `:1546` |

**`auto_feed` 三份实现并不等价**：电影版把响应先存 `auto_feed_link = response` 再用变量（`:237`），剧集/短剧版直接用 `response`（`:900`/`:1560`）；行为一致但测试断言 debug 文本时注意电影版多一次赋值。短剧版读 `team`/`source` 用的是 `=` 而非 `+=`（`:1553-1554`，其余两页签用 `+=`），结果相同。

#### 4.1.3 「选文件」按钮实现是 tkinter（src/gui/ui_tools.py）

**`src/gui/ui_tools.py` 整个文件共 40 行，只 `from tkinter import filedialog, Tk`，在 PyQt6 工程里用 tkinter 弹原生对话框**——这是显眼事实，值得单独断言。

| 函数 | 行 | 实现 | 过滤器 |
|---|---|---|---|
| `get_picture_file_path()` | `:4-13` | `filedialog.askopenfilename(title='Select a file', ...)`，**不建 `Tk()` 根窗口** | `('Picture files', '*.gif;*.png;*.jpg;*.jpeg;*.webp;*.avif;*.bmp;*.apng)')` —— **注意字符串末尾多了一个 `)`**，且 tkinter 的 filetypes 需要分号分隔**元组**而非单个字符串，这个过滤器的实际匹配行为不可靠 | 
| `get_video_file_path()` | `:16-25` | 同上，同样不建根窗口 | `('Video files', '*.mp4;*.m4v;*.avi;*.flv;*.mkv;*.mpeg;*.mpg;*.rm;*.rmvb;*.ts;*.m2ts')` —— 与 `src/core/video.py:7` 的 `VIDEO_EXTENSIONS` 列表完全一致（同样的 11 个扩展名），但**这份是硬编码副本**，扩展名增减不会自动同步 |
| `get_folder_path()` | `:28-40` | **这里才建 `Tk()` 根窗口**：`root = Tk()` → `root.withdraw()` → `askdirectory` → `root.destroy()`，返回路径 | 无 |

三个函数都只返回路径字符串，**没有元组包装、没有异常处理**（用户点取消返回 `''`）。测试时直接 `monkeypatch` 掉 `src.gui.ui_tools.filedialog` 即可，不需要真弹窗；**不要**去调 `Tk()`，离屏环境下会失败。

#### 4.1.4 初始化方法（`__init__` 调用链）

| 方法 | 行 | 行为 |
|---|---|---|
| `initialize_team_combobox` | `:140-150` | `get_combo_box_data('team')` → 逐项 `addItem` 到 `teamMovie`/`teamTV`/`teamPlaylet`（**三个页签共用同一份数据源**）；失败时三个 debug 框各写一条 `f'获取制作组信息出错：{data[0]}'` |
| `initialize_source_combobox` | `:152-162` | 同上，数据键 `'source'`，目标 `sourceMovie`/`sourceTV`/`sourcePlaylet`，失败文案 `'获取资源来源信息出错：'` |
| `initialize_playlet_source_combobox` | `:164-170` | 数据键 `'playlet-source'`，**只填 `playletSource` 一个控件**；失败文案 `'获取短剧来源信息出错：'`，只写短剧 debug 框 |
| `initialize_season_box` | `:172-174` | `seasonBoxTV.setValue(1)`、`seasonBoxPlaylet.setValue(1)`（电影页无季数控件） |

其余初始化（`:85-94`）：`videoPathMovie.setDragEnabled(True)`（**只有电影页签开了拖拽 URL**）、电影页 4 个浏览框 `setText('')`、`self.torrent_url = ''`。最后在 `:134-135` 往 `debugBrowserMovie` 写一条初始化提示。

**`enable_api` 分支**（`:137-138`）：`if get_settings('enable_api'): self.run_api_thread()` —— 这是 `apiThread` 唯一的生产触发点，在 `__init__` 里同步调用（`run_api_thread` 本身不阻塞，只是 `start()`）。

| 方法 | 行 | 行为 |
|---|---|---|
| `run_api_thread` | `:183-188` | 写 debug「您选择启用API功能，正在尝试启动api_thread」→ `apiThread()` → 连 `result_signal` 到 `handle_run_api_result` → `start()` → 写 debug `f'api_thread启动成功，监听端口：{get_settings("api_port")}'`。**注意端口文本来自设置而非线程实际监听结果，即使 `start_api()` 立刻崩了这里也照样报「启动成功」** |
| `handle_run_api_result` | `:190-191` | 单参数 `response`，直接 `debugBrowserMovie.append(response)` |
| `settings_clicked` | `:176-181` | `self.my_settings = settings()` → `getSettings()` → `setWindowIcon(QIcon('static/ph-bjd.ico'))` → `show()`。**对话框实例被存下来（`self.my_settings`），旧实例每次被覆盖但不会 close** |

### 4.2 get_name 重命名流水线

三个页签各一份，**差异很大**，必须分开看：

| | 电影 `get_name_button_movie_clicked` `:501` + 回调 `handle_get_pt_gen_for_name_movie_result` `:541` | 剧集 `get_name_button_tv_clicked` `:1138` + 回调 `handle_get_pt_gen_for_name_tv_result` `:1179` | 短剧 `get_name_button_playlet_clicked` `:1743` |
|---|---|---|---|
| 全局计数 | `get_name_movie_success/failure_number`（`:502` 声明 global） | `get_name_tv_success/failure_number`（`:1139`） | **无全局**，全程裸 `return`（无失败计数） |
| PT-Gen | 启动主+备 `GetPtGenThread` 竞速 | 同左 | **不调 PT-Gen**，调 `get_description_playlet_clicked()` 生成简介 |
| 前置守卫 | 无 | 无 | **有**：见 §4.5.3 |
| 集数来源 | `{集数}` 占位符单文件 | `seasonBoxTV` + `episodesStartBoxTV` + `get_video_files` 计数 | `seasonBoxPlaylet` + **误用 `episodesStartBoxTV`**（`:1794`） |
| 视频路径形态 | `is_video_path == 1`（单文件）或 `2` 都支持，但 `make_dir` 分支只在 `== 1` 生效（`:761`） | 只处理 `== 2`（文件夹） | 只处理 `== 2` |

#### 4.2.1 `get_name_button_*_clicked`（发起）

电影/剧集版本（`:501-539` / `:1138-1177`）：

1. 重置全局 `success=False`、`failure_number=0`，清 `self.path_movie`/`self.path_tv`、`self.get_pt_gen_success=False`；
2. `descriptionBrowser*.setText('')`；
3. 取 `pt_gen_api_url` / `pt_gen_api_url_backup` / `resourceUrl*.text()`；
4. **`resource_url == ''` → debug 提示 + `failure_number += 1` + return**（电影 `:513-515`，剧集 `:1151-1153`）；
5. **`pt_gen_api_url == ''` → debug 提示 + `failure_number += 1` + return**（`:516-519` / `:1154-1157`）；
6. 启主线程 `get_pt_gen_for_name_thread` → 连回调；启备用线程 `get_pt_gen_for_name_backup_thread` → 连**同一个**回调；
7. 整个函数包在 `try/except` 里，异常时 `failure_number += 1` 并 `return False, [f'启动PtGen线程出错：{e}']`（`:536-539` / `:1174-1177`）—— 这个 `return` 值**调用方从不接收**，是死返回值。

> **全局计数语义**：`failure_number` 同时承担两个角色 ——（a）流水线内部各步失败的累加器，（b）`WaitForRenameThread` 的轮询退出条件。因为主/备两个 PT-Gen 线程都会回调同一个 handler，`WaitForRenameThread` 的退出条件 `failure_number <= 1` 实际是在等「至多一次失败」。一旦流水线中途失败，计数 +1 后立即 return，`WaitForRenameThread` 下一次轮询（≤0.5s 后）就退出。

#### 4.2.2 回调 `handle_get_pt_gen_for_name_*_result(self, get_success, response, raw_data_json='')`

**电影版（`:541-831`）逐步骤与失败计数：**

| 步 | 行 | 行为 | 失败处理 |
|---|---|---|---|
| 1 | `:544-547` | `self.get_pt_gen_success` 已为真 → 「主线程已经成功获取到简介，备用线程关闭」 | **`failure_number += 1` 后 return**（备用线程被作废时也会把计数推到 1，这会顺带让 `WaitForRenameThread` 提前退出） |
| 2 | `:548-565` | `get_success` 为假 → debug `f'未成功获取到任何PT-Gen信息：{response}'`；为真但 `description` 为空 → debug `'获取PT-Gen信息失败，响应为空'` | 两条路径都 `failure_number += 1` + return（`:564` / `:553`） |
| 3 | `:559-561` | `description = self._process_poster_in_description(description)` 然后 `setText`。**此处在 `self.get_pt_gen_success = True`（`:566`）之前** | 海报处理内部 try/except，不影响流程 |
| 4 | `:566` | `self.get_pt_gen_success = True` | — |
| 5 | `:567-568` | 一次性解包 10 个空串：`video_format, video_codec, bit_depth, hdr_format, frame_rate, audio_codec, channels, audio_num, other_titles, actors` | — |
| 6 | `:569-574` | 取 `make_dir` / `rename_file` / `second_confirm_file_name` / `create_hard_link` 四个开关 + `path`（`videoPathMovie.text().replace('file:///', '')`，**只去 `file:///` 一种前缀**） | — |
| 7 | `:576-580` | `check_path_and_find_video(path)`，`is_video_path` 必须是 1 或 2 | `:817-820` debug `f'您的视频文件路径有误{response}'` + `+=1` + return |
| 8 | `:583-593` | `raw_data_json` 非空时 `json.loads` 成 `pt_gen_raw_data`（内层 try/except 吞掉 `pass`）→ `get_pt_gen_info(description, raw_data=pt_gen_raw_data)` 解 8 元组 `original_title, english_title, year, other_names_sorted, categories, actors_list, episodes, season` | 抛异常 → debug `f'获取到了PT-Gen Api的响应，但是对于响应的分析有错误：{e}...'`（`:595-600`）+ `+=1` + return |
| 9 | `:609-613` | `year == '' or year is None` → debug `'PT-Gen分析结果不包含年份，存在错误'` | `+=1` + return |
| 10 | `:617-629` | `actors_list` 用 `' / '` 拼接；`other_names_sorted` 每项后加 `' / '` 再 `[: -3]` 去尾（**注意：列表为空时 `''[: -3] == ''`，安全**） | — |
| 11 | `:631-673` | 英文名分支。`english_pattern` 正则见 `:631`。`second_confirm_file_name` 为真时：`english_title == ''` → `QMessageBox.information` 问是否用拼音；拼音结果不匹配正则 → 若用户选了 Yes 则 `QMessageBox.warning('资源名称不是汉语，无法使用汉语拼音')` → `QInputDialog.getText` 手输 → `.replace('.', ' ')` → 逐字符查非法字符，非空则 warning + `+=1` + return（`:660-661`）。**用户取消手输 → `english_title = ''` 并继续往下走**（`:663-666`，不失败、不 return）。`second_confirm_file_name` 为假时：`english_title == ''` → `chinese_name_to_pinyin(original_title)`，仍不匹配则 debug `'缺少英文名称，并且无法生成汉语拼音，请手动获取名称'` + `+=1` + return（`:670-673`） | 见左 |
| 12 | `:675-687` | `get_video_info(video_path)` → **`video_info[0..7]` 按位填 8 个变量** | 失败**不 return**（`if get_video_info_success:` 无 else），8 个变量保持空串继续 |
| 13 | `:688-709` | `source = sourceMovie.currentText()`、`team = teamMovie.currentText()` → `get_name_from_template(...)` × 3，模板键 `'main_title_movie' / 'second_title_movie' / 'file_name_movie'`。电影版第 3~6 个位置参数传空串、`season=''`、第 18~20 位也传空串 | — |
| 14 | `:710-721` | `second_confirm_file_name` → `QInputDialog.getText(self, '确认', '请确认文件名称，如有问题请修改', QLineEdit.EchoMode.Normal, file_name)`（**电影版提示语无「{集数}」说明**，剧集/短剧版有） | 用户取消 → debug `'您点了取消确认，重命名已取消'` + `+=1` + return |
| 15 | `:722-739` | `is_filename_too_long(file_name)`（阈值 **250 字符**，`len(filename) > 250`，`src/core/video.py:80-85`）→ 弹框改名；**改完再查一次**，仍过长 → `QMessageBox.warning('您输入的文件名过长，请重新核对后再生成标准命名！')` + `+=1` + return | 取消或二次过长均 `+=1` + return |
| 16 | `:741-743` | 三个结果框 `setText`（`mainTitleBrowserMovie` / `secondTitleBrowserMovie` / `fileNameBrowserMovie`） | — |
| 17 | `:745-759` | `create_hard_link` 为真 → `create_hard_link(path)`；成功则 `path = response`、`self.path_movie = path`、`videoPathMovie.setText(path)`，再 `check_path_and_find_video(path)`，**仅当 `is_video_path == 1` 时更新 `video_path`** | 失败 → debug `f'您选择创建硬链接，但是创建失败了：{response}'` + `+=1` + return |
| 18 | `:761-774` | `make_dir and is_video_path == 1` → `move_file_to_folder(path, file_name)`；成功则 `path = os.path.dirname(response)`、`video_path = response`、更新 `self.path_movie` 与路径框 | 失败 → `f'创建文件夹失败：{response}'` + `+=1` + return |
| 19 | `:776-797` | `rename_file` 为真且 `is_video_path == 2` → `rename_folder(path, file_name)`；成功则更新 `path`/`self.path_movie`/路径框，再 `check_path_and_find_video`，**要求返回 2** 才能更新 `video_path` | 读视频失败 / 重命名失败 → `+=1` + return（两处，`:791-793` / `:795-797`） |
| 20 | `:799-815` | 无条件继续 `rename_file(video_path, file_name)`（**即目录型也会对内部首个文件重命名**）；成功时按 `is_video_path` 分支写回路径框：`== 1` 写 `video_path`，`== 2` 写 `path`，两者都更新 `self.path_movie` | 失败 → `f'重命名失败：{response}'` + `+=1` + return |
| 21 | `:825-826` | `print("重命名全部成功")` → `get_name_movie_success = True` | — |
| 22 | `:827-831` | 外层 `except` 兜底 → debug `f'启动PtGen线程成功，但是重命名出错：{e}'` + `+=1` + `return False, [f'...']` | — |

**剧集版（`:1179-1498`）与电影版的实质差异：**

- 回调在 `:1179` 起，横幅顺序不同：`:1186-1202` 先判 `get_success` 再判空，且**多一层 `if description:` 嵌套** —— 注意 `:1188` 进了 `if description:` 之后 `:1190` 又判一次 `description == ''`，**这条分支是死代码**（为空时根本进不来）；真正为空走 `:1199-1202` 的 else。这个死分支在电影版同样存在（`:550-554`）。
- **`seasonBoxTV` 季数校验**（`:1261-1274`）：`season is not None and season_box != str(season)` → `QMessageBox.information(self, '您选择的季数信息与PT-Gen获取的不符', ...)`，三个按钮 Yes/No/Cancel。**Yes → 用用户选的 `season_box`；No → 不赋值，保持 PT-Gen 的值往下走；Cancel → `+=1` + return**（`:1268-1272`）。不一致但 `season is None` 时直接走 else 用 `season_box`。
- `season_number = season`，`len(season) < 2` 时补零 `f'0{season}'`（`:1275-1277`，**只补一位，season 为 `100` 不补**）。
- **总集数三态**（`:1280-1286`）：`episodes_start_number == 1 and episodes == episodes_num` → `f'全{N}集'`；否则 `episodes_num == 1` → `f'第{N}集'`；否则 `f'第{a}-{b}集'`（`b = a + episodes_num - 1`）。`episodes` 来自 PT-Gen，`episodes_num` 来自 `len(get_video_files(path))`（`:1226`）。
- `get_video_files` 失败 → `+=1` + return（`:1227-1231`）。
- `is_video_path` 必须是 **2**（`:1219`），否则 `:1485-1488` `+=1` + return。
- `english_title = delete_season_number(english_title, season_number)`（`:1373`）—— 电影版**没有**这一步。
- `get_name_from_template` 的模板键是 `'main_title_tv' / 'second_title_tv' / 'file_name_tv'`，`file_name` 那次传 `'{集数}'` 字面量。
- **重命名是循环**（`:1452-1484`）：`i` 从 `episodes_start_number` 起，`e = str(i)`，`while len(e) < len(str(episodes_start_number + episodes_num - 1)): e = f'0{e}'`，再 `if len(e) == 1: e = f'0{e}'`，`rename_file(video_file, file_name.replace('{集数}', e))`，`i += 1`。**单个文件重命名失败只是 debug 提示（`:1467-1468` 是唯一一处失败后不 return 的重命名，但 `+=1` 仍然发生），循环继续**。随后 `rename_folder(path, file_name.replace('E{集数}', '').replace('{集数}', ''))`（**连 `E{集数}` 一起去，处理 `E01` 这类前缀**），失败 → `+=1` + return（`:1481-1484`）。
- 硬链接成功后的 `get_video_files` 失败 → `+=1` + return（`:1445-1446`）。
- 成功末尾 `get_name_tv_success = True`（`:1493`），无 `print`。

**短剧版（`:1743-1960`）与另两者的实质差异：**

- 全函数包在一层 `try/except Exception`（`:1744` / `:1958-1960`），异常时 `print(f'获取命名出错：{e}')` 并 `return False, [f'获取命名出错：{e}']` —— **没有失败计数**（无全局）。
- 首行直接 `get_description_playlet_clicked()` 生成简介（`:1748`），不用 PT-Gen。
- **`episodes_start_number` 取自 `self.episodesStartBoxTV.text()`（`:1794`）—— 跨页签读控件**，短剧自己的 `episodesStartBoxPlaylet` 从未被读。这是复制粘贴留下的 bug，测试应按现状断言。
- 英文名分支的触发条件与另两者不同：不是「`english_title == ''`」而是 **`not re.match(english_pattern, original_title)`**（`:1755` / `:1787`）——即判断中文原名是否**不是**纯英文。
- **总集数条件也漂移**：`episodes_start_number == 1 and episodes_num != 1` → `f'全{N}集'`（电影/剧集版是 `episodes == episodes_num`）（`:1819`）。
- `get_name_from_template` 传 `other_titles=''`、`playlet_source=self.playletSource.currentText()`、`categories=self.get_categories()`、`actors=''`；模板键 `'main_title_playlet' / 'second_title_playlet' / 'file_name_playlet'`。
- **整套硬链接 / make_dir / 重命名逻辑在 `if is_video_path == 2:` 块内** —— 与电影/剧集不同，短剧没有单文件路径分支。
- **重命名循环里单文件失败不 return 也不计数**（`:1939-1941` 只有 debug 提示 + `i += 1`），**`rename_folder` 失败也不 return**（`:1952-1953` 只有 debug）—— 短剧版是三者中唯一「重命名失败仍然往下走」的。
- **短剧版没有 `second_confirm_file_name` 前置守卫之外的 make_dir 分支**（`make_dir` 开关在短剧页签**完全不生效**，全文件搜不到 `make_dir` 在 `:1743-1960` 区间的使用）。
- `original_title == ''` → 只 debug `'获取的中文名为空'`（`:1957`），**无 return 之外的处理**。

#### 4.2.3 `get_categories()`（`:1986-2023`）

短剧专用（剧集/电影的 `categories` 来自 PT-Gen）。读 **16 个复选框 `checkBox_0`..`checkBox_15`**（`mainwindow.py:1462-1511` 定义，都在 `tab_3`），按固定顺序拼中文词 + 尾随空格：

| 索引 | 词 | 索引 | 词 | 索引 | 词 | 索引 | 词 |
|---|---|---|---|---|---|---|---|
| 0 | 剧情 | 4 | 甜宠 | 8 | 重生 | 12 | 都市 |
| 1 | 爱情 | 5 | 恐怖 | 9 | 逆袭 | 13 | 古装 |
| 2 | 喜剧 | 6 | 动作 | 10 | 科幻 | 14 | 神豪 |
| 3 | 甜虐 | 7 | 穿越 | 11 | 武侠 | 15 | 霸总 |

拼接完若非空：先 `[: -1]` 去尾空格，再 `.replace(' ', ' / ')`。**因为去尾在前、替换在后，结果形如 `'剧情 / 爱情'`；全不勾返回 `''`。** 注意 `replace` 会把词内部可能存在的空格也替换掉（当前词表无内部空格，安全）。

### 4.3 截图并发上传：`_upload_pictures` 槽位有序回填

**三个页签共用同一个抽象 `_upload_pictures`（`:423-438`）**——这一点是旧文档最大遗漏。三个 `get_picture_button_*_clicked` 只是各自算参数、各自传自己的 handler 进去：

| 调用方 | 行 | 传的 handler |
|---|---|---|
| `get_picture_button_movie_clicked` | `:407-408` | `self.handle_upload_picture_movie_result` |
| `get_picture_button_tv_clicked` | `:1067-1068` | `self.handle_upload_picture_tv_result` |
| `get_picture_button_playlet_clicked` | `:1654-1655` | `self.handle_upload_picture_playlet_result` |

`_upload_pictures(self, pictures, picture_bed_path, picture_bed_token, do_get_thumbnail, handle_result)`：

```python
self._upload_slots = {}          # index -> 上传成功后的图片 URL
self._slots_to_path = {}         # index -> 本地图片路径（供 delete_screenshot 按序删除）
self._upload_total = len(pictures)
for idx, pic in enumerate(pictures):
    is_thumbnail = bool(do_get_thumbnail) and idx == len(pictures) - 1
    self._slots_to_path[idx] = pic
    thread = UploadPictureThread(picture_bed_path, picture_bed_token, pic, False, is_thumbnail, index=idx)
    thread.result_signal.connect(handle_result)
    thread.start()
```

要点（逐条核实 `:423-438`）：

1. **三个容器的初始化在 `_upload_pictures` 里做，不在 `__init__` 里做**（`__init__` 只把 `_upload_total` 置 0、两个 dict 置 `{}`，见 `:80-82`）。每个 `get_picture_button_*` 在调用 `_upload_pictures` 前还会先 `pictureUrlBrowser*.setText('')`。
2. `is_thumbnail = bool(do_get_thumbnail) and idx == len(pictures) - 1` —— 缩略图位于 `pictures` 列表末尾（`pictures = response + pictures` 把缩略图放到截图列表之后，`:397` / `:1057` / `:1646`），因此 **`do_get_thumbnail` 开启时缩略图的 index 恒为最大值，天然最后一位**。
3. **`is_cover` 恒为 `False`**（`_upload_pictures` 硬编码第 4 个参数），封面走的是独立路径 `upload_cover_button_playlet_clicked`（§4.4.4）。
4. 线程实例**不被保存**（局部变量 `thread`，循环结束后被 GC 引用计数回收），只靠 `result_signal` 回连 handler。
5. **僵尸实例变量 `self.upload_picture_thread0..5`（`:68-73`）**：6 个变量在 `__init__` 里赋值 `None`，**全文件再无任何读写**（已 grep 确认）。它们是「每张图一个具名变量」的旧样板残骸，已被 `_upload_pictures` 完全取代。写测试时不要依赖它们。

**handler 的槽位回填协议**（三份实现结构相同，Movie `:440-474`、TV `:1083-1115`、Playlet `:1671-1716`，签名均为 `(self, upload_success, api_response, screenshot_path, is_cover, is_thumbnail, index)`）：

| 步 | 行（Movie） | 行为 |
|---|---|---|
| 1 | `:446-450` | 失败 → `self._upload_slots[index] = ''` + debug `f'图床响应无效：{api_response}'`；成功 → `self._upload_slots[index] = api_response` |
| 2 | `:451-452` / `:1094-1095` / `:1695-1696` | `len(self._upload_slots) < self._upload_total` → **直接 return，继续等**（注意判的是 **dict 长度**，即已回填的槽位数） |
| 3 | `:454-455` | 全部到齐 → `ordered = [self._upload_slots[i] for i in range(self._upload_total) if self._upload_slots.get(i)]` —— **按 index 升序重建，空串被过滤掉**（失败的那些不占行） |
| 4 | `:455` / `:1097` / `:1698` | `pictureUrlBrowser*.setText('\n'.join(ordered))` |
| 5 | `:456-460` | `paste_screenshot_url` 为真 → `descriptionBrowser*.setText('\n'.join(ordered))` + debug `'成功将图片链接粘贴到简介后'`。**Movie/TV 用 `setText`（覆盖整段简介），Playlet 用 `append`（`:1702`）** —— 这是三份 handler 的实质差异之一（短剧要保留前面已生成的模板简介） |
| 6 | `:461-472` | `delete_screenshot` 为真 → `for i in range(self._upload_total)`，`_slots_to_path[i]` 存在且文件存在则 `os.remove` + debug `f'文件"{p}"已被删除'`，不存在则 debug `f'文件"{p}"不存在'` |
| 7 | `:473-474` / `:1114-1115` / `:1715-1716` | 清空 `_upload_slots` 与 `_slots_to_path`（**不重置 `_upload_total`**，但下一次 `_upload_pictures` 会覆盖） |

**Playlet handler 独有的封面短路**（`:1678-1689`）：`if is_cover:` 时**完全绕过槽位机制** —— 成功则把封面 URL **前插**到简介：`temp = self.descriptionBrowserPlaylet.toPlainText(); self.descriptionBrowserPlaylet.setText(f'{picture_url}\n{temp}')` + debug `'成功将封面链接粘贴到简介前'`；失败 debug `f'图床响应无效：{api_response}'`。**两条分支都立即 `return`，不碰 `_upload_slots`。** 另外 `:1675` 会 `print(f'is_cover: {is_cover}')`。

#### 4.3.1 截图与缩略图生成（三份 `get_picture_button_*_clicked`）

共同序列：

1. `pictureUrlBrowser*.setText('')` → `check_path_and_find_video(videoPath*.text().replace('file:///', ''))`；
2. 从设置读 9 个参数：`screenshot_storage_path` / `screenshot_number`(int) / `screenshot_threshold`(float) / `screenshot_start_percentage`(float) / `screenshot_end_percentage`(float) / `do_get_thumbnail`(bool) / `thumbnail_rows`(int) / `thumbnail_cols`(int) / `auto_upload_screenshot`(bool)；
3. `pictures = []`；`get_screenshot(video_path, screenshot_storage_path, screenshot_number, screenshot_threshold, screenshot_start_percentage, screenshot_end_percentage, screenshot_min_interval=0.01)` —— **`screenshot_min_interval` 传的是硬编码 `0.01`，不读设置**（三处一致：`:383-385` / `:1043-1045` / `:1633-1635`）；
4. `do_get_thumbnail` 为真则 `get_thumbnail(...)`，**成功才 `pictures.append(thumbnail_path)`**（缩略图放末尾）；
5. `screenshot_success` 为真 → `pictures = response + pictures`（截图在前、缩略图在后）；
6. `auto_upload_screenshot and len(pictures) > 0` → `_upload_pictures(...)`；否则把本地路径逐行拼进 `pictureUrlBrowser*`。

**三处参数获取顺序不一致**（测试若用「读设置的调用序列」断言会误判）：电影版在 `check_path_and_find_video` 成功后立刻读全部设置（`:371-379`）；剧集版相同（`:1031-1039`）；**短剧版把 `picture_bed_api_url` / `picture_bed_api_token` 提前到 `:1620-1621` 读**（其余两页签在上传分支里才读，`:401-402` / `:1061-1062`）。

**两处复制粘贴 bug（写测试时按现状断言）：**

- `get_picture_button_playlet_clicked` 的「不上传」分支（`:1665`）写的是 **`self.pictureUrlBrowserMovie.setText(screenshot_path)`** —— 短剧页签把本地截图路径**写进了电影页签的浏览框**，短剧自己的 `pictureUrlBrowserPlaylet` 保持为空字符串。
- 剧集版 `check_path_and_find_video` 的返回值解包成 `(is_video_path, video_path)`（`:1026`），失败分支只写 debug `'您的视频文件路径有误'`（`:1081`，**不带 `{response}`**）；电影/短剧失败分支写 `f'您的视频文件路径有误：{response}'`。截图失败文案也不统一：电影 `f'截图失败：{response[0]}'`（`:419`，带中文冒号）、剧集 `f'截图失败{response[0]}'`（`:1079`，无冒号）、短剧同剧集（`:1667`）。

### 4.4 制作种子与封面上传

#### 4.4.1 制作种子（三份 `make_torrent_button_*_clicked`）

| 页签 | 行 | 传给 `MakeTorrentThread` 的 path | `folder_path` |
|---|---|---|---|
| 电影 | `:833-845` | `path`（路径框原文，**单文件时就是文件本身**） | — |
| 剧集 | `:1500-1514` | **`folder_path = os.path.dirname(video_path)`** | 有 |
| 短剧 | `:1962-1976` | **`os.path.dirname(video_path)`** | 有 |

三者共同：先 `self.torrent_url = ''`（清空旧链接）→ `check_path_and_find_video`（要求 1 或 2）→ 读 `torrent_storage_path` 并 `str()` → `MakeTorrentThread(...)` → 连 `result_signal` 到各自的 handler → `start()` → debug `'制作种子线程启动成功，正在后台制作种子，请耐心等待种子制作完毕...'`。失败 → debug `f'制作种子失败：{response}'`。

三个 handler（电影 `:847-853`、剧集 `:1516-1522`、短剧 `:1978-1984`，签名均 `(get_success, response)`）：成功时统一构造

```python
self.torrent_url = f'http://127.0.0.1:{get_settings("api_port")}/api/getFile?filePath={torrent_path}'
```

—— **`torrent_path` 未做 URL 编码**（Windows 路径含空格/中文时会组成非法 URL），且 debug 文案 `f'成功制作种子：{torrent_path}'`。失败 debug `f'制作种子失败：{response}'`。

#### 4.4.2 上传封面（Playlet 专属，`:1596-1609`）

`coverPathPlaylet.text()` 非空 → debug `f'上传封面：{cover_path}'` → 读 `picture_bed_api_url` / `picture_bed_api_token` → **`UploadPictureThread(picture_bed_path, picture_bed_token, cover_path, True, False)`**（`is_cover=True, is_thumbnail=False`，**不传 `index`，走默认 0**）→ 连 `handle_upload_picture_playlet_result` → `start()`。路径为空则 debug `'封面路径为空'`。封面成功后前插简介的行为见 §4.3 的 Playlet handler 说明。

### 4.5 一键启动编排

#### 4.5.1 Movie（`:195-221`）

```python
def start_button_movie_clicked(self):
    self.get_name_button_movie_clicked()
    print(f'重命名启动成功')
    self.wait_for_rename_thread = WaitForRenameThread(True)
    self.wait_for_rename_thread.result_signal.connect(self.handle_process_after_rename_movie)
    self.wait_for_rename_thread.start()
    print('重命名启动成功，等待重命名完成后将自动进行其他操作...')
    self.debugBrowserMovie.append('重命名启动成功，等待重命名完成后将自动进行其他操作...')
```

- 先同步调 `get_name_button_movie_clicked()`（只**发起**两个 PT-Gen 线程，立刻返回）；
- 再启 `WaitForRenameThread(True)`，靠**模块全局变量轮询**等重命名收尾（不是靠信号串联）；
- `handle_process_after_rename_movie(self, rename_success)`（`:205-221`）：`rename_success` 为真 → debug `'重命名成功，开始进行后续操作'` → `videoPathMovie.setText(self.path_movie)` → `QApplication.processEvents()` → `get_media_info_button_movie_clicked()` → `processEvents()` → `get_picture_button_movie_clicked()` → `processEvents()` → `make_torrent_button_movie_clicked()` → `processEvents()`。**顺序是 MediaInfo → 截图 → 种子**（注意截图在 MediaInfo 之后）。为假 → `print`/debug `'重命名失败，一键启动已终止'` + **`show_toast(self, '重命名失败，一键启动已终止', 'error', 6000)`**（`src/gui/ui/toast.py:189`）。

#### 4.5.2 TV（`:858-884`）

与 Movie 逐行同构，差异只有三处：`WaitForRenameThread(False)`、连 `handle_process_after_rename_tv`、全部写 `debugBrowserTV`。`handle_process_after_rename_tv`（`:867-884`）在成功分支里**多一行 `print('当前的视频地址' + self.path_tv)`**（`:873`），且用 `videoPathTV.setText(self.path_tv)`。

#### 4.5.3 Playlet（`:1527-1544`）—— 串行，且首行是硬编码早退守卫

```python
def start_button_playlet_clicked(self):
    if get_settings('second_confirm_file_name'):
        self.debugBrowserMovie.append('如需一键启动，请到设置关闭二次确认文件名功能')
        return
    self.get_name_button_playlet_clicked()
    QApplication.processEvents()
    time.sleep(0)          # 注释写「等待 0 毫秒」
    self.get_picture_button_playlet_clicked()
    QApplication.processEvents()
    time.sleep(0)          # 注释写「等待 2000 毫秒」——注释与代码不符
    self.upload_cover_button_playlet_clicked()
    QApplication.processEvents()
    time.sleep(2)
    self.get_media_info_button_playlet_clicked()
    QApplication.processEvents()
    time.sleep(2)
    self.make_torrent_button_playlet_clicked()
    QApplication.processEvents()
```

与 Movie/TV 的三点本质差异：

1. **首行是读写设置的真实守卫，不是「前置条件」的抽象描述**：`second_confirm_file_name` 为真 → **写 `debugBrowserMovie`（写错页签！）** + 直接 `return`（`:1528-1530`）。Movie/TV 的一键启动**没有这个守卫**（它们的二次确认由 `get_name` 内部的 `QInputDialog` 弹窗处理）。
2. **不用 `WaitForRenameThread`**，靠 `time.sleep(0)`/`sleep(2)` 硬等。**精确串联序列是 `get_name → processEvents → sleep(0) → get_picture → processEvents → sleep(0) → upload_cover → processEvents → sleep(2) → get_media_info → processEvents → sleep(2) → make_torrent → processEvents`** —— 前两处是 `sleep(0)`（`:1533` / `:1536`），**不是 `sleep(2)`**。
3. `get_name_button_playlet_clicked` 内部是**同步阻塞**完成的（不含线程等待），所以「等 0 秒」在语义上够用；`sleep(2)` 是给截图/封面上传的异步线程留时间。**这意味着 Playlet 的一键启动在重命名耗时较长时并不可靠**，但测试应断言现状。
4. 电影页签的 debug 框在 Playlet 流程里被写入两次（`:1529` 守卫 + 无其他）。

### 4.6 海报自动处理（两份近重复实现）

| | 电影/剧集共用 | 剧集专属 |
|---|---|---|
| 方法 | `_process_poster_in_description(self, description)` `:305-361` | `_process_poster_in_description_tv(self, description)` `:965-1021` |
| 调用方 | `handle_get_pt_gen_movie_result` `:296`、`handle_get_pt_gen_for_name_movie_result` `:559`、**以及 TV 的 `handle_get_pt_gen_for_name_tv_result` `:1196`** | `handle_get_pt_gen_tv_result` `:956` |
| debug 框 | `debugBrowserMovie` | `debugBrowserTV` |

> **这是三份复制粘贴里最隐蔽的一处**：TV 页签有**两个**获取简介的回调，其中一个（重命名流水线用的 `handle_get_pt_gen_for_name_tv_result`）调的是**电影版的** `_process_poster_in_description`，debug 会写进电影页签的框；只有「获取简介按钮」走的 `handle_get_pt_gen_tv_result` 才调 TV 版。测试若要断言 debug 框，必须区分是哪个回调。

两版逻辑完全一致（`:305-361` 与 `:965-1021` 逐行可比）：

1. `auto_download_upload_poster = bool(get_settings('auto_download_upload_poster'))`，为假**立即 `return description`**；
2. `img_pattern = r'\[img\](https?://[^\]]+)\[/img\]'`，`re.search` 取**首个**匹配；不匹配则 `print('No [img] tag found in description')` 并 `return description`；
3. `original_poster_url = match.group(1)`（**不再校验是否已被替换过，重复调用会用首次的原始 URL 再传一遍**），debug `f'检测到海报链接：{original_poster_url}'`；
4. 函数内 `from src.core.poster import process_poster` 局部导入（**不是模块顶层导入**，便于 mock 到 `src.core.poster.process_poster`）；
5. 读 `picture_bed_api_url` / `picture_bed_api_token` / `screenshot_storage_path`，debug `'开始下载并上传海报...'`；
6. `success, result = process_poster(original_poster_url, picture_bed_api_url, picture_bed_api_token, screenshot_storage_path)`（签名 `src/core/poster.py:110-115`，第 4 参数是 `temp_dir`）；
7. 成功 → `description.replace(f'[img]{original_poster_url}[/img]', f'[img]{uploaded_url}[/img]')` + debug `'已替换简介中的海报链接'`；失败 → debug `f'海报上传失败：{result}'`；
8. **整个函数体在 `try/except Exception` 内**，异常 → `print(f'Error processing poster: {e}')` + debug `f'处理海报时出错：{e}'`；
9. **函数末尾必 `return description`**（无论成功失败，都返回可能已被替换的文本）。

### 4.7 `settings` 对话框（`:2029-2173`）

| 项 | 行 | 说明 |
|---|---|---|
| 类定义 | `:2029` | `class settings(QDialog, Ui_Settings)`，`from src.gui.ui.settings import Ui_Settings` |
| `__init__` | `:2030-2038` | `setupUi` + 连 4 个槽：`saveButton→saveButtonClicked`、`cancelButton→cancelButtonClicked`、`selectScreenshotPathButton→selectScreenshotPathButtonClicked`、`selectTorrentPathButton→selectTorrentPathButtonClicked` |
| `saveButtonClicked` | `:2040-2042` | `updateSettings()` 然后 `close()`（**无校验、无确认**） |
| `cancelButtonClicked` | `:2044-2045` | 仅 `close()` |
| `selectScreenshotPathButtonClicked` | `:2047-2050` | `get_folder_path()`，**非空才 `setText`**（与主窗口的选路径按钮不同，这里做了空值保护） |
| `selectTorrentPathButtonClicked` | `:2052-2055` | 同上，写 `torrentStoragePath` |
| `getSettings` | `:2057-2095` | 把 **38 个设置键**回填到控件。`int(...)` / `float(...)` / `bool(...)` 强制转换；`str(...)` 包裹路径 |
| `updateSettings` | `:2097-2173` | 把控件值写回 **38 个键**（`update_settings` 调用共 50 次、去重后 38 个键，与 `static/settings.json` 的 38 键完全对应） |

**`updateSettings` 的三个可测细节：**

1. **布尔键写法是「真写 `'True'`，假写 `''`」**（不是 `'False'`）——12 个复选框一律 `if checked: update_settings(k, 'True') else: update_settings(k, '')`（`:2111-2173`）。这与 `settings_tool.py` 的 `_BOOL_KEYS` 归一逻辑（`'True'`→True、`''`→False）配套，测试断言 settings.json 落盘值时按此断言。
2. **三个 QDoubleSpinBox 有 macOS 逗号小数点兼容处理**：`str(self.screenshotThreshold.text()).replace(',', '.')`（`:2108` / `:2109` / `:2110`），`thumbnail_delay` 同样（`:2118`）。其余数值控件（如 `screenshot_number`）直接 `str(...)`，无替换。
3. **`auto_feed_link` 用 `.toPlainText()`**（`:2169`，多行控件），其余单行控件用 `.text()`；`apiPort` 用 `self.apiPort.text()`（`:2159`）。

**未覆盖项**：`settings` 类没有 `closeEvent` 覆写，取消不会回滚已写入的值（`updateSettings` 只在保存按钮触发，所以取消是安全的，但窗口 `X` 关闭同理）。

### 4.8 关键模块全局与实例状态

#### 4.8.1 模块级全局（`:32-35`）

| 变量 | 初值 | 读写方 |
|---|---|---|
| `get_name_movie_success` | `False` | `get_name_button_movie_clicked` 重置、`handle_get_pt_gen_for_name_movie_result` 置 `True`、`WaitForRenameThread.run` 轮询 |
| `get_name_movie_failure_number` | `0` | 同上 + 流水线各失败点 `+= 1` |
| `get_name_tv_success` / `get_name_tv_failure_number` | `False` / `0` | 剧集版三个函数 |

**这四个是 GUI 唯一的模块级可变状态**（`git_clicked` 之外）。它们用 `global` 声明在**四个不同函数**里（`:502` / `:542` / `:2289` / `:2302`），测试要 `monkeypatch` 必须打到 `src.gui.startgui.<name>` 上，而不是某个实例属性。

#### 4.8.2 `mainwindow.__init__` 建立的实例状态（`:55-94`）

| 属性 | 初值 | 位置 | 用途 |
|---|---|---|---|
| `my_settings` | `None` | `:55` | 当前设置对话框实例 |
| `get_pt_gen_success` | `False` | `:59` | 简介「首胜」标志，主/备 PT-Gen 线程去重用。**六个 PT-Gen 回调共享同一个标志**（电影简介、剧集简介、电影重命名、剧集重命名）—— 存在跨页签串扰（先用电影页获取简介，再点剧集页的获取，剧集结果会被当作「已成功」丢弃） |
| `path_movie` | `""` | `:60` | 电影重命名后的资源路径，供 `handle_process_after_rename_movie` 回填 |
| `path_tv` | `""` | `:61` | 同上，剧集 |
| `get_pt_gen_thread` | `None` | `:64` | 主 PT-Gen 线程（简介按钮用） |
| `get_pt_gen_backup_thread` | `None` | `:65` | 备用 PT-Gen 线程（简介按钮用） |
| `get_pt_gen_for_name_thread` | `None` | `:66` | 主 PT-Gen 线程（重命名流水线用） |
| `get_pt_gen_for_name_backup_thread` | `None` | `:67` | 备用 PT-Gen 线程（重命名流水线用） |
| `upload_picture_thread0..5` | `None` ×6 | `:68-73` | **僵尸变量，只赋值 `None`，全文件再无读写**（已被 `_upload_pictures` 取代） |
| `upload_cover_thread` | `None` | `:74` | 封面上传线程（短剧） |
| `make_torrent_thread` | `None` | `:75` | 制种线程（**三页签共用一个属性，后启动的覆盖前一个的引用**） |
| `api_thread` | `None` | `:76` | API 线程 |
| `wait_for_rename_thread` | `None` | `:77` | 一键启动的等待线程（**电影/剧集共用，同上覆盖**） |
| `_upload_slots` | `{}` | `:80` | index → 上传成功后的 URL |
| `_slots_to_path` | `{}` | `:81` | index → 本地图片路径 |
| `_upload_total` | `0` | `:82` | 本次上传总张数 |
| `torrent_url` | `''` | `:94` | 最近制作的种子 URL，`auto_feed` 用 |

> **`torrent_url` 是三页签共用的单值**（三个 `make_torrent_button_*` 都先置 `''` 再在 handler 里写），切页签后互相覆盖 —— 测试若要验证 `auto_feed` 拿到的 URL，须在同一页签内先制种再点 auto_feed。

#### 4.8.3 线程类清单（构造签名 + 信号签名，逐条核实）

**这份表与旧文档 §4.6 冲突的地方：旧文档把「信号签名」误写成「构造签名」**。以下是源码事实：

| 类 | 行 | **构造签名** | **信号签名** | `run()` 行为 |
|---|---|---|---|---|
| `GetPtGenThread` | `:2179` | `__init__(self, api_url, resource_url)` `:2184` | `pyqtSignal(bool, str, str)` `:2182` | `(self.api_url or '').strip()` 为空 → `print('未配置PT-Gen接口，跳过该线程')` 并**直接 return（不发信号！）**；否则 `get_pt_gen_description(api_url, resource_url)`，成功时 `response` 是 `(format_data, full_data)` 嵌套元组，把 `full_data` `json.dumps(..., ensure_ascii=False)` 成 `raw_data_json` 后 `emit(True, format_data, raw_data_json)`；`dumps` 抛异常则 `raw_data_json = ''`。失败 `emit(False, response, '')`。**整个 run 的 `except Exception` 只 `print`，不发信号** |
| `UploadPictureThread` | `:2219` | `__init__(self, picture_bed_api_path, picture_bed_api_token, picture_path, is_cover, is_thumbnail, index=0)` `:2224` | `pyqtSignal(bool, str, str, bool, bool, int)` `:2222` | `is_thumbnail` 为真先 `time.sleep(float(get_settings('thumbnail_delay')))`；然后 `upload_picture(path, token, picture_path)`；`emit(success, response, self.picture_path, self.is_cover, self.is_thumbnail, self.index)`。**`except` 分支会 `emit(False, f'异常发生：{e}', ...)`（与本文件其它线程不同，这里异常也会发信号）** |
| `MakeTorrentThread` | `:2254` | `__init__(self, path, torrent_storage_path)` `:2258` | `pyqtSignal(bool, str)` `:2256` | `make_torrent(path, torrent_storage_path)` → `emit(success, response)`；`except` **只 print 不发信号**（意味着制种线程崩了 GUI 会永远等不到结果） |
| `WaitForRenameThread` | `:2277` | `__init__(self, is_movie)` `:2281` | `pyqtSignal(bool)` `:2279` | 见 §4.5 与下方说明 |
| `apiThread` | `:2319` | **`__init__(self)` 无参** `:2323` | `pyqtSignal(str)` `:2321` | `start_api()`（**阻塞**，Flask 起服务）→ 返回后 `emit('API线程终止')`；`except` → `emit(f'异常发生：{e}')` |

**`WaitForRenameThread.run` 的真实语义**（`:2285-2316`）：

```python
if self.is_movie:
    global get_name_movie_success, get_name_movie_failure_number
    wait_time = 0
    while get_name_movie_success is False and get_name_movie_failure_number <= 1 and wait_time <= 60:
        print('重命名尚未完成，等待0.5s')
        time.sleep(0.5)
        wait_time += 0.5
    print('等待重命名结束，开始返回结果')
    self.result_signal.emit(get_name_movie_success)
```

- 轮询条件是 `success is False and failure_number <= 1 and wait_time <= 60`，**每 0.5s 一次**（旧文档此处写对了）；
- **但真实语义要写清楚：这是兜底而非单纯超时。** 三个条件里 `failure_number <= 1` 才是主退出路径 —— 流水线一旦任一步失败，计数 +1（`WaitForRenameThread` 自己的 `<=1` 容忍一次），下一次轮询即退出，**且退出时 `emit` 的是当时的 `success` 值（False）**。若流水线长时间无响应（例如卡在 `QInputDialog` 模态框上），才靠 `wait_time <= 60` 兜底 —— **约 60.0~60.5s 后不论成败都会退出并 `emit` 当前 `success`**。也就是说「超时」和「成功」在这里走的是同一条 `emit`，调用方**无法区分「成功」与「超时但 success 恰好为 True」**（后者不可能，因为 success 只有流水线末尾才置 True；但「超时且 success 为 False」与「失败且 success 为 False」无法区分）。
- `is_movie` 为假时走 `else` 分支，逻辑逐行相同，只是换 TV 两个全局。
- **外层 `except Exception` 只 `print`，不发信号**（`:2314-2316`）—— 若 `emit` 本身抛异常（例如信号参数类型不符），GUI 侧永远等不到结果。
- `is_movie` 是普通属性，无校验 —— `WaitForRenameThread(0)` 与 `WaitForRenameThread(False)` 等价，`WaitForRenameThread('')` 也走 else 分支。

### 4.9 测试要点

#### 4.9.1 可测性分层

| 层 | 能不能脱离 Qt | 说明 |
|---|---|---|
| 模块级函数 `git_clicked()` | 可以 | 只需 `monkeypatch.setattr(startgui.webbrowser, 'open', ...)` |
| 线程类（5 个） | **可以完全不建 `QApplication`** | `QThread` 子类**实例化**需要 QCoreApplication 存在吗？不需要 —— `QThread()` 构造在无 `QApplication` 时可用，但 `pyqtSignal` 的 `emit` 在无事件循环时仅是同步调用已连接的槽（PyQt 直连）。**最稳的做法是 `monkeypatch.setattr(thread, 'result_signal', FakeSignal())` 或直接 `monkeypatch` 掉 `start()`**，只测 `run()` |
| `run()` 各方法 | 可以 | `GetPtGenThread.run` / `UploadPictureThread.run` / `MakeTorrentThread.run` / `WaitForRenameThread.run` 都是**纯同步过程**，直接 `obj.run()` 即可（不 `start()`），网络/文件操作 mock 到 `src.gui.startgui.<函数名>` 上（注意是 `startgui` 命名空间里那个名字，因为这些是模块顶层 `from ... import`） |
| `mainwindow` 的槽函数 | **需要 offscreen** | `self.setupUi(self)` 会创建全部控件；`QTextEdit.setText` 等在无 QApplication 时抛 `RuntimeError: wrapped C/C++ object of type ... has been deleted` 或直接崩。建议 `pytest` 里设 `QT_QPA_PLATFORM=offscreen`（`os.environ.setdefault` 必须在 `import PyQt6` **之前**），再用 session 级 `QApplication` fixture |
| `ui_tools` 三函数 | **需要 mock `filedialog`** | 直接 `monkeypatch.setattr('src.gui.ui_tools.filedialog', FakeDialog)`。`get_folder_path` 会建 `Tk()`，离屏环境**不可用**，必须整体 mock 掉 `Tk` |
| `settings` 对话框 | 需要 offscreen | 同 `mainwindow` |

#### 4.9.2 免 Qt 断言的具体清单

1. **`WaitForRenameThread.run` 直接调用**：`monkeypatch.setattr(startgui, 'get_name_movie_success', True)` 后 `WaitForRenameThread(True).run()` —— 循环体一次都不进（`success is True` 使第一个条件为假），只走一次 `emit`。要测轮询退出，用 `monkeypatch.setattr(startgui, 'get_name_movie_failure_number', 2)`（>1）同样零循环退出；要测**超时兜底**，把 `wait_time` 无法直接注入，需 `monkeypatch.setattr(startgui.time, 'sleep', lambda s: None)` 让 0.5s 变瞬时、再把 `wait_time` 增长逻辑跑到 60 —— 更简的做法是断言「三个条件都为真时零次循环、任一为假时进入循环」，用 `mock.patch('src.gui.startgui.time.sleep')` 记录调用次数（预期 0 或 1 次）。
2. **`GetPtGenThread.run` 空 URL 短路**：`GetPtGenThread('', 'http://x').run()` 应打印跳过且**不发信号**——用 FakeSignal 断言 `emit` 零调用。`GetPtGenThread('  ', ...)` 同样（`.strip()`）。
3. **`GetPtGenThread.run` 成功路径**：mock `src.gui.startgui.get_pt_gen_description` 返回 `(True, ({'a': 1}, {'raw': '数据'}))`，断言 `emit(True, {'a': 1}, '{"raw": "数据"}')`（`ensure_ascii=False`，中文不转义）。
4. **`UploadPictureThread.run` 缩略图延迟**：`is_thumbnail=True` 时断言 `time.sleep` 被以 `float(get_settings('thumbnail_delay'))` 调用；`is_thumbnail=False` 时零调用。异常分支断言 `emit(False, '异常发生：...', path, is_cover, is_thumbnail, index)` —— 参数顺序即信号签名顺序。
5. **`MakeTorrentThread.run` 异常不发信号**：mock `make_torrent` 抛异常，断言 FakeSignal 的 emit 零调用（与 `UploadPictureThread` 行为相反的对照点）。
6. **`apiThread.run`**：mock `src.gui.startgui.start_api`，断言正常返回时 `emit('API线程终止')`、抛异常时 `emit(f'异常发生：{e}')`。
7. **`git_clicked`**：断言 URL 常量。

#### 4.9.3 `_upload_pictures` 乱序回填的断言方式

这是 GUI 里最值得单测的一段（无 Qt 依赖之外的状态，只需一个够用的假 self）。**推荐在 offscreen 下的 `mainwindow` 实例上测**，或构造一个只带必要属性的 `types.SimpleNamespace`：

```python
mw = SimpleNamespace(_upload_slots={}, _slots_to_path={}, _upload_total=0,
                     pictureUrlBrowserMovie=..., ...)
mainwindow._upload_pictures(mw, ['a.png', 'b.png', 'c.png'], 'url', 'tok', True, handler)
```

断言点：

| 断言 | 期望 |
|---|---|
| 启动的线程数 | 3（用 `monkeypatch.setattr(startgui, 'UploadPictureThread', FakeThread)` 收集构造入参） |
| 每个线程的 `index` | 依次 `0, 1, 2`（`enumerate` 顺序，与 `pictures` 下标一致） |
| `is_thumbnail` 标志 | `False, False, True`（`do_get_thumbnail=True` 且最后一个）；`_upload_pictures(..., do_get_thumbnail=False, ...)` 时全 `False` |
| `is_cover` | 恒 `False`（含缩略图那次） |
| `_slots_to_path` | `{0:'a.png', 1:'b.png', 2:'c.png'}`，在启动线程**之前**就已填好 |
| `_upload_total` | `3` |
| FakeThread 收到的路径参数 | 依次 `'a.png','b.png','c.png'`（`picture_bed_api_path`/`token` 在前） |

**乱序回填**：在 offscreen 实例上，**手工乱序调用 handler**，而不是让真线程跑：

```python
h = mw.handle_upload_picture_movie_result
h(False, 'bad', 'b.png', False, False, 1)   # 先到的是 index 1（失败）
assert mw._upload_slots == {1: ''}          # 尚未满，不写 UI
assert mw.pictureUrlBrowserMovie.toPlainText() == ''
h(True, 'url-c', 'c.png', False, True, 2)   # 再到 index 2
assert mw.pictureUrlBrowserMovie.toPlainText() == ''   # 仍差 index 0
h(True, 'url-a', 'a.png', False, False, 0)  # 最后到 index 0，触发回填
assert mw.pictureUrlBrowserMovie.toPlainText() == 'url-a\nurl-c'   # 按序，空串被过滤
assert mw._upload_slots == {} and mw._slots_to_path == {}          # 已清空
```

关键断言清单：

- **回填顺序按 index 升序**，与到达顺序无关 —— 用 `'url-a\nurl-c'` 这类可区分字符串断言换行顺序；
- **失败项被过滤掉**（`if self._upload_slots.get(i)`），且**不影响后续槽位的顺序**（不是「失败就整体失败」）；
- **`len(_upload_slots) < _upload_total` 之前绝不写 UI**（断言浏览框内容为空串）；
- `paste_screenshot_url` 为真时断言 `descriptionBrowserMovie.toPlainText()` 同样是有序换行串；Playlet 版是 `append`（在已有文本后追加换行），需先给简介框塞初值再断言**前缀保留**；
- `delete_screenshot` 为真时用 `tmp_path` 造真文件，断言全部被删 + debug 框有 `f'文件"{p}"已被删除'`；
- **`_upload_slots` 复用同一 dict**：`_upload_pictures` 里是**重新赋值新 dict**（`= {}`）而非 `.clear()`，若测试持有旧引用会看到旧数据，断言要重新取 `mw._upload_slots`；
- Playlet 的 `is_cover=True` 分支：断言 `_upload_slots` **完全未被触碰**、简介框是 `f'{url}\n{原文本}'`（前插）。

#### 4.9.4 offscreen 下的槽函数测试

- fixture：`os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')` **在 import PyQt6 前**执行；`QApplication` 用 `qapp` fixture 单例；`mainwindow()` 构造需要 `static/` 可读（`git_clicked`/`setWindowIcon` 路径是 cwd 相对的，且 `__init__` 会连 `initialize_*_combobox` → `get_combo_box_data`，**必须把 cwd 切到仓库根或 patch `STATIC_DIR`**）。
- `__init__` 的 `enable_api` 分支会真的 `start_api()` 起 Flask：**patch `src.gui.startgui.apiThread`** 或 patch `get_settings` 让它返回假，否则测试会挂。
- 被 patch 的模块名要精确：`startgui` 用 `from src.core.text import chinese_name_to_pinyin` 这类**顶层导入**，所以 patch 目标是 `src.gui.startgui.chinese_name_to_pinyin`；而 `process_poster`（`_process_poster_in_description` 内局部导入）和 `_json`（`run()` 内局部导入）应 patch 到**原始模块** `src.core.poster.process_poster`。
- 会弹模态框的路径（`QMessageBox.*`、`QInputDialog.getText`）在 offscreen 下**会阻塞**，测试必须先 patch 成返回固定值（例如 `QMessageBox.StandardButton.Yes`）。这是覆盖 `get_name` 流水线的主要障碍。
- `QApplication.processEvents()` 在无事件循环时可安全调用（no-op），不必 patch。

#### 4.9.5 建议首批断言点（按性价比排序）

1. `_upload_pictures` 的线程参数与 `is_thumbnail` 计算（**零 UI 依赖，只查构造入参**）；
2. 三个 handler 的乱序回填 + 失败过滤 + 清空（offscreen，但只需 3 个假信号）；
3. `WaitForRenameThread.run` 的轮询退出三条件与「均满足时零循环」（纯逻辑）；
4. `GetPtGenThread.run` 的空 URL 短路（**不发信号**）与 `ensure_ascii=False` 序列化；
5. `UploadPictureThread.run` 的缩略图延迟与异常也发信号（与 `MakeTorrentThread` 的对照）；
6. `get_categories()` 的 16 个复选框顺序与 `' / '` 拼接、空选返回 `''`；
7. `_process_poster_in_description` 的 `auto_download_upload_poster` 关闭时**原样返回**、无 `[img]` 时原样返回、替换成功时的文本；
8. `settings.updateSettings` 的布尔键 `'True'`/`''` 写法与小数点逗号替换；
9. `ui_tools` 三函数的 mock-`filedialog` 返回值透传；
10. **跨页签 bug 的回归锁定**：`get_picture_button_playlet_clicked` 不上传分支写的是 `pictureUrlBrowserMovie`（`:1665`）、`get_name_button_playlet_clicked` 读 `episodesStartBoxTV`（`:1794`）、`actionsettings.triggered` 被连接两次（`:98` / `:111`）、`_upload_total` 语义。这四条最容易被「顺手修好」而让测试失效，建议在断言旁写明是现状锁定。

---

## 5. API 接口清单（`src/api/startapi.py`，2517 行）

> 本章面向写 API 测试的人。所有断言点均已对照源码逐条核实，关键处标注 `src/api/startapi.py:行号`。
> **三句话总纲**：① 有统一包络的「设计」，但没有统一包络的「实现」——26 个路由**零**调用 `_ok`，149 处手写 `jsonify`（其中 147 处手写 `statusCode` 字面量）；② 用错 HTTP 方法时 Flask 直接吐 HTML 405，**不套包络**；③ 所有「media 根域隔离」都因 `join` 后 `abspath` 恒非空而**退化成 CWD 逃逸检查**（见 5.3-S1）。

---

### 5.1 响应封装约定：设计意图 vs 现状

#### 5.1.1 包络形状（意图）

设计上每个响应体是 `{data, message, statusCode}`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data` | dict | 业务数据；**永远以 `or {}` 兜底**，故传 `None`/`{}`/`''` 一律变 `{}` |
| `message` | str | 中文人类可读文案（1 处例外，见 5.3-S6） |
| `statusCode` | str | **JSON 体内的字符串**，与 HTTP 状态码是两个独立维度 |

**两个 helper（`src/api/startapi.py:57`、`:62`）**：

```python
def _ok(data=None, message='成功', status_code='OK', http_status=200)      # L57
def _error(status_code, message, http_status=400, data=None, exc=None)    # L62
```

- `_ok` 有 4 个参数（`data/message/status_code/http_status`）；
- `_error` 有 **5 个参数**，注意第 4 个是 **`data=None`**、第 5 个是 `exc=None`（旧文档漏了 `data`）。`exc` 只写服务端日志（`logger.error(..., exc_info=exc)`），不外泄给客户端。

#### 5.1.2 现状：统一封装是死代码

| 事实 | 数字 | 复核方式 |
|---|---|---|
| 路由总数 | 26（另有 Flask 隐式 `/static/<path:filename>`，见下） | `grep -c "@api.route"` |
| 调用 `_ok` 的路由 | **0** | 全文件 `_ok(` 仅命中其定义行 `:57` |
| 调用 `_error` 的位置 | **1**（仅鉴权失败 `:47`） | `_error(` 仅命中 `:47` 与定义行 `:62` |
| 手写 `jsonify(...)` | **147 处响应体 + 2 处 helper = 149** | `grep -c "jsonify("` = 149 |
| 直接构造 `'statusCode': '...'` 字面量 | **147** | `grep -c "'statusCode': '"` = 147 |

**测试含义**：不要为了「走 helper」而 mock `_ok`/`_error`；直接断言响应体的三个键。`data` 的键名**每个路由都不一样**（见 5.2 逐路由表），没有统一 schema。

#### 5.1.3 `_payload()`：参数读取（`src/api/startapi.py:75`）

优先级 **JSON body（dict）→ form → URL query**，返回 werkzeug `ImmutableMultiDict`，因此各端点保留了 `request.args.get(key, default, type=str)` 式的 `.get(key, default=D, type=str)` 调用（`ImmutableMultiDict.get` 支持 `type=`）。

四个已知缺陷（写测试必须知道，否则会误判分支）：

| # | 缺陷 | 后果 | 行号 |
|---|---|---|---|
| P-a | JSON dict 优先于 form | **所有 POST 路由在以 form 提交、且同时带可解析 JSON body 时读不到 form**；`request.form` 分支实际是死代码（唯一能走到它的场景是 body 非 dict 且非空 form） | `:83-89` |
| P-b | JSON 的**嵌套/非字符串值被 `str()` 强转** | `{"template":{"a":1}}` → `"{'a': 1}"` 字符串，**命中 `PARAMETER_RANGE_ERROR`（模板不在白名单）而非缺参 422**；`{"season": 1}` → `"1"`（无害） | `:85` |
| P-c | 非 dict 的合法 JSON（数组/数字）**回退**到 form/args | `json=[1,2]` + 空 form/args → 缺参 422（`isinstance(data, dict)` 为假） | `:84` |
| P-d | `request.get_json` 不看方法 | **GET 带 JSON body 完全可行**（`c.get(url, json={...})` 能喂进参数），`methods` 声明只约束 Flask 的方法路由 | `:83` |

**实测佐证**（`api.test_client()`，下同）：

```
GET /api/getNameFromTemplate  json={"template":{"a":1}}      => 422 PARAMETER_RANGE_ERROR   # P-b
GET /api/getNameFromTemplate  json=[1,2]                     => 422 MISSING_REQUIRED_PARAMETER # P-c
```

- **`/api/settings/update` 是唯一不走 `_payload()` 的路由**：直接读 `request.json`（`src/api/startapi.py:1806`），`content-type` 非 JSON 时 `request.json` 抛 400-class 异常 → 被 `except` 兜成 **500**（实测：`POST /api/settings/update` 无 body → 500 `GENERAL_ERROR`）。

#### 5.1.4 鉴权与 CORS：来源、时机、大小写

```python
AUTH_TOKEN    = os.getenv('API_AUTH_TOKEN', '').strip()          # L32
_CORS_ORIGINS = os.getenv('API_CORS_ORIGINS', '*').strip() or '*' # L34
CORS(api, origins=_CORS_ORIGINS.split(',') if _CORS_ORIGINS != '*' else '*')  # L35
```

| 项 | 事实 | 行号 |
|---|---|---|
| 配置来源 | **环境变量**，不是 `static/settings.json`（区别于全项目其它配置） | `:32`、`:34` |
| 读取时机 | **模块 import 时读一次**；运行中改 `os.environ` 无效（要改得 reload 模块或重启） | `:32-35` |
| 鉴权开关 | `AUTH_TOKEN` 为空串（含仅空白，`.strip()` 后为空）→ **全端点放行**；非空 → 启用 | `:41-42` |
| 鉴权机制 | `@api.before_request` → **作用于全端点，含 `/static/<path:filename>`** | `:38-48` |
| token 前缀 | 只认**大写** `Bearer `（`auth.startswith('Bearer ')`），随后 `auth[7:]`；**裸 token、小写 `bearer` 一律 401** | `:44` |
| token 比较 | `token != AUTH_TOKEN` **明文 `!=`，非常量时间比较** | `:45` |
| 鉴权失败响应 | `_error('UNAUTHORIZED', '未授权或凭据无效。', 401)`——**`statusCode` 是 `UNAUTHORIZED`，与路由级越域的 `UNAUTHORIZED_ACCESS_ERROR` 不同名** | `:47` |
| CORS 白名单 | 逗号 `split(',')`，**未 `strip` 各项**；`API_CORS_ORIGINS='http://a, http://b'` 中第二项带前导空格，与真实 `Origin` 头不匹配 → 该源**拿不到 ACAO** | `:34-35` |

实测（子进程注入 env，`API_AUTH_TOKEN=secret123`）：

```
AU1 无 Authorization          => 401 statusCode='UNAUTHORIZED'
AU2 Authorization: secret123  => 401          # 裸 token 无效
AU3 Authorization: bearer ... => 401          # 小写前缀无效
AU4 Authorization: Bearer nope=> 401
AU5 Authorization: Bearer secret123 => 200
AU6 GET /static/nope.txt      => 401          # 静态资源也被鉴权拦下（不再是 404）
```

**测试注意**：`AUTH_TOKEN`/`_CORS_ORIGINS` 在 import 时固化，`monkeypatch.setenv` 对它无效——要测鉴权须**重新子进程导入**（或直接 monkeypatch `startapi.AUTH_TOKEN`）。

#### 5.1.5 「统一包络」的最大反例：HTTP 405 是 HTML

Flask 的方法路由在**进入视图函数之前**拦截，返回 **`text/html` 的 405 页**，既不套包络也没有 `statusCode`：

```
DELETE /api/getMediaInfo   => 405  ct=text/html  body='<!doctype html>...<title>405 Method Not Allowed</title>'
GET    /api/uploadPicture  => 405  ct=text/html
```

同类还有 **404**（未注册路径 `/api/nope`、鉴权关闭时的 `/static/不存在`）也是 HTML。**写「统一包络」相关测试时必须排除这两类**，否则断言 `resp.json['statusCode']` 会直接 `JSONDecodeError`。

#### 5.1.6 `statusCode` 常量完整清单（含出现次数与 HTTP 码）

**区分两个维度**：下表「次数」是 JSON 体内字面量出现次数（合计 **147**，另有 1 处鉴权 `UNAUTHORIZED` 由 `_error` 变量传入，故共 **148 次 statusCode 发射**）；「HTTP」是该常量**实际搭配**的 HTTP 状态码。

| statusCode | 次数 | HTTP | 备注 |
|---|---|---|---|
| `MISSING_REQUIRED_PARAMETER` | 32 | 422 | 缺参；**模板白名单不符也复用 `PARAMETER_RANGE_ERROR`** |
| `GENERAL_ERROR` | 26 | 500 | 兜底 `except Exception` |
| `OK` | 25 | 200 | 23 处隐式（函数末尾无第二位）、2 处显式 `}), 200`（`:1919`、`:2490`） |
| `BACKEND_PROCESSING_ERROR` | 24 | 400 | 领域函数返回 `(False, ...)` |
| `UNAUTHORIZED_ACCESS_ERROR` | 14 | 401 | 「越域」检查；**空路径也会命中**（见 5.3-S1） |
| `FILE_PATH_ERROR` | 12 | 422 | `os.path.exists` 失败 |
| `VALUE_RANGE_ERROR` | 5 | 422 | 数量/百分比越界 |
| `PARAMETER_RANGE_ERROR` | 3 | 422 | 白名单不符（模板、comboBox 名） |
| `VALUE_RELATIONSHIP_ERROR` | 2 | 422 | `start < end` 不成立 |
| `RUNTIME_ERROR` | **2** | **422 ×1 + 500 ×1** | 仅 `autoHandleVideo`：`ValueError`→422、`RuntimeError`→500（同名不同码） |
| `FILE_NOT_FOUND` | 1 | 404 | 仅 `getFile`（`:1763`） |
| `缺少PT-Gen简介内容。` | 1 | 422 | **脏数据**：中文文案被写进 statusCode（见 5.3-S6） |
| `UNAUTHORIZED` | 1 | 401 | 仅鉴权失败（`:47`，由 `_error` 传入，不计入 147 字面量） |

HTTP 侧合计：**200×25、400×24、401×15、404×1、422×56、500×27 = 148**。

---

### 5.2 完整路由清单

26 个 `@api.route` + 1 个 Flask 隐式静态端点（`api.url_map` 实测导出）：

```
['POST']          /api/autoHandleVideo          ['POST'] /api/createHardLink
['GET']           /api/getComboBoxData          ['GET']  /api/getFile
['GET']           /api/getMediaInfo             ['GET','POST'] /api/getNameFromTemplate
['GET']           /api/getPTGenInfoByResourceUrl['GET']  /api/getPlayletDescription (GET,POST)
['GET']           /api/getPtGenDescription      ['GET','POST'] /api/getPtGenInfo
['GET']           /api/getScreenshot            ['GET']  /api/getSettings
['GET']           /api/getThumbnail             ['GET']  /api/getTotalEpisode
['GET']           /api/getVideoInfo             ['POST'] /api/makeTorrent
['GET']           /api/media/file/list          ['POST'] /api/moveFileToFolder
['POST']          /api/renameEpisode            ['POST'] /api/renameFile
['POST']          /api/renameFolder             ['GET']  /api/settings
['POST']          /api/settings/update          ['POST'] /api/updateComboBoxData
['POST']          /api/updateSettings           ['POST'] /api/uploadPicture
['GET']           /static/<path:filename>       # Flask 隐式，非业务路由
```

#### 5.2.0 主表（参数、成功 data 键、必需性）

`*` = 代码显式校验为空则 422；`†` = **无校验但事实必填**（不传即 500/异常）；`~` = 缺省时回退 settings。

| # | 方法 路径 | 源码 | 参数（`_payload` 键） | 成功 `data` 键 | HTTP 域 |
|---|---|---|---|---|---|
| 1 | GET `/api/getScreenshot` | `:105` | `path`\*、`screenshotStoragePath`~、`screenshotNumber`~、`screenshotThreshold`~、`screenshotStartPercentage`~、`screenshotEndPercentage`~、`screenshotMinIntervalPercentage`（默认 `'0.01'`，**无 settings 回退**） | `screenshotNumber`(str)、`screenshotPath`(list/str)、`videoPath` | 401/422/400/500 |
| 2 | GET `/api/getThumbnail` | `:289` | `path`\*、`screenshotStoragePath`~、`thumbnailRows`~、`thumbnailCols`~、`screenshotStartPercentage`~、`screenshotEndPercentage`~ | `thumbnailPath`、`videoPath` | 401/422/400/500 |
| 3 | POST `/api/uploadPicture` | `:436` | `picturePath`\*、`pictureBedApiUrl`~、`pictureBedApiToken`~ | `pictureBbCode`、`pictureUrl` | 422/400/500 |
| 4 | GET `/api/getMediaInfo` | `:503` | `path`\* | `mediaInfo`、`videoPath` | 401/422/400/500 |
| 5 | GET `/api/getVideoInfo` | `:582` | `path`\* | `videoPath`+8 关键参数 | 401/422/400/500 |
| 6 | GET `/api/getPtGenDescription` | `:711` | `resourceUrl`\*、`ptGenApiUrl`~ | `description`、`posterUrl` | 422/400/500 |
| 7 | GET/POST `/api/getPlayletDescription` | `:791` | `originalTitle`\*、`year`、`area`、`category`、`language`、**`seasonNumber`†** | `playletDescription` | 422/**500** |
| 8 | GET/POST `/api/getPtGenInfo` | `:830` | `description`\* | `originalTitle/englishTitle/year/otherTitles/category/actors` | 422/500 |
| 9 | POST `/api/makeTorrent` | `:898` | `path`\*、`torrentStoragePath`~ | `torrentPath` | 401/422/400/500 |
| 10 | GET/POST `/api/getNameFromTemplate` | `:966` | `template`\*（白名单 9）、`englishTitle`、`originalTitle`、`season`、**`seasonNumber`†**、`year`、`videoFormat`、`source`、`videoCodec`、`bitDepth`、`hdrFormat`、`frameRate`、`audioCodec`、`channels`、`audioNum`、`team`、`otherTitles`、`totalEpisode`、`playletSource`、`category`、`actors`；**`episode` 已被注释掉**，传了也无效 | `name` | 422/**500** |
| 11 | POST `/api/renameFolder` | `:1037` | `folderPath`\*、`newFolderName`\* | `newFolderPath` | 401/422/400/500 |
| 12 | POST `/api/renameFile` | `:1100` | `filePath`\*、`newFileName`\* | `newFilePath` | 401/422/400/500 |
| 13 | POST `/api/createHardLink` | `:1175` | `path`\* | `hardLinkPath` | 401/422/400/500 |
| 14 | POST `/api/moveFileToFolder` | `:1239` | `filePath`\*（**见 5.3-S2，相对路径必 401**）、`folderName`\* | `newFilePath` | 401/422/400/500 |
| 15 | POST `/api/renameEpisode` | `:1314` | `folderPath`\*、`newFileName`\*、`episodeStartNumber`（缺省 `'1'`） | `newFolderPath` | 401/422/400/500 |
| 16 | GET `/api/getTotalEpisode` | `:1448` | `folderPath`\*、`episodeStartNumber`（缺省 `'1'`） | `totalEpisode` | 401/422/400/500 |
| 17 | GET `/api/getComboBoxData` | `:1549` | `configurationName`\*（白名单 `playlet-source`/`source`/`team`） | `configurationData` | 422/400/500 |
| 18 | POST `/api/updateComboBoxData` | `:1602` | `configurationName`\*、`configurationData`\* | `{}`（空） | 422/400/500 |
| 19 | GET `/api/getSettings` | `:1654` | `settingsName`\* | `settingsData` | 422/500 |
| 20 | POST `/api/updateSettings` | `:1689` | `settingsName`\*、`settingsData`\* | `{}` | 422/500 |
| 21 | GET `/api/getFile` | `:1727` | `filePath`\* | `send_file` 附件（**非 JSON**） | 422/401/404/500 |
| 22 | GET `/api/settings` | `:1777` | 无 | `settings`（全部 settings） | 500 |
| 23 | POST `/api/settings/update` | `:1801` | **`request.json` 原始 body**（不走 `_payload`） | `{}` | 500 |
| 24 | GET `/api/getPTGenInfoByResourceUrl` | `:1822` | `resourceUrl`\*、`ptGenApiUrl`~ | `originalTitle/.../description` | 422/400/500 |
| 25 | GET `/api/media/file/list` | `:1896` | `path`（**可缺省，无 422**） | `fileList` | 401/500 |
| 26 | POST `/api/autoHandleVideo` | `:1983` | `resourceUrl`\*、`path`\*、`source`\*、`team`\*、`category`\*、`season`（**被覆盖**）、`episodesStartNumber`（**被忽略**） | 22 键 camelCase（见下） | 422/500 |

#### 5.2.1 截图 / 缩略图

**`getScreenshot`（`:105`）**

- `screenshotMinIntervalPercentage`：`_payload().get(..., default='0.01')`，**没有 `get_settings` 回退**（与 `screenshotNumber`/`Threshold`/`Start`/`End` 四个「取 settings 默认 + 空串再取一次 settings」的模式不同）。
- `screenshotNumber`/`Threshold` 解析用 `int(...)`/`float(...)`，**非数字直接 `ValueError` → 500 `GENERAL_ERROR`**（与 `getThumbnail` 同病）。
- 校验链：`>0` → `<6` → `0<start<1 and 0<end<1` → `start<end`，否则 422（`VALUE_RANGE_ERROR` ×2 / `VALUE_RELATIONSHIP_ERROR`）。
- 成功（`:207-215`）：`screenshotNumber` 是 **`str(len(response))` 字符串**、`screenshotPath` 是 **`imagePath.replace(media_path, '')` 的列表**。
- **`replace` 常不生效**：`screenshot_storage_path` 默认 `'temp/pic'`（settings），截图落盘后 `response` 里的路径是 `temp/pic/xxx.png`，**不含 `media_path` 前缀 → `replace` 无操作**，故 `screenshotPath` 实为 `['temp/pic/xxx.png', ...]`（实测确认）。旧文档笼统称「相对 media/ 的列表」，**不成立**。
- 失败分支（含 401/422/400/500）的 `screenshotPath` 一律 `''`（字符串），`screenshotNumber` 一律 `'0'`。
- 401 分支（`:116`）的 `data` 是 **`{}`**（无 `screenshotNumber` 键）——**与其它失败分支形状不同**。实测：`GET /api/getScreenshot?path=../../x` → 401、`data={}`。

**`getThumbnail`（`:289`）**

- `thumbnailRows`/`thumbnailCols` 仅经 `int(...)` 解析，**没有「必须 >0」的入参校验**；`0` 走到 `:415` 的 `VALUE_RANGE_ERROR`（422），**非数字 → 500**。
- **没有 `thumbnailThreshold` 之类参数**（与 `getScreenshot` 不对称）：只有 `path`/`screenshotStoragePath`/`thumbnailRows`/`thumbnailCols`/`screenshotStartPercentage`/`screenshotEndPercentage`。
- `data` 键仅 `thumbnailPath`、`videoPath`。

实测：

```
GET /api/getThumbnail?path=Movie&thumbnailRows=0&thumbnailCols=0 => 422 VALUE_RANGE_ERROR '缩略图横向、纵向数量均需要大于0。'
GET /api/getThumbnail?path=Movie&thumbnailRows=x&thumbnailCols=1 => 500 GENERAL_ERROR
```

#### 5.2.2 图片上传：`uploadPicture`（`:436`）

- `pictureBedApiUrl`/`pictureBedApiToken` **缺省或空串时回退到 settings 的同名键**（`:461-469`，`get_settings('picture_bed_api_url')` / `('picture_bed_api_token')`）。
- `pictureUrl = picture_bbs_url[5:-6]`（去掉 `[img]`/`[/img]`），`:477`。
- 混合形状：`picturePath` 缺失时 `data={'pictureUrl': ''}`，路径不存在时 `data={'pictureBbCode': '', 'pictureUrl': ''}`（键数不同）。

#### 5.2.3 PT-Gen 四路由

**`getPtGenDescription`（`:711`）** — 成功 `{'description': format_data, 'posterUrl': poster_url}`。`auto_download_upload_poster` 为真时内联调 `get_poster_from_pt_gen_response`（`:748`），**该步骤异常被内层 `try/except` 吞掉，只写日志**，不影响 200。

**`getPlayletDescription`（`:791`）— `seasonNumber` 事实必填**

- 声明 `methods=['GET','POST']`；`seasonNumber` **无空值校验**，取到 `''` 就直接传给 `get_playlet_description`。
- `src/core/ptgen.py:182`：`if season_number != '1': original_title += ' 第' + int_to_chinese(int(season_number)) + '季'` → `int('')` 抛 `ValueError` → 被兜底 → **500 `GENERAL_ERROR`**。
- 实测：`GET /api/getPlayletDescription?originalTitle=X` → **500**；带 `seasonNumber=1` → 200；带 `=abc` → 500；带 `=0` → 200（渲染为「第零季」）。

**`getPtGenInfo`（`:830`）— `message`/`statusCode` 互换（见 5.3-S6）**，`:846-847`。

**`getPTGenInfoByResourceUrl`（`:1822`）— 返回未解包的元组（见 5.3-S8）**，`:1872`。

#### 5.2.4 `getNameFromTemplate`（`:966`）— GET/POST 实为等价，无「POST 走不到」

- **实测推翻旧说**：「POST + JSON body 永远走不到」**不成立**。`methods` 同时声明 GET/POST，而 `_payload()` 对两者一视同仁。
- **白名单 9 个**（`:982`）：`main_title_`/`second_title_`/`file_name_` × `movie`/`tv`/`playlet`；不符 → 422 `PARAMETER_RANGE_ERROR`。**任何载体都能触发**：

```
POST json={'template':'zzz'}                 => 422 PARAMETER_RANGE_ERROR
POST form template=zzz                       => 422 PARAMETER_RANGE_ERROR
POST query template=zzz                      => 422 PARAMETER_RANGE_ERROR   # 旧文档称只有 GET 能触发，错
```

- `episode` 参数**在代码里被注释掉**（`:994` `# episode = _payload().get('episode', ...)  # Currently unused`），传了无效（但 `_payload()` 里仍能取到，不影响）。
- `english_title = delete_season_number(english_title, season_number)`（`:1012`）**在 `seasonNumber` 为空时同样抛 `ValueError` → 500**，与 `getPlayletDescription` 同源（`src/core/video.py:98`）。实测：

```
POST json={'template':'main_title_movie','originalTitle':'X'}                          => 500
POST json={'template':'main_title_movie','originalTitle':'X','seasonNumber':'1'}       => 200 {"name":"-"}
```

即 **`seasonNumber` 对本路由同样事实必填**（旧文档未提）。

#### 5.2.5 文件操作七路由

| 路由 | 成功 data | 返回路径形状（测试易错点） | 行号 |
|---|---|---|---|
| `renameFolder` | `newFolderPath` | `response.replace(media_path + '/', '')`；实测 Windows 下**命中**（`rename_folder` 拼出的 `new_dir` 恰为 `media_path + '/' + name`）→ 相对名 | `:1077` |
| `renameFile` | `newFilePath` | 同上 replace；**实测 Windows 下不命中** → 返回绝对混合路径 `C:\...\media\D/a.mkv`。另**无扩展名保护**：`newFileName='z.mkv'` 对 `a.mkv` 产出 `z.mkv.mkv` | `:1148` |
| `createHardLink` | `hardLinkPath` | **在判断成功前就 replace**（`:1211` 先于 `:1212` 的 `if`）；`os.path.join` 拼路径 → replace **不命中** → 返回全反斜杠绝对路径 | `:1211` |
| `moveFileToFolder` | `newFilePath` | **原样透传**（未 replace），实测得到 `C:\...\media\Movie/Out/a.mkv` 这种**混合分隔符绝对路径** | `:1285-1294` |
| `renameEpisode` | `newFolderPath` | `response.replace(media_path, '')` 再**去掉前导 `/`**（`:1400-1402`）→ **实测**取文件夹路径的 dirname，得 `...\media\Show` → 裁成 `Show`（相对名） | `:1400` |
| `getTotalEpisode` | `totalEpisode` | `全N集` / `第N集` / `第N-M集` | `:1499-1505` |
> **`media_path + '/'` 的 replace 在这些路由上成败不一**（`:1077`、`:1148`、`:1211`）。根因在更下层 `src/core/rename.py`：`rename_file`（`:468`）与 `rename_folder`（`:507`）用 **`file_dir + '/' + new_name`** 手工拼接，**永远产出正斜杠混合路径** `C:\...\media\NewName/x.mkv`；而 `media_path`（来自 `abspath(join(...))`）**只含 `\`**，故子串 `media_path + '/'` 只有在**该 `/` 恰是拼接点时**才存在——`rename_folder` 的 `new_dir = dirname + '/' + name` 满足（**命中**），`rename_file` 是 `dir + '/' + name + ext`，`dir` 段内已无 `/`，但 `dir` 自身由 `os.path.split` 得来含 `\`，拼出的 `...\media\D/a.mkv` 中 `media\D/a` 不匹配 `...\media/`（**不命中**）。
> **结论：同一族路由返回形状不统一且平台相关**——实测（Windows、绝对入参）`renameFolder` → `"Movie2"`（相对）、`renameFile` → 完整绝对路径、`renameEpisode` → `"Show"`（相对）、`createHardLink`/`moveFileToFolder` → 绝对路径。写断言不要假设「一律相对形式」。

**`renameEpisode`（`:1314`）**

- `if episode_start_number == '' or episode_start_number == '':`（`:1362`）——**左右两侧同式，右侧是死条件**（复制粘贴残留），等价于 `if episode_start_number == '':`。
- 补零逻辑（`:1380-1384`）：`while len(e) < len(str(start + num - 1)): e = '0'+e`，随后**再无条件 `if len(e)==1: e='0'+e`** —— 宽度口径与 `autoHandleVideo` 一致但也有个位数特殊处理。
- 要求 `check_path_and_find_video == 2`（文件夹）；传**文件**路径 → 400 `'不支持文件路径：...'`（`:1421-1428`）。

**`getTotalEpisode`（`:1448`）**

- 同样 `if episode_start_number == '' or episode_start_number == '':`（`:1485`）——同款重复死条件。
- **`第N集` 分支（`:1501-1502`）是可达的**：判据 `str(start) == str(start + num - 1)` 只在 `num == 1` 时成立。`num == 1 && start != 1` 会落到这里，返回 `第N集`。**这不是 bug**（早期版本曾误判为死分支，已更正）。
- 实测（`media/One` 1 个视频、`media/Many` 3 个视频）：

```
folderPath=One&episodeStartNumber=5  => 200 {"totalEpisode":"第5集"}     # :1501 分支，num==1
folderPath=Many&episodeStartNumber=5 => 200 {"totalEpisode":"第5-7集"}   # :1504 分支，num>1
folderPath=Many&episodeStartNumber=1 => 200 {"totalEpisode":"全3集"}     # :1498 分支
folderPath=<文件>                     => 400 '不支持文件路径：...'
```


#### 5.2.6 数据 / 设置六路由

| 路由 | 要点 | 行号 |
|---|---|---|
| `getComboBoxData` | 白名单 `playlet-source`/`source`/`team`，不符 → 422 `PARAMETER_RANGE_ERROR` | `:1565` |
| `updateComboBoxData` | 同上白名单 + `configurationData` 必填；成功 `data={}` | `:1616`、`:1625` |
| `getSettings` | `settingsName` 必填；**键不存在不报错**，`get_settings` 返回 `None` → `settingsData: null` | `:1670` |
| `updateSettings` | `settingsName`+`settingsData` 双必填 | `:1712` |
| `settings` | 无参，返回全量 `get_settings_json()` | `:1782` |
| `settings/update` | **`request.json` 原始 body**，整表覆写（`update_settings_json`）；无 JSON → 500 | `:1806-1807` |

#### 5.2.7 `getFile`（`:1727`）— 唯一加固过的文件路由

- 基准 **`Path(config.TEMP_DIR).resolve()`**（项目根 `temp/`），**不是 `media/`**；`Path(file_path).resolve()` 解析符号链接与 `..`；`if temp_root not in target_path.parents` 做**路径分隔符边界的成员判断**（防 `temp_evil/` 前缀绕过）；`temp` 根自身不可作为目标。
- `filePath` 为**相对路径**时按**进程 CWD** 解析，故从非项目根启动时 `temp/pic/x.png` 会解析到别处 → 401（实测：cwd 为非项目根时 `?filePath=temp/pic/a.png` → 401）。**只有绝对路径可用**（实测：绝对路径 → 200 + `Content-Disposition: attachment`）。
- 与「截图/种子存 temp」的一致性靠约定：`getFile` 白名单是 `config.TEMP_DIR`，而 `autoHandleVideo` 把截图硬编码写相对 `'temp/pic'`（`:2129`）——**两处基准不同源，见 5.3-S3**。

#### 5.2.8 `media/file/list`（`:1896`）— 无 422

- **无 `path` 参数时直接列 media 根**，实测 200（无 `MISSING_REQUIRED_PARAMETER` 分支）。旧文档标 `path*`，**错**。
- `data` 键为 `fileList`，元素 `{name, size, type}`，`size` 经 `convert_size` 人类可读（`'N/A'` 表示目录），`type` 为中文 `'文件'`/`'文件夹'`（`:1951`、`:1954`）。
- **失败分支的 `data` 键写成 `description`**（`:1926`），与成功分支的 `fileList` 不一致，见 5.3-S7。

#### 5.2.9 `autoHandleVideo`（`:1983-2517`）— 自动编排全流程

**入参处理（`:1987-2000`）**

| 参数 | 事实 |
|---|---|
| `resourceUrl`/`path`/`source`/`team`/`category` | 空 → 422 `MISSING_REQUIRED_PARAMETER`（`:2012-2045`）。**先做 401 越域检查（`:2005`）再查空** |
| `season` | 缺省 `'1'`；**随后被 PT-Gen 解析出的 `season` 覆盖**（`:2282` 解包 → `:2304-2306` 重算并**补零到 2 位**） |
| `episodesStartNumber` | 仅用于 `validate_and_convert_to_int`（`:2000`），**TV 分支在 `:2316` 硬编码 `episodes_start_number = 1` 覆盖**，故**入参对集数/标签完全无效**；非法值仍会 422 `RUNTIME_ERROR` |

**完整流程（真实顺序，`:2118` 起）**

1. `data_instance.source/team` 赋值；`category=='Movie'→'电影'`、`=='TV'→'剧集'`（`:2120-2123`）。
2. **`if 'AGSV' in team: tags += ['官方','冰种']`**（`:2124-2125`）——**先于**后续标签。
3. 读 settings：`screenshot_number/threshold/start/end`、`picture_bed_api_url/token`、`thumbnail_rows/cols`、**`do_get_thumbnail`**、**`delete_screenshot`**（`:2130-2140`）。`screenshot_min_interval_percentage` **硬编码 `0.01`**（`:2134`）。
4. **截图目录硬编码 `screenshot_storage_path = 'temp/pic'`**（`:2129`），不走 settings。
5. PT-Gen 简介：失败**重试一次**，再失败 → `RuntimeError`（`:2143-2148`）；`data_instance.description = format_data`（`:2153`）。
6. 截图校验链同 `getScreenshot`（`>=0` → `<6` → 百分比 → 关系），**逐张 `upload_picture`，失败重试一次，成功则把 bbcode 追加到 `description`**（`:2173-2187`）。
7. **`delete_screenshot` 为真则逐张 `os.remove`**（`:2189-2195`）。
8. **`if do_get_thumbnail:`** 才生成缩略图（`:2211`），upload 后同样追加 `description` 并按 `delete_screenshot` 删除（`:2239-2245`）。
9. `get_video_info` → 8 个字段 + **`tags.extend(response[8])`**（`:2274`）。
10. `get_pt_gen_info(data_instance.description)` → 标题/年份/别名/类别/演员/集数/季。
11. **TV 分支**（`:2311-2333`）：要求文件夹；`episodes_num = len(video_files)`；
    - `episodes == episodes_num` → `total_episodes='全N集'` + **`tags.append('合集')`**；
    - 否则 → `第N集`/`第N-M集` + **`tags.append('分集')`**（`num==1` → `第N集`；`num>1` → `第N-M集`）。
    - 故标签最终序为 `['官方','冰种'] + [videoInfo tags] + ['合集'|'分集']`。
12. 三套模板：`main_title_<cat>`、`second_title_<cat>`、`file_name_<cat>`（`:2336-2372`），`category.lower()` 得 `movie`/`tv`。
13. **Movie 重命名分叉**（`:2374-2414`）：`is_video_path==1` → 先 **`move_file_to_folder`** 再 `rename_file`；`==2` → 先 **`rename_folder`**，重新探测后再 `rename_file`。
14. **TV 重命名分叉**（`:2415-2447`）：`is_video_path==2` required；**逐文件 `rename_file`（`{集数}` 按 `:2424-2427` 补零）**，再 **`rename_folder`**（同时去掉 `E{集数}` 与 `{集数}`）。
15. `get_media_info` → `data_instance.media_info`（`:2449-2458`）。
16. `get_data_from_pt_gen_description(...)` 一次写入 **8 个字段**（`:2463-2467`）：`imdb_url`、`douban_url`、`category`、`area`、`video_format`、`audio_codec`、`video_codec`、`medium`。
17. **`make_torrent`**（`:2476`）；成功则 `torrent_file_url = f'{base_url}/getFile?filePath={torrent_path}'`，`base_url = request.base_url.rsplit('/',1)[0]`（`:2480-2481`）。
18. 返回 `convert_to_camel_case(data_instance)`。

**异常映射**：`except ValueError → 422 RUNTIME_ERROR`（`:2492-2499`）；`except RuntimeError → 500 RUNTIME_ERROR`（`:2501-2508`）；`except Exception → 500 GENERAL_ERROR`（`:2510-2517`）。
**实测**：`:2000` 的 `validate_and_convert_to_int('abc')` 抛 `ValueError` → **422 RUNTIME_ERROR**；`category='Music'` 走完流程到模板阶段抛 `ValueError` → **500 RUNTIME_ERROR**（同一 statusCode，两种 HTTP）。

**`Data` 的完整 22 键 camelCase 清单**（`@dataclass Data` `:2047-2093`，`convert_to_camel_case` `:100`，实测导出）

| # | JSON key | # | JSON key | # | JSON key |
|---|---|---|---|---|---|
| 1 | `area` | 9 | `fileName` | 17 | `source` |
| 2 | `audioCodec` | 10 | `frameRate` | 18 | `tags` |
| 3 | `audioNum` | 11 | `hdrFormat` | 19 | `team` |
| 4 | `bitDepth` | 12 | `imdbUrl` | 20 | **`torrentFileUrl`** |
| 5 | `category` | 13 | `mediaInfo` | 21 | `videoCodec` |
| 6 | `channels` | 14 | `medium` | 22 | `videoFormat` |
| 7 | `description` | 15 | `mainTitle` | | |
| 8 | `doubanUrl` | 16 | `secondTitle` | | |

> 旧文档写作 `torrent_file_url`（snake）**是错的**：`to_camel_case` 按 `_` 切分并把首字母大写，实际键是 **`torrentFileUrl`**。默认值 `torrentFileUrl='/api/getFile?filePath='`（`:2115`），成功制种后被整串替换为 `f'{base_url}/getFile?filePath={torrent_path}'`（**注意 base_url 已含 `/api`，故替换后少了 `/api`，路径为 `<host>/getFile?...`**）。旧文档漏列 9 个键（`bitDepth`、`channels`、`description`、`frameRate`、`hdrFormat`、`mediaInfo`、`medium`、`secondTitle`、`videoCodec` 等，按旧文列举口径计）。

---

### 5.3 不一致 / Bug 清单（含修复状态）

> **状态说明**：本节记录的都是这些行为**曾经**的样子。标 ✅已修 的已在
> [修复提交] 中改正，其「实测值」列保留为**历史对照**——当前行为请看每条末尾的
> 「修复后」行，或直接跑 `tests/test_api_bug_locks.py`（每条 S 都有对应用例）。
> 标 ⬜未修 的仍是当前现状。


**先回答复核结论**：旧文档列出的 **7 条全部仍然存在**（逐条对应 S1、S2、S6、S8、S10、S11、S12），无一被修复。下表按**严重度降序**合并「仍然存在的旧 bug」与「本次新发现」，共 **19 条**（S1–S17 + S9b/S9c）。

严重度分级：**S** = 安全性/可达的越权或数据破坏；**D** = 功能不可用或数据丢失；**C** = 契约/形状不一致，测试易误判。

#### S1 ✅已修（旧5，范围大幅扩大）13 处越域检查退化为 `media_path` 前缀检查

- 位置（13 处，`grep` 全量）：`:115`、`:299`、`:512`、`:591`、`:908`、`:1046`、`:1110`、`:1185`、`:1249`、`:1324`、`:1458`、`:1905`、`:2005`。
- 每处的形态都是：`path = os.path.abspath(os.path.join(media_path, path))` **紧跟** `if not path.startswith(media_path)`。`os.path.join(media, '')` + `abspath` **恒等于 `media_path` 本身**，故**空路径/`.` 永远通过**——紧随其后的 `if path == '':` 422 分支（13 处，`:122`/`:306`/`:518`/`:597`/`:915`/`:1052`/`:1117`/`:1192`/`:1256`/`:1331`/`:1465`/`:1735`/`:2019`）**全部是死代码**；`:1735` 是唯一例外（`getFile` 未做 join，故其 422 可达）。
- **真正的问题不是「空路径命中 401」这种良性偏移，而是检查本身不是路径边界检查**：它是**字符串前缀**比较，只要传参能字符串式 `startswith(media_path)` 就放行。因此 `path=../media_evil/x` 这类「兄弟目录」逃逸**完全不受拦**。实测：

```
# 以下均在 cwd=<scratch> 下实测；media_path = <scratch>/media
GET  /api/media/file/list?path=../media_evil              => 200 OK   列出 <scratch>/media_evil 内容   ← 越权读取
POST /api/renameFolder {folderPath:'../media_evil'}       => 200 OK   兄弟目录被改名                   ← 越权写
POST /api/renameFolder {folderPath:''}                    => 422 '缺少需要重命名的名称信息。'           ← 空路径 422 可达
                                                                       （但来自 newFolderName 的检查，不是 folderPath 的）
POST /api/createHardLink {path:''}                        => 200 OK   hardLinkPath='<scratch>/media-hardlink'
                                                                       并在 <scratch> 下真实创建兄弟目录  ← 越权写
POST /api/makeTorrent {path:''}                           => 200 OK   torrentPath='temp/torrent/media.torrent' ← 对 media 根整体制种
POST /api/moveFileToFolder {filePath:''}                  => 401      唯一把空路径判成 401 的路由（S2）
GET  /api/getMediaInfo?path=                              => 200 OK   若 media 根**直接**有视频，返回该视频 MI
GET  /api/getVideoInfo?path=                              => 200 或 400  **取决于 media 根里有没有可解析的视频**：
                                                                       有 → 200；无 → 400 BACKEND_PROCESSING_ERROR。
                                                                       两种都不是 422。断言前先固定 media/ 内容
GET  /api/getScreenshot?path=                             => 200 OK   对 media 根直接截图（有直属视频时）
```

- **空路径的现状是「200 + 对 media 根操作」，不是「401」**（唯一例外是 S2 的 `moveFileToFolder`）。旧文档把它写成「命中 401 而非 422」既漏了范围（不止一处），也把方向说反了（多数是 200 而非 401）。
- 同时 `path` 是 `os.path.abspath` 后的**本地路径**：`file:///` 前缀等畸入参不受理也不报错（落 `os.path.exists` → 422）。
- **正确边界语义见 `getFile`（`:1750`）**：`if temp_root not in target_path.parents` 才是分隔符边界的成员判断。**测试应按现状断言**，并把「空/相对路径 → 200 且作用于 media 根」列为**预期行为**而非异常。

#### S2 ✅已修（旧2，比旧文档所述更严重）`moveFileToFolder` 的 401 检查用了**原始未 join 的参数**

- `:1244` 取 `path = _payload().get('filePath', ...)`，`:1246` 算 `file_path = abspath(join(media_path, path))`，但 `:1249` 检查的是 **`path`（相对形式）而非 `file_path`**：

```python
if not path.startswith(media_path):     # 用错变量
```

- 后果比「空路径命中 401」严重得多：**任何相对路径都 401**（`''.startswith('<abs>/media')` 与 `'Movie/a.mkv'.startswith('<abs>/media')` 皆为假），只有**绝对路径**能通过字面 `startswith`。实测：

```
POST json={'filePath':'Movie/a.mkv','folderName':'Out'}                       => 401   ← 常规用法直接不可用
POST json={'filePath':'<abs>\\media\\Movie\\a.mkv','folderName':'Out'}        => 200   {'newFilePath':'<abs>\\media\\Movie/Out/a.mkv'}
POST data={'filePath':'Movie/a.mkv','folderName':'Out'}                       => 401
POST ?filePath=Movie/a.mkv&folderName=Out                                      => 401
```

- 注意：这是**假安全 + 真不可用**的组合——它挡住了所有正常调用，却又放行绝对路径。

#### S3 ⚠️部分修（新增）`autoHandleVideo` 截图目录改为读 settings，但整体仍是 cwd 相对

- `:2129` `screenshot_storage_path = 'temp/pic'`（注释「默认储存位置，防止无法访问」），**不读 settings、不做 `combine_directories`**，故落盘位置 = **API 进程 CWD 下的 `temp/pic`**。
- 而 `getFile`（`:1746`）的白名单是 `config.TEMP_DIR.resolve()` = **项目根 `temp/`**，与 CWD 无关。
- 二者只有在「进程 CWD == 项目根」时才重合。从别处启动 API 时，`autoHandleVideo` 生成的图落在外部 `temp/pic`，**`getFile` 拿不到**（404/401）；而 `screenshotPath` 的回传值仍是裸 `temp/pic/xxx.png`（同 S16 的 replace 失效问题）。
- 实测（cwd 为非项目根的临时目录）：`getFile?filePath=temp/pic/a.png` → **401**，即从外部 cwd 启动时连自己刚写的截图都取不回——已从侧面证明该基准不一致。

#### S4 ✅已修（新增）`getPlayletDescription` 省略 `seasonNumber` 即 500

- `:806` 取默认 `''`，`:807` 传给 `get_playlet_description`；`src/core/ptgen.py:182` 的 `int('')` 抛 `ValueError` → 兜底 500 `GENERAL_ERROR`。
- 实测：`GET /api/getPlayletDescription?originalTitle=X` → **500**；`seasonNumber=1` → 200。**最常见的调用姿势即崩**，实为「事实必填」。
- 同类：`getNameFromTemplate` 缺 `seasonNumber` 时在 `delete_season_number` 里同样 `int('')` → 500（`src/core/video.py:98`）。

#### S5 ⬜未修（新增）`autoHandleVideo` TV 分支集数/标签忽略 `episodesStartNumber`

- `:2316` **硬编码 `episodes_start_number = 1`**，覆盖 `:2000` 解析出的入参；`:2319` 的 `episodes == episodes_num` 判据因此恒按「从 1 开始」比较。
- 补零宽度用**真实值** `episodes_start_number + episodes_num - 1`（`:2424`），而 `:2426` 又对个位数无条件补 `'0'`——**两套口径**（`:1380-1384` 的 `renameEpisode` 是同一份逻辑的复制）。
- 结论：`episodesStartNumber` 入参**除了能在非法时触发 422 之外无任何效果**。

#### S6 ✅已修（旧1）`getPtGenInfo` 的 `message`/`statusCode` 互换

- `:846-847`：`'message': 'MISSING_REQUIRED_PARAMETER', 'statusCode': '缺少PT-Gen简介内容。'`（HTTP 仍 422）。
- 实测：`GET /api/getPtGenInfo` → `422 statusCode='缺少PT-Gen简介内容。' message='MISSING_REQUIRED_PARAMETER'`。
- 附带影响：这是全文件**唯一**把中文文案写进 `statusCode` 的位置，使 `statusCode` 取值的**封闭集合被破坏**。

#### S7 ✅已修（新增）`media/file/list` 失败分支 `data` 键写成 `description`

- `:1925-1927`：`'data': {'description': ''}`，而成功分支（`:1914-1916`）是 `{'fileList': ...}`。
- 500 时前端按 `fileList` 取值会拿到 `undefined`。

#### S8 ✅已修（旧3）`getPTGenInfoByResourceUrl` 的 `description` 是元组

- `:1844` `format_data, full_data = response` **不改写 `response`**，`:1872` 仍返回 `'description': response`，即 `(format_data, full_data)` 元组 → JSON 序列化为**两元素数组**。
- 契约上该字段应为字符串（同一路由的 `:1831`/`:1880`/`:1889` 失败分支都把它当字符串 `''`）。

#### S9 ✅已修（新增）`createHardLink` 在判断成功前就对返回值做 `replace`

- `:1210` 取 `success, response`；`:1211` **无条件** `response = response.replace(media_path + '/', '')`；`:1212` 才 `if make_hard_link_success`。
- 失败时 `response` 是错误串，被多执行一次 replace（**空操作**，因为错误串里不含 `media_path + '/'`；属冗余但无害）。
- 成功时 `hardLinkPath` 是**全反斜杠的绝对路径**（`create_hard_link` 用 `os.path.join`，不像 `rename_*` 手工拼 `/`）：实测 `{'hardLinkPath': 'C:\\...\\media\\D\\a-hardlink.mkv'}`、目录形式 `'C:\\...\\media\\D-hardlink'`。

#### S9b（新增）`moveFileToFolder` 的成功/失败 `data` 形状不一，且成功路径带混合分隔符

- 成功 `:1289-1291` 返回 `{'newFilePath': response}`（`move_file_to_folder` 用 `os.path.join`，返回 `\` 混合 `/` 的绝对路径）；失败 `:1265-1272`、`:1276-1283` 与通用 500 走 `{'newFilePath': ''}`。
- 与 `renameFile` 不同，**此处不做任何前缀裁剪**，故 `newFilePath` 是绝对路径。旧文档称其为「相对 media/」，**错**。

#### S9c ✅已修（新增）`rename_file` 无扩展名保护：`newFileName` 带扩展名会被重复追加

- `src/core/rename.py:465-468`：`file_name, file_extension = os.path.splitext(file_base)`，然后 `new_name = file_dir + '/' + new_file_name + file_extension`。
- 传 `newFileName='z.mkv'` 对 `a.mkv` → 产物 **`z.mkv.mkv`**（实测）。API 路由不做二次校验，故 `renameFile`/`renameEpisode` 都会被此行为影响（`renameEpisode` 的 `newFileName` 是模板串，通常不含扩展名，风险较低）。

#### S10 ✅已修（旧4）鉴权与路由级的 `statusCode` 不同名

- 鉴权失败：`UNAUTHORIZED`（`:47`）；路由级越域：`UNAUTHORIZED_ACCESS_ERROR`（14 处）。同为 HTTP 401，`statusCode` 不同。测试需按两条分支分别断言。

#### S11（旧6，仍存在）`getFile` 是唯一以 `TEMP_DIR` 为基准并做真边界判断的路由

- `:1746-1750`。其余 13 处（S1）都是 cwd 相对的 `combine_directories('media')` + 字符串前缀，从非项目根启动时基准漂移。
- `getFile` 的两个附带事实：① 相对 `filePath` 按 **CWD** 解析（实测 cwd=scratch 时 `temp/pic/a.png` → 401），**只有绝对路径可用**；② `temp` 根自身 → 401（走 `parents` 成员判断失败）。

#### S12（旧7，仍存在）`getTotalEpisode` / `renameEpisode` 要求文件夹

- `check_path_and_find_video` 返回 `1`（文件）→ 400 `'不支持文件路径：...'`（`:1522-1529`、`:1421-1428`）；返回 `0` → 400 `'资源路径错误：...'`。
- 实测 `folderPath=<文件路径>` → 400 `BACKEND_PROCESSING_ERROR`。

#### S13（已更正：**不是 bug**）`getTotalEpisode` 的三个分支都可达

- 早期版本曾记录「`第N集` 分支恒不可达」——**该结论有误**，推理时漏掉了 `episode_num == 1` 的情形。
- `:1501` 的判据 `str(start) == str(start + num - 1)` 在 `num == 1` 时成立，因此 `num==1 && start!=1` 会走 `第N集` 分支。实测（mock `check_path_and_find_video→(2,…)` + `get_video_files` 返回 1 个文件 + `episodeStartNumber=5`）→ **200 `{'totalEpisode': '第5集'}`**。
- 三条分支各有一条实测样例，见 §5.2.5 的实测块。**测试可按分支逐一锁定**：`start=1` → `全3集`；`start=5, num=3` → `第5-7集`；`start=5, num=1` → `第5集`。

#### S14 ✅已修（新增）`renameEpisode` / `getTotalEpisode` 的 `or` 左右同式死条件

- `:1362` 与 `:1485` 均为 `if episode_start_number == '' or episode_start_number == '':`——复制粘贴残留，右侧永真永假（与左侧等价）。语义等价于单条件，但**覆盖率工具会把右侧记为不可达**。

#### S15 ✅已修（新增）`updateSettings` / `settings/update` 整表覆写且丢键

- `settings/update`（`:1806-1807`）把 `request.json` 原样交给 `update_settings_json` → `SettingsManager.update_all_settings` → **直接 `json.dump(settings, file, indent=4, ensure_ascii=False)`**（`src/core/settings_tool.py:122-126`），无 schema 校验、无 merge。少传一个键就**永久丢一个键**（`_get_default_settings` 有 38 键，现文件只有 37 键、缺 `auto_download_upload_poster`——与旧文档 §3.1「38 键」的差异即由此类覆写造成）。
- `updateSettings`（`:1712`）的第二参**恒为字符串**（`_payload()` 把 JSON 值 `str()` 化），布尔设置被写成 `'True'`，只能靠 `get_setting` 的 `_BOOL_KEYS` 归一 + `_handle_legacy_keys` 补救（`src/core/settings_tool.py:162-167`）。
- **测试若调 `settings/update` 必须先把 `static/settings.json` 备份并还原**——这是唯一会**重写实体配置**的 API。

#### S16 ✅已修（新增）`getScreenshot` 的 `screenshotPath` 裁剪逻辑

- `:205`、`:210` 的 `imagePath.replace(media_path, '')` 在默认 `screenshot_storage_path='temp/pic'` 下**不命中**，返回裸相对路径 `temp/pic/xxx.png`。
- 旧文档称「相对 media/ 的列表」**不成立**；仅当 storage path 落在 `media_path` 之下时该 replace 才生效。
- 同时 `screenshotNumber` 恒为**字符串**（成功 `str(len(response))`、失败 `'0'`），**不是 int**。

#### S17 ✅已修（新增）HTTP 405/404 不套包络，「统一包络」前提被打破

- 用错方法（`DELETE /api/getMediaInfo`、`GET /api/uploadPicture`）→ **`text/html` 405**；未注册路径 → **`text/html` 404**。
- 开鉴权后（`before_request` 先于方法路由）这些请求会**先被拦成 401 JSON**（实测 AU7），行为随 `AUTH_TOKEN` 是否设置而变——同一请求在两种配置下返回**两种 Content-Type**。测试必须显式区分。

---

#### 写测试时的建议基线（避免误判）

| 主题 | 建议 |
|---|---|
| 包络 | 断言 `resp.get_json()` 的 `data`/`message`/`statusCode` 三键；**不要**断言 `_ok`/`_error` 被调用 |
| 方法错/路径错 | 先判 `resp.status_code in (404, 405)` 再决定是否 `get_json()` |
| 参数载体 | 优先测 `json=` 与 query；`data=`（form）仅在 `getScreenshot`/`getThumbnail`/`getMediaInfo`/`getVideoInfo` 等 **纯 GET** 路由上可靠（POST 路由的 form 会被 JSON 覆盖，见 P-a） |
| 路径类参数 | 用 `tmp_path` 的**绝对路径**（相对路径在 S1/S2 下会被解析成 media 根或直接 401）；并另用 `tmp_path` 当 cwd 单独补「`path=''` → 作用于 media 根」和「相对路径 → 401（仅 `moveFileToFolder`）」两条现状断言 |
| 副作用 | 有写副作用的路由：`updateSettings`、`settings/update`、`updateComboBoxData`、`autoHandleVideo`、`renameFolder`/`renameFile`/`renameEpisode`/`moveFileToFolder`/`createHardLink`/`makeTorrent`/`getScreenshot`/`getThumbnail`/`uploadPicture`。**测试前备份 `static/settings.json`**（`settings/update` 会整表覆写），并用 `tmp_path` 当 cwd 或 `monkeypatch.chdir` 隔离文件落点 |
| `autoHandleVideo` | 必须 mock `get_pt_gen_description`/`get_screenshot`/`upload_picture`/`get_video_info`/`make_torrent`（否则走网络与 ffmpeg）；422 与 500 都可能带 `statusCode='RUNTIME_ERROR'` |

---

## 6. 测试覆盖矩阵（中心章节）

> 旧版本节已整体失效，勿参考。旧文声称「现有测试 7 个文件」，实测早已是 **20 个测试文件 + `conftest.py`**，`--collect-only` 收集 **362 条用例**。
> 本节所有数字均来自命令实测，复现命令随表给出。

### 6.1 真实测试集清单

实测命令：

```bash
ls tests/
wc -l tests/*.py
python -m pytest tests/ --collect-only -q -o addopts="" | tail -1   # 409 tests collected
python -m pytest tests/ -q --cov=src                                # 409 passed, 1 skipped
grep -c "def test_" tests/*.py
```

`tests/` 目录共 23 个 `.py`（`__init__.py` + `conftest.py` + 21 个 `test_*.py`），合计 4159 行。

#### 6.1.1 逐文件明细

| 文件 | 行数 | 用例数 | 覆盖模块 / 关注点 |
|---|---|---|---|
| `conftest.py` | 180 | — | 共享 fixture 与伪对象（见 6.1.2），不含用例 |
| `test_api_getfile.py` | 98 | 8 | `/api/getFile` 安全边界（TEMP_DIR 基准、前缀绕过、`..` 穿越、symlink 逃逸） |
| `test_api_bug_locks.py` | 250 | 18 | **§5.3 缺陷锁定专测**：S1 兄弟目录逃逸 / S4 `seasonNumber` 必填 500 / S7 失败键名 / S8 description 元组 / S9 响应形状 / S9c 扩展名重复 / S10 两个 401 常量 / S13 三态分支 / S15 整表覆写丢键 / S16 字符串张数 / S17 HTML 405/404 |
| `test_api_restful.py` | 74 | 6 | `_payload()` POST/GET 双栈、可选鉴权矩阵、`autoHandleVideo` 405、`makeTorrent` 缺参 |
| `test_api_routes.py` | 478 | 62 | 21 个此前未测的 API 路由，mock 核心函数走成功路径 + 错误分支；宽断言已全部收窄为唯一状态码；含 `getScreenshot`/`getThumbnail` 的参数校验 422 分支 |
| `test_config.py` | 118 | 13 | `src.config.settings.Config`、`SettingsManager`、env 覆盖、图片床配置 |
| `test_core_autofeed.py` | 37 | 2 | `core.autofeed.get_auto_feed_link` |
| `test_core_branches.py` | 477 | 62 | 跨模块残余分支：ptgen 映射表逐项、rename 季数正则、data/settings_tool 异常、screenshot 调用分支、mediainfo Text track、torrent 异常、`file_utils` 四个函数；`create_hard_link` 的 Unsupported 分支已由空断言改为真断言 |
| `test_core_data.py` | 147 | 15 | `core.data`：`get_combo_box_data` / `update_combo_box_data`（含**真换行** bug 用例）/ `get_abbreviation`（死参数、损坏抛 `ValueError`）/ `load_names`；列表长度 6/9/7 |
| `test_core_mediainfo.py` | 138 | 5 | `core.mediainfo.get_media_info`（伪 track、对齐、章节正则、suffix） |
| `test_core_picturebed.py` | 326 | 31 | `core.picturebed`：类型识别 + 6 家 provider 成功/错误路径；`generate_image_filename` 增「6 位互不相同」的真实 `random.sample` 断言（原 mock 用了不可能的值） |
| `test_core_poster.py` | 124 | 13 | `core.poster`：URL 提取、下载（UA/Referer）、上传、临时文件去留 |
| `test_core_ptgen.py` | 270 | 32 | `core.ptgen`：新/旧 API 判定、URL 归一（含缺 scheme 双路径 bug）、签名、描述后处理、playlet 模板、字段映射（含 `480P→480i` bug 与「最后命中者胜」并列覆盖） |
| `test_core_rename.py` | 441 | 28 | `core.rename`：`get_video_info`（含 `0Audio`、双 Video track 串联失真）、`get_name_from_template`（含 `AttributeError`/`IndexError` 两处必崩）、`rename_file`、`rename_folder` 等 |
| `test_core_screenshot.py` | 178 | 11 | `core.screenshot`：`get_screenshot` / `get_thumbnail`（mock `cv2`/`random`） |
| `test_core_text.py` | 178 | 29 | `core.text`：罗马/中文数字（含「万」进档错误）、拼音、`natural_keys`、base64、`validate_and_convert_to_int`、`convert_chinese_punctuation_to_english` 的注释打断 dict bug |
| `test_core_torrent.py` | 69 | 6 | `core.torrent.make_torrent`（trackers/created_by、先删后写、空目录） |
| `test_core_video.py` | 123 | 19 | `core.video`：路径判定、视频列举、自然序、文件名过长、季数删除 |
| `test_file_utils_json.py` | 87 | 8 | `utils.file_utils.load_or_initialize_json`（backfill 语义、字节级不变、缩进保留） |
| `test_rename_info.py` | 164 | 18 | `core.rename.get_pt_gen_info`（raw_data 优先、纯正则回退、逐字段回退） |
| `test_settings_tool.py` | 184 | 15 | `core.settings_tool`：`_BOOL_KEYS` 归一、默认值（**38 键**）、迁移、env 覆盖；新增 env 分支**不归一**、env 跳过 legacy 迁移、`_settings_cache` 缓存语义 |
| `test_utils.py` | 91 | 8 | `utils.file_utils`（`ensure_directory`/`safe_filename`/`get_file_hash`/`get_file_size_human`）+ `utils.logger.setup_logger` |
| **合计** | **3587** | **362 收集 / 361 通过 / 1 跳过** | |

> 1 条跳过：`tests/test_api_getfile.py:93`，`pytest.skip("cannot create symlink")`——Windows 非管理员无 symlink 权限，symlink 逃逸用例无法执行（见 §7）。

#### 6.1.2 `tests/conftest.py` 提供的 fixture 清单

这是旧文档最大的遗漏，也是后续写测试的**基础设施底座**。全部 9 个 fixture 均定义在 `tests/conftest.py`，无 `pytest.ini`/`pyproject` 级共享 fixture。

| fixture | 依赖 | 作用 | 典型用法 |
|---|---|---|---|
| `settings_file` | `tmp_path` | 返回 `tmp_path/"settings.json"`（未初始化路径） | `SettingsManager(settings_file)` |
| `manager` | `settings_file` | 指向临时文件的 `SettingsManager` 实例，隔离真实 static | `manager.get_setting(...)` / `manager.update_setting(...)` |
| `mock_settings` | `monkeypatch`, `tmp_path` | **重定向 `src.core.<mod>.get_settings` 到临时 manager**，防止读到真实 `static/settings.json`。返回对象含 `patch(module_path)` / `set(k,v)` / `get_defaults()` | `mock_settings.patch("src.core.rename")` 后 `rename.get_settings(key)` 读临时文件 |
| `chdir_to_tmp` | `tmp_path`, `monkeypatch` | `monkeypatch.chdir(tmp_path)`，使 `combine_directories()` 落到 tmp 而非真实 static | 任何会写 static/ 的用例 |
| `write_static` | `tmp_path`, `chdir_to_tmp` | 工厂：在 `tmp_path/static/<name>` 写 JSON（cwd 相对，隔离），返回路径字符串 | `write_static("combo-box-data.json", {...})` |
| `fake_mediainfo` | `monkeypatch` | 把 `rename.MediaInfo.parse` 与 `mediainfo.MediaInfo.parse` 换成伪对象，`.to_json()` 由 `tracks` 列表生成；通过 `fake_mediainfo.tracks = [...]` 喂数据 | `fake_mediainfo.tracks = [make_track("Video", ...)]` |
| `api_client` | — | `src.api.startapi.api.test_client()`，Flask 测试客户端（**110 处引用，最常用**） | `api_client.get("/api/getSettings")` |
| `media_file` | `tmp_path`, `monkeypatch` | chdir 到 tmp 并建 `tmp/media/视频.mkv` 占位文件，使 `combine_directories('media')` 命中 tmp 且 `os.path.exists` 通过 | 媒体类路由 mock 成功路径 |
| `real_media` | — | 返回仓库内 47MB 真实样本相对路径 `media/测试媒体文件.mp4`，供少数真实冒烟路由（不 chdir，保持 cwd=项目根） | `api_client.get("/api/getMediaInfo", query_string={"path": real_media})` |

**另有 2 个非 fixture 的共享辅助对象**（`from tests.conftest import ...` 直接导入，非 pytest 注入）：

| 名称 | 作用 | 使用处 |
|---|---|---|
| `make_track(track_type, **attrs)` | 构造伪 MediaInfo track（`SimpleNamespace`），支持 `other_width=['1920']` 这类列表形状字段 | `test_core_mediainfo.py`、`test_core_branches.py` |
| `FakeResponse(status_code, text, json_data, content)` | requests 风格伪响应，含 `.json()` / `.iter_content()` / `.raise_for_status()` | `test_core_picturebed.py`、`test_core_branches.py` |

### 6.2 当前覆盖率基线

实测命令（`pyproject.toml` 的 `addopts` 已自带 `--cov=src`，此处显式再写一次仅为明确口径）：

```bash
python -m pytest tests/ -q --cov=src --cov-report=term-missing
```

#### 6.2.1 逐文件覆盖率

| 文件 | 语句数 | 未覆盖 | 覆盖率 |
|---|---|---|---|
| `src/__init__.py` | 0 | 0 | 100% |
| `src/api/__init__.py` | 0 | 0 | 100% |
| `src/api/startapi.py` | 1019 | 515 | 49% |
| `src/config/__init__.py` | 3 | 0 | 100% |
| `src/config/settings.py` | 46 | 0 | 100% |
| `src/core/__init__.py` | 0 | 0 | 100% |
| `src/core/autofeed.py` | 35 | 0 | 100% |
| `src/core/data.py` | 56 | 14 | 75% |
| `src/core/mediainfo.py` | 64 | 6 | 91% |
| `src/core/picturebed.py` | 250 | 38 | 85% |
| `src/core/poster.py` | 89 | 16 | 82% |
| `src/core/ptgen.py` | 221 | 13 | 94% |
| `src/core/rename.py` | 399 | 36 | 91% |
| `src/core/screenshot.py` | 129 | 9 | 93% |
| `src/core/settings_tool.py` | 99 | 7 | 93% |
| `src/core/text.py` | 101 | 0 | 100% |
| `src/core/torrent.py` | 28 | 0 | 100% |
| `src/core/video.py` | 51 | 0 | 100% |
| `src/gui/__init__.py` | 0 | 0 | 100% |
| `src/gui/startgui.py` | 1794 | 1794 | **0%** |
| `src/gui/ui_tools.py` | 15 | 15 | **0%** |
| `src/main_api.py` | 29 | 29 | **0%** |
| `src/main_cli.py` | 1193 | 1193 | **0%** |
| `src/main_gui.py` | 28 | 28 | **0%** |
| `src/utils/__init__.py` | 0 | 0 | 100% |
| `src/utils/exceptions.py` | 18 | 0 | 100% |
| `src/utils/file_utils.py` | 125 | 5 | 96% |
| `src/utils/logger.py` | 42 | 1 | 98% |
| **TOTAL** | **5834** | **3719** | **36%** |

#### 6.2.2 零覆盖文件

| 文件 | 源码行数 | 语句数 | 理由 |
|---|---|---|---|
| `src/gui/startgui.py` | 2334 | 1794 | PyQt6 主窗口，当前 **0 个 GUI 测试** |
| `src/gui/ui_tools.py` | 40 | 15 | 文件对话框包装，依赖 `QFileDialog` |
| `src/main_cli.py` | 1966 | 1193 | CLI 入口，当前无测试 |
| `src/main_api.py` | 61 | 29 | Flask 启动入口（`__main__` 壳） |
| `src/main_gui.py` | 76 | 28 | GUI 启动入口（含 PyInstaller 引导） |

#### 6.2.3 「剔除排除项后的有效覆盖率」

裸 TOTAL 36% 严重失真：分母里塞进了 3059 条**从未打算被单测覆盖**的语句（GUI/CLI/入口）与 292 条巨型编排路由。在有意义的测试范围内，实测覆盖率是 **85.2%**。

**口径定义**：从分母中剔除下列两块——它们的语句默认「不可单测」或尚未建立测试脚手架：

1. **GUI / CLI / 入口文件**：`src/gui/startgui.py`、`src/gui/ui_tools.py`、`src/main_cli.py`、`src/main_api.py`、`src/main_gui.py`（合计 3059 语句，全未覆盖）。
2. **`src/api/startapi.py` 的 `autoHandleVideo` 路由体**（`api_auto_handle_movie`，实测归属该函数的未覆盖语句 292 条）：它是一条 9 个外部依赖的端到端编排，现有测试只覆盖了 `GET→405`、缺参 `422`、越域 `401` 三个入口判断，主体 292 语句全未覆盖，拉低 startapi 整体覆盖率约 29 个百分点。

**计算结果**：

```
有效语句数 = 5834 - 3059 - 292 = 2483
有效未覆盖 = 3719 - 3059 - 292 =  368
有效覆盖率 = (2483 - 368) / 2483 = 85.2%
```

复现脚本（沿用 `--cov-report=json` 产物）：

```bash
python -m pytest tests/ -q --cov=src --cov-report=json:cov.json
```

```python
import json
d = json.load(open("cov.json"))
B = chr(92)
EXCL = {f"src{B}gui{B}startgui.py", f"src{B}gui{B}ui_tools.py", f"src{B}main_api.py",
        f"src{B}main_cli.py", f"src{B}main_gui.py", f"src{B}gui{B}__init__.py"}
tot_s = tot_m = ex_s = 0
for f, v in d["files"].items():
    tot_s += v["summary"]["num_statements"]; tot_m += v["summary"]["missing_lines"]
    if f in EXCL:
        ex_s += v["summary"]["num_statements"]
AH = 292  # api_auto_handle_movie 未覆盖语句数
eff_s, eff_m = tot_s - ex_s - AH, tot_m - ex_s - AH
print(f"TOTAL     {tot_s} stmts / {tot_m} miss -> {100*(tot_s-tot_m)/tot_s:.1f}%")
print(f"EFFECTIVE {eff_s} stmts / {eff_m} miss -> {100*(eff_s-eff_m)/eff_s:.1f}%")
```

> 结果：`TOTAL 5834 stmts / 3719 miss -> 36.3%`，`EFFECTIVE 2483 stmts / 368 miss -> 85.2%`。
> 引用覆盖率时**必须声明口径**，否则 36% 与 85% 会被误读为矛盾。

#### 6.2.4 核心模块的残余未覆盖点（有效范围内的「最后 15%」）

| 文件 | 残余未覆盖 | 说明 |
|---|---|---|
| `data.py` (75%) | `:79-89, 101-103, 162-167` | `update_combo_box_data` 的写回路径、`load_names` 部分分支 |
| `poster.py` (82%) | `:97-107, 140, 179, 183-185, 193-194` | 下载/上传异常分支与临时文件去留 |
| `picturebed.py` (85%) | `:29-40, 81-82, 92-93, 100-101, 107-112, 180-182, 234-239, 271-273, 306, 338-340` | `get_picture_bed_type` 部分识别分支、个别 provider 键缺失路径 |
| `rename.py` (91%) | `:82, 96-97, 109-112, 202, 228, 230, 233-238, 305, 307, 340, 353-356, 397-398, 450, 457, 516-517, 554-556, 594, 607, 619-623` | 零散异常/兜底分支 |
| `mediainfo.py` (91%) | `:202-209` | 非 `OSError` 的 `except Exception` 分支 |
| `api/startapi.py` (49%) | 见 6.2.3 | 主要是 `autoHandleVideo`（292）+ 各路由的 401/422 之外分支 |

### 6.3 测试运行与配置

#### 6.3.1 `pyproject.toml` —— `[tool.pytest.ini_options]`

```toml
[tool.pytest.ini_options]
minversion = "6.0"
addopts = "-ra -q --strict-markers --cov=src --cov-report=term-missing"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
```

| 键 | 值 | 影响 |
|---|---|---|
| `addopts` | `-ra -q --strict-markers --cov=src --cov-report=term-missing` | **默认带 `--cov=src`**：哪怕只跑一个测试文件（`pytest tests/test_utils.py`），末尾也会打印**全量 28 个源文件**的覆盖率报告。新手最容易困惑的点——不是测试跑错了，是 `addopts` 强制加了覆盖率。要关掉用 `-p no:cacheprovider` 无效，正确做法是 `-o addopts=""` 或 `--no-cov`。 |
| `testpaths` | `["tests"]` | 直接 `pytest` 时只收集 `tests/` |
| `python_files` | `["test_*.py", "*_test.py"]` | 两种命名都收 |
| `--strict-markers` | — | 未注册的 marker 会报错。**当前代码库没有任何 `pytest.mark.*` 使用**（`grep -rn "pytest.mark" tests/` 为空），因此无 markers 需要注册。 |
| `-ra` | — | 汇总显示 skip/xfail 原因（这也是能看到 `SKIPPED [1] ... cannot create symlink` 的原因） |

#### 6.3.2 `pyproject.toml` —— `[tool.coverage.*]`

```toml
[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/test_*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
```

- `source = ["src"]` → 分母是 `src/` 全树，故 TOTAL 被 GUI/CLI/入口拉低（见 6.2.3）。
- `omit` 只排除测试文件本身，**不排除 GUI/CLI**——若想让默认报告更贴近有效口径，应把 6.2.3 的排除清单加进 `omit`。
- `exclude_lines` 里 `if __name__ == .__main__.:` 已生效，所以入口文件的 `main()` 守卫行不计入分母（但 `src/main_cli.py` 等模块体仍在）。

#### 6.3.3 `Makefile` 目标

| 目标 | 命令 | 说明 |
|---|---|---|
| `test` | `pytest tests/ -v` | 因 `addopts`，**实际带 `--cov=src`** |
| `test-coverage` | `pytest tests/ --cov=src --cov-report=html --cov-report=term` | 生成 `htmlcov/` |
| `lint` | `flake8 src/ tests/` 然后 `mypy src/` | 88 列；mypy 非 strict 但要求 `disallow_untyped_defs` |
| `format` | `black src/ tests/` 然后 `isort src/ tests/` | line-length 88 |
| `format-check` | `black --check` + `isort --check-only` | CI 用 |
| `check-all` | `format-check lint test security` | 注意顺序：`test` 在 `lint` 之后，且包含 `security`（bandit + safety） |
| `clean` | 删 `*.pyc` / `__pycache__` / `.pytest_cache` / `.coverage` / `htmlcov` / `dist` / `build` | — |

#### 6.3.4 Windows 上的 symlink 跳过

`tests/test_api_getfile.py:85-95` 的 symlink 逃逸用例：

```python
if not hasattr(os, "symlink"):
    pytest.skip("platform without symlink support")
...
try:
    os.symlink(str(outside), str(link))
except OSError:
    pytest.skip("cannot create symlink")
```

- **原因**：Windows 上创建符号链接需要「开发者模式」或管理员权限；普通用户 `os.symlink` 抛 `OSError`（`WinError 1314 客户端没有所需的特权`）。
- **表现**：本机实测为 `SKIPPED [1] tests\test_api_getfile.py:93: cannot create symlink`，故 362 收集 = **361 passed + 1 skipped**。
- **规避方式**：以管理员身份运行、或开启「设置 → 隐私和安全性 → 开发者选项 → 开发人员模式」，之后 `os.symlink` 可用（但仍需 `os.symlink` 的 `target_is_directory` 对目录正确传参）。CI 上建议保持跳过而非强制通过，Linux/macOS runner 会实跑该用例。
- 断言强度提示：即使跳过，`/api/getFile` 的 `..` 穿越与前缀绕过（`temp_evil`）用例仍在跑，安全边界并非无保护。

### 6.4 当前真实 gap 清单

旧文 §6.2 那张长 gap 表**绝大多数项已被覆盖**，不再罗列。以下为实测后**仍然缺失**的项（`grep` + 实跑确认）：

| # | gap | 证据 | 规模 |
|---|---|---|---|
| 1 | **GUI 全部** | `src/gui/startgui.py` 0%（1794 语句）、`src/gui/ui_tools.py` 0%（15 语句）；`grep -rn "startgui\|ui_tools" tests/` 无命中 | 约 2334 行源码，0 用例 |
| 2 | **`src/main_cli.py` 全部** | 0%（1193 语句）；测试目录无任何引用 | 1966 行，0 用例 |
| 3 | **入口文件** `src/main_api.py` / `src/main_gui.py` | 各 0%；仅被当作 `__main__` 壳，未 import | 137 行 |
| 4 | **`autoHandleVideo` 主流程** | `api_auto_handle_movie` 292 语句全未覆盖；现有 5 条用例只打 `GET→405`、缺参 `422`、越域 `401` 三个入口 | 1 条路由的 9 依赖编排 |

#### 6.4.1 已补齐（本轮）

以下三块此前列为 gap 或存在「有测试但锁不住」，**已全部补齐**：

| 项 | 补法 |
|---|---|
| `getScreenshot` / `getThumbnail` 的参数校验 422 分支 | `test_api_routes.py` 新增 6 条，精确断言 `VALUE_RANGE_ERROR`/`VALUE_RELATIONSHIP_ERROR` + 逐字消息。**注意陷阱**：`getThumbnail` 的 rows/cols 校验在 `check_path_and_find_video` **之前**（无需 mock）；而 start>end 在后置，必须先 mock `check_path_and_find_video`，否则被 422 `FILE_PATH_ERROR` 抢先 |
| §5.3 缺陷锁定 | 新增 `tests/test_api_bug_locks.py`（18 条），逐条锁定 S1/S4/S7/S8/S9/S9c/S10/S13/S15/S16/S17 |
| 文档点名但零断言的边界值 | `480P→480i`、`0Audio`、`chinese_to_int('十二万')`、双 Video track 串联、`_norm_ptgen_url` 缺 scheme、`Unsupported path type`、`AttributeError`/`IndexError`、`get_abbreviation` 抛 `ValueError`、列表长度 6/9/7、env 分支不归一、`_settings_cache`、注释打断 dict |

#### 6.4.2 三条「坏测试」已修（此前在替 bug 背书）

| 位置 | 原问题 | 现状 |
|---|---|---|
| `test_core_branches.py` `test_unsupported_path_type` | 主体是 `monkeypatch = None` + `assert True`，**真·空断言**，却被覆盖率计为「已覆盖」 | 改为 monkeypatch `os.path.exists/isfile/isdir` 真断言 `Unsupported path type: …` |
| `test_core_picturebed.py` `test_fixed_random_digits` | mock `random.sample` 返回 `["0","0",…]`（两个 0）——**真实 `random.sample` 无放回，永远不可能产生**，把「6 位互异」契约擦掉了 | mock 值改为互异；**另加一条不 mock 的真实语义断言** |
| `test_core_data.py` `test_newline_split_and_write` | 用字面量 `"A\nB\nC"` 断言被切分，措辞暗示「按换行分割」，为 `split('\n')` 的 bug 背书 | 更名并加注；**另加一条真换行用例**锁定 bug 另一侧 |

#### 6.4.3 仍未锁（已评估，不建议写用例）

- **S14 `or` 左右同式死条件**（`startapi.py:1362`/`:1485` 的 `x == '' or x == ''`）：语义上与单条件等价，**没有任何断言能区分**它是死条件还是真条件，写用例只会锁住一个假象。建议在代码层清理，而非测试层。
- `autoHandleVideo`（gap 4）：需 mock 9 个依赖且会走网络/ffmpeg，性价比低，按用户先前决定不做。

#### 6.4.4 覆盖率现状（本轮后实测）

```
python -m pytest tests/ -q --cov=src
409 passed, 1 skipped
TOTAL 5834 语句 / 3678 未覆盖 = 37%
```

| 模块 | 覆盖 | 模块 | 覆盖 |
|---|---|---|---|
| text / torrent / video / autofeed / config / exceptions | **100%** | screenshot / settings_tool | 93% |
| logger | 98% | mediainfo / rename | 91% |
| file_utils | 96% | picturebed | 85% |
| ptgen | 95% | **API `startapi.py`** | **53%** |
| | | data | 79% |
| | | poster | 82% |

**有效覆盖率口径**（剔除 GUI/CLI/入口 3059 语句 + `autoHandleVideo` 292 语句）：分母 2483，未覆盖 368 → **约 85%**。复现脚本见 §6.2 的说明。

> 注意：本轮补的测试**提升的是「锁定强度」而非覆盖率数字**（37% vs 之前 36%）——新增用例大多打在已覆盖的行上（同一行不同分支/不同断言）。这是刻意的：之前的问题是「覆盖了但锁不住」，不是「没覆盖」。

### 6.5 断言强度：从「宽断言」到「唯一值」（本轮已修）

此前新测试里大量使用宽断言，导致 §5.3 声称「已按现状锁定」的几个 bug **其实并未被真正锁住**。本轮**已全部收窄**，`grep` 确认零残留：

```bash
grep -n "status_code in (\|!= 500" tests/*.py   # 本轮之后：0 命中
```

#### 6.5.1 收窄前后对照（实测真值）

| 原位置 | 原断言 | 收窄为 | 依据 |
|---|---|---|---|
| `test_api_routes.py:227` | `== 401 or == 422` | `== 422` + `MISSING_REQUIRED_PARAMETER` | `renameFolder` 空 `folderPath` |
| `:236` | `in (200, 422)` | `== 200` + `OK` | mock `rename_folder` 后走成功分支 |
| `:242` | `in (401, 422)` | `== 422` + `MISSING_REQUIRED_PARAMETER` | `renameFile` 空 `filePath` |
| `:247` | `in (200, 422)` | `== 200` + `OK` | mock `rename_file` |
| `:255` | `in (200, 422)` | `== 200` + `OK` | mock `create_hard_link` |
| `:262` | `== 401 or == 422` | `== 401` + `UNAUTHORIZED_ACCESS_ERROR` | **S2 bug 的现状**，宽断言曾使其失去锁定力 |
| `:266` | `in (401, 422)` | `== 401` + `UNAUTHORIZED_ACCESS_ERROR` | 同上（相对路径必然 401） |
| `:274` | `in (200, 401, 422)` | 拆两条：绝对路径 `== 200`+`OK` / 相对路径 `== 401`+`UNAUTHORIZED_ACCESS_ERROR` | 三值全开曾等于没断言 |
| `:280` | `in (401, 422)` | `== 422` + `MISSING_REQUIRED_PARAMETER` | `renameEpisode` 空 `folderPath` |
| `:300` | `== 200 or == 400` | `== 200` + `OK` | mock 后成 |
| `:307` | `in (200, 400, 422)` | `== 400` + `BACKEND_PROCESSING_ERROR` | `folderPath` 指向**文件** → 「不支持文件路径」 |
| `:30/:52/:100/:125` | `!= 500` | `== 200` + `OK`（空 path 落 media 根后一路成功） | 空路径不是 422，而是对 media 根操作 |

#### 6.5.2 改宽断言时的两个坑（实测踩过）

1. **不要照抄「实测状态码」列而不核对用例的 mock 上下文**。`getTotalEpisode` 那条用例把 `folderPath` 指向一个**文件** → 走「不支持文件路径」得 **400**；若改成指向**不存在的路径**才会是 422 `FILE_PATH_ERROR`。同一路由、不同入参，取值不同。
2. **`moveFileToFolder` 的成功路径必须传绝对路径**。S2 的越域检查用的是未 join 的原始参数，任何相对路径都会 401——所以「成功路径」用例只有传 `os.path.abspath(...)` 才能拿到 200。已按此拆成 `test_success_with_absolute_path` 与 `test_relative_path_hits_401_bug` 两条。

#### 6.5.3 保持做法

1. **状态码 + statusCode 双锁**，能再加逐字消息就加（`test_api_routes.py` 的 `PARAMETER_RANGE_ERROR`、`test_api_bug_locks.py` 全篇都是正面范例）。
2. **bug 锁定用例必须先裸跑取真值再写死**，并在注释里写上 S 编号与源码行号——修 bug 时能立刻找到要改的用例。
3. **门禁建议**：在 `Makefile` 的 `lint` 里加一条
   `! grep -rn "status_code in (\|!= 500" tests/`
   防止新增宽断言回潮。

---

## 7. 测试环境注意事项（写给测试实现）

> 本节按实测重写，并补充旧文遗漏的隔离陷阱。旧版第 6 条提到 `docs/DEVELOPMENT.md` 的测试文件树过时——**该事实本身成立**（该文档确实写了不存在的 `test_core.py`/`test_api.py`/`test_gui.py`），见 §7.4。

### 7.1 路径与 cwd 隔离

1. **`combine_directories` 基于 cwd，且存在两份不等价实现。**
   - `src/utils/file_utils.py:22` → `os.path.join(os.getcwd(), path)`（返回 str）
   - `src/core/settings_tool.py:279` → `str(Path.cwd() / relative_path)`
   - **实际生效的是 `file_utils` 的那份**：`src/api/startapi.py:23` 明确 `from src.utils.file_utils import combine_directories`。虽然两者在 Windows 上路径分隔符表现不同，但都以 `os.getcwd()` 为基准，因此**任何涉及路径拼接的测试都必须 `monkeypatch.chdir(tmp_path)`**，否则会写到仓库根目录。`conftest.py` 的 `chdir_to_tmp` / `write_static` / `media_file` fixture 已封装此点。

2. **`config.MEDIA_DIR` 在 `src/` 内零消费——改它无效。**
   - `grep -rn "MEDIA_DIR" src/` 只有 3 处命中：`src/config/settings.py:23`（定义）、`:61`（在启动目录创建列表里），以及 `__pycache__`。**没有任何业务代码读它**。
   - API 的真实 media 基准是 `src/api/startapi.py` 里 **13 处 `combine_directories('media')`**（cwd 相对）。
   - 结论：想让 API 把 media 根指向 tmp，**`monkeypatch.setattr(config, "MEDIA_DIR", ...)` 完全无效**，必须 `monkeypatch.chdir(tmp_path)` 再建 `tmp_path/media/`。`conftest.py` 的 `media_file` fixture 正是这么做的。

3. **`settings_manager = SettingsManager()` 是模块级单例。**
   - `src/core/settings_tool.py:231` 在 **import 时**即读写 `static/settings.json`。任何 `import src.core.settings_tool` 都会触发磁盘 IO。
   - `get_abbreviation` / `get_combo_box_data` / `get_picture_bed_type` 会**写回** static 文件（backfill 语义）。测试必须指向 tmp：
     - 直接构造 `SettingsManager(tmp_path / "settings.json")`（fixture `manager` / `settings_file`）；
     - 或 `monkeypatch.chdir(tmp_path)` 后由 `combine_directories` 把 static 落到 tmp（fixture `chdir_to_tmp` / `write_static`）；
     - 或把目标模块的 `get_settings` 换成临时版（fixture `mock_settings`，用法 `mock_settings.patch("src.core.rename")`）。
   - 不隔离的后果：测试跑完污染仓库的 `static/settings.json` / `static/combo-box-data.json`，且用例之间相互串味。
   - **实测澄清**：单纯的 `import src.api.startapi`（或 `settings_tool`）在**本仓库当前状态下不会**改写 `static/settings.json`（已实测：import 前后 `git status` 均为干净）。该文件被改写的**唯一**已知路径是**调用**写接口——`POST /api/settings/update` 会整表覆写（见 §5.3 S9）。所以测试要防的是「调了写接口」，不是「导入模块」；但 `static/combo-box-data.json` / `static/abbreviation.json` 确实会被 `get_combo_box_data` / `get_abbreviation` 的 backfill 写回，仍须 chdir 隔离。
   - 另注意：`static/settings.json` 在工作区里出现「`\uXXXX` 变成真汉字」的 diff 时，是**某次写回**（`json.dump(..., ensure_ascii=False)`）的产物，不是 import 的副作用。

4. **`src/utils/logger.py` 是扁平导入且无兼容桥，拿到的是「另一个 config 实例」。**
   - `src/utils/logger.py:8` 直接 `from config.settings import config`，**没有** `file_utils`/`settings_tool` 那种「若 `src/` 不在 `sys.path` 则插入」的兼容桥。
   - 实测：`logger.config` 与 `src.config.settings.config` **不是同一个对象**（前者 id 与扁平 `config.settings.config` 相同，后者不同）。
   - 后果：`monkeypatch.setattr(config, ...)`（作用于 `src.` 前缀实例）**控制不到日志**，测试的日志会往真实 `logs/app.log` 写。
   - 规避：要控制日志行为，应 `monkeypatch.setattr("src.utils.logger.config", fake_config)`（按模块对象打补丁），或测 `setup_logger` 时显式传 `log_file=tmp_path/...`。注意 `tests/test_utils.py` 已引入 `setup_logger`，新增日志用例请沿用显式文件参数。

### 7.2 非确定性与外部依赖

5. **非确定性必须 mock。**
   - `src/core/screenshot.py:56, 78, 87` 使用 `random.sample`（截图帧挑选）；
   - `src/core/picturebed.py:377` `random.sample('0123456789', 6)` 生成图片文件名的随机后缀。
   - 两者都会让断言在多次运行间漂移。测试应 `monkeypatch.setattr(random, "sample", ...)` 或用固定种子；`generate_image_filename` 的用例只断言格式 `%Y%m%d-%H%M%S-6位数字.png`，不断言具体值。

6. **网络、MediaInfo、硬链接全部需要打桩。**   - **网络**：`ptgen` / `picturebed` / `poster` / `autofeed` 全部走 `requests`，一律 `monkeypatch.setattr(requests, "get"/"post", ...)`，用 `conftest.FakeResponse` 构造响应（它实现了 `.json()` / `.iter_content()` / `.raise_for_status()`）。
   - **MediaInfo**：`get_media_info` / `get_video_info` 依赖 `pymediainfo.MediaInfo.parse`，用 `conftest.make_track(...)` 造假 track、`fake_mediainfo` fixture 注入；注意 `rename` 与 `mediainfo` 两个模块**各自 import 了 `MediaInfo`**，`fake_mediainfo` 已同时打补丁到 `src.core.rename` 与 `src.core.mediainfo` 两处，手写补丁时别漏。
   - **硬链接**：`src/core/rename.py:575, 601` 调 `os.link`，`:617` 判 `errno.EXDEV`。跨文件系统场景需 `monkeypatch.setattr(os, "link", raise_exc)` 抛带 `errno.EXDEV` 的 `OSError`，否则在单盘 CI 上该分支不可达。

### 7.3 PyQt6 与 GUI 测试现状

7. **PyQt6 已安装，但当前 0 个 GUI 测试。**
   - 本机实测 `import PyQt6` 成功，因此**无法用「未安装」作为跳过理由**；`src/gui/startgui.py` 与 `src/gui/ui_tools.py` 覆盖率 0% 纯粹是因为**还没有人写 GUI 测试**，不是因为环境缺失。
   - 写 GUI 测试时的注意点：
     - 必须设 `QT_QPA_PLATFORM=offscreen`（CI/无头环境），否则 `QApplication` 构造会因缺少显示设备而失败；
     - 优先直接调用 handler / 线程类的 `run()`（不 `start()`），绕过事件循环与 `QApplication`；
     - `startgui.py` import 时会拉起大量 Qt 对象与全局线程，仅在测试模块内 import 即可，勿在 `conftest.py` 顶层 import（会给全部 362 条用例增加开销）。
   - 具体到方法级建议见 §4.9。

### 7.4 文档与版本一致性

8. **过时文档的两处，不要被误导。**
   - `docs/DEVELOPMENT.md` 的「测试策略」段声称存在 `test_core.py` / `test_api.py` / `test_gui.py`——**这三个文件不存在**，真实清单见本文 §6.1。
   - 本文的**旧版 §6** 声称「7 个测试文件」，同样过时——以当前 §6.1 的 20 个测试文件 + `conftest.py`、362 条用例为准。
9. **版本号两处不同步**：`pyproject.toml` 为 `2.0.0`，`src/config/__init__.py` 的 `__version__` 与 `GUI_VERSION` 默认值为 `1.4.5`。写涉及版本断言的测试时先确认读的是哪一个，别硬编码。

---

## 8. CLI 交互式管线（src/main_cli.py）

> 本节是旧版文档完全缺失的部分。`src/main_cli.py`（1966 行）是与 GUI、API **并列的第三套完整发布管线**，且它是**唯一一套不需要 Qt 就能端到端跑通**的实现——对测试而言价值最高：GUI 的每一步流水线都能在这里找到无界面、可注入的对应物。

### 8.1 形态

| 项 | 内容 |
|---|---|
| 交互方式 | **prompt_toolkit 交互式向导**。没有子命令、没有 `argparse`、没有 `click`（`pyproject.toml` 的依赖里列了 `click` 但**全仓未使用**） |
| 启动 | `python src/main_cli.py`（`Makefile` 的 `run-cli`）；`pyproject.toml` 的 `[project.scripts]` **只有** `publish-helper-gui` / `publish-helper-api`，**没有 CLI 的 console script** |
| 路径补全 | 自定义 `PathCompleterWithSlash(PathCompleter)`（`:56`），在唯一匹配且目标是目录时给补全结果补上路径分隔符；`prompt_path()`（`:281`）绑定了 Tab 键在其上刷新补全 |
| 退出码 | 三条管线各返回 `True`/`False`，`main()` 末尾 `return 0 if success else 1`（`:1953`）；中途校验失败直接 `return 1`（如空标题 `:1751`、空路径 `:1844`）；用户取消返回 `0`（`:1728`） |

### 8.2 入口编排（`main()`，`:1719`）

1. `print_header()`（`:217`）+ `print_settings_summary()`（`:224`）——后者逐个打印 settings 开关的启用状态（`_status()`，`:247`）。
2. `prompt_media_type()`（`:334`）：`1/2/3` = 电影 / 电视剧 / 短剧，`0` 或 `q` 退出。
3. 按类型收集参数：
   - **电影 / 电视剧**：资源链接（豆瓣 / IMDb URL）+ 季数 + 开始集数。
   - **短剧**（不走 PT-Gen，全部手输）：资源名称、年份、产地（5 选，`:1770` 附近的 `area_map`）、类别、语言（5 选）、收费类型（3 选）、季数、开始集数。
4. `prompt_path("请输入视频文件或文件夹路径")` + 三重路径归一（`:1848-1930`）：
   - `strip('"\'')` 去粘贴时的包裹引号；
   - `os.path.expanduser` 展开 `~`；
   - `os.path.normpath` 归一分隔符；
   - 原路径**不存在时**才尝试 `os.path.realpath` 展开 Windows 8.3 短名（保留可用的短路径，只在需要时展开）。
5. 按类型分发 `process_movie` / `process_tv` / `process_playlet`。

### 8.3 三条管线

三条都是 `total_steps = 6`（`:411` / `:827` / `:1308`）的**线性流水线**，每步用 `print_step(n, total, message)`（`:252`）打点。**先收集全部用户选择再做任何 API 调用**（`source`/`team` 通过 `select_from_combo_box` 在开头取完）。

| 步骤 | 电影 `process_movie` `:409` | 电视剧 `process_tv` `:825` | 短剧 `process_playlet` `:1306` |
|---|---|---|---|
| 1 | 获取 PT-Gen 信息（主接口失败自动降级备用接口） | 同左 | **生成简介**（`get_playlet_description`，不调 PT-Gen） |
| 2 | 解析 PT-Gen 信息 | 解析 + **校验 PT-Gen 季数与输入季数**，不符时打印警告并**采用输入季数** | 获取视频信息 |
| 3 | 获取视频信息 | 获取视频信息 + **统计集数**（`get_video_files` 计文件数） | 生成文件名 |
| 4 | 生成文件名 | 生成文件名 | 生成摘要 |
| 5 | 生成摘要 | 生成摘要 | （无） |
| 6 | （无打印，见下） | （无打印，见下） | **重命名和后续处理**（`:1440`） |

**短剧的步骤编号有跳号**：它只有 4 个 `print_step`（1/2/3/4）加一个第 6 步，**没有第 5 步**。电影/电视剧的第 5 步「生成摘要」之后直接进入后续处理，未再打点。

后续处理（三条沿同一套顺序，第 6 步/摘要之后）：

1. **重命名**（受 `rename_file` 开关控制），按 `is_video_path`（`check_path_and_find_video` 的返回值）分两支：
   - **单文件（`==1`）且 `make_dir` 开启**：先 `move_file_to_folder` → 再 `rename_folder` 重命名目录 → 用 `check_path_and_find_video` 重新定位文件 → 最后 `rename_file` 重命名文件。目录与文件**都改**。
   - **单文件且 `make_dir` 关闭**：只 `rename_file`。
   - **目录（`==2`）**：先 `rename_folder` → 重新定位 → `rename_file`。
   - 任一步失败即 `return False`。
2. **MediaInfo**（`get_media_info`）——**在重命名之后**取，保证 MediaInfo 里的 `Complete name` 是重命名后的文件名；失败只警告并把 `media_info` 置空继续。
3. **硬链接**（受 `create_hard_link` 开关控制）。
4. **截图**：读 settings 的 `screenshot_storage_path`/`screenshot_number`/`screenshot_threshold`/起止百分比，调 `get_screenshot(..., screenshot_min_interval=0.01)`。
5. **缩略图**（受 `do_get_thumbnail` 控制）：成功后 `pictures.append(thumbnail_path)`——注意是**追加到末尾**（API 的 autoHandleVideo 是插到开头，口径不同）。
6. **上传图床**（受 `auto_upload_screenshot` 控制）：逐张 `upload_picture`；`delete_screenshot` 为真且上传成功才删本地；**上传失败时保留本地路径并 append 到结果列表**（不是丢弃）。
7. **制作种子**：`make_torrent(video_path, torrent_storage)`。
8. **生成 auto-feed 链接**：`get_auto_feed_link(...)`；成功后先试 `pyperclip.copy`，失败则走平台特定命令（Windows 用 `clip` 且以 **utf-16le** 编码喂入，其它平台用 `xclip`/`pbcopy` 与 utf-8），再失败则退化为把链接写到 `temp/auto_feed_link.txt` 并打印。

### 8.4 与 GUI / API 的差异（做测试时容易误设的期望）

| 项 | CLI | GUI / API |
|---|---|---|
| 缩略图位置 | `pictures.append(thumbnail_path)` 追加到**末尾** | `autoHandleVideo` 插到**开头** |
| `torrent_url` | **恒为空串**（`:754` / `:1239` / `:1652` 三处都写死 `""`，种子链接从未回填） | GUI 把种子路径填进 `torrent_url`；API 用 `request.base_url` 拼 `/getFile?filePath=` |
| 上传失败 | 保留本地路径并计入结果列表 | 记错误 |
| 二次确认 | 无交互确认，摘要打印后**直接执行后续操作** | GUI 有 `second_confirm_file_name` 二次确认；Playlet 一键启动在该开关为真时**直接早退** |
| 依赖 | 无 Qt；但 `pyperclip` 是可选（`import` 在 `try` 内） | GUI 强依赖 PyQt6 |

### 8.5 测试要点

- **最可测的入口**：`process_movie` / `process_tv` / `process_playlet` 都是**普通函数**（不是 Qt 槽），签名全是标量（`(resource_url, video_path)` / `(resource_url, video_path, season, episodes_start)` / 短剧 9 个参数），可以直接调用并把 `src.core.*` 全部 monkeypatch 掉。这是验证「重命名 + 截图 + 种子」编排顺序的最省力路径——比 GUI 的 offscreen 方案便宜得多。
- **交互层要 mock 的两处**：`prompt_path()` 与 `select_from_combo_box()`（后者会调 `get_combo_box_data` 读 `static/combo-box-data.json`，**必须 chdir 到 tmp** 以免污染真实 static）。`prompt_media_type()` 同理。
- **返回值契约**：三条管线的返回值是 `True`/`False`（不是 `(success, payload)` 元组）；`main()` 把 `False` 转成退出码 `1`。**中途校验失败是 `return 1` 而非 `False`**，测 `main()` 时要区分这两类。
- **降级路径值得单独测**：PT-Gen 主接口失败 → 备用接口（电影/电视剧第 1 步）；剪贴板三级降级（pyperclip → 平台命令 → 写文件）；`get_media_info` 失败后仍继续。
- **路径归一的边界**：带引号的路径、`~`、Windows 8.3 短名、以及 `PathCompleterWithSlash` 只在唯一匹配时补分隔符的行为。
- **不要在测试里真跑截图/种子**：`get_screenshot` 会调 `cv2`，`make_torrent` 会建 `.torrent` 文件。三者全部 mock。

---

---

## 9. 维护约定

本文的失效根源是「写完即停更」：上一版停在 `5c8f479`，之后 3 个提交把整章覆盖矩阵写废，且多处把 bug 写成了正确行为。为避免重演：

1. **改 `src/` 就要改本文**。以下三类改动必须同步：
   - 函数签名 / 返回形状 / 错误消息文本 → 改对应 §2.x；
   - API 路由、参数名、statusCode → 改 §5；
   - 新增或修改测试 → 改 §6（用例数、覆盖率数字、gap 清单都要重新实测）。
2. **不要凭记忆写数字**。§3.1 的键数、§5 的 statusCode 计数、§6 的覆盖率与用例数都是实测值，请用命令重新测（§6.3 列了命令）。
3. **记录 bug 时保持中立**：写清「代码当前如此 + 行号 + 实测行为」，不要写成期望行为，也不要在文档里直接改成建议值——文档是现状的镜像。
4. **标注版本与行号的时效**：行号会随代码移动；大改动后建议用文中的函数名/关键串重新定位，而不是硬信行号。
