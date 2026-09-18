import base64
import datetime
import glob
import json
import os
import random
import re
from typing import Any, Dict, List, Tuple, Union

from torf import Torrent
from xpinyin import Pinyin

from src.utils.file_utils import load_or_initialize_json

# settings 系统单一实现：迁移到 settings_tool.settings_tool（带类型注解的 SettingsManager）。
# 这里 re-export，使现有 `from src.core.tool import get_settings/...` 消费方零改动切换实现。
# 注意删除了本文件旧的 get_settings/update_settings/get_settings_json/update_settings_json 实现。
from src.core.settings_tool import (
    get_settings,
    get_settings_json,
    update_settings,
    update_settings_json,
)

# 视频文件扩展名（统一常量，供 check_path_and_find_video / get_video_files 复用）
VIDEO_EXTENSIONS = ['.mp4', '.m4v', '.avi', '.flv', '.mkv', '.mpeg', '.mpg', '.rm', '.rmvb', '.ts', '.m2ts']

# 分辨率分段表：宽度阈值 -> 分辨率简称。tool.get_abbreviation 与 rename.load_min_widths_from_json 共用，
# 避免两处定义漂移（阈值单位为像素）。
MIN_WIDTHS = {
    '9600': '8640p',
    '4608': '4320p',
    '3200': '2160p',
    '2240': '1440p',
    '1600': '1080p',
    '900': '720p',
    '533': '480p',
}


# 写一个方法，取当前工程工作目录与传入的目录，组合成一个新的目录
# 项目里被 API（拼 media/temp 路径）及 get_combo_box_data/get_abbreviation 使用。
def combine_directories(path: str) -> str:
    """
    取当前工程工作目录与传入相对路径，生成新的路径

    返回:
    参数的值
    """
    project_dir = os.getcwd()
    return os.path.join(project_dir, path)


def get_combo_box_data(data_name: str) -> Tuple[bool, list]:
    try:
        # Define the file path
        file_path = combine_directories('static/combo-box-data.json')

        default_content = {}

        # Define default content if key is missing
        if data_name == 'playlet-source':
            default_content = {
                'playlet-source': [
                    '网络收费短剧',
                    '网络免费短剧',
                    '抖音短剧',
                    '快手短剧',
                    '腾讯短剧',
                    ''
                ]
            }

        elif data_name == 'source':
            default_content = {
                'source': [
                    'WEB-DL',
                    'Remux',
                    'Blu-ray',
                    'UHD Blu-ray',
                    'Blu-ray Remux',
                    'UHD Blu-ray Remux',
                    'HDTV',
                    'DVD',
                    ''
                ]
            }

        elif data_name == 'team':
            default_content = {
                'team': [
                    'AGSVWEB',
                    'AGSVMUS',
                    'AGSVPT',
                    'GodDramas',
                    'CatEDU',
                    'Pack',
                    ''
                ]
            }

        # 文件不存在则以 default_content 创建；已存在时补齐缺失的数据键（对应原行为）并写回
        data = load_or_initialize_json(file_path, default_content, backfill=True)
        return True, data[data_name]

    except Exception as e:
        # Return False and the error message if an exception occurs
        return False, [str(e)]


def update_combo_box_data(configuration_data: str, configuration_name: str) -> Tuple[bool, str]:
    # 将给定的字符串分割成列表
    sources_list = configuration_data.split('\\n')

    # 文件路径
    file_path = combine_directories('static/combo-box-data.json')

    try:
        # 尝试打开现有的 JSON 文件并加载其内容
        with open(file_path, 'r', encoding='utf-8') as file:
            existing_data = json.load(file)

        # 检查是否存在指定的配置名称，如果不存在则创建
        if configuration_name not in existing_data:
            existing_data[configuration_name] = []

        # 更新指定的配置名称的数据
        existing_data[configuration_name] = sources_list

        # 将更新后的数据写回到 JSON 文件中
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(existing_data, file, ensure_ascii=False, indent=4)

        return True, '更新成功'

    except FileNotFoundError:
        # 文件不存在时，创建新文件并写入数据
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump({configuration_name: sources_list}, file, ensure_ascii=False, indent=4)
        return True, '文件不存在，已创建新文件并更新'

    except json.JSONDecodeError:
        return False, 'JSON解码错误，文件内容可能损坏'

    except Exception as e:
        # 处理可能发生的其他异常
        return False, f'更新失败，错误：{str(e)}'


def get_picture_bed_type(picture_bed_api_url: str) -> Tuple[bool, str]:
    try:
        # Define the file path
        file_path = combine_directories('static/picture-bed-data.json')

        # Define default content if key is missing
        default_content = {
            'lsky-pro': [
                'https://picture.agsv.top/api/v1/upload',
                'https://img.ptvicomo.net/api/v1/upload'
            ],
            'bohe': [
                'https://img.agsv.top/api/upload'
            ],
            'freeimage': [
                'https://freeimage.host/api/1/upload'
            ],
            'imgbb': [
                'https://api.imgbb.com/1/upload'
            ],
            'pixhost': [
                'https://api.pixhost.to/images'
            ]
        }

        # Check if the file exists and load existing content or initialize with default content
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                existing_content = json.load(file)
        else:
            existing_content = {}

        # Merge default content into the existing content if it's missing
        updated = False
        for key, urls in default_content.items():
            if key not in existing_content:
                existing_content[key] = urls
                updated = True
            else:
                # Check each URL in the default content's URL list
                for url in urls:
                    if url not in existing_content[key]:
                        existing_content[key].append(url)
                        updated = True

        # Save the updated content back to the file if there were updates
        if updated:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(existing_content, file, ensure_ascii=False, indent=4)

        # Now, try to find the API type
        get_picture_bed_type_success, picture_bed_type = find_picture_bed_type(picture_bed_api_url,
                                                                               existing_content)
        if get_picture_bed_type_success:
            print(picture_bed_type)
            return True, picture_bed_type
        else:
            print(picture_bed_type)
            return False, picture_bed_type

    except Exception as e:
        # Return False and the error message if an exception occurs
        return False, str(e)


def find_picture_bed_type(picture_bed_api_url: str, picture_bed_api_data: dict) -> Tuple[bool, str]:
    """
    根据给定的URL和JSON数据，寻找URL对应的标识符。
    如果URL以http开头，自动替换为https。
    如果URL最后一位是'/'，则去除这个'/'。
    如果找不到URL对应的标识符，返回'没找到'。

    参数:
    url (str): 需要查找的网址
    json_data (dict): 包含网址和对应标识符的JSON字典

    返回:
    str: URL对应的标识符或者'没找到'
    """
    # 替换http为https
    if picture_bed_api_url.startswith('http://'):
        picture_bed_api_url = 'https://' + picture_bed_api_url[7:]

    # 去除URL末尾的'/'
    if picture_bed_api_url.endswith('/'):
        picture_bed_api_url = picture_bed_api_url[:-1]

    # 遍历JSON数据，查找对应的标识符
    for identifier, urls in picture_bed_api_data.items():
        if picture_bed_api_url in urls:
            return True, identifier

    # 如果找不到对应的标识符，返回'没找到'
    return False, f'您使用的图床上传接口{picture_bed_api_url}暂未配置，请检查static/picture-bed-data.json文件，如果您的图床符合其中的配置，可将上传接口URL按照格式添加到对应类型下'


def get_abbreviation(original_name: str, json_file_path: str = 'static/abbreviation.json') -> str:
    print('开始对参数名称进行转化')
    try:
        json_file_path = combine_directories('static/abbreviation.json')

        # 文件不存在则以默认表创建；存在的 key 缺失时自动补齐并写回
        abbreviation_map = load_or_initialize_json(
            json_file_path,
            {
                'min_widths': MIN_WIDTHS,
                '7 680 pixels': '4320p',
                '3 840 pixels': '2160p',
                '2 560 pixels': '1440p',
                '1 920 pixels': '1080p',
                '1 440 pixels': '720p',
                '1 280 pixels': '720p',
                '720 pixels': '480p',
                '640 pixels': '480p',
                'HEVC': 'HEVC',
                'AVC': 'AVC',
                'AV1': 'AV1',
                'x264': 'x264',
                'x265': 'x265',
                'x266': 'x266',
                '12 bits': '12bit',
                '10 bits': '10bit',
                '8 bits': '',
                'Dolby Vision, Version 1.0, dvhe.05.06, BL+RPU': 'DV',
                'SMPTE ST 2094 App 4, Version 1, HDR10+ Profile B compatible': 'HDR10+',
                'SMPTE ST 2086, HDR10 compatible': 'HDR10',
                'HDR Vivid, Version 1': 'HDR',
                '60.000 FPS': '60FPS',
                '50.000 FPS': '50FPS',
                '48.000 FPS': '48FPS',
                '30.000 FPS': '',
                '29.970 FPS': '',
                '25.000 FPS': '',
                '24.037 FPS': '',
                '24.000 FPS': '',
                '23.976 FPS': '',
                'Dolby Digital Plus with Dolby Atmos': 'Atmos DDP',
                'Dolby TrueHD with Dolby Atmos': 'Atmos TrueHD',
                'DTS-HD Master Audio': 'DTS-HD MA',
                'Dolby Digital Plus': 'DDP',
                'Dolby Digital': 'DD',
                'HE-AAC': 'AAC',
                'L R C LFE Ls Rs Lb Rb': '7.1',
                'L R C LFE Ls Rs': '5.1',
                'C L R Ls Rs LFE': '5.1',
                'L R': '2.0',
                'Audio': 'Audio',
            },
        )

        # Return the abbreviation if found, else return the original name
        return str(abbreviation_map.get(original_name, original_name))
    except FileNotFoundError:
        print(f'File not found: {json_file_path}')
        return original_name
    except json.JSONDecodeError:
        print(f'Error decoding JSON from file: {json_file_path}')
        return original_name


# 此方法用于自动生成一个不易重复的图片文件名称
def generate_image_filename(base_path: str) -> str:
    now = datetime.datetime.now()
    date_time = now.strftime('%Y%m%d-%H%M%S')
    letters = random.sample('0123456789', 6)
    random_str = ''.join(letters)
    filename = f'{date_time}-{random_str}.png'
    path = base_path + '/' + filename
    return path


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
        return 0, f'您提供的路径{path}既不是文件也不是文件夹'  # 路径既不是文件也不是文件夹


def get_playlet_description(original_title: str, year: str, area: str, category: str, language: str, season_number: str) -> str:
    if season_number != '1':
        original_title += ' 第' + int_to_chinese(int(season_number)) + '季'
    return f'\n◎片　　名　{original_title}\n◎年　　代　{year}\n◎产　　地　{area}\n◎类　　别　{category}\n◎语　　言　{language}\n◎简　　介　\n'


def make_torrent(path: str, torrent_storage_path: str) -> Tuple[bool, str]:
    print(path + '  ' + torrent_storage_path)
    try:
        # 检查路径是否存在
        if not os.path.exists(path):
            raise ValueError('提供的路径不存在')

        # 检查这个路径是否是一个非空目录
        if os.path.isdir(path) and not os.listdir(path):
            raise ValueError('路径指向一个空目录')

        # 构造完整的torrent文件路径
        torrent_file_name = os.path.basename(path.rstrip('/\\')) + '.torrent'
        torrent_file_path = torrent_storage_path + '/' + torrent_file_name

        # 确保torrent文件的目录存在
        os.makedirs(os.path.dirname(torrent_file_path), exist_ok=True)

        # 如果目标 Torrent 文件已存在，则删除它
        if os.path.exists(torrent_file_path):
            os.remove(torrent_file_path)

        # 获取当前时间
        current_time = datetime.datetime.now()

        # 创建 Torrent 对象，添加当前时间作为创建时间
        t = Torrent(path=path, trackers=['https://tracker.example.com/announce'], created_by='Publish Helper',
                    creation_date=current_time)

        # 生成和写入 Torrent 文件
        t.generate()
        t.write(torrent_file_path)

        print(f'Torrent created: {torrent_file_path}')
        return True, torrent_file_path

    except (OSError, IOError, ValueError) as e:
        # 捕获并处理文件操作相关的异常和值错误
        print(f'Error occurred: {e}')
        return False, str(e)

    except Exception as e:
        # 捕获所有其他异常
        print(f'An unexpected error occurred: {e}')
        return False, str(e)


def load_names(file_path: str, name: str) -> Any:
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

        return data[name]


def chinese_name_to_pinyin(chinese_name: str) -> str:
    p = Pinyin()
    result = ''
    py = p.get_pinyin(chinese_name)
    s = py.split('-')
    for c in s:
        result += c.capitalize()
        result += ' '
    result = convert_chinese_punctuation_to_english(result)
    result = result.replace(' ,', ',')
    result = result.replace(' .', '.')
    result = result.replace(' !', '!')
    result = result.replace(' ?', '?')
    result = result.replace(' :', ':')
    result = result.replace(' ;', ';')
    result = result.replace('( ', '(')
    result = result.replace(' )', ')')
    result = result.replace('[ ', '[')
    result = result.replace(' ]', ']')
    result = result.replace('< ', '<')
    result = result.replace(' >', '>')
    result = re.sub(r'\s+', ' ', result)  # 将连续的空格变成一个

    return result


def convert_chinese_punctuation_to_english(text: str) -> str:
    # Mapping of Chinese punctuation to English punctuation
    punctuation_map = {
        '，': ', ',  # Comma
        '。': '. ',  # Period
        '！': '! ',  # Exclamation mark
        '？': '? ',  # Question mark
        '：': ': ',  # Colon
        '；': '; ',  # Semicolon
        '“': '\'',  # Double quotation mark (opening)
        '”': '\'',  # Double quotation mark (closing)
        '‘': ''',  # Single quotation mark (opening)
        '’': ''',  # Single quotation mark (closing)
        '（': ' (',  # Left parenthesis
        '）': ') ',  # Right parenthesis
        '【': ' [',  # Left square bracket
        '】': '] ',  # Right square bracket
        '《': ' <',  # Less than sign
        '》': '> ',  # Greater than sign
        '、': ', ',  # Enumeration comma
        '——': '--',  # Dash
        '…': '...'  # Ellipsis
        # Add more mappings if necessary
    }

    # Replace each Chinese punctuation mark with its English equivalent
    for chinese, english in punctuation_map.items():
        text = text.replace(chinese, english)

    return text


def natural_keys(text: str) -> List[Union[int, str]]:
    """
    alist.sort(key=natural_keys) 使用这个函数作为key来按数字顺序排序文本
    """
    return [int(c) if c.isdigit() else c.lower() for c in re.split('(\d+)', text)]


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


def int_to_roman(num: int) -> str:
    val = [
        1000, 900, 500, 400,
        100, 90, 50, 40,
        10, 9, 5, 4,
        1
    ]
    syms = [
        'M', 'CM', 'D', 'CD',
        'C', 'XC', 'L', 'XL',
        'X', 'IX', 'V', 'IV',
        'I'
    ]
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syms[i]
            num -= val[i]
        i += 1
    return roman_num


def int_to_special_roman(num: int) -> str:
    special_roman_dict = {
        1: 'Ⅰ',
        2: 'Ⅱ',
        3: 'Ⅲ',
        4: 'Ⅳ',
        5: 'Ⅴ',
        6: 'Ⅵ',
        7: 'Ⅶ',
        8: 'Ⅷ',
        9: 'Ⅸ',
        10: 'Ⅹ',
    }
    if num in special_roman_dict:
        return special_roman_dict[num]
    else:
        return str(num)


def int_to_chinese(num: int) -> str:
    if num < 0 or num > 9999:
        return '数字超出范围'

    digits = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    units = ['', '十', '百', '千']
    parts = []

    if num == 0:
        return digits[0]

    # 处理千位到个位
    unit_index = 0
    while num > 0:
        digit = num % 10
        if digit > 0:
            parts.append(digits[digit] + units[unit_index])
        elif len(parts) > 0 and parts[-1] != digits[0]:
            parts.append(digits[0])
        num //= 10
        unit_index += 1

    # 处理完毕后，parts 数组是倒序的，需要反转回来
    return ''.join(parts[::-1])


def chinese_to_int(chinese_num: str) -> Union[int, None]:
    try:
        # 定义中文数字到阿拉伯数字的映射
        num_map = {
            '零': 0,
            '一': 1,
            '二': 2,
            '三': 3,
            '四': 4,
            '五': 5,
            '六': 6,
            '七': 7,
            '八': 8,
            '九': 9,
        }

        unit = 1
        total = 0

        for char in reversed(chinese_num):
            if char in num_map:
                value = num_map[char]
                if value >= unit:
                    unit = value
                else:
                    total += unit * value
            elif char == '十':
                unit *= 10
            elif char == '百':
                unit *= 100
            elif char == '千':
                unit *= 1000
            elif char == '万':
                unit *= 10000
            else:
                raise ValueError(f"无法识别的字符: {char}")

        if unit >= 1:
            total += unit

        return total
    except ValueError:
        return None


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


def base64encoding(string: str) -> str:
    return base64.b64encode(string.encode('utf-8')).decode('utf-8')


def get_data_from_pt_gen_description(main_title: str, description: str, media_info: str, source: str, category: str) -> Tuple[str, str, str, str, str, str, str, str]:
    imdb_url = ''  # IMDb链接
    douban_url = ''  # 豆瓣链接
    description = description  # 简介
    area = ''  # 地区
    video_format = ''  # 分辨率
    audio_codec = ''  # 音频编码
    video_codec = ''  # 视频编码
    medium = ''  # 媒介

    # 获取IMDb链接
    imdb_pattern = r'https://www\.imdb\.com/title/tt\d+/'
    match = re.search(imdb_pattern, description)
    # If a match is found, return it as a string, otherwise return an empty string
    imdb_url += match.group(0) if match else ''
    print('获取到IMDb链接' + imdb_url)

    # 获取豆瓣链接
    douban_pattern = r'https://movie\.douban\.com/subject/\d+/'
    match = re.search(douban_pattern, description)
    # If a match is found, return it as a string, otherwise return an empty string
    douban_url += match.group(0) if match else ''
    print('获取到豆瓣链接' + douban_url)

    # 获取其他类型 电影/纪录/体育/剧集/动画/综艺……
    category_pattern = r'◎类　　别　([^\n]+)'
    match = re.search(category_pattern, description)
    # If a match is found, return it as a string, otherwise return an empty string
    t = match.group(0) if match else ''
    if '纪录' in t:
        category = '纪录'
    if '体育' in t:
        category = '体育'
    if '动画' in t:
        category = '动画'
    if '综艺' in t or '脱口秀' in t:
        category = '综艺'
    if '短片' in t:
        category = '短剧'
    print('获取到类型' + category)

    # 获取产地 欧美/大陆/港台/日本/韩国/印度
    area_pattern = r'◎产　　地　([^\n]+)'
    match = re.search(area_pattern, description)
    # If a match is found, return the matched location, otherwise return an empty string
    s = match.group(1) if match else ''
    if '美国' in s or '英国' in s or '德国' in s or '法国' in s:
        area = '欧美'
    if '大陆' in s:
        area = '大陆'
    if '香港' in s or '台湾' in s:
        area = '港台'
    if '日本' in s:
        area = '日本'
    if '韩国' in s:
        area = '韩国'
    if '印度' in s:
        area = '印度'
    print('获取到产地' + area)

    # 获取分辨率 4K/1080p/1080i/720p/SD
    if '3840p' in main_title or '3840P' in main_title or '3840i' in main_title:
        video_format = '8K'
    if '2160p' in main_title or '2160P' in main_title or '2160i' in main_title:
        video_format = '4K'
    if '1080p' in main_title or '1080P' in main_title:
        video_format = '1080p'
    if '1080i' in main_title:
        video_format = '1080i'
    if '720p' in main_title or '720P' in main_title:
        video_format = '720p'
    if '720i' in main_title:
        video_format = '720i'
    if '480p' in main_title or '480P' in main_title:
        video_format = '480p'
    if '720i' in main_title:
        video_format = '480i'
    print('获取到分辨率' + video_format)

    # 获取音频编码 AAC/AC3/DTS…………
    if 'AAC' in main_title:
        audio_codec = 'AAC'
    if 'AC3' in main_title or 'DD' in main_title:
        audio_codec = 'AC3'
    if 'EAC3' in main_title or 'E-AC3' in main_title or 'DDP' in main_title or 'DD+' in main_title:
        audio_codec = 'EAC3'
    if 'DTS' in main_title:
        if 'HD' in main_title and 'MA' in main_title:
            audio_codec = 'DTS-HDMA'
        else:
            audio_codec = 'DTS'
    if 'Atmos' in main_title or 'ATMOS' in main_title:
        audio_codec = 'Atmos'
    if 'TrueHD' in main_title or 'TRUEHD' in main_title:
        audio_codec = 'TrueHD'
    if 'Flac' in main_title or 'FLAC' in main_title:
        audio_codec = 'Flac'
    print('获取到音频编码' + audio_codec)

    # 获取视频编码 H264/H265……
    if 'H264' in main_title or 'H.264' in main_title or 'h264' in main_title or 'h.264' in main_title or 'AVC' in main_title or 'avc' in main_title:
        video_codec = 'H264'
    if 'H265' in main_title or 'H.265' in main_title or 'h265' in main_title or 'h.265' in main_title or 'HEVC' in main_title or 'hevc' in main_title:
        video_codec = 'H265'
    if 'H266' in main_title or 'H.266' in main_title or 'h266' in main_title or 'h.266' in main_title or 'VVC' in main_title or 'vvc' in main_title:
        video_codec = 'H266'
    if 'X264' in main_title or 'x264' in main_title:
        video_codec = 'X264'
    if 'X265' in main_title or 'x265' in main_title:
        video_codec = 'X265'
    if 'X266' in main_title or 'x266' in main_title:
        video_codec = 'X266'
    if 'AV1' in main_title or 'av1' in main_title:
        video_codec = 'AV1'
    print('获取到视频编码' + video_codec)

    # 获取媒介 web-dl/remux/encode……
    if source == 'WEB-DL' or 'WEB-DL' in main_title or source == 'Web-DL' or 'Web-DL' in main_title or source == 'web-dl' or 'web-dl' in main_title or source == 'WEBDL' or 'WEBDL' in main_title or source == 'WebDL' or 'WebDL' in main_title or source == 'webdl' or 'webdl' in main_title:
        medium = 'WEB-DL'
    if source == 'Blu-ray' or 'Blu-ray' in main_title or source == 'Blu-Ray' or 'Blu-Ray' in main_title or source == 'BluRay' or 'BluRay' in main_title or source == 'UHD Blu-ray' or source == 'UHD Blu-Ray' or source == 'UHD BluRay':
        if 'X26' in video_codec:
            medium = 'Encode'
        else:
            if 'Remux' in main_title or 'REMUX' in main_title or 'remux' in main_title or 'mkv' in media_info:
                medium = 'Remux'
    if source == 'HDTV' or 'HDTV' in main_title:
        medium = 'HDTV'
    if source == 'DVD' or 'DVD' in main_title:
        medium = 'DVD'
    print('获取到媒介' + medium)

    return imdb_url, douban_url, category, area, video_format, audio_codec, video_codec, medium


def validate_and_convert_to_int(value: Any, value_name: str) -> int:
    if value is None or value == '':
        raise ValueError(f'{value_name} 不能为 None 或空字符串')

    try:
        converted_value = int(value)
    except ValueError as e:
        raise ValueError(f'{value_name} 必须是数字，您提供的是：{value}') from e

    return converted_value
