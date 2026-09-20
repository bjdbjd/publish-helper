"""core/tool.py —— 兼容转发表（P1 拆分后的 re-export 层）。

历史作用：工具函数垃圾桶。现将各函数按领域拆分到 data / text / video / torrent / ptgen / picturebed，
以及 utils.file_utils（combine_directories）。此处保留全部符号 re-export，
使现有 `from src.core.tool import X` 消费方（api / gui / cli / core）零改动继续可用。

新代码请直接 import 各自领域模块；待调用方迁移完毕后（P4）删除本文件。
"""

# settings（单一实现，原样 re-export）
from src.core.settings_tool import (
    get_settings,
    get_settings_json,
    update_settings,
    update_settings_json,
)

# 静态数据文件管理
from src.core.data import (
    get_combo_box_data,
    update_combo_box_data,
    get_abbreviation,
    load_names,
)

# 文本 / 数字 / 拼音工具
from src.core.text import (
    chinese_name_to_pinyin,
    convert_chinese_punctuation_to_english,
    natural_keys,
    int_to_roman,
    int_to_special_roman,
    int_to_chinese,
    chinese_to_int,
    base64encoding,
    validate_and_convert_to_int,
)

# 视频路径 / 文件处理
from src.core.video import (
    check_path_and_find_video,
    get_video_files,
    is_filename_too_long,
    delete_season_number,
    VIDEO_EXTENSIONS,
    MIN_WIDTHS,
)

# 种子制作
from src.core.torrent import make_torrent

# PT-Gen 文本组装
from src.core.ptgen import get_data_from_pt_gen_description, get_playlet_description

# 图床类型识别 / 文件名生成
from src.core.picturebed import (
    get_picture_bed_type,
    find_picture_bed_type,
    generate_image_filename,
)

# 通用路径工具
from src.utils.file_utils import combine_directories

__all__ = [
    "get_settings", "get_settings_json", "update_settings", "update_settings_json",
    "get_combo_box_data", "update_combo_box_data", "get_abbreviation", "load_names",
    "chinese_name_to_pinyin", "convert_chinese_punctuation_to_english", "natural_keys",
    "int_to_roman", "int_to_special_roman", "int_to_chinese", "chinese_to_int",
    "base64encoding", "validate_and_convert_to_int",
    "check_path_and_find_video", "get_video_files", "is_filename_too_long",
    "delete_season_number", "VIDEO_EXTENSIONS", "MIN_WIDTHS",
    "make_torrent",
    "get_data_from_pt_gen_description", "get_playlet_description",
    "get_picture_bed_type", "find_picture_bed_type", "generate_image_filename",
    "combine_directories",
]