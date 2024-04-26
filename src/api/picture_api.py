import os

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from src.api.response.response import ResponseEntity, response_decorator
from src.core.screenshot import get_screenshot, get_thumbnail
from src.core.tool import get_settings, combine_directories, \
    check_path_and_find_video
from src.error.publish_helper_error import PublishHelperError, StatusCode

router = APIRouter()


class GetScreenshotModel(BaseModel):
    path: str = Field("", alias='path')
    screenshotStoragePath: str = Field("", alias='screenshotStoragePath')
    screenshotNumber: str = Field("", alias='screenshotNumber')
    screenshotThreshold: str = Field("", alias='screenshotThreshold')
    screenshotStartPercentage: str = Field("", alias='screenshotStartPercentage')
    screenshotEndPercentage: str = Field("", alias='screenshotEndPercentage')
    screenshotMinIntervalPercentage: str = Field("", alias='screenshotMinIntervalPercentage')
    videoPath: str = Field("", alias='videoPath')


@router.post('/api/getScreenshot')
@response_decorator
# 获取截图
def api_get_screenshot(body: GetScreenshotModel = Body(...)):
    path = body.path
    screenshot_storage_path = body.screenshotStoragePath or get_settings("screenshot_storage_path")
    screenshot_number = int(body.screenshotNumber or get_settings("screenshot_number"))
    screenshot_threshold = float(body.screenshotThreshold or get_settings("screenshot_threshold"))
    screenshot_start_percentage = float(body.screenshotStartPercentage or get_settings("screenshot_start_percentage"))
    screenshot_end_percentage = float(body.screenshotEndPercentage or get_settings("screenshot_end_percentage"))
    screenshot_min_interval_percentage = float(body.screenshotMinIntervalPercentage or "0.01")

    media_path = combine_directories('media')
    path = os.path.abspath(os.path.join(media_path, path))
    # 确认绝对路径为temp目录即可
    if not path.startswith(media_path):
        raise PublishHelperError(message="无权访问此文件。", status_code=StatusCode.UNAUTHORIZED_ACCESS_ERROR)
    if not os.path.exists(path):
        raise PublishHelperError(message="您提供的文件路径不存在。", status_code=StatusCode.FILE_PATH_ERROR)

    if screenshot_number > 0:
        if screenshot_number < 6:
            if 0 < screenshot_start_percentage < 1 and 0 < screenshot_end_percentage < 1:
                if screenshot_start_percentage < screenshot_end_percentage:
                    is_video_path, video_path = check_path_and_find_video(path)  # 视频资源的路径
                    if is_video_path == 1 or is_video_path == 2:
                        screenshot_success, response = get_screenshot(video_path, screenshot_storage_path,
                                                                      screenshot_number,
                                                                      screenshot_threshold,
                                                                      screenshot_start_percentage,
                                                                      screenshot_end_percentage,
                                                                      screenshot_min_interval_percentage)

                        if screenshot_success:
                            [imagePath.replace(media_path, '') for imagePath in response]
                            return ResponseEntity(
                                data={
                                    "screenshotNumber": str(len(response)),
                                    "screenshotPath": [imagePath.replace(media_path, '') for imagePath in response],
                                    "videoPath": video_path
                                },
                                message="获取截图成功。",
                            )
                        else:
                            raise PublishHelperError(message=f"获取截图失败：{response[0]}",
                                                     status_code=StatusCode.SERVER_ERROR)
                    else:
                        raise PublishHelperError(message=f"获取视频路径失败：{video_path}",
                                                 status_code=StatusCode.SERVER_ERROR)
                else:
                    raise PublishHelperError(message="截图起始点不能大于终止点。",
                                             status_code=StatusCode.SERVER_ERROR)

            else:
                raise PublishHelperError(message="截图起始点和终止点不能小于0或大于1。",
                                         status_code=StatusCode.SERVER_ERROR)
        else:
            raise PublishHelperError(message="一次获取的截图数量不能大于5张。",
                                     status_code=StatusCode.SERVER_ERROR)

    else:
        raise PublishHelperError(message="一次获取的截图数量不能小于1张。",
                                 status_code=StatusCode.SERVER_ERROR)


class ThumbnailParams(BaseModel):
    path: str = Field(default="", description="视频或资源的路径")
    screenshotStoragePath: str = Field(default="", description="截图存储路径")
    thumbnailRows: str = Field(default="", description="缩略图行数")
    thumbnailCols: str = Field(default="", description="缩略图列数")
    screenshotStartPercentage: str = Field(default="", description="截图开始百分比")
    screenshotEndPercentage: str = Field(default="", description="截图结束百分比")


@router.post('/api/getThumbnail')
@response_decorator
# 用于获取缩略图，传入相关参数，返回缩略图路径
def api_get_thumbnail(params: ThumbnailParams = Body(...)):
    # 从模型实例中获取参数
    path = params.path
    screenshot_storage_path = params.screenshotStoragePath or get_settings("screenshot_storage_path")
    thumbnail_rows = int(params.thumbnailRows or get_settings("thumbnail_rows"))
    thumbnail_cols = int(params.thumbnailCols or get_settings("thumbnail_cols"))
    screenshot_start_percentage = float(
        params.screenshotStartPercentage or get_settings("screenshot_start_percentage"))
    screenshot_end_percentage = float(params.screenshotEndPercentage or get_settings("screenshot_end_percentage"))

    if path == '':
        raise PublishHelperError(message="缺少资源路径。", status_code=StatusCode.MISSING_REQUIRED_PARAMETER)
    if not os.path.exists(path):
        raise PublishHelperError(message="您提供的文件路径不存在。", status_code=StatusCode.SERVER_ERROR)

    if thumbnail_rows > 0 and thumbnail_cols > 0:
        if 0 < screenshot_start_percentage < 1 and 0 < screenshot_end_percentage < 1:
            if screenshot_start_percentage < screenshot_end_percentage:
                is_video_path, video_path = check_path_and_find_video(path)  # 视频资源的路径
                if is_video_path == 1 or is_video_path == 2:
                    get_thumbnail_success, response = get_thumbnail(video_path, screenshot_storage_path,
                                                                    thumbnail_rows,
                                                                    thumbnail_cols, screenshot_start_percentage,
                                                                    screenshot_end_percentage)
                    if get_thumbnail_success:
                        ResponseEntity(
                            data={
                                "thumbnailPath": response,
                                "videoPath": video_path
                            },
                            message="获取截图成功。",
                        )
                    else:
                        raise PublishHelperError(message=f"获取截图失败：{response}",
                                                 status_code=StatusCode.SERVER_ERROR)
                else:
                    raise PublishHelperError(message=f"获取视频路径失败：{video_path}",
                                             status_code=StatusCode.SERVER_ERROR)
            else:
                raise PublishHelperError(message="截图起始点不能大于终止点。",
                                         status_code=StatusCode.SERVER_ERROR)
        else:
            raise PublishHelperError(message="截图起始点和终止点不能小于0或大于1。",
                                     status_code=StatusCode.SERVER_ERROR)
    else:
        raise PublishHelperError(message="缩略图横向、纵向数量均需要大于0。",
                                 status_code=StatusCode.SERVER_ERROR)
