from fastapi import FastAPI

from src.api import settings_api

bootstrap = FastAPI(title="Publish Helper", docs_url=None, redoc_url=None)

bootstrap.include_router(settings_api.router)
