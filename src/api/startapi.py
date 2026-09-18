import os
from dataclasses import dataclass, asdict

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from src.core.mediainfo import get_media_info
from src.core.picturebed import upload_picture
from src.core.ptgen import get_pt_gen_description
from src.core.rename import get_video_info, get_pt_gen_info, get_name_from_template, rename_file, rename_folder, \
    move_file_to_folder, create_hard_link
from src.core.screenshot import get_screenshot, get_thumbnail
from src.core.tool import check_path_and_find_video, get_settings, make_torrent, delete_season_number, \
    get_video_files, update_combo_box_data, update_settings, \
    get_playlet_description, get_combo_box_data, get_settings_json, update_settings_json, combine_directories, \
    get_data_from_pt_gen_description, validate_and_convert_to_int

api = Flask(__name__)
CORS(api)


def start_api():
    api.run(host='0.0.0.0', port=int(get_settings('api_port')), debug=True, use_reloader=False, threaded=True)


def to_camel_case(snake_str):
    """Convert snake_case string to camelCase."""
    components = snake_str.split('_')
    # We capitalize the first letter of each component except the first one
    # with the 'title' method and join them together.
    return components[0] + ''.join(x.title() or '_' for x in components[1:])


def convert_to_camel_case(data_class_instance):
    original_dict = asdict(data_class_instance)
    return {to_camel_case(key): value for key, value in original_dict.items()}


@api.route('/api/getScreenshot', methods=['GET'])
# 用于获取MediaInfo，传入一个文件地址或者一个文件夹地址，返回视频文件路径和MediaInfo
def api_get_screenshot():
    try:
        # 从请求URL中获取参数
        path = request.args.get('path', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        path = os.path.abspath(os.path.join(media_path, path))

        # 为了保证安全，确认绝对路径为media目录
        if not path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此路径下的视频文件，请把视频文件储存在media目录下。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if path == '':
            return jsonify({
                'data': {
                    'screenshotNumber': '0',
                    'screenshotPath': '',
                    'videoPath': ''
                },
                'message': '缺少资源路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(path):
            return jsonify({
                'data': {
                    'screenshotNumber': '0',
                    'screenshotPath': '',
                    'videoPath': ''
                },
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        screenshot_storage_path = request.args.get('screenshotStoragePath',
                                                   default=get_settings('screenshot_storage_path'), type=str)

        if screenshot_storage_path == '':
            screenshot_storage_path = get_settings('screenshot_storage_path')

        screenshot_number = request.args.get('screenshotNumber', default=get_settings('screenshot_number'), type=str)

        if screenshot_number == '':
            screenshot_number = int(get_settings('screenshot_number'))
        else:
            screenshot_number = int(screenshot_number)

        screenshot_threshold = request.args.get('screenshotThreshold', default=get_settings('screenshot_threshold'),
                                                type=str)

        if screenshot_threshold == '':
            screenshot_threshold = float(get_settings('screenshot_threshold'))
        else:
            screenshot_threshold = float(screenshot_threshold)

        screenshot_start_percentage = request.args.get('screenshotStartPercentage',
                                                       default=get_settings('screenshot_start_percentage'), type=str)

        if screenshot_start_percentage == '':
            screenshot_start_percentage = float(get_settings('screenshot_start_percentage'))
        else:
            screenshot_start_percentage = float(screenshot_start_percentage)

        screenshot_end_percentage = request.args.get('screenshotEndPercentage',
                                                     default=get_settings('screenshot_end_percentage'), type=str)

        if screenshot_end_percentage == '':
            screenshot_end_percentage = float(get_settings('screenshot_end_percentage'))
        else:
            screenshot_end_percentage = float(screenshot_end_percentage)

        screenshot_min_interval_percentage = request.args.get('screenshotMinIntervalPercentage', default='0.01',
                                                              type=str)

        if screenshot_min_interval_percentage == '':
            screenshot_min_interval_percentage = 0.01
        else:
            screenshot_min_interval_percentage = float(screenshot_min_interval_percentage)

        if screenshot_number > 0:
            if screenshot_number < 6:
                if 0 < screenshot_start_percentage < 1 and 0 < screenshot_end_percentage < 1:
                    if screenshot_start_percentage < screenshot_end_percentage:
                        is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
                        if is_video_path == 1 or is_video_path == 2:
                            video_path = response
                            screenshot_success, response = get_screenshot(video_path, screenshot_storage_path,
                                                                          screenshot_number,
                                                                          screenshot_threshold,
                                                                          screenshot_start_percentage,
                                                                          screenshot_end_percentage,
                                                                          screenshot_min_interval_percentage)

                            if screenshot_success:

                                [imagePath.replace(media_path, '') for imagePath in response]

                                return jsonify({
                                    'data': {
                                        'screenshotNumber': str(len(response)),
                                        'screenshotPath': [imagePath.replace(media_path, '') for imagePath in response],
                                        'videoPath': video_path
                                    },
                                    'message': '获取截图成功。',
                                    'statusCode': 'OK'
                                })
                            else:
                                return jsonify({
                                    'data': {
                                        'screenshotNumber': '0',
                                        'screenshotPath': '',
                                        'videoPath': video_path
                                    },
                                    'message': f'获取截图失败：{response[0]}',
                                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                                }), 400
                        else:
                            return jsonify({
                                'data': {
                                    'screenshotNumber': '0',
                                    'screenshotPath': '',
                                    'videoPath': ''
                                },
                                'message': f'获取视频路径失败：{response}',
                                'statusCode': 'BACKEND_PROCESSING_ERROR'
                            }), 400
                    else:
                        return jsonify({
                            'data': {
                                'screenshotNumber': '0',
                                'screenshotPath': '',
                                'videoPath': ''
                            },
                            'message': '截图起始点不能大于终止点。',
                            'statusCode': 'VALUE_RELATIONSHIP_ERROR'
                        }), 422
                else:
                    return jsonify({
                        'data': {
                            'screenshotNumber': '0',
                            'screenshotPath': '',
                            'videoPath': ''
                        },
                        'message': '截图起始点和终止点不能小于0或大于1。',
                        'statusCode': 'VALUE_RANGE_ERROR'
                    }), 422
            else:
                return jsonify({
                    'data': {
                        'screenshotNumber': '0',
                        'screenshotPath': '',
                        'videoPath': ''
                    },
                    'message': '一次获取的截图数量不能大于5张。',
                    'statusCode': 'VALUE_RANGE_ERROR'
                }), 422
        else:
            return jsonify({
                'data': {
                    'screenshotNumber': '0',
                    'screenshotPath': '',
                    'videoPath': '',
                },
                'message': '一次获取的截图数量不能小于1张。',
                'statusCode': 'VALUE_RANGE_ERROR'
            }), 422
    except Exception as e:
        return jsonify({
            'data': {
                'screenshotNumber': '0',
                'screenshotPath': '',
                'videoPath': ''
            },
            'message': f'获取截图失败：{e}',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getThumbnail', methods=['GET'])
# 用于获取缩略图，传入相关参数，返回缩略图路径
def api_get_thumbnail():
    try:
        # 从请求URL中获取参数
        path = request.args.get('path', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        path = os.path.abspath(os.path.join(media_path, path))

        # 为了保证安全，确认绝对路径为media目录
        if not path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此路径下的视频文件，请把视频文件储存在media目录下。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if path == '':
            return jsonify({
                'data': {
                    'thumbnailPath': '',
                    'videoPath': ''
                },
                'message': '缺少资源路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(path):
            return jsonify({
                'data': {
                    'thumbnailPath': '',
                    'videoPath': ''
                },
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        screenshot_storage_path = request.args.get('screenshotStoragePath',
                                                   default=get_settings('screenshot_storage_path'), type=str)

        if screenshot_storage_path == '':
            screenshot_storage_path = get_settings('screenshot_storage_path')

        thumbnail_rows = request.args.get('thumbnailRows', default=get_settings('thumbnail_rows'), type=str)
        if thumbnail_rows == '':
            thumbnail_rows = int(get_settings('thumbnail_rows'))
        else:
            thumbnail_rows = int(thumbnail_rows)

        thumbnail_cols = request.args.get('thumbnailCols', default=get_settings('thumbnail_cols'), type=str)
        if thumbnail_cols == '':
            thumbnail_cols = int(get_settings('thumbnail_cols'))
        else:
            thumbnail_cols = int(thumbnail_cols)

        screenshot_start_percentage = request.args.get('screenshotStartPercentage',
                                                       default=get_settings('screenshot_start_percentage'), type=str)
        if screenshot_start_percentage == '':
            screenshot_start_percentage = float(get_settings('screenshot_start_percentage'))
        else:
            screenshot_start_percentage = float(screenshot_start_percentage)

        screenshot_end_percentage = request.args.get('screenshotEndPercentage',
                                                     default=get_settings('screenshot_end_percentage'), type=str)
        if screenshot_end_percentage == '':
            screenshot_end_percentage = float(get_settings('screenshot_end_percentage'))
        else:
            screenshot_end_percentage = float(screenshot_end_percentage)

        if thumbnail_rows > 0 and thumbnail_cols > 0:
            if 0 < screenshot_start_percentage < 1 and 0 < screenshot_end_percentage < 1:
                if screenshot_start_percentage < screenshot_end_percentage:
                    is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
                    if is_video_path == 1 or is_video_path == 2:
                        video_path = response
                        get_thumbnail_success, response = get_thumbnail(video_path, screenshot_storage_path,
                                                                        thumbnail_rows,
                                                                        thumbnail_cols, screenshot_start_percentage,
                                                                        screenshot_end_percentage)

                        if get_thumbnail_success:
                            thumbnail_path = response
                            return jsonify({
                                'data': {
                                    'thumbnailPath': thumbnail_path,
                                    'videoPath': video_path
                                },
                                'message': '获取截图成功。',
                                'statusCode': 'OK'
                            })
                        else:
                            return jsonify({
                                'data': {
                                    'thumbnailPath': '',
                                    'videoPath': video_path
                                },
                                'message': f'获取截图失败：{response}',
                                'statusCode': 'BACKEND_PROCESSING_ERROR'
                            }), 400
                    else:
                        return jsonify({
                            'data': {
                                'thumbnailPath': '',
                                'videoPath': ''
                            },
                            'message': f'获取视频路径失败：{response}',
                            'statusCode': 'BACKEND_PROCESSING_ERROR'
                        }), 400
                else:
                    return jsonify({
                        'data': {
                            'thumbnailPath': '',
                            'videoPath': ''
                        },
                        'message': '截图起始点不能大于终止点。',
                        'statusCode': 'VALUE_RELATIONSHIP_ERROR'
                    }), 422
            else:
                return jsonify({
                    'data': {
                        'thumbnailPath': '',
                        'videoPath': ''
                    },
                    'message': '截图起始点和终止点不能小于0或大于1。',
                    'statusCode': 'VALUE_RANGE_ERROR'
                }), 422
        else:
            return jsonify({
                'data': {
                    'thumbnailPath': '',
                    'videoPath': ''
                },
                'message': '缩略图横向、纵向数量均需要大于0。',
                'statusCode': 'VALUE_RANGE_ERROR'
            }), 422
    except Exception as e:
        return jsonify({
            'data': {
                'thumbnailPath': '',
                'videoPath': ''
            },
            'message': f'获取截图失败：{e}',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/uploadPicture', methods=['POST'])
#  用于上传本地图片到图床
def api_upload_picture():
    try:
        # 从请求URL中获取参数
        picture_path = request.args.get('picturePath', default='', type=str)  # 必须信息
        if picture_path == '':
            return jsonify({
                'data': {
                    'pictureUrl': ''
                },
                'message': '缺少图片路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(picture_path):
            return jsonify({
                'data': {
                    'pictureBbCode': '',
                    'pictureUrl': ''
                },
                'message': '您提供的图片路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        picture_bed_api_url = request.args.get('pictureBedApiUrl', default=get_settings('picture_bed_api_url'),
                                               type=str)
        if picture_bed_api_url == '':
            picture_bed_api_url = get_settings('picture_bed_api_url')

        picture_bed_api_token = request.args.get('pictureBedApiToken', default=get_settings('picture_bed_api_token'),
                                                 type=str)
        if picture_bed_api_token == '':
            picture_bed_api_token = get_settings('picture_bed_api_token')

        upload_picture_success, response = upload_picture(picture_bed_api_url, picture_bed_api_token, picture_path)
        if upload_picture_success:
            picture_bbs_url = response
            return jsonify({
                'data': {
                    'pictureBbCode': picture_bbs_url,  # 注意是[img]1.png[/img]的bbsCode格式
                    'pictureUrl': picture_bbs_url[5:-6]
                },
                'message': '上传图片成功。',
                'statusCode': 'OK'
            })
        else:
            return jsonify({
                'data': {
                    'pictureBbCode': '',
                    'pictureUrl': ''
                },
                'message': f'上传图片失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'pictureBbCode': '',
                'pictureUrl': ''
            },
            'message': f'上传图片失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getMediaInfo', methods=['GET'])
# 用于获取MediaInfo，传入一个文件地址或者一个文件夹地址，返回视频文件路径和MediaInfo
def api_get_media_info():
    try:
        # 从请求URL中获取path
        path = request.args.get('path', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        path = os.path.abspath(os.path.join(media_path, path))
        # 为了安全，确认绝对路径media目录
        if not path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401
        if path == '':
            return jsonify({
                'data': {
                    'mediaInfo': '',
                    'videoPath': ''
                },
                'message': '缺少资源路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(path):
            return jsonify({
                'data': {
                    'mediaInfo': '',
                    'videoPath': ''
                },
                'message': '您提供的资源路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            get_media_info_success, response = get_media_info(video_path)
            if get_media_info_success:
                media_info = response
                return jsonify({
                    'data': {
                        'mediaInfo': media_info,
                        'videoPath': video_path
                    },
                    'message': '获取MediaInfo成功。',
                    'statusCode': 'OK'
                })
            else:
                return jsonify({
                    'data': {
                        'mediaInfo': '',
                        'videoPath': video_path
                    },
                    'message': f'获取视频路径成功，但是获取MediaInfo失败，错误：{response}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
        else:
            return jsonify({
                'data': {
                    'mediaInfo': '',
                    'videoPath': ''
                },
                'message': f'获取视频路径失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'mediaInfo': '',
                'videoPath': ''
            },
            'message': f'获取MediaInfo失败，错误：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getVideoInfo', methods=['GET'])
# 用于获取视频关键信息，传入一个文件地址或者一个文件夹地址，返回视频文件路径和关键信息
def api_get_video_info():
    try:
        # 从请求URL中获取path
        path = request.args.get('path', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        path = os.path.abspath(os.path.join(media_path, path))
        # 为了安全，确认绝对路径media目录
        if not path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401
        if path == '':
            return jsonify({
                'data': {
                    'videoPath': '',
                    'videoFormat': '',
                    'videoCodec': '',
                    'bitDepth': '',
                    'hdrFormat': '',
                    'frameRate': '',
                    'audioCodec': '',
                    'channels': '',
                    'audioNum': ''
                },
                'message': '缺少资源路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(path):
            return jsonify({
                'data': {
                    'videoPath': '',
                    'videoFormat': '',
                    'videoCodec': '',
                    'bitDepth': '',
                    'hdrFormat': '',
                    'frameRate': '',
                    'audioCodec': '',
                    'channels': '',
                    'audioNum': ''
                },
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            get_video_info_success, response = get_video_info(video_path)
            if get_video_info_success:
                print('获取到关键参数：' + str(response))
                video_format = response[0]
                video_codec = response[1]
                bit_depth = response[2]
                hdr_format = response[3]
                frame_rate = response[4]
                audio_codec = response[5]
                channels = response[6]
                audio_num = response[7]
                return jsonify({
                    'data': {
                        'videoPath': video_path,
                        'videoFormat': video_format,
                        'videoCodec': video_codec,
                        'bitDepth': bit_depth,
                        'hdrFormat': hdr_format,
                        'frameRate': frame_rate,
                        'audioCodec': audio_codec,
                        'channels': channels,
                        'audioNum': audio_num
                    },
                    'message': '获取视频关键参数成功。',
                    'statusCode': 'OK'
                })
            else:
                return jsonify({
                    'data': {
                        'videoPath': video_path,
                        'videoFormat': '',
                        'videoCodec': '',
                        'bitDepth': '',
                        'hdrFormat': '',
                        'frameRate': '',
                        'audioCodec': '',
                        'channels': '',
                        'audioNum': ''
                    },
                    'message': f'获取视频关键参数失败：{response[0]}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
        else:
            return jsonify({
                'data': {
                    'videoPath': '',
                    'videoFormat': '',
                    'videoCodec': '',
                    'bitDepth': '',
                    'hdrFormat': '',
                    'frameRate': '',
                    'audioCodec': '',
                    'channels': '',
                    'audioNum': ''
                },
                'message': f'获取视频路径失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'videoPath': '',
                'videoFormat': '',
                'videoCodec': '',
                'bitDepth': '',
                'hdrFormat': '',
                'frameRate': '',
                'audioCodec': '',
                'channels': '',
                'audioNum': ''
            },
            'message': f'获取视频关键参数失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getPtGenDescription', methods=['GET'])
# 用于获取PT-Gen简介，传入一个豆瓣链接，返回PT-Gen简介
def api_get_pt_gen_description():
    try:
        # 从请求URL中获取参数
        resource_url = request.args.get('resourceUrl', default='', type=str)  # 必须信息

        if resource_url == '':
            return jsonify({
                'data': {
                    'description': ''
                },
                'message': '缺少资源链接。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        pt_gen_api_url = request.args.get('ptGenApiUrl', default=get_settings('pt_gen_api_url'), type=str)
        if pt_gen_api_url == '':
            pt_gen_api_url = get_settings('pt_gen_api_url')

        get_pt_gen_description_success, response = get_pt_gen_description(pt_gen_api_url, resource_url)
        if get_pt_gen_description_success:
            # response is now (format_data, full_data)
            format_data, full_data = response
            
            # Check if auto download and upload poster is enabled
            auto_download_upload_poster = bool(get_settings('auto_download_upload_poster'))
            poster_url = ''
            
            if auto_download_upload_poster:
                try:
                    from src.core.poster import get_poster_from_pt_gen_response
                    
                    picture_bed_api_url = get_settings('picture_bed_api_url')
                    picture_bed_api_token = get_settings('picture_bed_api_token')
                    screenshot_storage_path = combine_directories(get_settings('screenshot_storage_path'))
                    
                    process_success, process_result = get_poster_from_pt_gen_response(
                        full_data,
                        picture_bed_api_url,
                        picture_bed_api_token,
                        screenshot_storage_path
                    )
                    
                    if process_success:
                        poster_url = process_result
                        print(f'Poster uploaded successfully: {poster_url}')
                    else:
                        print(f'Poster processing failed: {process_result}')
                except Exception as e:
                    print(f'Error processing poster: {e}')
            
            return jsonify({
                'data': {
                    'description': format_data,
                    'posterUrl': poster_url
                },
                'message': '获取PT-Gen简介成功。',
                'statusCode': 'OK'
            })
        else:
            return jsonify({
                'data': {
                    'description': ''
                },
                'message': f'获取PT-Gen简介失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'description': ''
            },
            'message': f'获取PT-Gen简介失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getPlayletDescription', methods=['GET'])
# 用于获取短剧简介
def api_get_playlet_description():
    try:
        original_title = request.args.get('originalTitle', default='', type=str)  # 必须信息

        if original_title == '':
            return jsonify({
                'data': {
                    'playletDescription': ''
                },
                'message': '缺少资源名称。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        year = request.args.get('year', default='', type=str)
        area = request.args.get('area', default='', type=str)
        category = request.args.get('category', default='', type=str)
        language = request.args.get('language', default='', type=str)
        season_number = request.args.get('seasonNumber', default='', type=str)
        playlet_description = get_playlet_description(original_title, year, area, category, language, season_number)
        return jsonify({
            'data': {
                'playletDescription': playlet_description
            },
            'message': '获取短剧简介成功。',
            'statusCode': 'OK'
        })
    except Exception as e:
        return jsonify({
            'data': {
                'playletDescription': ''
            },
            'message': f'获取短剧简介失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getPtGenInfo', methods=['GET'])
# 用于获取PT-Gen简介，传入一个豆瓣链接，返回PT-Gen简介
def api_get_pt_gen_info():
    try:
        # 从请求URL中获取参数
        description = request.args.get('description', default='', type=str)  # 必须信息
        if description == '':
            return jsonify({
                'data': {
                    'originalTitle': '',
                    'englishTitle': '',
                    'year': '',
                    'otherTitles': '',
                    'category': '',
                    'actors': ''
                },
                'message': 'MISSING_REQUIRED_PARAMETER',
                'statusCode': '缺少PT-Gen简介内容。'
            }), 422

        original_title, english_title, year, other_names_sorted, category, actors_list, episodes, season = get_pt_gen_info(
            description)
        print(original_title, english_title, year, other_names_sorted, category, actors_list)
        actors = ''
        other_titles = ''
        is_first = True

        for data in actors_list:  # 把演员名转化成str
            if is_first:
                actors += data
                is_first = False
            else:
                actors += ' / '
                actors += data

        for data in other_names_sorted:  # 把别名转化为str
            other_titles += data
            other_titles += ' / '

        other_titles = other_titles[: -3]
        return jsonify({
            'data': {
                'originalTitle': original_title,
                'englishTitle': english_title,
                'year': year,
                'otherTitles': other_titles,
                'category': category,
                'actors': actors
            },
            'message': '获取PT-Gen简介关键参数成功。',
            'statusCode': 'OK'
        })
    except Exception as e:
        return jsonify({
            'data': {
                'originalTitle': '',
                'englishTitle': '',
                'year': '',
                'otherTitles': '',
                'category': '',
                'actors': ''
            },
            'message': f'对于简介的分析有错误：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/makeTorrent', methods=['POST'])
# 用于制作种子
def api_make_torrent():
    try:
        # 从请求URL中获取参数
        path = request.args.get('path', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        path = os.path.abspath(os.path.join(media_path, path))

        # 为保证安全，确认绝对路径为media目录
        if not path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if path == '':
            return jsonify({
                'data': {
                    'torrentPath': ''
                },
                'message': '缺少资源路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(path):
            return jsonify({
                'data': {
                    'torrentPath': ''
                },
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        torrent_storage_path = request.args.get('torrentStoragePath', default=get_settings('torrent_storage_path'),
                                                type=str)
        if torrent_storage_path == '':
            torrent_storage_path = get_settings('torrent_storage_path')

        make_torrent_success, response = make_torrent(path, torrent_storage_path)
        if make_torrent_success:
            return jsonify({
                'data': {
                    'torrentPath': response
                },
                'message': '制作种子成功。',
                'statusCode': 'OK'
            })
        else:
            return jsonify({
                'data': {
                    'torrentPath': ''
                },
                'message': f'制作种子失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'torrentPath': ''
            },
            'message': f'制作种子失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getNameFromTemplate', methods=['GET'])
# 用于通过模板数据获取命名，关键参数和模板，返回获取到的命名
def api_get_name_from_template():
    try:
        # 从请求URL中获取参数
        template = request.args.get('template', default='', type=str)  # 必须信息

        if template == '':
            return jsonify({
                'data': {
                    'name': ''
                },
                'message': '缺少模板名称。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if template != 'main_title_movie' and template != 'main_title_tv' and template != 'main_title_playlet' and template != 'second_title_movie' and template != 'second_title_tv' and template != 'second_title_playlet' and template != 'file_name_movie' and template != 'file_name_tv' and template != 'file_name_playlet':
            return jsonify({
                'data': {
                    'name': ''
                },
                'message': '模板名称不在范围内。',
                'statusCode': 'PARAMETER_RANGE_ERROR'
            }), 422

        english_title = request.args.get('englishTitle', default='', type=str)
        original_title = request.args.get('originalTitle', default='', type=str)
        season = request.args.get('season', default='', type=str)
        # episode = request.args.get('episode', default='', type=str)  # Currently unused
        year = request.args.get('year', default='', type=str)
        video_format = request.args.get('videoFormat', default='', type=str)
        source = request.args.get('source', default='', type=str)
        video_codec = request.args.get('videoCodec', default='', type=str)
        bit_depth = request.args.get('bitDepth', default='', type=str)
        hdr_format = request.args.get('hdrFormat', default='', type=str)
        frame_rate = request.args.get('frameRate', default='', type=str)
        audio_codec = request.args.get('audioCodec', default='', type=str)
        channels = request.args.get('channels', default='', type=str)
        audio_num = request.args.get('audioNum', default='', type=str)
        team = request.args.get('team', default='', type=str)
        other_titles = request.args.get('otherTitles', default='', type=str)
        season_number = request.args.get('seasonNumber', default='', type=str)
        total_episode = request.args.get('totalEpisode', default='', type=str)
        playlet_source = request.args.get('playletSource', default='', type=str)
        category = request.args.get('category', default='', type=str)
        actors = request.args.get('actors', default='', type=str)
        english_title = delete_season_number(english_title, season_number)

        name = get_name_from_template(english_title, original_title, season, '{集数}', year, video_format,
                                      source, video_codec, bit_depth, hdr_format, frame_rate,
                                      audio_codec, channels, audio_num, team, other_titles, season_number,
                                      total_episode, playlet_source, category, actors, template)
        print(f'获取到名称是{name}')
        return jsonify({
            'data': {
                'name': name
            },
            'message': '获取名称成功。',
            'statusCode': 'OK'
        })
    except Exception as e:
        return jsonify({
            'data': {
                'name': ''
            },
            'message': f'获取名称失败：{e}',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/renameFolder', methods=['POST'])
# 用于重命名文件夹
def api_rename_folder():
    try:
        # 从请求URL中获取参数
        folder_path = request.args.get('folderPath', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        folder_path = os.path.abspath(os.path.join(media_path, folder_path))
        # 为保证安全，确认绝对路径为media目录
        if not folder_path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401
        if folder_path == '':
            return jsonify({
                'data': {},
                'message': '缺少文件路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(folder_path):
            return jsonify({
                'data': {},
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        new_folder_name = request.args.get('newFolderName', default='', type=str)  # 必须信息

        if new_folder_name == '':
            return jsonify({
                'data': {},
                'message': '缺少需要重命名的名称信息。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        rename_success, response = rename_folder(folder_path, new_folder_name)
        if rename_success:
            new_folder_path = response.replace(media_path + '/', '')
            return jsonify({
                'data': {
                    'newFolderPath': new_folder_path
                },
                'message': '重命名文件成功。',
                'statusCode': 'OK'
            })
        else:
            return jsonify({
                'data': {},
                'message': f'重命名文件失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {},
            'message': f'重命名文件失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/renameFile', methods=['POST'])
# 用于重命名文件
def api_rename_file():
    try:
        # 从请求URL中获取参数
        file_path = request.args.get('filePath', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        file_path = os.path.abspath(os.path.join(media_path, file_path))

        # 为保证安全，确认绝对路径为media目录
        if not file_path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if file_path == '':
            return jsonify({
                'data': {
                    'newFilePath': ''
                },
                'message': '缺少文件路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(file_path):
            return jsonify({
                'data': {
                    'newFilePath': ''
                },
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        new_file_name = request.args.get('newFileName', default='', type=str)  # 必须信息

        if new_file_name == '':
            return jsonify({
                'data': {
                    'newFilePath': ''
                },
                'message': '缺少需要重命名的名称信息。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        rename_success, new_file_path = rename_file(file_path, new_file_name)
        if rename_success:
            new_file_path = new_file_path.replace(media_path + '/', '')
            return jsonify({
                'data': {
                    'newFilePath': new_file_path
                },
                'message': '重命名文件成功。',
                'statusCode': 'OK'
            })
        else:
            return jsonify({
                'data': {
                    'newFilePath': ''
                },
                'message': f'重命名文件失败：{new_file_path}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'newFilePath': ''
            },
            'message': f'重命名文件失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/createHardLink', methods=['POST'])
# 用于创建硬链接
def api_create_hard_link():
    try:
        # 从请求URL中获取参数
        path = request.args.get('path', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        path = os.path.abspath(os.path.join(media_path, path))

        # 为保证安全，确认绝对路径为media目录
        if not path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if path == '':
            return jsonify({
                'data': {
                    'hardLinkPath': ''
                },
                'message': '缺少路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(path):
            return jsonify({
                'data': {
                    'hardLinkPath': ''
                },
                'message': '您提供的路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        make_hard_link_success, response = create_hard_link(path)
        response = response.replace(media_path + '/', '')
        if make_hard_link_success:
            return jsonify({
                'data': {
                    'hardLinkPath': response
                },
                'message': '创建硬链接成功。',
                'statusCode': 'OK'
            })
        else:
            return jsonify({
                'data': {
                    'hardLinkPath': ''
                },
                'message': f'创建硬链接失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'hardLinkPath': ''
            },
            'message': f'创建硬链接失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/moveFileToFolder', methods=['POST'])
# 用于将文件塞入指定文件夹
def api_move_file_to_folder():
    try:
        # 从请求URL中获取参数
        path = request.args.get('filePath', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        file_path = os.path.abspath(os.path.join(media_path, path))

        # 为保证安全，确认绝对路径为media目录
        if not path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if file_path == '':
            return jsonify({
                'data': {
                    'newFilePath': ''
                },
                'message': '缺少文件路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(file_path):
            return jsonify({
                'data': {
                    'newFilePath': ''
                },
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        folder_name = request.args.get('folderName', default='', type=str)  # 必须信息

        if folder_name == '':
            return jsonify({
                'data': {
                    'newFilePath': ''
                },
                'message': '缺少文件夹名称。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        move_file_to_folder_success, response = move_file_to_folder(file_path, folder_name)

        if move_file_to_folder_success:
            return jsonify({
                'data': {
                    'newFilePath': response
                },
                'message': '移动文件成功。',
                'statusCode': 'OK'
            })
        else:
            return jsonify({
                'data': {
                    'newFilePath': ''
                },
                'message': f'移动文件失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'newFilePath': ''
            },
            'message': f'移动文件失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/renameEpisode', methods=['POST'])
# 用于给剧集批量重命名
def api_rename_episode():
    try:
        # 从请求URL中获取参数
        folder_path = request.args.get('folderPath', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        folder_path = os.path.abspath(os.path.join(media_path, folder_path))

        # 为保证安全，确认绝对路径为media目录
        if not folder_path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if folder_path == '':
            return jsonify({
                'data': {
                    'newFolderPath': ''
                },
                'message': '缺少资源路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(folder_path):
            return jsonify({
                'data': {
                    'newFolderPath': ''
                },
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        new_file_name = request.args.get('newFileName', default='', type=str)  # 必须信息

        if new_file_name == '':
            return jsonify({
                'data': {
                    'newFolderPath': ''
                },
                'message': '缺少文件名称。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        episode_start_number = request.args.get('episodeStartNumber', default='', type=str)  # 必须信息

        if episode_start_number == '' or episode_start_number == '':
            episode_start_number = '1'

        is_video_path, response = check_path_and_find_video(folder_path)  # 获取视频的路径

        if is_video_path == 2:  # 视频路径是文件夹
            video_path = response
            get_video_files_success, video_files = get_video_files(folder_path)  # 获取文件夹内部的所有文件

            if get_video_files_success:
                print('检测到以下文件：', video_files)
                episode_start_number = int(episode_start_number)
                episode_num = len(video_files)  # 获取视频文件的总数
                i = episode_start_number

                for video_file in video_files:
                    e = str(i)

                    while len(e) < len(str(episode_start_number + episode_num - 1)):
                        e = '0' + e

                    if len(e) == 1:
                        e = '0' + e

                    rename_file_success, response = rename_file(video_file, new_file_name.replace('{集数}', e))

                    if rename_file_success:
                        video_path = response
                        i += 1
                    else:
                        raise OSError('重命名文件失败：' + response)

                print('开始对文件夹重新命名')
                rename_directory_success, response = rename_folder(os.path.dirname(video_path), new_file_name.
                                                                   replace('E{集数}', '').
                                                                   replace('{集数}', ''))

                if rename_directory_success:
                    new_folder_path_final = response.replace(media_path, '')
                    if len(new_folder_path_final) and new_folder_path_final.startswith('/'):
                        new_folder_path_final = new_folder_path_final[1:]
                    return jsonify({
                        'data': {
                            'newFolderPath': new_folder_path_final
                        },
                        'message': '批量重命名成功。',
                        'statusCode': 'OK'
                    })
                else:
                    raise OSError('重命名文件夹失败：' + response)
            else:
                return jsonify({
                    'data': {
                        'newFolderPath': ''
                    },
                    'message': f'获取资源错误：{video_files[0]}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
        else:
            if is_video_path == 1:  # 视频路径是文件夹
                return jsonify({
                    'data': {
                        'newFolderPath': ''
                    },
                    'message': f'不支持文件路径：{response}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
            else:
                return jsonify({
                    'data': {
                        'newFolderPath': ''
                    },
                    'message': f'资源路径错误：{response}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'newFolderPath': ''
            },
            'message': f'批量重命名失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getTotalEpisode', methods=['GET'])
# 用于获取文件夹中的集数信息
def api_get_total_episode():
    try:
        # 从请求URL中获取参数
        folder_path = request.args.get('folderPath', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        folder_path = os.path.abspath(os.path.join(media_path, folder_path))

        # 为保证安全，确认绝对路径为media目录
        if not folder_path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if folder_path == '':
            return jsonify({
                'data': {
                    'totalEpisode': ''
                },
                'message': '缺少资源路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if not os.path.exists(folder_path):
            return jsonify({
                'data': {
                    'totalEpisode': ''
                },
                'message': '您提供的文件路径不存在。',
                'statusCode': 'FILE_PATH_ERROR'
            }), 422

        episode_start_number = request.args.get('episodeStartNumber', default='', type=str)

        if episode_start_number == '' or episode_start_number == '':
            episode_start_number = '1'

        is_video_path, response = check_path_and_find_video(folder_path)  # 获取视频的路径

        if is_video_path == 2:  # 视频路径是文件夹
            get_video_files_success, video_files = get_video_files(folder_path)  # 获取文件夹内部的所有文件

            if get_video_files_success:
                print('检测到以下文件：', video_files)
                episode_start_number = int(episode_start_number)
                episode_num = len(video_files)  # 获取视频文件的总数

                if episode_start_number == 1:
                    total_episode = '全' + str(episode_num) + '集'
                else:
                    if str(episode_start_number) == str(episode_start_number + episode_num - 1):
                        total_episode = '第' + str(episode_start_number) + '集'
                    else:
                        total_episode = '第' + str(episode_start_number) + '-' + str(
                            episode_start_number + episode_num - 1) + '集'
                return jsonify({
                    'data': {
                        'totalEpisode': total_episode
                    },
                    'message': '获取集数信息成功。',
                    'statusCode': 'OK'
                })
            else:
                return jsonify({
                    'data': {
                        'totalEpisode': ''
                    },
                    'message': f'获取资源错误：{video_files[0]}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
        else:
            if is_video_path == 1:  # 视频路径是文件夹
                return jsonify({
                    'data': {
                        'totalEpisode': ''
                    },
                    'message': f'不支持文件路径：{response}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
            else:
                return jsonify({
                    'data': {
                        'totalEpisode': ''
                    },
                    'message': f'资源路径错误：{response}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'totalEpisode': ''
            },
            'message': f'批量重命名失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getComboBoxData', methods=['GET'])
# 用于读取playlet-source.json source.json team.json文件中的数据
def api_get_combo_box_data():
    try:
        # 从请求URL中获取参数
        configuration_name = request.args.get('configurationName', default='', type=str)  # 必须信息

        if configuration_name == '':
            return jsonify({
                'data': {
                    'configurationData': ''
                },
                'message': '缺少所需数据名称。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if configuration_name != 'playlet-source' and configuration_name != 'source' and configuration_name != 'team':
            return jsonify({
                'data': {
                    'configurationData': ''
                },
                'message': '数据名称不在范围内。',
                'statusCode': 'PARAMETER_RANGE_ERROR'
            }), 422
        else:
            get_combo_box_data_success, response = get_combo_box_data(configuration_name)
            if get_combo_box_data_success:
                return jsonify({
                    'data': {
                        'configurationData': response
                    },
                    'message': '获取数据成功。',
                    'statusCode': 'OK'
                })
            else:
                return jsonify({
                    'data': {
                        'configurationData': ''
                    },
                    'message': f'获取数据失败：{response}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'configurationData': ''
            },
            'message': f'获取数据失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/updateComboBoxData', methods=['POST'])
# 用于更新combo-box-data.json文件中的数据
def api_update_combo_box_data():
    try:
        # 从请求URL中获取参数
        configuration_name = request.args.get('configurationName', default='', type=str)  # 必须信息

        if configuration_name == '':
            return jsonify({
                'data': {},
                'message': '缺少所需数据名称。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if configuration_name != 'playlet-source' and configuration_name != 'source' and configuration_name != 'team':
            return jsonify({
                'data': {},
                'message': '数据名称不在范围内。',
                'statusCode': 'PARAMETER_RANGE_ERROR'
            }), 422

        configuration_data = request.args.get('configurationData', default='', type=str)  # 必须信息

        if configuration_data == '':
            return jsonify({
                'data': {},
                'message': '缺少数据内容。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422
        else:
            update_data_in_json_success, response = update_combo_box_data(configuration_data, configuration_name)
            if update_data_in_json_success:
                return jsonify({
                    'data': {},
                    'message': '更新数据成功。',
                    'statusCode': 'OK'
                })
            else:
                return jsonify({
                    'data': {},
                    'message': f'更新数据失败：{response}。',
                    'statusCode': 'BACKEND_PROCESSING_ERROR'
                }), 400
    except Exception as e:
        return jsonify({
            'data': {},
            'message': f'更新数据失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getSettings', methods=['GET'])
# 用于获取settings.json的数据
def api_get_settings():
    try:
        # 从请求URL中获取参数
        settings_name = request.args.get('settingsName', default='', type=str)  # 必须信息

        if settings_name == '':
            return jsonify({
                'data': {
                    'settingsData': ''
                },
                'message': '缺少所需获取的设置信息名称。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        settings_data = get_settings(settings_name)
        return jsonify({
            'data': {
                'settingsData': settings_data
            },
            'message': '获取设置信息成功。',
            'statusCode': 'OK'
        })
    except Exception as e:
        return jsonify({
            'data': {
                'settingsData': ''
            },
            'message': f'获取设置信息失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/updateSettings', methods=['POST'])
# 用于更新settings.json的数据
def api_update_settings():
    try:
        # 从请求URL中获取参数
        settings_name = request.args.get('settingsName', default='', type=str)  # 必须信息

        if settings_name == '':
            return jsonify({
                'data': {},
                'message': '缺少所需更新的设置信息名称。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        settings_data = request.args.get('settingsData', default='', type=str)  # 必须信息

        if settings_data == '':
            return jsonify({
                'data': {},
                'message': '缺少所需更新的设置信息的值。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        update_settings(settings_name, settings_data)
        return jsonify({
            'data': {},
            'message': '更新设置信息成功。',
            'statusCode': 'OK'
        })
    except Exception as e:
        return jsonify({
            'data': {},
            'message': f'更新设置信息失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getFile', methods=['GET'])
# 用于获取本地种子、图片文件
def api_get_file():
    try:
        # 从请求参数中获取文件路径
        file_path = request.args.get('filePath', default='', type=str)  # 获取文件路径

        # 检查文件路径参数是否已提供
        if file_path == '':
            return jsonify({
                'data': {},
                'message': '缺少所需的文件路径参数。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        # 先构建绝对路径，再进行校验防止越权
        temp_path = combine_directories('temp')
        target_path = os.path.abspath(file_path)

        # 确认绝对路径为temp目录即可
        if not target_path.startswith(temp_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        # 检查文件是否存在
        if not os.path.exists(target_path):
            print(target_path)
            return jsonify({
                'data': {},
                'message': '文件未找到。',
                'statusCode': 'FILE_NOT_FOUND'
            }), 404

        # 返回文件
        return send_file(target_path, as_attachment=True)
    except Exception as e:
        return jsonify({
            'data': {},
            'message': f'获取文件失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/settings', methods=['GET'])
# 用于获取settings.json的数据，返回所有参数
def api_settings():
    try:
        # 从请求URL中获取参数
        settings_json = get_settings_json()
        return jsonify({
            'data': {
                'settings': settings_json
            },
            'message': '获取设置信息成功。',
            'statusCode': 'OK'
        })
    except Exception as e:
        return jsonify({
            'data': {
                'settings': ''
            },
            'message': f'获取设置信息失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/settings/update', methods=['POST'])
# 更新所有参数
def api_settings_update():
    try:
        # 从请求URL中获取参数
        request_body = request.json
        update_settings_json(request_body)
        return jsonify({
            'data': {},
            'message': '更新设置信息成功。',
            'statusCode': 'OK'
        })
    except Exception as e:
        return jsonify({
            'data': {},
            'message': f'更新设置信息失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/getPTGenInfoByResourceUrl', methods=['GET'])
# 用于获取PT-Gen简介，传入一个豆瓣链接，返回PT-Gen简介
def api_get_pt_gen_info_by_url():
    try:
        # 从请求URL中获取参数
        resource_url = request.args.get('resourceUrl', default='', type=str)  # 必须信息
        if resource_url == '':
            return jsonify({
                'data': {
                    'description': ''
                },
                'message': '缺少资源链接。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        pt_gen_api_url = request.args.get('ptGenApiUrl', default=get_settings('pt_gen_api_url'), type=str)
        if pt_gen_api_url == '':
            pt_gen_api_url = get_settings('pt_gen_api_url')

        get_pt_gen_description_success, response = get_pt_gen_description(pt_gen_api_url, resource_url)
        if get_pt_gen_description_success:
            # response is now (format_data, full_data)
            format_data, full_data = response
            original_title, english_title, year, other_names_sorted, category, actors_list, episodes, season = get_pt_gen_info(
                format_data, raw_data=full_data)
            actors = ''
            other_titles = ''
            is_first = True

            for data in actors_list:  # 把演员名转化成str
                if is_first:
                    actors += data
                    is_first = False
                else:
                    actors += ' / '
                    actors += data

            for data in other_names_sorted:  # 把别名转化为str
                other_titles += data
                other_titles += ' / '

            other_titles = other_titles[: -3]
            return jsonify({
                'data': {
                    'originalTitle': original_title,
                    'englishTitle': english_title,
                    'year': year,
                    'otherTitles': other_titles,
                    'category': category,
                    'actors': actors,
                    'description': response
                },
                'message': '获取PT-Gen简介关键参数成功。',
                'statusCode': 'OK'
            })
        else:
            return jsonify({
                'data': {
                    'description': ''
                },
                'message': f'获取PT-Gen简介失败：{response}。',
                'statusCode': 'BACKEND_PROCESSING_ERROR'
            }), 400
    except Exception as e:
        return jsonify({
            'data': {
                'description': ''
            },
            'message': f'获取PT-Gen简介失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


@api.route('/api/media/file/list', methods=['GET'])
# 用于获取文件
def api_medis_path():
    try:
        # 从请求URL中获取参数
        path = request.args.get('path', default='', type=str)  # 必须信息
        media_path = combine_directories('media')
        target_path = os.path.abspath(os.path.join(media_path, path))
        # 确认绝对路径为temp目录即可
        if not target_path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此文件。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401
        # 获取当前目录下文件列表
        contents = list_files_and_dirs(target_path)
        return jsonify({
            'data': {
                'fileList': contents,
            },
            'message': '获取成功',
            'statusCode': 'OK'
        }), 200

    except Exception as e:
        return jsonify({
            'data': {
                'description': ''
            },
            'message': f'获取路径失败：{e}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500


def list_files_and_dirs(target_path):
    """
    Lists files and directories in the given target path along with their sizes and types.

    Args:
    - target_path (str): The path to the directory to list contents from.

    Returns:
    - list: A list of dictionaries, each containing the name, size, and type ('file' or 'directory') of each item in the target directory.
    """
    file_list = []
    try:
        # List all entries in the directory given by 'target_path'
        for entry in os.listdir(target_path):
            full_path = os.path.join(target_path, entry)
            if os.path.isfile(full_path):
                # It's a file, get its size using os.path.getsize()
                size = os.path.getsize(full_path)
                file_list.append({'name': entry, 'size': convert_size(size), 'type': '文件'})
            elif os.path.isdir(full_path):
                # It's a directory, size is not applicable
                file_list.append({'name': entry, 'size': 'N/A', 'type': '文件夹'})
    except Exception as e:
        raise RuntimeError(f'Error accessing {target_path}: {e}', e)
    return file_list


def convert_size(size_bytes):
    """
    Convert the given file size in bytes to a human-readable format.

    Args:
    - size_bytes (int): File size in bytes.

    Returns:
    - str: Human-readable file size.
    """
    if size_bytes == 0:
        return '0B'

    size_name = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    i = 0
    while size_bytes >= 1024 and i < len(size_name) - 1:
        size_bytes /= 1024
        i += 1

    return '{:.2f} {}'.format(size_bytes, size_name[i])


@api.route('/api/autoHandleVideo', methods=['GET'])
# 用于获取MediaInfo，传入一个文件地址或者一个文件夹地址，返回视频文件路径和MediaInfo
def api_auto_handle_movie():
    try:
        resource_url = request.args.get('resourceUrl', default='', type=str)  # 必须信息
        path = request.args.get('path', default='', type=str)  # 必须信息
        source = request.args.get('source', default='', type=str)  # 必须信息
        team = request.args.get('team', default='', type=str)  # 必须信息
        category = request.args.get('category', default='', type=str)  # 必须信息
        season = request.args.get('season', default='1', type=str)
        episodes_start_number = request.args.get('episodesStartNumber', default='1', type=str)

        if season == '':
            season = '1'
        if episodes_start_number == '':
            episodes_start_number = 1
        else:
            episodes_start_number = validate_and_convert_to_int(episodes_start_number, 'episodes_start_number')

        # 为了保证安全，只能访问media目录下的资源
        media_path = combine_directories('media')
        path = os.path.abspath(os.path.join(media_path, path))
        if not path.startswith(media_path):
            return jsonify({
                'data': {},
                'message': '无权访问此路径下的视频文件，请把视频文件储存在media目录下。',
                'statusCode': 'UNAUTHORIZED_ACCESS_ERROR'
            }), 401

        if resource_url == '':
            return jsonify({
                'data': {},
                'message': '缺少资源链接。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if path == '':
            return jsonify({
                'data': {},
                'message': '缺少资源文件路径。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if source == '':
            return jsonify({
                'data': {},
                'message': '缺少资源来源信息。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if team == '':
            return jsonify({
                'data': {},
                'message': '缺少制作组信息。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        if category == '':
            return jsonify({
                'data': {},
                'message': '缺少资源类型信息。',
                'statusCode': 'MISSING_REQUIRED_PARAMETER'
            }), 422

        @dataclass
        class Data:
            """数据，包含返回数据"""
            '''地区'''
            area: str
            '''音频编码'''
            audio_codec: str
            '''音轨数'''
            audio_num: str
            '''色深'''
            bit_depth: str
            '''类型'''
            category: str
            '''声道数'''
            channels: str
            '''简介'''
            description: str
            '''豆瓣链接'''
            douban_url: str
            '''文件名'''
            file_name: str
            '''帧率'''
            frame_rate: str
            '''HDR格式'''
            hdr_format: str
            '''IMDb链接'''
            imdb_url: str
            '''MI'''
            media_info: str
            '''媒介'''
            medium: str
            '''主标题'''
            main_title: str
            '''副标题'''
            second_title: str
            '''来源'''
            source: str
            '''标签，部分可识别的标签'''
            tags: []
            '''小组'''
            team: str
            '''种子文件'''
            torrent_file_url: str
            '''视频编码'''
            video_codec: str
            '''分辨率'''
            video_format: str

        data_instance = Data(
            area='',
            audio_codec='',
            audio_num='',
            bit_depth='',
            category='',
            channels='',
            description='',
            douban_url='',
            file_name='',
            frame_rate='',
            hdr_format='',
            imdb_url='',
            media_info='',
            medium='',
            main_title='',
            second_title='',
            source='',
            tags=[],
            team='',
            torrent_file_url='/api/getFile?filePath=',
            video_codec='',
            video_format='', )
        data_instance.source = source
        data_instance.team = team
        if category == 'Movie':
            data_instance.category = '电影'
        if category == 'TV':
            data_instance.category = '剧集'
        if 'AGSV' in team:
            data_instance.tags.extend(['官方', '冰种'])

        # 从后台读取参数
        pt_gen_api_url = get_settings('pt_gen_api_url')
        screenshot_storage_path = 'temp/pic'  # 默认储存位置，防止无法访问
        screenshot_number = int(get_settings('screenshot_number'))
        screenshot_threshold = float(get_settings('screenshot_threshold'))
        screenshot_start_percentage = float(get_settings('screenshot_start_percentage'))
        screenshot_end_percentage = float(get_settings('screenshot_end_percentage'))
        screenshot_min_interval_percentage = 0.01
        picture_bed_api_url = get_settings('picture_bed_api_url')
        picture_bed_api_token = get_settings('picture_bed_api_token')
        thumbnail_rows = int(get_settings('thumbnail_rows'))
        thumbnail_cols = int(get_settings('thumbnail_cols'))
        do_get_thumbnail = bool(get_settings('do_get_thumbnail'))
        delete_screenshot = bool(get_settings('delete_screenshot'))

        # 获取pt_gen简介
        get_pt_gen_description_success, response = get_pt_gen_description(pt_gen_api_url, resource_url)
        if not get_pt_gen_description_success:
            # 一次不成功，再试一次
            get_pt_gen_description_success, response = get_pt_gen_description(pt_gen_api_url, resource_url)
            if not get_pt_gen_description_success:
                raise RuntimeError(f'获取PT-Gen简介失败：{response}')

        # response is now (format_data, full_data)
        format_data, full_data = response
        # print(f'获取到pt_gen响应：{format_data}')
        data_instance.description = format_data

        # 获取截图
        if screenshot_number >= 0:
            if screenshot_number < 6:
                if 0 < screenshot_start_percentage < 1 and 0 < screenshot_end_percentage < 1:
                    if screenshot_start_percentage < screenshot_end_percentage:
                        is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
                        if is_video_path == 1 or is_video_path == 2:
                            video_path = response
                            screenshot_success, response = get_screenshot(video_path, screenshot_storage_path,
                                                                          screenshot_number,
                                                                          screenshot_threshold,
                                                                          screenshot_start_percentage,
                                                                          screenshot_end_percentage,
                                                                          screenshot_min_interval_percentage)

                            if screenshot_success:
                                # 获取截图成功了
                                picture_paths = response
                                for picture_path in picture_paths:
                                    # 开始逐个上传截图
                                    upload_picture_success, response = upload_picture(picture_bed_api_url,
                                                                                      picture_bed_api_token,
                                                                                      picture_path)
                                    if not upload_picture_success:
                                        # 一次不成功，再试一次
                                        upload_picture_success, response = upload_picture(picture_bed_api_url,
                                                                                          picture_bed_api_token,
                                                                                          picture_path)
                                        if not upload_picture_success:
                                            raise RuntimeError(f'上传图片到图床失败：{response}')
                                    # 上传截图成功，把截图bbs_url粘贴到简介后面
                                    picture_bbs_url = response
                                    data_instance.description += '\n' + picture_bbs_url
                                    # 是否删除截图
                                    if delete_screenshot:
                                        if os.path.exists(picture_path):
                                            # 删除文件
                                            os.remove(picture_path)
                                            print(f'文件 {picture_path} 已被删除。')
                                        else:
                                            print(f'文件 {picture_path} 不存在。')
                            else:
                                raise RuntimeError(f'截图失败：{response[0]}')
                        else:
                            raise ValueError(f'资源的路径不正确：{response}')
                    else:
                        raise ValueError(
                            f'截图起始点不可以大于终止点，您设置的起始点为{screenshot_start_percentage}，终止点为{screenshot_end_percentage}')
                else:
                    raise ValueError(
                        f'截图起始点和终止点均需要在0-1之间，您设置的起始点为{screenshot_start_percentage}，终止点为{screenshot_end_percentage}')
            else:
                raise ValueError(f'截图最多5张，您选择了{screenshot_number}张')
        else:
            raise ValueError(f'截图最少0张，您选择了{screenshot_number}张')

        if do_get_thumbnail:
            # 获取缩略图
            if thumbnail_rows > 0 and thumbnail_cols > 0:
                if 0 < screenshot_start_percentage < 1 and 0 < screenshot_end_percentage < 1:
                    if screenshot_start_percentage < screenshot_end_percentage:
                        is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
                        if is_video_path == 1 or is_video_path == 2:
                            video_path = response
                            get_thumbnail_success, response = get_thumbnail(video_path, screenshot_storage_path,
                                                                            thumbnail_rows,
                                                                            thumbnail_cols, screenshot_start_percentage,
                                                                            screenshot_end_percentage)
                            if get_thumbnail_success:
                                thumbnail_path = response
                                upload_picture_success, response = upload_picture(picture_bed_api_url,
                                                                                  picture_bed_api_token,
                                                                                  thumbnail_path)
                                if not upload_picture_success:
                                    # 一次不成功，再试一次
                                    upload_picture_success, response = upload_picture(picture_bed_api_url,
                                                                                      picture_bed_api_token,
                                                                                      thumbnail_path)
                                    if not upload_picture_success:
                                        raise RuntimeError(f'上传图片到图床失败：{response}')
                                # 上传截图成功，把缩略图bbs_url粘贴到简介后面
                                thumbnail_bbs_url = response
                                data_instance.description += '\n' + thumbnail_bbs_url
                                # 是否删除截图
                                if delete_screenshot:
                                    if os.path.exists(thumbnail_path):
                                        # 删除文件
                                        os.remove(thumbnail_path)
                                        print(f'文件 {thumbnail_path} 已被删除。')
                                    else:
                                        print(f'文件 {thumbnail_path} 不存在。')
                            else:
                                raise RuntimeError(f'生成缩略图失败：{response}')
                        else:
                            raise ValueError(f'资源的路径不正确：{response}')
                    else:
                        raise ValueError(
                            f'截图起始点不可以大于终止点，您设置的起始点为{screenshot_start_percentage}，终止点为{screenshot_end_percentage}')
                else:
                    raise ValueError(
                        f'截图起始点和终止点均需要在0-1之间，您设置的起始点为{screenshot_start_percentage}，终止点为{screenshot_end_percentage}')
            else:
                raise ValueError(f'缩略图的行列数均需要大于0，您设置的行数为{thumbnail_rows}，列数为{thumbnail_cols}')

        # 获取VideoInfo
        is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            get_video_info_success, response = get_video_info(video_path)
            if get_video_info_success:
                print('获取到VideoInfo：' + str(response))
                data_instance.video_format = response[0]
                data_instance.video_codec = response[1]
                data_instance.bit_depth = response[2]
                data_instance.hdr_format = response[3]
                data_instance.frame_rate = response[4]
                data_instance.audio_codec = response[5]
                data_instance.channels = response[6]
                data_instance.audio_num = response[7]
                data_instance.tags.extend(response[8])
            else:
                raise RuntimeError(f'获取VideoInfo失败：{response[0]}')
        else:
            raise ValueError(f'资源的路径不正确：{response}')

        # 获取PT-GenInfo
        print(f'获取PT-GenInfo，从{data_instance.description}')
        original_title, english_title, year, other_names_sorted, categories, actors_list, episodes, season = get_pt_gen_info(
            data_instance.description)
        print(original_title, english_title, year, other_names_sorted, categories, actors_list)
        actors = ''
        other_titles = ''
        is_first = True

        for data in actors_list:  # 把演员名转化成str
            if is_first:
                actors += data
                is_first = False
            else:
                actors += ' / '
                actors += data

        for data in other_names_sorted:  # 把别名转化为str
            other_titles += data
            other_titles += ' / '

        other_titles = other_titles[: -3]

        # 给个位数的季数前面补0
        season_number = season
        if len(season) < 2:
            season = '0' + season

        # 获取total_episode
        total_episodes = ''
        episodes_num = 0
        if category == 'TV':
            is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
            if is_video_path == 2:  # 视频路径是文件夹
                get_video_files_success, video_files = get_video_files(path)  # 获取文件夹内部的所有文件
                if get_video_files_success:
                    episodes_start_number = 1  # 默认从第一集开始
                    print('检测到以下文件：', video_files)
                    episodes_num = len(video_files)  # 获取视频文件的总数
                    if episodes_start_number == 1 and episodes == episodes_num:
                        total_episodes = f'全{str(episodes_num)}集'
                        data_instance.tags.append('合集')
                    else:
                        if episodes_num == 1:
                            total_episodes = f'第{str(episodes_start_number)}集'
                        else:
                            total_episodes = f'第{str(episodes_start_number)}-{str(episodes_start_number + episodes_num - 1)}集'
                        data_instance.tags.append('分集')
                    print(f'总集数信息：{total_episodes}')

                else:
                    raise RuntimeError(f'获取文件夹内部的所有文件失败：{response[0]}')
            else:
                raise ValueError(f'资源的路径不正确，必须是文件夹：{response}')

        # 获取主标题
        template = 'main_title_' + category.lower()
        data_instance.main_title = get_name_from_template(english_title, original_title, season, '{集数}', year,
                                                          data_instance.video_format,
                                                          data_instance.source, data_instance.video_codec,
                                                          data_instance.bit_depth, data_instance.hdr_format,
                                                          data_instance.frame_rate,
                                                          data_instance.audio_codec, data_instance.channels,
                                                          data_instance.audio_num, data_instance.team, other_titles,
                                                          season_number,
                                                          total_episodes, '', categories, actors, template)
        print(f'获取到主标题是{data_instance.main_title}')

        # 获取副标题
        template = 'second_title_' + category.lower()
        data_instance.second_title = get_name_from_template(english_title, original_title, season, '{集数}', year,
                                                            data_instance.video_format,
                                                            data_instance.source, data_instance.video_codec,
                                                            data_instance.bit_depth, data_instance.hdr_format,
                                                            data_instance.frame_rate,
                                                            data_instance.audio_codec, data_instance.channels,
                                                            data_instance.audio_num, data_instance.team, other_titles,
                                                            season_number,
                                                            total_episodes, '', categories, actors, template)
        print(f'获取到副标题是{data_instance.second_title}')

        # 获取文件名
        template = 'file_name_' + category.lower()
        data_instance.file_name = get_name_from_template(english_title, original_title, season, '{集数}', year,
                                                         data_instance.video_format,
                                                         data_instance.source, data_instance.video_codec,
                                                         data_instance.bit_depth, data_instance.hdr_format,
                                                         data_instance.frame_rate,
                                                         data_instance.audio_codec, data_instance.channels,
                                                         data_instance.audio_num, data_instance.team, other_titles,
                                                         season_number,
                                                         total_episodes, '', categories, actors, template)
        print(f'获取到文件名是{data_instance.file_name}')

        if category == 'Movie':
            # 给文件或者文件夹重命名
            is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
            if is_video_path == 1 or is_video_path == 2:
                file_path = response
                if is_video_path == 1:
                    print('开始把影片资源视频塞进文件夹')
                    move_file_to_folder_success, response = move_file_to_folder(file_path, data_instance.file_name)
                    if move_file_to_folder_success:
                        file_path = response
                    else:
                        raise RuntimeError(f'把影片资源视频塞进文件夹失败：{response}')
                if is_video_path == 2:
                    folder_path = path
                    # 开始对目录重命名
                    print('开始对影片资源目录重命名')
                    rename_success, response = rename_folder(folder_path, data_instance.file_name)
                    if rename_success:
                        new_folder_path = response
                        print(f'新的文件夹路径：{new_folder_path}')
                        is_video_path, response = check_path_and_find_video(new_folder_path)  # 视频资源的路径
                        if is_video_path == 2:
                            file_path = response
                    else:
                        raise RuntimeError(f'对影片资源目录重命名失败：{response}')

                # 开始对文件重命名
                print('开始对影片资源视频重命名')
                rename_success, response = rename_file(file_path, data_instance.file_name)
                if rename_success:
                    new_file_path = response
                    if is_video_path == 1:
                        path = new_file_path
                        print(f'重命名后的新文件路径：{path}')
                    if is_video_path == 2:
                        path = os.path.dirname(new_file_path)
                        print(f'重命名后的新文件夹路径：{path}')
                else:
                    raise RuntimeError(f'对影片资源视频重命名失败：{response}')
            else:
                raise ValueError(f'影片资源的路径不正确：{response}')
        if category == 'TV':
            # 给剧集重命名
            is_video_path, response = check_path_and_find_video(path)  # 视频资源的路径
            if is_video_path == 2:  # 视频路径是文件夹
                get_video_files_success, video_files = get_video_files(path)  # 获取文件夹内部的所有文件
                i = episodes_start_number
                print('开始对剧集资源文件夹里的视频重新命名')
                for video_file in video_files:
                    e = str(i)
                    while len(e) < len(str(episodes_start_number + episodes_num - 1)):
                        e = '0' + e
                    if len(e) == 1:
                        e = '0' + e
                    rename_file_success, response = rename_file(video_file,
                                                                data_instance.file_name.replace('{集数}', e))
                    if rename_file_success:
                        video_path = response
                        print('剧集资源视频成功重新命名为：' + video_path)
                    else:
                        print('重命名失败：' + response)
                        raise RuntimeError('剧集资源视频重命名失败：' + response)
                    i += 1
                print('对剧集资源文件夹重新命名')
                rename_directory_success, response = rename_folder(os.path.dirname(video_path), data_instance.file_name.
                                                                   replace('E{集数}', '').
                                                                   replace('{集数}', ''))
                if rename_directory_success:
                    path = response
                    print('剧集资源文件夹成功重新命名为：' + path)
                else:
                    raise RuntimeError('剧集资源文件夹重命名失败：' + response)
            else:
                raise ValueError(f'剧集资源的路径不正确，必须是文件夹：{response}')

        # 获取MediaInfo
        is_video_path, response = check_path_and_find_video(path)  # 资源的路径
        if is_video_path == 1 or is_video_path == 2:
            video_path = response
            get_media_info_success, response = get_media_info(video_path)
            if get_media_info_success:
                data_instance.media_info = response
                # print(f'成功获取MediaInfo：\n{data_instance.media_info}')
            else:
                raise RuntimeError('获取MediaInfo失败：' + response)
        else:
            raise ValueError(f'资源的路径不正确：{response}')

        print('开始分析其他关键参数')
        (data_instance.imdb_url, data_instance.douban_url, data_instance.category, data_instance.area,
         data_instance.video_format,
         data_instance.audio_codec, data_instance.video_codec, data_instance.medium) \
            = get_data_from_pt_gen_description(data_instance.main_title, data_instance.description,
                                               data_instance.media_info, data_instance.source, data_instance.category)
        # print('获得的参数：', data_instance.main_title, data_instance.second_title, data_instance.imdb_url,
        #       data_instance.douban_url, data_instance.description, data_instance.media_info, data_instance.category,
        #       data_instance.area, data_instance.video_format, data_instance.audio_codec, data_instance.video_codec,
        #       data_instance.medium, data_instance.team)

        # 开始制作种子
        torrent_storage_path = get_settings('torrent_storage_path')

        make_torrent_success, response = make_torrent(path, torrent_storage_path)
        if make_torrent_success:
            torrent_path = response
            # 动态生成文件下载链接
            base_url = request.base_url.rsplit('/', 1)[0]  # 获取当前API的基础URL
            data_instance.torrent_file_url = f'{base_url}/getFile?filePath={torrent_path}'

        else:
            raise RuntimeError(f'制作种子失败：{response}')

        return jsonify({
            'data': convert_to_camel_case(data_instance),
            'message': '获取成功。',
            'statusCode': 'OK'
        }), 200

    except ValueError as e:
        return jsonify({
            'data': {},
            'message': f'您提供的参数有误：{str(e)}。',
            'statusCode': 'RUNTIME_ERROR'
        }), 422

    except RuntimeError as e:
        return jsonify({
            'data': {},
            'message': f'自动处理视频资源失败：{str(e)}。',
            'statusCode': 'RUNTIME_ERROR'
        }), 500

    except Exception as e:
        return jsonify({
            'data': {},
            'message': f'自动处理视频文件时发生了意外错误：{str(e)}。',
            'statusCode': 'GENERAL_ERROR'
        }), 500
