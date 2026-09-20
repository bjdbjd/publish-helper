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
    if num == 0:
        return '零'

    digits = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    units = ['', '十', '百', '千']

    s = str(num)
    chars = []
    for i, ch in enumerate(s):
        d = int(ch)
        unit = units[len(s) - 1 - i]
        if d == 0:
            # 只有中间（后面还有非零位）才补 '零'；尾部/连续零不补
            if chars and chars[-1] != '零' and any(x != '0' for x in s[i + 1:]):
                chars.append('零')
        else:
            chars.append(digits[d] + unit)

    result = ''.join(chars)
    # 10-19 省略十位前导一：'一十'→'十'、'一十五'→'十五'
    if 10 <= num < 20:
        result = result[1:]
    return result


def chinese_to_int(chinese_num: str) -> Union[int, None]:
    try:
        if not chinese_num:
            return None
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
        unit_map = {
            '十': 10,
            '百': 100,
            '千': 1000,
            '万': 10000,
        }

        # 逐字符解析：数字字符累加到 current，遇到单位则按单位进档
        total = 0
        current = 0
        for char in chinese_num:
            if char in num_map:
                current = num_map[char]
            elif char in unit_map:
                unit = unit_map[char]
                # '十' 前无数字时视为 1 个十（'十' → 10）
                current = current if current != 0 else 1
                total += current * unit
                current = 0
            else:
                raise ValueError(f"无法识别的字符: {char}")
        total += current
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