# 开发者指南

## 项目结构

```
publish-helper/
├── src/                    # 源代码
│   ├── api/               # API模块
│   ├── core/              # 核心功能模块
│   ├── gui/               # GUI模块
│   ├── config/            # 配置模块
│   ├── utils/             # 工具模块
│   ├── main_gui.py        # GUI入口点
│   ├── main_api.py        # API入口点
│   └── main_cli.py        # CLI入口点（交互式命令行）
├── tests/                 # 测试代码
├── docs/                  # 文档
├── static/                # 静态资源
├── requirements.txt       # 生产依赖
├── requirements-dev.txt   # 开发依赖
├── .env.example          # 环境配置示例
├── docker-compose.yml    # Docker编排
├── Makefile              # 开发任务
└── pyproject.toml        # 项目配置
```

## 开发环境设置

### 1. 克隆项目

```bash
git clone https://github.com/bjdbjd/publish-helper.git
cd publish-helper
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或者
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
# 安装开发依赖
make install-dev

# 或者手动安装
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. 配置环境

```bash
cp .env.example .env
# 编辑 .env 文件，配置你的API密钥等
```

### 5. 设置pre-commit钩子

```bash
pre-commit install
```

## 开发工作流

### 代码规范

本项目遵循以下代码规范：

- **PEP 8** - Python代码风格指南
- **Black** - 代码格式化
- **isort** - 导入排序
- **flake8** - 代码检查
- **mypy** - 类型检查

### 运行代码检查

```bash
# 格式化代码
make format

# 检查代码质量
make lint

# 运行所有检查
make check-all
```

### 运行测试

```bash
# 运行所有测试
make test

# 运行测试并生成覆盖率报告
make test-coverage
```

### 运行应用

```bash
# 运行GUI版本
make run-gui

# 运行API版本
make run-api

# 运行CLI版本（交互式命令行）
make run-cli
```

也可以直接用对应入口脚本启动：

```bash
python src/main_gui.py    # GUI
python src/main_api.py    # API
python src/main_cli.py    # CLI
```

三个入口均自包含：基于 `Path(__file__)` 自举项目根与 `src/` 到 `sys.path`，无论从哪个工作目录都能启动。

## 架构设计

### 配置管理

项目使用分层配置系统：

1. **默认配置** - 在代码中定义的默认值
2. **配置文件** - `static/settings.json`
3. **环境变量** - 优先级最高

```python
from src.config.settings import config
from src.core.settings_tool import get_settings

# 使用全局配置
api_port = config.API_PORT

# 使用设置管理器
screenshot_num = get_settings('screenshot_number', '3')
```

### 日志系统

使用结构化日志系统：

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Processing started")
logger.error("Error occurred", exc_info=True)
```

### 异常处理

定义了专用异常类：

```python
from src.utils.exceptions import MediaInfoError, ScreenshotError

try:
    process_media()
except MediaInfoError as e:
    logger.error(f"Media processing failed: {e}")
```

### 文件操作

使用工具函数进行文件操作：

```python
from src.utils.file_utils import ensure_directory, safe_filename

# 确保目录存在
output_dir = ensure_directory(config.TEMP_DIR / "output")

# 创建安全的文件名
safe_name = safe_filename("unsafe<>filename.txt")
```

## 测试策略

### 测试结构

```
tests/
├── test_config.py      # 配置测试
├── test_utils.py       # 工具函数测试
├── test_core.py        # 核心功能测试
├── test_api.py         # API测试
└── test_gui.py         # GUI测试
```

### 编写测试

```python
import pytest
from src.utils.file_utils import safe_filename

class TestFileUtils:
    def test_safe_filename(self):
        unsafe = "file<>name.txt"
        safe = safe_filename(unsafe)
        assert '<' not in safe
        assert '>' not in safe
```

### 运行特定测试

```bash
# 运行特定文件的测试
pytest tests/test_utils.py -v

# 运行特定测试函数
pytest tests/test_utils.py::TestFileUtils::test_safe_filename -v
```

## Docker开发

### 构建镜像

```bash
make docker-build
```

### 运行容器

```bash
make docker-run
```

### 开发模式

```bash
# 使用volume挂载进行开发
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## 发布流程

### 1. 版本管理

更新版本号：

- `src/config/__init__.py`
- `pyproject.toml`

### 2. 运行完整测试

```bash
make check-all
```

### 3. 构建包

```bash
make build
```

### 4. 创建发布

- 创建Git标签
- 上传到GitHub Releases
- 更新Docker镜像

## 贡献指南

### 提交代码

1. Fork项目
2. 创建功能分支
3. 提交代码并包含测试
4. 运行代码检查
5. 创建Pull Request

### 提交消息格式

```
feat: 添加新功能
fix: 修复bug
docs: 更新文档
style: 代码格式调整
refactor: 重构代码
test: 添加测试
chore: 构建相关更新
```

### 代码审查

所有代码需要通过：

- 自动化测试
- 代码质量检查
- 至少一人代码审查

## 常见问题

### Q: 如何添加新的图床支持？

A: 在 `src/config/settings.py` 的 `ImageHostConfig` 中添加新的图床配置，然后在相应的上传模块中实现API调用。

### Q: 如何修改命名模板？

A: 编辑 `static/settings.json` 文件或通过GUI界面修改模板。模板支持变量替换，如 `{title}`、`{year}` 等。

### Q: 如何调试API？

A: 设置环境变量 `LOG_LEVEL=DEBUG`，然后查看详细日志输出。

## 性能优化

### 1. 异步处理

对于耗时操作（如截图、上传），使用异步处理避免阻塞界面。

### 2. 缓存机制

对于重复计算的结果（如媒体信息），实现缓存机制。

### 3. 资源管理

及时释放大文件的内存占用，使用生成器处理大数据集。

## 安全考虑

### 1. 输入验证

所有用户输入都需要验证和清理。

### 2. 文件路径

使用 `pathlib` 处理文件路径，避免路径遍历攻击。

### 3. API安全

实现速率限制和输入验证。
