from fastapi import APIRouter

from app.api.endpoints import health, resume

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(resume.router, tags=["resume"])
