# 此处仅提供一个简单的示例，具体实现起来方案有很多，可按需开发
import datetime
import json
import os
import random
from typing import Tuple

import requests

from src.utils.file_utils import combine_directories


def upload_picture(picture_bed_api_url, picture_bed_api_token, picture_path):
    print(picture_bed_api_url, picture_bed_api_token, picture_path)
    if not os.path.exists(picture_path):  # 检测是否存在图片
        print('图片文件路径不存在')
        return False, '图片文件路径不存在'
    else:
        print('开始获取图床类型')
        # 去除URL的中的' '、'　'和'\n'，针对用户错误输入的优化
        picture_bed_api_url = picture_bed_api_url.replace(' ', '')
        picture_bed_api_url = picture_bed_api_url.replace('　', '')
        picture_bed_api_url = picture_bed_api_url.replace('\n', '')
        get_picture_bed_type_success, picture_bed_type = get_picture_bed_type(picture_bed_api_url)
        if get_picture_bed_type_success:
            print(f'获取到图床的类型：{picture_bed_type}')
            if picture_bed_type == 'lsky-pro':
                return lsky_pro_picture_bed(picture_bed_api_url, picture_bed_api_token, picture_path)
            elif picture_bed_type == 'bohe':
                return bohe_picture_bed(picture_bed_api_url, picture_bed_api_token, picture_path)
            elif picture_bed_type == 'chevereto':
                return chevereto_picture_bed(picture_bed_api_url, picture_bed_api_token, picture_path)
            elif picture_bed_type == 'freeimage':
                return freeimage_picture_bed(picture_bed_api_url, picture_bed_api_token, picture_path)
            elif picture_bed_type == 'imgbb':
                return imgbb_picture_bed(picture_bed_api_url, picture_bed_api_token, picture_path)
            elif picture_bed_type == 'pixhost':
                return pixhost_picture_bed(picture_bed_api_url, picture_path)
            else:
                return False, '你错误更改了图床配置文件？冒号前面的类型是不能随便改的！如果需要支持更多新类型的图床请提Issues，前提是图床支持API上传！'
        else:
            return False, picture_bed_type


# 兰空图床
def lsky_pro_picture_bed(api_url, api_token, frame_path):
    print('接受到上传兰空图床请求')
    url = api_url
    files = {'file': (frame_path, open(frame_path, 'rb'), 'image/png')}
    headers = {'Authorization': api_token, 'Accept': 'json'}
    data = {}
    print('值已经获取')

    # Debug: print request details
    print(f'[DEBUG] Request URL: {url}')
    print(f'[DEBUG] Headers: {headers}')
    print(f'[DEBUG] File path: {frame_path}')
    print(f'[DEBUG] File size: {os.path.getsize(frame_path)} bytes')

    try:
        # 发送POST请求
        print('开始发送上传图床的请求')
        res = requests.post(url, headers=headers, data=data, files=files)
        print('已成功发送上传图床的请求')
        print(f'响应状态码：{res.status_code}')
        print(f'[DEBUG] Response headers: {dict(res.headers)}')
        print(f'响应内容：{res.text[:500] if res.text else "(empty)"}')  # Print first 500 chars to avoid overwhelming output
    except requests.RequestException as e:
        print(f'请求过程中出现错误：{str(e)}')
        return False, f'请求过程中出现错误：{str(e)}'

    # Check HTTP status code first
    if res.status_code != 200:
        print(f'图床API返回非200状态码：{res.status_code}')
        return False, f'图床API返回错误状态码：{res.status_code}，响应内容：{res.text}'

    try:
        data = json.loads(res.text)
        # 检查data是否为None或不包含预期的结构
        if data is None:
            print(f'图床API返回了空数据，响应文本：{res.text}')
            return False, f'图床API返回了空数据，响应文本：{res.text}'
        
        # Check if the API returned an error in the response
        if 'status' in data and data['status'] is False:
            error_msg = data.get('message', '未知错误')
            print(f'图床API返回错误：{error_msg}')
            return False, f'图床API返回错误：{error_msg}'
        
        # Validate nested structure exists
        if 'data' not in data or data['data'] is None:
            print(f'图床API响应缺少data字段，完整响应：{res.text}')
            return False, f'图床API响应格式错误：缺少data字段'
        
        if 'links' not in data['data'] or data['data']['links'] is None:
            print(f'图床API响应缺少links字段，data内容：{data.get("data")}')
            return False, f'图床API响应格式错误：缺少links字段'
        
        if 'bbcode' not in data['data']['links']:
            print(f'图床API响应缺少bbcode字段，links内容：{data["data"]["links"]}')
            return False, f'图床API响应格式错误：缺少bbcode字段'
        
        # 提取所需的URL
        image_bbs_url = data['data']['links']['bbcode']
        print(image_bbs_url)
        return True, image_bbs_url
    except KeyError as e:
        print(f'图床响应结果缺少所需的值：{str(e)}，响应内容：{res.text}')
        return False, f'图床响应结果缺少所需的值：{str(e)}，响应内容：{res.text}'
    except json.JSONDecodeError as e:
        print(f'处理返回的JSON过程中出现错误：{str(e)}，响应文本：{res.text}')
        return False, f'处理返回的JSON过程中出现错误：{str(e)}，响应文本：{res.text}'


# 薄荷图床
def bohe_picture_bed(api_url, api_token, frame_path):
    print('开始上传薄荷图床')
    url = api_url
    files = {'uploadedFile': (frame_path, open(frame_path, 'rb'), 'image/png')}
    data = {'api_token': api_token, 'image_compress': 0, 'image_compress_level': 80}

    try:
        # 发送POST请求
        res = requests.post(url, data=data, files=files)
        print('已成功发送上传图床的请求')
    except requests.RequestException as e:
        print(f'请求过程中出现错误：{str(e)}')
        return False, f'请求过程中出现错误：{str(e)}'

    # 关闭文件流，避免资源泄露
    files['uploadedFile'][1].close()

    # 将响应文本转换为字典
    try:
        api_response = json.loads(res.text)
    except json.JSONDecodeError:
        print('响应不是有效的JSON格式')
        return False, '响应不是有效的JSON格式'

    # 打印提取的url
    status_code = api_response.get('statusCode', '')
    result_data = api_response.get('resultData', '')

    if status_code == '200':
        image_bbs_url = str(api_response.get('bbsurl', ''))
        return True, image_bbs_url
    elif status_code == '':
        return False, '未接受到响应'
    else:
        return False, f'API响应出错了，错误码：{status_code}，错误提示：{result_data}'


# chevereto图床
def chevereto_picture_bed(api_url, api_token, frame_path):
    print('接受到上传chevereto图床请求')
    url = api_url
    data = {'expiration': 'PT5M', 'X-API-Key': api_token, 'key': api_token}
    files = {'source': (frame_path, open(frame_path, 'rb'), 'image/png')}
    print('值已经获取')

    try:
        # 发送POST请求
        print('开始发送上传图床的请求')
        res = requests.post(url, data=data, files=files)
        print('已成功发送上传图床的请求')
    except requests.RequestException as e:
        print(f'请求过程中出现错误：{str(e)}')
        return False, f'请求过程中出现错误：{str(e)}'

    try:
        print(res.text)
        data = json.loads(res.text)
        # 提取所需的URL
        image_url = data['image']['url']
        print(image_url)
        return True, f'[img]{image_url}[/img]'
    except KeyError as e:
        print(f'图床响应结果缺少所需的值：{str(e)}，{str(res)}')
        return False, f'图床响应结果缺少所需的值：{str(e)}，{str(res)}'
    except json.JSONDecodeError as e:
        print(f'处理返回的JSON过程中出现错误：{str(e)}，{str(res)}')
        return False, f'处理返回的JSON过程中出现错误：{str(e)}，{str(res)}'


# freeimage图床
def freeimage_picture_bed(api_url, api_token, frame_path):
    print('接受到上传freeimage图床请求')
    url = api_url
    data = {'key': api_token, 'format': 'txt'}
    files = {'source': (frame_path, open(frame_path, 'rb'), 'image/png')}
    print('值已经获取')

    try:
        # 发送POST请求
        print('开始发送上传图床的请求')
        res = requests.post(url, data=data, files=files)
        print('已成功发送上传图床的请求')
    except requests.RequestException as e:
        print('请求过程中出现错误：', e)
        return False, '请求过程中出现错误：' + str(e)

    print(res.text)
    if res.text[:4] == 'http':
        bbs_url = '[img]' + res.text + '[/img]'
        print(bbs_url)
        return True, bbs_url
    else:
        return False, res.text


# imgbb图床
def imgbb_picture_bed(api_url, api_token, frame_path):
    print('接受到上传imgbb图床请求')
    url = api_url
    data = {'expiration': '600', 'key': api_token}
    files = {'image': (frame_path, open(frame_path, 'rb'), 'image/png')}
    print('值已经获取')

    try:
        # 发送POST请求
        print('开始发送上传图床的请求')
        res = requests.post(url, data=data, files=files)
        print('已成功发送上传图床的请求')
    except requests.RequestException as e:
        print('请求过程中出现错误：', e)
        return False, '请求过程中出现错误：' + str(e)

    try:
        data = json.loads(res.text)
        # 提取所需的URL
        image_url = data['data']['image']['url']
        print(image_url)
        return True, f'[img]{image_url}[/img]'
    except KeyError as e:
        print(f'图床响应结果缺少所需的值：{str(e)}，{str(res)}')
        return False, f'图床响应结果缺少所需的值：{str(e)}，{str(res)}'
    except json.JSONDecodeError as e:
        print(f'处理返回的JSON过程中出现错误：{str(e)}，{str(res)}')
        return False, f'处理返回的JSON过程中出现错误：{str(e)}，{str(res)}'


# pixhost图床
def pixhost_picture_bed(api_url, frame_path):
    print('接受到上传pixhost图床请求')
    url = api_url
    files = {'img': (frame_path, open(frame_path, 'rb'), 'image/jpeg')}
    data = {'content_type': 0, 'max_th_size': 420}
    headers = {'Accept': 'application/json'}
    print('值已经获取')

    try:
        # 发送POST请求
        print('开始发送上传图床的请求')
        res = requests.post(url, headers=headers, data=data, files=files)
        print('已成功发送上传图床的请求')
    except requests.RequestException as e:
        print('请求过程中出现错误：', e)
        return False, '请求过程中出现错误：' + str(e)

    try:
        data = json.loads(res.text)
        # 提取所需的URL
        image_url = data['th_url']
        image_url = image_url.replace('//t', '//img')
        image_url = image_url.replace('/thumbs/', '/images/')
        print(image_url)
        return True, f'[img]{image_url}[/img]'
    except KeyError as e:
        print(f'图床响应结果缺少所需的值：{str(e)}，{str(res)}')
        return False, f'图床响应结果缺少所需的值：{str(e)}，{str(res)}'
    except json.JSONDecodeError as e:
        print(f'处理返回的JSON过程中出现错误：{str(e)}，{str(res)}')
        return False, f'处理返回的JSON过程中出现错误：{str(e)}，{str(res)}'


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


def generate_image_filename(base_path: str) -> str:
    now = datetime.datetime.now()
    date_time = now.strftime('%Y%m%d-%H%M%S')
    letters = random.sample('0123456789', 6)
    random_str = ''.join(letters)
    filename = f'{date_time}-{random_str}.png'
    path = base_path + '/' + filename
    return path
