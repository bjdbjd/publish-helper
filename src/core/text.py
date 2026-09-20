import base64
import re
from typing import Any, List, Union

from xpinyin import Pinyin

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


def base64encoding(string: str) -> str:
    return base64.b64encode(string.encode('utf-8')).decode('utf-8')


def validate_and_convert_to_int(value: Any, value_name: str) -> int:
    if value is None or value == '':
        raise ValueError(f'{value_name} 不能为 None 或空字符串')

    try:
        converted_value = int(value)
    except ValueError as e:
        raise ValueError(f'{value_name} 必须是数字，您提供的是：{value}') from e

    return converted_value