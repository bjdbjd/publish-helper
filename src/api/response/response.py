import datetime
import json
import traceback
from functools import wraps

from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from src.error.publish_helper_error import PublishHelperError, StatusCode
from src.utils.enum_util import get_enum_by_value, get_enum_by_name


def response_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.datetime.now()
        try:
            response_entity = func(*args, **kwargs)
            elapsed_time = datetime.datetime.now() - start_time
            response_entity.elapsed_time = elapsed_time.total_seconds()
            response_entity.version = "0.0.1"
            response_entity.statusCode = StatusCode.OK.name
        except PublishHelperError as publish_helper_error:
            elapsed_time = datetime.datetime.now() - start_time
            response_entity = ResponseEntity(
                message=publish_helper_error.message,
                elapsed_time=elapsed_time.total_seconds(),
                version="0.0.1",
                statusCode=publish_helper_error.status_code.name
            )
            traceback.print_exc()
        except Exception as e:
            elapsed_time = datetime.datetime.now() - start_time
            response_entity = ResponseEntity(
                message="未知错误",
                elapsed_time=elapsed_time.total_seconds(),
                version="0.0.1",
                statusCode=StatusCode.SERVER_ERROR.name
            )
            traceback.print_exc()
        # return response_entity
        # 使用 JSONResponse 返回响应，并设置状态码
        return JSONResponse(content=response_entity.dict(),
                            status_code=get_enum_by_name(StatusCode, response_entity.statusCode).value)
    return wrapper


class ResponseEntity(BaseModel):
    version: str = Field(None, example="0.0.1", description="version")
    message: str = Field(None, example="success", description="message")
    data: object = Field(None, description="data")
    statusCode: str = Field(None, description="OK")
    elapsed_time: int = Field(None, example=0, description="elapsed_time")


class Page(BaseModel):
    page: int = Field(1, description="页码")
    page_size: int = Field(20, description="每页数量")
    total: int = Field(0, description="总数")
