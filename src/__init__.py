import os

from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html, get_redoc_html
from starlette.staticfiles import StaticFiles

from src.api import bootstrap



bootstrap.mount(
    "/static",
    StaticFiles(
        directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    ),
    name="static",
)


@bootstrap.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=bootstrap.openapi_url,
        title=bootstrap.title + " - OPENAPI UI",
        oauth2_redirect_url=bootstrap.swagger_ui_oauth2_redirect_url,
        swagger_favicon_url="/static/favicon.ico",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )


@bootstrap.get(bootstrap.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@bootstrap.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=bootstrap.openapi_url,
        title=bootstrap.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )