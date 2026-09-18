"""File and path utilities."""

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# 导入兼容桥：扁平导入 (utils.*) 要求 src/ 在 sys.path 上。
# _new 入口会插入 src/；旧入口 (main_gui/main_api, PyInstaller 用) 不插，这里缺省时手动补上。
try:
    from utils.logger import get_logger
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from utils.logger import get_logger

logger = get_logger(__name__)


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, create if it doesn't.

    Args:
        path: Directory path

    Returns:
        Path object
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {path_obj}")
    return path_obj


def safe_filename(filename: str, max_length: int = 255) -> str:
    """
    Create a safe filename by removing/replacing invalid characters.

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Safe filename
    """
    # Characters not allowed in filenames
    invalid_chars = '<>:"/\\|?*'

    # Replace invalid characters with underscore
    safe_name = filename
    for char in invalid_chars:
        safe_name = safe_name.replace(char, "_")

    # Remove multiple consecutive underscores
    while "__" in safe_name:
        safe_name = safe_name.replace("__", "_")

    # Trim length if necessary
    if len(safe_name) > max_length:
        name, ext = Path(safe_name).stem, Path(safe_name).suffix
        max_name_length = max_length - len(ext)
        safe_name = name[:max_name_length] + ext

    logger.debug(f"Created safe filename: '{filename}' -> '{safe_name}'")
    return safe_name


def get_file_hash(file_path: Union[str, Path], algorithm: str = "md5") -> str:
    """
    Calculate file hash.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256)

    Returns:
        File hash string
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"File not found: {path_obj}")

    hash_func = getattr(hashlib, algorithm.lower())()

    with open(path_obj, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)

    hash_value: str = hash_func.hexdigest()
    logger.debug(f"Calculated {algorithm} hash for {path_obj}: {hash_value}")
    return hash_value


def copy_with_structure(
    src: Union[str, Path], dst: Union[str, Path], preserve_structure: bool = True
) -> Path:
    """
    Copy file or directory with optional structure preservation.

    Args:
        src: Source path
        dst: Destination path
        preserve_structure: Whether to preserve directory structure

    Returns:
        Destination path
    """
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.exists():
        raise FileNotFoundError(f"Source not found: {src_path}")

    if src_path.is_file():
        # Ensure destination directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        logger.info(f"Copied file: {src_path} -> {dst_path}")
    else:
        # Copy directory
        if preserve_structure:
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        else:
            # Copy contents without structure
            ensure_directory(dst_path)
            for item in src_path.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(src_path)
                    new_name = "_".join(relative_path.parts)
                    shutil.copy2(item, dst_path / new_name)
        logger.info(f"Copied directory: {src_path} -> {dst_path}")

    return dst_path


def create_hardlink(src: Union[str, Path], dst: Union[str, Path]) -> Path:
    """
    Create a hard link from src to dst.

    Args:
        src: Source file path
        dst: Destination link path

    Returns:
        Destination path
    """
    src_path = Path(src)
    dst_path = Path(dst)

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    if not src_path.is_file():
        raise ValueError(f"Source must be a file: {src_path}")

    # Ensure destination directory exists
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing destination if it exists
    if dst_path.exists():
        dst_path.unlink()

    # Create hard link
    dst_path.hardlink_to(src_path)
    logger.info(f"Created hard link: {src_path} -> {dst_path}")

    return dst_path


def find_files(
    directory: Union[str, Path], patterns: List[str], recursive: bool = True
) -> List[Path]:
    """
    Find files matching patterns in directory.

    Args:
        directory: Directory to search
        patterns: List of glob patterns
        recursive: Whether to search recursively

    Returns:
        List of matching file paths
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    files: List[Path] = []
    for pattern in patterns:
        if recursive:
            files.extend(dir_path.rglob(pattern))
        else:
            files.extend(dir_path.glob(pattern))

    # Remove duplicates and sort
    unique_files = sorted(set(files))
    logger.debug(f"Found {len(unique_files)} files matching patterns {patterns}")

    return unique_files


def get_file_size_human(size_bytes: int) -> str:
    """
    Convert file size to human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human readable size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    size_index = 0
    size = float(size_bytes)

    while size >= 1024.0 and size_index < len(size_names) - 1:
        size /= 1024.0
        size_index += 1

    return f"{size:.1f} {size_names[size_index]}"


def load_or_initialize_json(
    path: Union[str, Path],
    defaults: Dict[str, Any],
    ensure_ascii: bool = False,
    backfill: bool = False,
) -> Dict[str, Any]:
    """
    Load a JSON file, initializing it with *defaults* when missing.

    收敛 tool.py 中重复的「文件不存在则以默认创建 → 读取 → （可选）缺 key 补默认」模式：
    - 文件不存在时以 *defaults* 创建，并返回 defaults 的副本；
    - 文件存在时：
      * backfill=False（默认）：直接读取返回，绝不改写已有文件（对应原 get_abbreviation 语义）；
      * backfill=True：缺失的默认 key 补入并写回（对应原 get_combo_box_data 语义，保留原缩进）；
    - 文件损坏（JSON 解析失败）时抛出 ValueError，由调用方决定兜底。

    Args:
        path: JSON 文件路径
        defaults: 需要保证存在（创建时写入 / backfill 时补入）的默认键值
        ensure_ascii: 写文件时是否用 ASCII 转义（中文通常应为 False）
        backfill: 已存在文件是否补齐缺失默认键并写回（默认 False，只读）

    Returns:
        加载（新建或补齐后）的 JSON 字典
    """
    path_obj = Path(path)

    # 文件不存在：以 defaults 创建（新建时用 indent=4）
    if not path_obj.exists():
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        path_obj.write_text(
            json.dumps(defaults, ensure_ascii=ensure_ascii, indent=4), encoding="utf-8"
        )
        return dict(defaults)

    # 文件已存在：读取（backfill=False 时绝不改写；True 时仅在补缺失键时保留原缩进写回）
    try:
        raw = path_obj.read_text(encoding="utf-8")
        data: Dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"JSON 解析失败，文件可能损坏: {path_obj}")

    changed = False
    if backfill:
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
                changed = True

    if backfill and changed:
        # 尽量沿用文件原有缩进；无法探测（无前导空格）时退回 4 空格
        first_indent = ""
        for line in raw.splitlines():
            stripped = line.lstrip(" \t")
            if stripped and not stripped.startswith("#") and line.startswith((" ", "\t")):
                first_indent = line[: len(line) - len(stripped)]
                break
        indent = first_indent if first_indent else 4
        path_obj.write_text(
            json.dumps(data, ensure_ascii=ensure_ascii, indent=indent), encoding="utf-8"
        )

    return data
