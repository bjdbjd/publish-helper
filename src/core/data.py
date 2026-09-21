import json
import os
from typing import Any, Tuple

from src.core.video import MIN_WIDTHS
from src.utils.file_utils import combine_directories, load_or_initialize_json


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
    # 将给定的字符串按**换行**分割成列表
    sources_list = configuration_data.split('\n')

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
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump({configuration_name: sources_list}, file, ensure_ascii=False, indent=4)
        return True, '文件不存在，已创建新文件并更新'

    except json.JSONDecodeError:
        return False, 'JSON解码错误，文件内容可能损坏'

    except Exception as e:
        # 处理可能发生的其他异常
        return False, f'更新失败，错误：{str(e)}'


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


def load_names(file_path: str, name: str) -> Any:
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

        return data[name]