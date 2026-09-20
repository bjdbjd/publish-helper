"""
Publish Helper  Copyright (C) 2023  BJD
This program comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
This is free software, and you are welcome to redistribute it
under certain conditions; type `show c' for details.

The licensing of this program is under the GNU General Public License version 3 (GPLv3) or later.
For more information on this license, you can visit https://www.gnu.org/licenses/gpl-3.0.html
"""
"""
打包编译方式(Windows)：安装Python 3.10，执行pip install pyinstaller，安装“docs/requirements.txt”中的所有相关模块后，在项目根目录（README文件所在目录）下执行下面的代码：

pyinstaller --paths="src;." -F -w -i static/ph-bjd.ico src/main_gui.py -n "Publish Helper.exe"
xcopy static dist\\static /E /I /Y
mkdir dist\\media
mkdir dist\\temp\\pic
mkdir dist\\temp\\torrent
copy media\\视频资源存放目录.txt dist\\media\\视频资源存放目录.txt
copy temp\\pic\\默认图片目录.txt dist\\temp\\pic\\默认图片目录.txt
copy temp\\torrent\\默认种子目录.txt dist\\temp\\torrent\\默认种子目录.txt
copy libs\pinyin\Mandarin.dat dist\
copy LICENSE dist\
copy README.md dist\
copy docs\readme-usage.txt dist\readme.txt

项目根目录下生成的dist文件夹就是打包好的软件。
项目仓库地址：https://github.com/bjdbjd/publish-helper
如果有帮助到您，请帮忙给仓库点亮Star，万分感谢！！！
"""

import sys
from pathlib import Path

# 自举：以脚本方式运行（python src/main_gui.py）时，Python 仅把脚本所在目录 src/ 加入
# sys.path，既带不了顶层 'src' 包（需项目根），也带不了扁平 'config.*'/'utils.*'（需 src/）。
# 这里主动把项目根与 src/ 都插入 sys.path，使两种导入风格都能解析（模式同 main_cli.py）。
SRC_ROOT = Path(__file__).resolve().parent           # .../src
PROJECT_ROOT = SRC_ROOT.parent                        # 项目根
sys.path.insert(0, str(PROJECT_ROOT))   # 顶层 'src' 包可导入
sys.path.insert(0, str(SRC_ROOT))       # 扁平导入 config.* / utils.* 可导入

from config.settings import config
from utils.exceptions import PublishHelperError
from utils.logger import get_logger


def main():
    """主入口。console script（publish-helper-gui）与命令行均指向此函数。"""
    logger = get_logger(__name__)

    try:
        logger.info("Starting Publish Helper GUI...")
        logger.info(f"Version: {config.GUI_VERSION}")
        logger.info(f"Configuration loaded from: {config.STATIC_DIR}")

        # 延迟导入，避免 import 阶段触发 GUI 副作用
        from src.gui.startgui import start_gui

        start_gui()

    except PublishHelperError as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Publish Helper GUI stopped")


# 作者：bjdbjd ID：bjd
# 贡献者：Pixel-LH、EasonWong0603、sertion1126、TommyMerlin
if __name__ == '__main__':
    main()  # GUI启动