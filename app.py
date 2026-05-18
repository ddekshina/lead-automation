from fastapi import FastAPI

from app.routes.main import router

app = FastAPI(
    title="Lead Automation API"
)

app.include_router(router)