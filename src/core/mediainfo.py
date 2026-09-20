import json
import os
import re

from pymediainfo import MediaInfo

from src.core.settings_tool import get_settings


def get_media_info(file_path):
    if not os.path.exists(file_path):
        print('文件路径不存在')
        return False, '视频文件路径不存在'

    try:
        # 尝试解析媒体信息
        media_info = MediaInfo.parse(file_path)
        json_data = media_info.to_json()

        # 解析 JSON 数据
        data = json.loads(json_data)

        # 初始化输出字符串
        output = ''

        # 初始化计数器
        audio_count, text_count = 1, 1

        # 遍历所有 track
        # print(data)
        for track in data['tracks']:
            if track['track_type'] == 'General':
                # 处理 General 类型的 track
                output += 'General\n'
                for key, label in [
                    ('other_unique_id', 'Unique ID'),
                    ('complete_name', 'Complete name'),
                    ('other_format', 'Format'),
                    ('format_version', 'Format version'),
                    ('format_profile', 'Format profile'),
                    ('other_codec_id', 'Codec ID'),
                    ('other_file_size', 'File size'),
                    ('other_duration', 'Duration'),
                    ('other_overall_bit_rate_mode', 'Overall bit rate mode'),
                    ('other_overall_bit_rate', 'Overall bit rate'),
                    ('other_frame_rate', 'Frame rate'),
                    ('movie_name', 'Movie name'),
                    ('album', 'Album'),
                    ('description', 'Description'),
                    ('encoded_date', 'Encoded date'),
                    ('writing_application', 'Writing application'),
                    ('writing_library', 'Writing library'),
                    ('comment', 'Comment'),
                    ('cover', 'Cover'),
                    ('attachments', 'Attachments')
                ]:
                    value = track[key][0] if isinstance(track.get(key), list) else track.get(key)
                    if value is not None:
                        if label == 'Complete name':
                            value = os.path.basename(value)  # 用于只保留影片文件名，去除路径
                        output += f'{label:36}: {value}\n'

            elif track['track_type'] == 'Video':
                # 处理 Video 类型的 track
                output += '\nVideo\n'
                for key, label in [
                    ('other_track_id', 'ID'),
                    ('other_id_in_the_original_source_medium', 'ID in the original source medium'),
                    ('other_format', 'Format'),
                    ('format_info', 'Format/Info'),
                    ('format_profile', 'Format profile'),
                    ('format_settings', 'Format settings'),
                    ('format_settings__cabac', 'Format settings, CABAC'),
                    ('other_format_settings__reference_frames', 'Format settings, Reference frames'),
                    ('other_hdr_format', 'HDR format'),
                    ('codec_id', 'Codec ID'),
                    ('codec_id_info', 'Codec ID / Info'),
                    ('other_duration', 'Duration'),
                    ('other_bit_rate', 'Bit rate'),
                    ('other_width', 'Width'),
                    ('other_height', 'Height'),
                    ('other_display_aspect_ratio', 'Display aspect ratio'),
                    ('other_frame_rate_mode', 'Frame rate mode'),
                    ('other_frame_rate', 'Frame rate'),
                    ('other_minimum_frame_rate', 'Minimum frame rate'),
                    ('other_maximum_frame_rate', 'Maximum frame rate'),
                    ('color_space', 'Color space'),
                    ('other_chroma_subsampling', 'Chroma subsampling'),
                    ('other_bit_depth', 'Bit depth'),
                    ('scan_type', 'Scan type'),
                    ('bits__pixel_frame', 'Bits/(Pixel*Frame)'),
                    ('other_stream_size', 'Stream size'),
                    ('other_language', 'Language'),
                    ('other_writing_library', 'Writing library'),
                    ('encoding_settings', 'Encoding settings'),
                    ('default', 'Default'),
                    ('forced', 'Forced'),
                    ('color_range', 'Color range'),
                    ('color_primaries', 'Color primaries'),
                    ('transfer_characteristics', 'Transfer characteristics'),
                    ('matrix_coefficients', 'Matrix coefficients'),
                    ('mastering_display_color_primaries', 'Mastering display color primaries'),
                    ('mastering_display_luminance', 'Mastering display luminance'),
                    ('maximum_content_light_level', 'Maximum Content Light Level'),
                    ('maxcll_original', 'MaxCLL Original'),
                    ('maximum_frameaverage_light_level', 'Maximum Frame-Average Light Level'),
                    ('maxfall_original', 'MaxFALL Original'),
                    ('original_source_medium', 'Original source medium'),
                    ('sei_rbsp_stop_one_bit', 'SEI_rbsp_stop_one_bit'),
                    ('codec_configuration_box', 'Codec configuration box'),
                ]:
                    value = track[key][0] if isinstance(track.get(key), list) else track.get(key)
                    if value is not None:
                        output += f'{label:36}: {value}\n'

            elif track['track_type'] == 'Audio':
                # 处理 Audio 类型的 track
                output += f'\nAudio #{audio_count}\n'
                audio_count += 1  # 由于有多音频的资源，故计数器+1
                for key, label in [
                    ('other_track_id', 'ID'),
                    ('other_id_in_the_original_source_medium', 'ID in the original source medium'),
                    ('other_format', 'Format'),
                    ('format_info', 'Format/Info'),
                    ('other_commercial_name', 'Commercial name'),
                    ('codec_id', 'Codec ID'),
                    ('other_duration', 'Duration'),
                    ('other_bit_rate_mode', 'Bit rate mode'),
                    ('other_bit_rate', 'Bit rate'),
                    ('other_maximum_bit_rate', 'Maximum bit rate'),
                    ('other_channel_s', 'Channel(s)'),
                    ('channel_layout', 'Channel layout'),
                    ('other_sampling_rate', 'Sampling rate'),
                    ('other_frame_rate', 'Frame rate'),
                    ('other_bit_depth', 'Bit depth'),
                    ('other_compression_mode', 'Compression mode'),
                    ('other_delay_relative_to_video', 'Delay relative to video'),
                    ('other_stream_size', 'Stream size'),
                    ('title', 'Title'),
                    ('other_language', 'Language'),
                    ('other_service_kind', 'Service kind'),
                    ('default', 'Default'),
                    ('other_forced', 'Forced'),
                    ('original_source_medium', 'Original source medium'),
                    ('complexity_index', 'Complexity index'),
                    ('number_of_dynamic_objects', 'Number of dynamic objects'),
                    ('other_bed_channel_count', 'Bed channel count'),
                    ('bed_channel_configuration', 'Bed channel configuration'),
                    ('alternate_group', 'Alternate group'),
                ]:
                    value = track[key][0] if isinstance(track.get(key), list) else track.get(key)
                    if value is not None:
                        if label == 'Delay relative to video' and value == '00:00:00.000':
                            continue
                        output += f'{label:36}: {value}\n'

            elif track['track_type'] == 'Text':
                # 处理 Text 类型的 track
                output += f'\nText #{text_count}\n'
                text_count += 1  # 由于有多字幕的资源，故计数器+1
                for key, label in [
                    ('other_track_id', 'ID'),
                    ('other_id_in_the_original_source_medium', 'ID in the original source medium'),
                    ('other_format', 'Format'),
                    ('muxing_mode', 'Muxing mode'),
                    ('codec_id', 'Codec ID'),
                    ('codec_id_info', 'Codec ID/Info'),
                    ('other_duration', 'Duration'),
                    ('other_bit_rate', 'Bit rate'),
                    ('other_frame_rate', 'Frame rate'),
                    ('count_of_elements', 'Count of elements'),
                    ('other_stream_size', 'Stream size'),
                    ('title', 'Title'),
                    ('other_language', 'Language'),
                    ('default', 'Default'),
                    ('forced', 'Forced'),
                    ('original_source_medium', 'Original source medium'),
                ]:
                    value = track[key][0] if isinstance(track.get(key), list) else track.get(key)
                    if value is not None:
                        output += f'{label:36}: {value}\n'

            elif track['track_type'] == 'Menu':
                output += f'\nMenu\n'
                # 遍历所有章节条目
                for key, value in track.items():
                    # 使用正则表达式匹配时间戳和章节标题的格式
                    match = re.match(r'(\d{2})_(\d{2})_(\d{5})', key)
                    if match:
                        # 格式化时间戳
                        hours, minutes, seconds_millis = match.groups()
                        seconds, millis = divmod(int(seconds_millis), 1000)
                        timestamp = f'{hours}:{minutes}:{seconds:02}.{millis:03}'
                        # 添加到输出字符串
                        output += f'{timestamp:36}: {value}\n'

        if get_settings('media_info_suffix'):  # 用户可以选择是否需要增加工具水印（方便推广）
            output += '\nCreated by Publish Helper'

        return True, output

    except OSError as e:
        # 文件路径相关的错误
        print(f'文件路径错误：{e}')
        return False, f'文件路径错误：{e}'
    except Exception as e:
        # MediaInfo无法解析文件
        print(f'无法解析文件：{e}')
        return False, f'无法解析文件：{e}'
