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
copy Mandarin.dat dist\
copy LICENSE dist\
copy README.md dist\
copy readme.txt dist\

项目根目录下生成的dist文件夹就是打包好的软件。
项目仓库地址：https://github.com/bjdbjd/publish-helper
如果有帮助到您，请帮忙给仓库点亮Star，万分感谢！！！
"""

# 作者：bjdbjd ID：bjd
# 贡献者：Pixel-LH、EasonWong0603、sertion1126、TommyMerlin
#
# 旧版入口：作为薄转发指向新版 main_gui_new.main（同一业务：src.gui.startgui.start_gui），
# 保留本文件的 PyInstaller 打包命令可用。日常开发请用 src/main_gui_new.py。
from src.main_gui_new import main

if __name__ == '__main__':
    main()  # GUI启动（转发到新版入口）
