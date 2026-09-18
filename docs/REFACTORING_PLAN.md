# 重构计划：核心/配置层清理 + 文件鉴权加固

> 本文件是重构计划的**持久文档**，用作跨会话的参考基准，避免遗忘。
> 计划源文件：`C:\Users\11064\.claude\plans\greedy-knitting-lemur.md`
> 当前范围：**「先把核心/配置层清理干净」**（用户确认）+ **「文件鉴权需要处理」**（用户点名）。

---

## 一、背景 / Context

对 `publish-helper`（PyQt6 桌面 + Flask API 的 PT 发种工具）做重构。深度分析（遍历全部 32 个 `.py` 文件 + 3 个并行探索 agent 全量核查 git 历史/核心模块/GUI-API 层）后发现核心层存在以下明显问题：

1. **双套 settings 系统**：`src/core/settings_tool.py` 是带类型注解、意图中的新实现（`SettingsManager`），但**零模块引用**（`grep -rl "settings_tool" src/` 为空）；全部 11 个消费方都 `from src.core.tool import get_settings` 使用`tool.py` 里无类型的旧版。两套对同一 `static/settings.json` 语义已有分歧（tool.py 有 env 覆盖 + `{category}→{categories}` 迁移副作用，settings_tool 没有）。
2. **零类型注解**：`tool.py` 28 个顶层函数、`rename.py` 10 个顶层函数**全部无注解**，而 `pyproject.toml` 配置了 `disallow_untyped_defs = true` → mypy 严格模式直接不通过。`settings_tool.py` 是全项目唯一全注解文件。
3. **字符串布尔**：所有布尔设置存成 `'True'/'False'` 字符串，28 处 `== 'True'` 比较，无真正 `bool`。
4. **重复代码**：`video_extensions` 列表在 `tool.py` 复制 2 份；`min_widths` 分辨率表在 tool.py/rename.py 定义 3 次；JSON 初始化模式（不存在→写默认→读→缺 key 补）在 `get_settings`/`get_combo_box_data`/`get_abbreviation` 重复 3 次；tool.py 与 rename.py 各自实现一套 PT-Gen 描述解析。
5. **`/api/getFile` 路径鉴权缺陷**：`target_path.startswith(temp_path)` 是字符串前缀匹配——`temp_evil/...` 可绕过；`os.path.abspath` 不解析符号链接，`temp/` 内软链可逃逸读任意文件；`temp_path` 基准基于 `cwd` 而非 `config.TEMP_DIR`。

> 注：`static/settings.json` 中确有真实密钥（`picture_bed_api_token`、`pt_gen_auth_secret`）被提交进 git，但**用户已确认这些是公开 demo 密钥，无需轮换或移出版本库**。本轮要处理的是 `/api/getFile` 的**文件访问鉴权**。

---

## 二、目标

- 合并为**单套** settings 系统（以 `settings_tool.py` 为唯一实现），移除 `tool.py` 旧版重复实现。
- 为 `tool.py`/`rename.py` 顶层函数补类型注解（通过 mypy 严格模式 `mypy src/core/`）。
- 布尔设置从 `'True'` 字符串改为真正的 `bool`，消除 28 处 `== 'True'`。
- 抽公共常量（`VIDEO_EXTENSIONS`、分辨率表、JSON 初始化 helper）。
- 加固 `/api/getFile` 文件访问鉴权。
- **不改变业务逻辑**（输出、文件名模板、API 行为不变）；风险低、逐阶段可验证。

---

## 三、关键设计决策

### D1. settings 合并的导入兼容问题（最关键）

`settings_tool.py` 用扁平导入 `from config.settings import config`，要求 `src/` 在 `sys.path` 上——只有 `main_gui_new.py`/`main_api_new.py`（`_new` 入口）会插入 `src/`；旧入口 `main_gui.py`/`main_api.py`（PyInstaller 打包用）不插。直接 repoint 会让旧入口在导入 `settings_tool` 时抛 `ModuleNotFoundError: config`。

**方案**：在 `settings_tool.py` 顶部加导入兼容桥：

```python
try:
    from config.settings import config
    from utils.exceptions import ConfigurationError
    from utils.file_utils import ensure_directory
    from utils.logger import get_logger
except ModuleNotFoundError:      # 旧入口未把 src/ 加入 sys.path
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from config.settings import config
    from utils.exceptions import ConfigurationError
    from utils.file_utils import ensure_directory
    from utils.logger import get_logger
```

（`parents[2]` = 项目根，`/ "src"` 即 `src/`。）保证两套入口都能工作。

### D2. `combine_directories` 的归属

`combine_directories(path)` = `os.path.join(os.getcwd(), path)`，被 API 用来拼 `media/`、`temp/`，且被 tool.py 的 `get_combo_box_data`/`get_abbreviation` 用。它依赖 `cwd`，与 `config.STATIC_DIR/TEMP_DIR/MEDIA_DIR` 是两套路径来源。**本轮不改路径语义**（cwd-relative 是既有行为），只把它**保留在 tool.py**，从 settings 合并中剥离——它不属于 settings I/O。

### D3. 布尔化策略（低风险）

不一次性把 `static/settings.json` 里的 `'True'` 硬改 `true`（持久化格式 + 用户本地/旧版本会不一致）。**在读取层归一**：

- `SettingsManager.get_setting` 对布尔型 key：字符串 `'True'/'False'` → 返回 `bool`；其余保持原样。
- 调用方 28 处 `== 'True'` 改为直接 truthy 判断（`if get_settings('rename_file'):`）。
- `_get_default_settings` 布尔 key 用真 `True/False`。

保证新代码用真布尔；旧文件里的 `'True'` 字符串自动归一为 `bool`，向后兼容。

### D4. `/api/getFile` 加固

```python
from pathlib import Path
temp_root = Path(config.TEMP_DIR).resolve()      # 基准：config 而非 cwd
target_path = Path(file_path).resolve()          # 归一：软链 + .. 全解析
if temp_root not in target_path.parents and target_path != temp_root:
    return jsonify({... 'UNAUTHORIZED_ACCESS_ERROR'}), 401
if not target_path.exists() or not target_path.is_file():
    return jsonify({... 'FILE_NOT_FOUND'}), 404
return send_file(str(target_path), as_attachment=True)
```

`Path.resolve()` 默认 `strict=False`，不存在时也解析 `..`/软链，故边界检查放 `exists` 之前。`temp_root in target_path.parents` 是路径分隔符边界的成员判断，天然杜绝 `temp_evil` 前缀绕过。

---

## 四、实施步骤

### 阶段 0：把本计划固化到仓库（首个交付物）

产出 `docs/REFACTORING_PLAN.md`（本文档），作为跨会话持久参考。提交风格按仓库中文 `[docs]:[...]`。

### 阶段 1：settings 系统合并（核心）

**1.1** `src/core/settings_tool.py`：
- 加 D1 导入兼容桥。
- `_get_default_settings()` 与 tool.py 的 `standard_values` 合并，取较新值：`pt_gen_api_url` = 新版服务、`pt_gen_auth_secret = hares.23663`、`screenshot_threshold` 统一 `30.0`、`api_port` 统一 `15372`（settings.py 的 `API_PORT` env 默认也是 `15372`）。
- 补 `{category}→{categories}`、`{total_episode}→{total_episodes}` 迁移逻辑（沿用 tool.py 现行为）。
- `get_setting` 增加布尔归一（D3）。

**1.2** `src/core/tool.py`：
- **删除** `get_settings`(54-180)、`update_settings`(14-40)、`get_settings_json`(183-191)、`update_settings_json`(194-198)。
- 在顶部 **re-export** 以切换实现、消费方零改动：
  ```python
  from src.core.settings_tool import get_settings, update_settings, get_settings_json, update_settings_json
  ```
  11 个现有 `from src.core.tool import get_settings` 消费方一行不改，实现已切单一套。
- `combine_directories` 保留在 tool.py（D2）。

**1.3 验证**：`get_settings('rename_file')` 读取与改前一致；`_new` 与旧入口都能启动。

### 阶段 2：布尔化 + 类型注解

**2.1** 布尔化（D3）：`_get_default_settings` 用真 bool；28 处 `== 'True'` 改 truthy（分布：`startgui.py` ~15、`main_cli.py` ~10、`startapi.py` ~3）。
**2.2** 类型注解：`tool.py` 28 函数、`rename.py` 10 函数。优先高价值：`check_path_and_find_video`、`get_data_from_pt_gen_description`、`get_pt_gen_info`、`get_name_from_template`（16 参）、`make_torrent`、`create_hard_link`。**本轮不引入 Enum**（改 25+ 调用点，属「拆分巨型」阶段）。
**2.3 验证**：`mypy src/core/` 无 `disallow_untyped_defs` 报错；`pytest tests/ -q` 通过。

### 阶段 3：抽公共常量 + 去重

**3.1** `video_extensions`（tool.py 503、662 两处）→ 模块级 `VIDEO_EXTENSIONS`。
**3.2** 分辨率表 `min_widths`（tool.py `get_abbreviation` 422-430 与 rename.py `load_min_widths_from_json` 363-371 两处）→ 收敛一处。
**3.3** JSON 初始化模式（`get_settings`/`get_combo_box_data`/`get_abbreviation` 重复 3 次）→ 抽 `load_or_initialize_json(path, defaults)` 放 `utils/file_utils.py`。

### 阶段 4：`/api/getFile` 鉴权加固（D4）

修改 `src/api/startapi.py:1640-1683` 的 `api_get_file`。验证负面用例全被拒。

---

## 五、明确不做（本轮范围外）

- 拆分 `startgui.py`(2458)/`startapi.py`(2414)/`main_cli.py`(1970) 巨型文件与 GUI/API/CLI 三套重复管线。
- `check_path_and_find_video` 魔数 → Enum（改 25+ 调用点）。
- 移除密钥/轮换（用户已确认密钥公开）。
- `from src.` → 相对导入全量转换。
- 双套 PT-Gen 解析器（`get_data_from_pt_gen_description` vs `get_pt_gen_info`）合并。

---

## 六、涉及文件清单

| 文件 | 动作 |
|---|---|
| `src/core/settings_tool.py` | 加导入桥、合并默认值、布尔归一 |
| `src/core/tool.py` | 删 4 个 settings 函数、re-export、抽 `VIDEO_EXTENSIONS`、补注解、抽 JSON helper |
| `src/core/rename.py` | 补 10 个函数注解、收敛分辨率表 |
| `src/utils/file_utils.py` | 新增 `load_or_initialize_json` |
| `src/api/startapi.py` | 修 `api_get_file` 鉴权 |
| `src/gui/startgui.py`、`src/main_cli.py`、`src/api/startapi.py` | 28 处 `== 'True'` → truthy |

---

## 七、验证清单

0. `docs/REFACTORING_PLAN.md` 已存在且可独立阅读（含目标、问题、步骤、验证、范围外）。
1. `python -m pytest tests/ -q` — 全绿。
2. `mypy src/core/` — 无 `disallow_untyped_defs` 报错。
3. `python src/main_gui_new.py` 启动 GUI（无异常）。
4. `python src/main_api_new.py` 启动 API；`curl /api/settings` 返回 200；`/api/getFile` 负面用例（前缀绕过/越权/不存在）全被拒。
5. `get_settings('rename_file')` 等 key 读取值与改前一致（布尔已归一为 True）。
