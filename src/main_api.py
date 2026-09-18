"""
Publish Helper  Copyright (C) 2023  BJD
This program comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
This is free software, and you are welcome to redistribute it
under certain conditions; type `show c' for details.

The licensing of this program is under the GNU General Public License version 3 (GPLv3) or later.
For more information on this license, you can visit https://www.gnu.org/licenses/gpl-3.0.html
"""
"""
项目仓库地址：https://github.com/bjdbjd/publish-helper
如果有帮助到您，请帮忙给仓库点亮Star，万分感谢！！！
"""

# 作者：bjdbjd ID：bjd
# 贡献者：Pixel-LH、EasonWong0603、sertion1126、TommyMerlin
#
# 旧版入口：作为薄转发指向新版 main_api_new.main（同一业务：src.api.startapi.start_api），
# 保留向后兼容。日常开发请用 src/main_api_new.py。
from src.main_api_new import main

if __name__ == '__main__':
    main()  # API启动（转发到新版入口）
