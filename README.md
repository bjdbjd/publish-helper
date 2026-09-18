# Publish Helper 2.0

> 🚀 **现代化PT资源发布助手** - 重构版本

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-GPL%20v3-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## ✨ 重构亮点

本版本是对原项目的全面重构，在**完全保持向后兼容性**的同时，大幅提升了代码质量和开发体验：

🏗️ **现代化架构** - 模块化设计，符合Python最佳实践  
⚙️ **智能配置** - 分层配置系统，支持环境变量覆盖  
📝 **专业日志** - 彩色输出，结构化记录  
🛡️ **类型安全** - 完整的异常体系和类型检查  
🧪 **测试保证** - 完整的测试框架和代码覆盖  
🔧 **开发工具** - 自动化代码质量保证  

## 🎯 功能特性

### 核心功能

- 🎬 **自动获取PT-Gen简介信息** - 支持多个API源
- 📋 **MediaInfo信息提取** - 智能媒体分析
- 📸 **自动截图生成** - 可配置截图参数
- 🖼️ **缩略图制作** - 自动生成预览图
- ☁️ **图床上传** - 支持多种图床服务
- 🏷️ **智能命名** - 根据模板自动生成标题和文件名
- 📁 **文件整理** - 自动创建目录结构
- 🌱 **种子制作** - 一键生成torrent文件

### 高级功能

- 📺 **剧集批量处理** - 支持批量重命名和分集处理
- 🔗 **硬链接支持** - 节省存储空间
- 🎭 **短剧特殊处理** - 专门的短剧命名和简介生成
- 🚀 **API接口** - 完整的RESTful API
- 🐳 **Docker支持** - 容器化部署

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/your-username/publish-helper.git
cd publish-helper

# 安装依赖
pip install -r requirements.txt

# 配置环境（可选）
cp .env.example .env
# 编辑 .env 文件配置你的API密钥
```

### 系统依赖

本项目使用 [pymediainfo](https://pypi.org/project/pymediainfo/) 提取视频信息，需要 `libmediainfo` 库支持。

**Windows & macOS:** 无需手动安装，pymediainfo 已打包所需库文件。

**Linux:** 需要手动安装 `libmediainfo`：

```bash
# Debian/Ubuntu
apt install libmediainfo0v5

# CentOS/RHEL/Fedora
yum install libmediainfo  # 或 dnf install libmediainfo

# Arch Linux
pacman -S libmediainfo
```

### 中文字体（Linux 服务器）

如果在 Linux 服务器上运行时中文显示为方块或乱码，需要安装中文字体：

```bash
# Debian/Ubuntu
apt install fonts-wqy-zenhei fonts-wqy-microhei
# 或使用 Noto CJK 字体（更全面）
apt install fonts-noto-cjk

# CentOS/RHEL/Fedora
yum install wqy-zenhei-fonts

# Arch Linux
pacman -S wqy-zenhei

# 刷新字体缓存
fc-cache -f -v
```

### 运行

```bash
# GUI模式
python src/main_gui_new.py

# API模式  
python src/main_api_new.py

# 原有方式依然支持
python src/main_gui.py
python src/main_api.py
```

### Docker部署

```bash
# 使用docker-compose
docker-compose up -d

# 或直接构建
docker build -t publish-helper .
docker run -p 15372:15372 publish-helper
```

## ⚙️ 配置说明

### 环境变量配置

创建 `.env` 文件：

```bash
# API配置
API_PORT=15372
API_DEBUG=false

# PT-Gen配置
PTGEN_API_URL=https://ptgen.agsvpt.work/
PTGEN_API_KEY=your_api_key

# 图床配置
IMAGE_HOST_TYPE=freeimage
IMAGE_HOST_API_KEY=your_image_host_key

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### 支持的图床

#### 免费图床

- [FreeImage](https://freeimage.host/) - 无需API密钥
- [ImgBB](https://imgbb.com/) - 需要API密钥
- [ImageHub](https://www.imagehub.cc/) - 无需API密钥
- [PixHost](https://pixhost.to/) - 无需API密钥

#### 商业图床

- [薄荷图床](https://zixiaoyun.com/) - 需要API密钥

#### 自建图床

- [兰空图床](https://github.com/lsky-org/lsky-pro) - 开源图床方案
- [Chevereto](https://github.com/rodber/chevereto-free) - 开源图床方案

## 🛠️ 开发指南

### 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 安装pre-commit钩子
pre-commit install

# 运行测试
pytest tests/ -v --cov=src
```

### 代码质量

```bash
# 代码格式化
black src/ tests/
isort src/ tests/

# 代码检查
flake8 src/ tests/
mypy src/

# 或使用Makefile
make format  # 格式化代码
make lint    # 代码检查
make test    # 运行测试
```

### 项目结构

```
publish-helper/
├── src/
│   ├── config/            # 配置管理
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── utils/             # 工具模块
│   │   ├── logger.py      # 日志系统
│   │   ├── exceptions.py  # 异常定义
│   │   └── file_utils.py  # 文件工具
│   ├── core/              # 核心功能
│   ├── gui/               # GUI界面
│   ├── api/               # API接口
│   ├── main_gui_new.py    # GUI入口
│   └── main_api_new.py    # API入口
├── tests/                 # 测试代码
├── docs/                  # 文档
├── requirements.txt       # 生产依赖
├── requirements-dev.txt   # 开发依赖
└── docker-compose.yml     # Docker配置
```

## 📚 文档

- 📖 [开发者指南](docs/DEVELOPMENT.md) - 详细的开发文档
- 🔧 [重构说明](FORK_PROPOSAL.md) - 重构内容和改进说明
- 🐳 [Docker部署](docker-compose.yml) - 容器化部署指南
- ⚙️ [配置参考](.env.example) - 完整的配置选项

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 代码规范

- 遵循 PEP 8 代码风格
- 使用 Black 进行代码格式化
- 添加类型注解
- 编写测试用例
- 更新文档

## 📝 更新日志

### v2.0.0 - 架构重构版 (2025-07-21)

#### 🚀 新增功能

- 现代化项目架构
- 分层配置管理系统
- 专业日志框架
- 完整的异常处理体系
- 自动化开发工具链
- 完整的测试框架

#### 🔧 改进

- 代码质量大幅提升
- 更好的错误处理
- 改进的Docker配置
- 完善的文档系统

#### 🛡️ 兼容性

- 完全向后兼容
- 保持所有原有功能
- 现有配置自动迁移

## 📞 支持

- 📧 [提交Issue](https://github.com/bjdbjd/publish-helper/issues)
- 💬 [讨论区](https://github.com/bjdbjd/publish-helper/discussions)
- 📖 [Wiki文档](https://github.com/bjdbjd/publish-helper/wiki)

## 📄 许可证

本项目基于 [GNU General Public License v3.0](LICENSE) 开源。

## 🙏 致谢

### 贡献者

- **bjdbjd** - 原作者和主要维护者
- **Pixel-LH** - 核心贡献者
- **EasonWong0603** - 功能开发
- **sertion1126** - Docker支持
- **TommyMerlin** - 功能改进

### 特别感谢

感谢所有为项目贡献代码、报告问题、提供建议的开发者和用户！

---

如果这个项目对你有帮助，请给我们一个 ⭐ **Star**！
