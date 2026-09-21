#!/usr/bin/env python3
"""跨平台发布打包脚本：构建可执行文件 + 组装发布用压缩包。

用法（项目根目录执行）：
    python packaging/make_release.py

产物：
    dist/Publish Helper.exe          （Windows）
    dist/Publish Helper.app          （macOS）
    dist/Publish Helper              （Linux）
    release/Publish.Helper.v<版本>.<平台>.zip

设计要点：可执行文件是 **自包含** 的——首次运行会自行解出
static/ 与 media/、temp/、logs/ 目录（见 src/config/settings.py
的 _seed_from_bundle），所以压缩包里只需放可执行文件与本说明，
不再需要旧配方里那一长串 xcopy/mkdir。
"""

import json
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
RELEASE = ROOT / "release"


def read_version() -> str:
    """版本号以 src/config/__init__.py 的 __version__ 为单一来源。"""
    ns: dict = {}
    text = (ROOT / "src" / "config" / "__init__.py").read_text(encoding="utf-8")
    exec(compile(text, "config/__init__.py", "exec"), ns)  # noqa: S102
    return str(ns["__version__"])


def platform_tag() -> str:
    """平台标签，同时用于产物文件名。

    文件名里用 macos 而非 platform.system() 的 "darwin"：对用户而言
    "macos-arm64" 比 "darwin-arm64" 更直观，也与 Release 页的
    windows-x64 / linux-x64 命名保持一致。
    """
    system = platform.system().lower()
    if system == "darwin":
        system = "macos"
    machine = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        machine, machine
    )
    return f"{system}-{arch}"


def build() -> None:
    """调用 PyInstaller，使用仓库内的 spec。"""
    spec = ROOT / "packaging" / "publish_helper.spec"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec),
        "--noconfirm",
        "--distpath",
        str(DIST),
        "--workpath",
        str(ROOT / "build"),
    ]
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def find_built_artifact() -> Path:
    """定位 PyInstaller 的产物（Windows 是 .exe，macOS 是 .app，Linux 是无后缀）。"""
    system = platform.system()
    if system == "Windows":
        candidate = DIST / "Publish Helper.exe"
    elif system == "Darwin":
        candidate = DIST / "Publish Helper.app"
    else:
        candidate = DIST / "Publish Helper"
    if not candidate.exists():
        raise SystemExit(f"未找到构建产物：{candidate}")
    return candidate


def make_zip(artifact: Path, version: str) -> Path:
    """把产物 + LICENSE + 使用说明打进 release/ 下的 zip。"""
    RELEASE.mkdir(parents=True, exist_ok=True)
    tag = platform_tag()
    out = RELEASE / f"Publish.Helper.v{version}.{tag}.zip"

    stage = RELEASE / f"_stage_{tag}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    if artifact.is_dir():  # macOS .app
        shutil.copytree(artifact, stage / artifact.name, symlinks=True)
    else:
        shutil.copy2(artifact, stage / artifact.name)

    for extra, target in [
        (ROOT / "LICENSE", "LICENSE"),
        (ROOT / "docs" / "readme-usage.txt", "readme.txt"),
        (ROOT / "packaging" / "首次运行必读.txt", "首次运行必读.txt"),
    ]:
        if extra.exists():
            shutil.copy2(extra, stage / target)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(stage.rglob("*")):
            if item.is_file():
                zf.write(item, item.relative_to(stage))

    shutil.rmtree(stage)
    return out


def main() -> None:
    version = read_version()
    print(f"Publish Helper v{version}  ({platform_tag()})")
    build()
    artifact = find_built_artifact()
    out = make_zip(artifact, version)
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"\n[DONE] {out}  ({size_mb:.1f} MB)")
    print(f"       artifact: {artifact}")


if __name__ == "__main__":
    main()
