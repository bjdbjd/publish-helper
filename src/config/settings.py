"""Application settings and configuration management."""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包产物中。"""
    return bool(getattr(sys, "frozen", False))


def get_writable_base_dir() -> Path:
    """用户数据根目录（可写、需跨次运行持久化）。

    - 源码运行：项目根（``src/config/settings.py`` 的上三级）。
    - 打包运行：**可执行文件所在目录**，而不是 ``sys._MEIPASS``。

    这一点是打包的关键：onefile 模式下 ``_MEIPASS`` 是每次启动新建、退出即删的
    临时解包目录。若把 BASE_DIR 指向它，用户改过的 ``static/settings.json`` 会在
    下次启动时被重置，``media/``、``logs/`` 也会随之消失。
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_bundle_dir() -> Path:
    """只读资源根目录（打包产物内随包携带的 static/ 等）。

    - 打包运行：``sys._MEIPASS``（PyInstaller 解包目录）。
    - 源码运行：项目根，与 ``get_writable_base_dir()`` 相同。
    """
    return Path(getattr(sys, "_MEIPASS", get_writable_base_dir()))


class Config:
    """Application configuration class."""

    def __init__(self):
        """Initialize configuration by loading environment variables."""
        # Load environment variables from .env file
        load_dotenv()

        # Base paths
        # BASE_DIR/BUNDLE_DIR: 可写数据根 / 只读资源根。开发态两者相同；
        # 打包态分别为「exe 所在目录」与「_MEIPASS」。
        self.BASE_DIR = get_writable_base_dir()
        self.BUNDLE_DIR = get_bundle_dir()
        self.SRC_DIR = self.BASE_DIR / "src"
        self.STATIC_DIR = self.BASE_DIR / "static"
        self.TEMP_DIR = self.BASE_DIR / "temp"
        self.MEDIA_DIR = self.BASE_DIR / "media"
        self.LOGS_DIR = self.BASE_DIR / "logs"

        # 打包态首次运行：把随包的只读 static/ 播种到可写目录
        self._seed_from_bundle()

        # 打包态把 cwd 归一到 BASE_DIR：core 层多处用 combine_directories()
        # （= Path.cwd()/相对路径）读 static/*.json、写 temp/、media/。
        # 用户从快捷方式启动时 cwd 常是 C:\Windows\System32 之类，
        # 会导致这些相对读取全部落空。开发态不 chdir，保持既有 cwd 语义。
        if is_frozen():
            try:
                os.chdir(self.BASE_DIR)
            except OSError:
                pass

        # Ensure directories exist
        self._create_directories()

        # API Configuration
        self.API_HOST = os.getenv("API_HOST", "0.0.0.0")
        self.API_PORT = int(os.getenv("API_PORT", "15372"))
        self.API_DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"

        # GUI Configuration
        self.GUI_TITLE = os.getenv("GUI_TITLE", "Publish Helper")
        self.GUI_VERSION = os.getenv("GUI_VERSION", "2.0.0")

        # PT-Gen Configuration
        self.PTGEN_API_URL = os.getenv("PTGEN_API_URL", "")
        self.PTGEN_API_KEY = os.getenv("PTGEN_API_KEY", "")

        # Image Hosting Configuration
        self.IMAGE_HOST_TYPE = os.getenv("IMAGE_HOST_TYPE", "freeimage")
        self.IMAGE_HOST_API_URL = os.getenv("IMAGE_HOST_API_URL", "")
        self.IMAGE_HOST_API_KEY = os.getenv("IMAGE_HOST_API_KEY", "")

        # Media Info Configuration
        self.MEDIAINFO_PATH = os.getenv("MEDIAINFO_PATH", "")

        # Logging Configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE = self.LOGS_DIR / os.getenv("LOG_FILE", "app.log")

    def _seed_from_bundle(self) -> None:
        """把随包携带的只读资源播种到可写目录（仅打包态、且仅在缺失时）。

        ``static/settings.json`` 是用户的配置载体：**只在不存在时写入**，
        绝不覆盖——否则升级安装包就会抹掉用户已改好的设置与密钥。
        """
        if not is_frozen() or self.BUNDLE_DIR == self.BASE_DIR:
            return

        bundled_static = self.BUNDLE_DIR / "static"
        if not bundled_static.is_dir():
            return

        target_static = self.STATIC_DIR
        target_static.mkdir(parents=True, exist_ok=True)
        for item in bundled_static.iterdir():
            if not item.is_file():
                continue
            destination = target_static / item.name
            # settings.json：存在即保留用户版本（升级不覆盖配置）
            if destination.exists():
                continue
            try:
                shutil.copy2(item, destination)
            except OSError:
                # 播种失败不应阻止启动：settings.json 缺失时
                # SettingsManager 会用内置默认值自建。
                pass

    def _create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            self.STATIC_DIR,
            self.TEMP_DIR,
            self.TEMP_DIR / "pic",
            self.TEMP_DIR / "torrent",
            self.MEDIA_DIR,
            self.LOGS_DIR,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_temp_pic_dir(self) -> Path:
        """Get temporary picture directory."""
        return self.TEMP_DIR / "pic"

    def get_temp_torrent_dir(self) -> Path:
        """Get temporary torrent directory."""
        return self.TEMP_DIR / "torrent"

    def is_development(self) -> bool:
        """Check if running in development mode."""
        return os.getenv("ENVIRONMENT", "production").lower() == "development"


# Global configuration instance
config = Config()


class ImageHostConfig:
    """Configuration for different image hosting services."""

    SUPPORTED_HOSTS = {
        "freeimage": {
            "name": "FreeImage",
            "api_url": "https://freeimage.host/api/1/upload",
            "requires_key": False,
        },
        "imgbb": {
            "name": "ImgBB",
            "api_url": "https://api.imgbb.com/1/upload",
            "requires_key": True,
        },
        "imagehub": {
            "name": "ImageHub",
            "api_url": "https://www.imagehub.cc/api/1/upload",
            "requires_key": False,
        },
        "pixhost": {
            "name": "PixHost",
            "api_url": "https://api.pixhost.to/images",
            "requires_key": False,
        },
        "bohe": {
            "name": "薄荷图床",
            "api_url": "",  # To be configured by user
            "requires_key": True,
        },
        "lsky-pro": {
            "name": "兰空图床",
            "api_url": "",  # To be configured by user
            "requires_key": True,
        },
        "chevereto": {
            "name": "Chevereto",
            "api_url": "",  # To be configured by user
            "requires_key": True,
        },
    }

    @classmethod
    def get_host_config(cls, host_type: str) -> Optional[dict]:
        """Get configuration for a specific image host."""
        return cls.SUPPORTED_HOSTS.get(host_type)

    @classmethod
    def get_supported_hosts(cls) -> list[str]:
        """Get list of supported image host types."""
        return list(cls.SUPPORTED_HOSTS.keys())
