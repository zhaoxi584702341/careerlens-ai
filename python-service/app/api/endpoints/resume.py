from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AnalyzeResumeRequest(BaseModel):
    resume_text: str


class AnalyzeResumeResponse(BaseModel):
    keywords: list[str]
    score: int
    message: str


# 关键词候选字典，命中即作为标签返回
KEYWORD_POOL = [
    "Python", "Java", "Vue", "React", "TypeScript", "FastAPI", "Spring Boot",
    "MySQL", "Redis", "Docker", "Kubernetes", "AI", "机器学习", "数据分析",
    "项目管理", "团队协作", "微服务", "RESTful", "Git", "Linux",
]


@router.post("/analyze-resume", response_model=AnalyzeResumeResponse)
def analyze_resume(payload: AnalyzeResumeRequest) -> AnalyzeResumeResponse:
    text = payload.resume_text or ""
    lowered = text.lower()

    keywords = [kw for kw in KEYWORD_POOL if kw.lower() in lowered]

    # 基于关键词命中数与文本长度给出 0-100 的简单评分
    hit_score = min(len(keywords) * 8, 80)
    length_score = min(len(text) // 100, 20)
    score = min(hit_score + length_score, 100)

    if not text.strip():
        return AnalyzeResumeResponse(keywords=[], score=0, message="简历内容为空，请粘贴文本后重试。")

    message = f"共识别到 {len(keywords)} 个关键词，综合评分 {score} 分。"
    return AnalyzeResumeResponse(keywords=keywords, score=score, message=message)
