import os
from typing import List, Tuple, Union

from src.core.text import natural_keys, int_to_roman, int_to_special_roman


VIDEO_EXTENSIONS = ['.mp4', '.m4v', '.avi', '.flv', '.mkv', '.mpeg', '.mpg', '.rm', '.rmvb', '.ts', '.m2ts']

MIN_WIDTHS = {
    '9600': '8640p',
    '4608': '4320p',
    '3200': '2160p',
    '2240': '1440p',
    '1600': '1080p',
    '900': '720p',
    '533': '480p',
}

def check_path_and_find_video(path: str) -> Tuple[int, str]:
    # 指定的视频文件类型列表
    video_extensions = VIDEO_EXTENSIONS  # 复用模块级常量，避免两份定义漂移

    # 如果最后一位加了'/'则默认去除
    if path.endswith('/'):
        path = path[:-1]

    # 如果最前面加了'file:///'则默认去除
    if path.startswith('file:///'):
        path = path.replace('file:///', '', 1)

    # 检查路径是否是一个文件
    if os.path.isfile(path):
        if any(path.lower().endswith(ext) for ext in video_extensions):
            return 1, path  # 是文件且符合视频类型
        print(f'路径下获取到文件{path}，但该文件不符合视频类型')
        return 0, f'路径下获取到文件{path}，但该文件不符合视频类型'  # 是文件，但不符合视频类型

    # 检查路径是否是一个文件夹
    elif os.path.isdir(path):
        for file in os.listdir(path):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                print(path + file)
                return 2, path + '/' + file  # 在文件夹中找到符合类型的视频文件
        print('文件夹中没有符合类型的视频文件')
        return 0, '文件夹中没有符合类型的视频文件'  # 文件夹中没有符合类型的视频文件

    else:
        print('您提供的路径既不是文件也不是文件夹')
        return 0, f'您提供的路径{path}既不是文件也不是文件夹'


def get_video_files(folder_path: str) -> Tuple[bool, list]:
    try:
        # 要查找的视频文件扩展名列表（复用模块级常量）
        video_extensions = VIDEO_EXTENSIONS

        # 检查文件夹路径是否有效和可访问
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            raise ValueError(f'您提供的路径"{folder_path}"不是一个有效的目录。')

        # 初始化一个空列表来存储文件路径
        video_files = []

        # 遍历文件夹中的所有文件
        for file in os.listdir(folder_path):
            # 检查文件扩展名（不区分大小写）
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_files.append(os.path.join(folder_path, file))

        # 使用自定义的natural_keys函数进行排序
        video_files.sort(key=natural_keys)

        return True, video_files

    except Exception as e:
        # 返回错误信息
        return False, [f'错误：{e}']


def is_filename_too_long(filename: str) -> bool:
    max_filename_length = 250  # Windows下文件名最长为255，去除掉后缀名为250
    if len(filename) > max_filename_length:
        return True
    else:
        return False


def delete_season_number(title: str, season_number: str) -> str:
    # 仅移除位于标题末尾的季数后缀，避免误伤标题中间的数字
    # （例如 "Ni Hao 1983" 在 season=1 时不应被改写为 "Ni Hao983"）
    title = title.rstrip()
    suffixes = [
        ' Season ' + season_number,
        ' season ' + season_number,
        ' Season' + season_number,
        ' season' + season_number,
        ' ' + season_number,
        ' ' + int_to_roman(int(season_number)),
        ' ' + int_to_special_roman(int(season_number)),
    ]
    # 先匹配最长后缀，避免 " Season 1" 被先匹配为 " 1"
    for suffix in sorted(suffixes, key=len, reverse=True):
        if title.endswith(suffix):
            title = title[: -len(suffix)]
            break
    return title.strip()