from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="CareerLens AI Python Service",
    version="0.0.1",
    description="AI 能力服务（简历解析、岗位匹配等）",
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "careerlens-ai-python"}
