# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：Publish Helper GUI（Windows / macOS 通用）。

用法（在项目根目录执行）：
    pyinstaller packaging/publish_helper.spec --noconfirm

产物落在 dist/ 下。本 spec 相比 main_gui.py 里旧的一行命令配方，
补上了两处**必需但旧配方遗漏**的随包数据：
  - ``static/``      —— settings.json / abbreviation.json / combo-box-data.json /
                        picture-bed-data.json / ph-bjd.ico，缺失会启动即崩；
  - ``libs/pinyin/Mandarin.dat`` —— xpinyin 的中文拼音数据表。
运行期由 src/config/settings.py 的 get_bundle_dir()（sys._MEIPASS）读取，
并由 _seed_from_bundle() 播种到 exe 同级的可写 static/。
"""

import sys
from pathlib import Path

# 项目根目录（本 spec 位于 packaging/ 下）
ROOT = Path(SPECPATH).parent

block_cipher = None

# ---- 随包只读数据 ----
datas = [
    (str(ROOT / "static"), "static"),
    (str(ROOT / "libs" / "pinyin" / "Mandarin.dat"), "libs/pinyin"),
]

# ---- 隐式导入 ----
# PyInstaller 对以下几处探测不到，必须显式声明，否则运行期 ImportError：
hiddenimports = [
    "src",                       # 入口以 from src.gui.startgui 导入，包名需可见
    "src.gui.startgui",
    "src.api.startapi",
    "src.core.settings_tool",    # 扁平导入兼容桥
    "xpinyin",                   # 通过数据表动态加载
    "pymediainfo",
    "torf",
    "cv2",
]

# ---- 排除项：减小体积 ----
# 注意 NOT 排除 tkinter：src/gui/ui_tools.py 用 tkinter.filedialog 做文件选择框，
# 排除后 GUI 启动即 ModuleNotFoundError（已实测）。
excludes = [
    "matplotlib",
    "pytest",
    "PIL.ImageQt",   # 避免与 PyQt6 的重复 Qt 绑定告警
    # pkg_resources / setuptools 一并排除：本应用无任何模块需要它们
    # （xpinyin 用 pathlib 读数据表，不走 pkg_resources）。
    # 保留它们会触发 PyInstaller 的 pyi_rth_pkgres 运行时钩子，而新版
    # setuptools(>=81) 已不再自带 jaraco.text，钩子会以
    # "ModuleNotFoundError: No module named 'jaraco'" 直接让程序启动失败。
    "pkg_resources",
    "setuptools",
    "jaraco",
]

a = Analysis(
    [str(ROOT / "src" / "main_gui.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Publish Helper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI 程序：不弹控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 图标仅 Windows 生效：PyInstaller 要求 .ico(Windows) / .icns(macOS)。
    # Linux 忽略 icon，且传 .ico 会告警；macOS 需另行准备 icons.icns。
    icon=str(ROOT / "static" / "ph-bjd.ico") if sys.platform == "win32" else None,
)
