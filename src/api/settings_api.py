from fastapi import APIRouter, Body
from src.api.response import ResponseEntity, response_decorator
from src.core.tool import get_settings_json, update_settings_json

router = APIRouter()


@router.get('/api/settings')
# 用于获取settings.json的数据，返回所有参数
@response_decorator
def api_settings():
    # 从请求URL中获取参数
    settings_json = get_settings_json()
    return ResponseEntity(data=settings_json, message="获取设置信息成功。", statusCode="OK")


@router.post('/api/settings/update')
@response_decorator
# 更新所有参数
def api_settings_update(request_body: str = Body(...)):
    # 从请求URL中获取参数
    update_settings_json(request_body)
    return ResponseEntity(data={}, message="更新设置信息成功。")
