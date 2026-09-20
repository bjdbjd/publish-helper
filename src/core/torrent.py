import datetime
import os
from typing import Tuple

from torf import Torrent


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