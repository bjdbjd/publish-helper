from enum import Enum


class StatusCode(Enum):
    """状态码"""
    UNAUTHORIZED_ACCESS_ERROR = 401
    MISSING_REQUIRED_PARAMETER = 422
    FILE_PATH_ERROR = 422
    OK = 200
    SERVER_ERROR = 500


class PublishHelperError(Exception):
    """自定义异常类"""

    status_code: StatusCode = StatusCode.OK

    def __init__(self, message, status_code: StatusCode = StatusCode.OK):
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    def __str__(self):
        return f"{self.message}"
