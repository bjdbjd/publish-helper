import requests

from src.core.tool import get_settings


def get_pt_gen_description(pt_gen_api_url, resource_url):
    try:
        # 清除多余的空格
        resource_url.replace(' ', '')
        resource_url.replace('　', '')

        # 检查是否是tt开头后面跟数字的字符串
        if resource_url.startswith('tt') and resource_url[2:].isdigit():
            resource_url = f'https://www.imdb.com/title/{resource_url}/'
        # 检查是否是纯数字的字符串
        elif resource_url.isdigit():
            resource_url = f'https://movie.douban.com/subject/{resource_url}/'

        # 去除后缀
        resource_url = resource_url.split('?')[0]

        # 设置一个合理的超时时间，10s
        response = requests.get(f'{pt_gen_api_url}?url={resource_url}', timeout=10)

        # 检查响应是否成功
        if response.status_code != 200:
            print('请求失败，状态码:', response.status_code)
            return False, f'PT-Gen接口请求失败，状态码：{str(response.status_code)}'

        # 尝试解析JSON响应
        try:
            data = response.json()
            print(f'[DEBUG] PT-Gen API URL: {pt_gen_api_url}')
            print(f'[DEBUG] Resource URL: {resource_url}')
            print(f'[DEBUG] Response keys: {list(data.keys())}')
            print(f'[DEBUG] chinese_title: {data.get("chinese_title", "N/A")}')
            print(f'[DEBUG] foreign_title: {data.get("foreign_title", "N/A")}')
        except ValueError:
            print('响应不是有效的JSON格式')
            return False, 'PT-Gen接口响应不是有效的JSON格式，请检查PT-Gen接口是否正常'

        # 根据响应结构获取format字段
        format_data = data.get('format') if 'format' in data else data.get('data', {}).get('format', '')

        # 返回处理后的format字段和完整的数据
        if format_data != '' and format_data is not None:
            print(f'[DEBUG] Raw format_data (first 500 chars): {repr(format_data[:500])}')
            format_data = format_data.replace('&#39;', '\'')

            # Post-process: restructure title fields using raw data
            # 片名 = foreign_title, 译名 = chinese_title, 别名 = aka titles
            chinese_title = data.get('chinese_title', '')
            if chinese_title:
                import re as _re
                # Match the 译名 line with both ◎ and ❁ prefix formats
                # Pattern: prefix + 译　　名 + separator + content + newline
                trans_pattern = _re.compile(
                    r'(([◎❁])\s*译\s*名\s*[:：]?\s*)(.*?)(\n)',
                    _re.DOTALL
                )
                match = trans_pattern.search(format_data)
                if match:
                    prefix_char = match.group(2)  # ◎ or ❁
                    aka_content = match.group(3).strip()  # original 译名 content (aka titles)
                    # Detect the separator style used in the description
                    # ◎ format uses ◎译　　名　, ❁ format uses ❁ 译　　名:　
                    if prefix_char == '❁':
                        new_trans_line = f'❁ 译　　名:　{chinese_title}\n'
                        if aka_content:
                            new_trans_line += f'❁ 别　　名:　{aka_content}\n'
                    else:
                        new_trans_line = f'◎译　　名　{chinese_title}\n'
                        if aka_content:
                            new_trans_line += f'◎别　　名　{aka_content}\n'
                    format_data = format_data[:match.start()] + new_trans_line + format_data[match.end():]
                    print(f'[DEBUG] Restructured title fields: 译名={chinese_title}')

            personalized_signature = get_settings("personalized_signature")
            # 处理简介
            if personalized_signature != '' and format_data is not None:
                format_data = personalized_signature + '\n' + format_data
            format_data += '\n'
            format_data = format_data.replace('img1', 'img2')
            # Return both format and full data for poster URL extraction
            return True, (format_data, data)
        else:
            return False, '获取到的PT-Gen简介为空，可能是资源链接有误或PT-Gen接口出错，请检查后重试'

    except requests.Timeout:
        # 处理超时异常
        print('请求超时')
        return False, 'PT-Gen接口请求超时'

    except requests.RequestException as e:
        # 处理响应过程中的其他异常
        print(f'请求发生错误：{e}')
        return False, f'PT-Gen接口响应发生错误：{e}'

    except Exception as e:
        # 处理请求过程中的其他异常
        print(f'请求发生错误：{e}')
        return False, f'PT-Gen接口请求发生错误：{e}'
