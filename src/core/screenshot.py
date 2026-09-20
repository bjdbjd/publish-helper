import os
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from src.core.picturebed import generate_image_filename


# 参数：video_path：源视频路径；screenshot_path：输出图片路径；screenshot_number：截图的总数量；screenshot_start：截图的起始帧占比，避免截取黑帧；
# screenshot_end：截图的结束帧占比，中间的范围不要太小，否则会导致截图数量不够；min_interval：最小帧间隔占比，避免连续截图；
# screenshot_threshold：参数，用于判断关键帧的复杂程度，数字越大越复杂，不宜过大，否则可能会导致截图数量不够
def get_screenshot(video_path, screenshot_path, screenshot_number, screenshot_threshold, screenshot_start,
                   screenshot_end,
                   screenshot_min_interval=0.01):
    # 确保输出路径存在
    try:
        if not os.path.exists(screenshot_path):
            os.makedirs(screenshot_path)
            print('已创建输出路径')
    except PermissionError:
        print('权限不足，无法创建目录')
        return False, ['权限不足，无法创建目录']
    except FileExistsError:
        print('路径已存在，且不是目录')
        return False, ['路径已存在，且不是目录']
    except Exception as e:
        print(f'创建目录时出错：{e}')
        return False, [f'创建目录时出错：{e}']

    try:
        # 加载视频
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print('无法加载视频')
            return False, ['无法加载视频']
        else:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps
            print('加载视频成功')

            # 计算起止时间帧编号
            start_frame = int(total_frames * screenshot_start)
            end_frame = int(total_frames * screenshot_end)
            screenshot_min_interval = duration * screenshot_min_interval
            print(f'起止帧：{str(start_frame)} 终止帧：{str(end_frame)} 最小帧间隔：{str(screenshot_min_interval)}')

            # 初始化变量
            extracted_images = []
            last_keyframe_time = -screenshot_min_interval

            # 生成随机时间戳
            timestamps = sorted(random.sample(range(start_frame, end_frame), screenshot_number))

            for timestamp in timestamps:
                # 跳转到特定帧
                cap.set(cv2.CAP_PROP_POS_FRAMES, timestamp)
                ret, frame = cap.read()
                if not ret:
                    continue

                current_time = timestamp / fps
                if current_time >= last_keyframe_time + screenshot_min_interval:
                    std_dev = np.std(frame)
                    print(f'Frame ID: {timestamp}, Timestamp: {current_time}, Std Dev: {std_dev}')  # 调试信息

                    if std_dev > screenshot_threshold:
                        frame_path = generate_image_filename(screenshot_path)
                        im_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        im_pil.save(Path(frame_path))
                        extracted_images.append(frame_path)
                        last_keyframe_time = current_time
                    else:
                        print('当前帧不满足复杂度要求，获取随机帧代替')  # 调试信息
                        timestamp = random.sample(range(start_frame, end_frame), 1)[0]
                        cap.set(cv2.CAP_PROP_POS_FRAMES, timestamp)
                        ret, frame = cap.read()
                        frame_path = generate_image_filename(screenshot_path)
                        im_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        im_pil.save(Path(frame_path))
                        extracted_images.append(frame_path)
                else:
                    print('当前帧不满足时间间隔要求，获取随机帧代替')  # 调试信息
                    timestamp = random.sample(range(start_frame, end_frame), 1)[0]
                    cap.set(cv2.CAP_PROP_POS_FRAMES, timestamp)
                    ret, frame = cap.read()
                    frame_path = generate_image_filename(screenshot_path)
                    im_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    im_pil.save(Path(frame_path))
                    extracted_images.append(frame_path)

            cap.release()

            print(extracted_images)
            return True, extracted_images
    except Exception as e:
        print(f'截图出错：{e}')
        return False, [f'截图出错：{e}']


def get_thumbnail(video_path, screenshot_storage_path, thumbnail_rows, thumbnail_cols, screenshot_start_percentage,
                  screenshot_end_percentage):
    try:
        if not os.path.exists(screenshot_storage_path):  # 输出路径不存在
            os.makedirs(screenshot_storage_path)
            print('已创建输出路径。')
    except PermissionError:
        print('权限不足，无法创建目录。')
        return False, ['权限不足，无法创建目录']
    except FileExistsError:
        print('路径已存在，且不是目录。')
        return False, ['路径已存在，且不是目录']
    except Exception as e:
        print(f'创建目录时出错：{e}')
        return False, [f'创建目录时出错：{e}']
    video_capture = None
    try:
        video_capture = cv2.VideoCapture(video_path)

        if not video_capture.isOpened():  # 打不开文件
            raise Exception('Error: 无法打开视频文件')

        total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))

        # 计算开始和结束帧
        start_frame = int(total_frames * screenshot_start_percentage)
        end_frame = int(total_frames * screenshot_end_percentage)

        # 计算每张截取图像的时间间隔
        interval = (end_frame - start_frame) // (thumbnail_cols * thumbnail_rows)

        images = []

        for i in range((thumbnail_cols * thumbnail_rows)):
            frame_number = start_frame + i * interval
            if frame_number >= end_frame:
                break

            video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = video_capture.read()

            if not ret:
                raise Exception(f'Error: 无法读取第 {i + 1} 张图像')

            images.append(frame)

        # 处理图像数量小于预期的情况
        if len(images) < (thumbnail_cols * thumbnail_rows):
            print(f'Warning: 只能获取 {len(images)} 张图像，小于预期的 {thumbnail_cols * thumbnail_rows} 张')

        resized_images = [cv2.resize(image, (0, 0), fx=1.0 / thumbnail_rows, fy=1.0 / thumbnail_rows) for image in
                          images]
        border_size = 5
        concatenated_image = np.ones((thumbnail_cols * (resized_images[0].shape[0] + 2 * border_size),
                                      thumbnail_rows * (resized_images[0].shape[1] + 2 * border_size), 3),
                                     dtype=np.uint8) * 255
        for i in range(thumbnail_cols):
            for j in range(thumbnail_rows):
                index = i * thumbnail_rows + j
                if index >= len(resized_images):
                    break
                y_offset = i * (resized_images[0].shape[0] + 2 * border_size) + border_size
                x_offset = j * (resized_images[0].shape[1] + 2 * border_size) + border_size

                concatenated_image[y_offset:y_offset + resized_images[0].shape[0],
                x_offset:x_offset + resized_images[0].shape[1]] = resized_images[index]
        thumbnail_path = generate_image_filename(screenshot_storage_path)
        im_pil = Image.fromarray(cv2.cvtColor(concatenated_image, cv2.COLOR_BGR2RGB))
        im_pil.save(Path(thumbnail_path))

    except Exception as e:
        print(f'发生异常：{e}')
        return False, str(e)

    finally:
        video_capture.release()

    print(f'拼接后的图像已保存到{thumbnail_path}')
    return True, thumbnail_path
