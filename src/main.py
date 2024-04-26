"""
Publish Helper  Copyright (C) 2023  BJD
This program comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
This is free software, and you are welcome to redistribute it
under certain conditions; type `show c' for details.

The licensing of this program is under the GNU General Public License version 3 (GPLv3) or later.
For more information on this license, you can visit https://www.gnu.org/licenses/gpl-3.0.html
"""
import uvicorn

from src.api import bootstrap
from src.core.tool import get_settings

"""
项目仓库地址：https://github.com/publish-helper/publish-helper
如果有帮助到您，请帮忙给仓库点亮Star，万分感谢！！！
"""
# API启动

# 作者：bjdbjd ID：bjd
# 贡献者：Pixel-LH、EasonWong0603、sertion1126
if __name__ == '__main__':
    uvicorn.run(
        bootstrap,
        host="0.0.0.0",
        port=int(get_settings("api_port")),
    )
