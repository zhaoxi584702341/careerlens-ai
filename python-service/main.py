"""CareerLens AI Python 服务。

链路：Vue 前端 → BFF(Node) → Python(FastAPI) → LLM

对外提供四个接口：
- POST /api/analyze  简历文本清洗、技能归一化，返回结构化解析结果
- POST /api/match    简历 + JD 技能匹配分析，返回匹配度、命中项、能力缺口
- POST /api/optimize 简历 + JD，调用 LLM 生成简历优化建议
- POST /api/radar    简历 + JD，调用 LLM 做多维度能力打分
"""

import json
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel

# 加载 .env（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）
load_dotenv()

# ===== LLM 客户端初始化（与 BFF 共用同一套 LLM 地址配置） =====
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.5")

# 修复点2：openai_client 可用性检查 - 启动时探测 LLM 连通性
openai_client: Optional[OpenAI] = None
llm_enabled = False

if LLM_API_KEY:
    try:
        kwargs = {"api_key": LLM_API_KEY}
        if LLM_BASE_URL:
            kwargs["base_url"] = LLM_BASE_URL
        openai_client = OpenAI(**kwargs)
        # 轻量探测：发送一个最小请求验证连通性
        try:
            openai_client.models.list()
            llm_enabled = True
            logger.info("LLM client initialized and verified, model=%s, base_url=%s", LLM_MODEL, LLM_BASE_URL or "default")
        except Exception as probe_exc:
            logger.warning("LLM probe failed (%s), client will still be available for later calls", probe_exc)
            llm_enabled = True  # 探针失败不完全阻断，实际调用时再降级
    except Exception as init_exc:
        logger.error("Failed to initialize LLM client: %s", init_exc)
        openai_client = None
else:
    logger.warning("LLM_API_KEY not set, LLM features will be disabled")

app = FastAPI(
    title="CareerLens AI Python Service",
    version="0.1.0",
    description="AI 能力服务（简历解析、岗位匹配、优化建议、能力雷达）",
)

# ===== 技能归一化字典：别名 -> 标准技能名 =====
SKILL_ALIASES: dict[str, list[str]] = {
    "JavaScript": ["javascript", "js", "es6", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "Vue": ["vue", "vue2", "vue3", "vue.js"],
    "React": ["react", "react.js", "reactjs"],
    "Node.js": ["node", "node.js", "nodejs"],
    "Python": ["python", "py"],
    "Java": ["java"],
    "Go": ["golang", "go语言", " go "],
    "Spring Boot": ["spring boot", "springboot", "spring"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres", "pg"],
    "Redis": ["redis"],
    "MongoDB": ["mongodb", "mongo"],
    "Docker": ["docker", "容器化"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Git": ["git", "github", "gitlab"],
    "Linux": ["linux", "unix"],
    "Webpack": ["webpack"],
    "Vite": ["vite"],
    "RESTful": ["restful", "rest api", "rest"],
    "微服务": ["微服务", "microservice", "micro-services"],
    "机器学习": ["机器学习", "machine learning", "ml"],
    "深度学习": ["深度学习", "deep learning", "dl"],
    "数据分析": ["数据分析", "data analysis", "data analyst"],
    "项目管理": ["项目管理", "project management"],
    "团队协作": ["团队协作", "teamwork", "团队合作"],
    "性能优化": ["性能优化", "performance optimization", "性能调优"],
    "单元测试": ["单元测试", "unit test", "jest", "vitest", "pytest"],
    "CI/CD": ["ci/cd", "cicd", "持续集成", "持续交付", "jenkins"],
}

# 需要参与打分的高价值技能集合（用于评分权重）
CORE_SKILLS = set(SKILL_ALIASES.keys())


def normalize_text(text: str) -> str:
    """文本清洗：去除多余空白与不可见字符，统一小写用于匹配。"""
    cleaned = re.sub(r"[\u200b-\u200f\ufeff]", "", text or "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_skills(text: str) -> list[str]:
    """技能归一化提取：返回命中的标准技能名列表（去重且保持稳定顺序）。"""
    lowered = f" {normalize_text(text).lower()} "
    hits: list[str] = []
    for standard, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                hits.append(standard)
                break
    return hits


# 修复点3：call_llm_json 增加 timeout 参数，防止 LLM 服务挂起导致请求永久阻塞
LLM_TIMEOUT_SECONDS = 30  # 30秒超时


def call_llm_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """调用 LLM 并强制返回 JSON 对象。失败时抛出异常由上层捕获。"""
    if not openai_client:
        raise RuntimeError("LLM client not initialized")

    completion = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        timeout=LLM_TIMEOUT_SECONDS,  # 修复点3：设置超时
    )
    content = completion.choices[0].message.content or "{}"
    return json.loads(content)


def clamp_score(value: Any) -> int:
    """将分数规范化到 0-100 的整数范围。"""
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError):
        num = 0
    return max(0, min(100, num))


# ===== 请求/响应模型 =====
# 修复点4：AnalyzeRequest 同时支持 resume_text（蛇形）和 resumeText（驼峰）
class AnalyzeRequest(BaseModel):
    resume_text: Optional[str] = None
    resumeText: Optional[str] = None

    def get_resume_text(self) -> Optional[str]:
        return self.resume_text or self.resumeText


class MatchRequest(BaseModel):
    resume_text: str
    job_description: str


class OptimizeRequest(BaseModel):
    resume_text: str
    job_description: str


class RadarRequest(BaseModel):
    resume: str
    jd: str


# ===== 统一错误返回工具 =====
def error_payload(fields: dict[str, Any], message: str) -> dict[str, Any]:
    return {**fields, "message": message}


LLM_ERROR_MESSAGE = "LLM 调用失败，请检查 Python 服务 .env 中的 API Key、Base URL 与模型名称配置后重试"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "careerlens-ai-python", "llm_enabled": llm_enabled}


def normalize_llm_skills(raw_skills: Any) -> list[str]:
    """将 LLM 抽取的自由文本技能名归一化到标准技能名。

    - 优先映射到 SKILL_ALIASES 中的标准名（含别名匹配）；
    - 字典无法覆盖的新技能，保留 LLM 原始表述；
    - 去重并保持稳定顺序。
    """
    if not isinstance(raw_skills, list):
        return []
    normalized: list[str] = []
    for item in raw_skills:
        name = str(item).strip()
        if not name:
            continue
        standard = canonical_skill(name)
        canonical_name = standard or name
        if canonical_name not in normalized:
            normalized.append(canonical_name)
    return normalized


def canonical_skill(raw_name: str) -> Optional[str]:
    """把单个技能名映射为标准技能名，无法映射时返回 None。"""
    lowered = f" {raw_name.lower()} "
    for standard, aliases in SKILL_ALIASES.items():
        if standard.lower() == raw_name.lower():
            return standard
        for alias in aliases:
            if alias in lowered or lowered.strip() == alias.strip():
                return standard
    return None


# ===== POST /api/analyze：LLM 语义级技能抽取 + 本地字典归一化，返回结构化解析结果 =====
@app.post("/api/analyze")
def analyze(payload: AnalyzeRequest):
    text = payload.get_resume_text() or ""
    if not text.strip():
        return error_payload(
            {"keywords": [], "score": 0},
            "请求参数错误：resume_text 不能为空",
        )

    cleaned = normalize_text(text)
    # 本地字典规则匹配作为兜底与归一化基准
    local_keywords = extract_skills(cleaned)

    # 调用 LLM 做语义级技能抽取（可识别字典未覆盖的技能及其语义等价表达）
    try:
        data = call_llm_json(
            "你是一名资深简历解析专家。请对用户简历文本做语义级技能抽取，"
            "不仅要识别明确写出的技术栈名称，还要识别语义等价、简写、"
            "以及用自然语言描述的能力（例如“负责前端页面开发”应抽取“前端开发”，"
            "“搭建自动化测试”应抽取“自动化测试”）。"
            "必须只返回 JSON，且严格遵循如下结构："
            '{"keywords": ["技能1", "技能2"], "score": 72}。'
            "keywords 为技能名数组（去重、不超过 20 个）；"
            "score 为简历整体竞争力的 0 到 100 整数评分。"
            "不要输出 JSON 以外的任何内容。",
            f"简历文本：\n{cleaned}",
        )
    except Exception as exc:  # noqa: BLE001 - 统一转为 500 友好提示
        print(f"[analyze] LLM 调用失败: {exc}")
        logger.warning("[analyze] LLM 调用失败，降级到本地字典: %s", exc)
        # 修复点1：LLM 失败时不再返回 500，而是返回 HTTP 200 + 本地字典结果 + 警告信息
        return JSONResponse(
            status_code=200,
            content=error_payload(
                {"keywords": local_keywords, "score": 0, "cleaned_text": cleaned},
                f"{LLM_ERROR_MESSAGE}（已降级使用本地字典匹配）",
            ),
        )

    # 合并 LLM 语义抽取结果与本地字典命中结果，统一归一化去重
    llm_keywords = normalize_llm_skills(data.get("keywords"))
    keywords: list[str] = []
    for skill in llm_keywords + local_keywords:
        if skill not in keywords:
            keywords.append(skill)

    # 评分优先采用 LLM 结果；缺失时回退到本地规则评分
    if data.get("score") is not None:
        score = clamp_score(data.get("score"))
    else:
        core_hits = len([k for k in keywords if k in CORE_SKILLS])
        score = clamp_score(min(core_hits * 8, 80) + min(len(cleaned) // 100, 20))

    return {
        "keywords": keywords,
        "score": score,
        "cleaned_text": cleaned,
        "message": f"共识别到 {len(keywords)} 个关键词，综合评分 {score} 分。",
    }


# ===== POST /api/match：技能匹配分析，返回匹配度、命中项、能力缺口 =====
@app.post("/api/match")
def match(payload: MatchRequest):
    resume_text = payload.resume_text or ""
    jd = payload.job_description or ""
    if not resume_text.strip():
        return error_payload(
            {"match_score": 0, "advantages": [], "improvements": [], "matched_skills": [], "missing_skills": []},
            "请求参数错误：resume_text 不能为空",
        )
    if not jd.strip():
        return error_payload(
            {"match_score": 0, "advantages": [], "improvements": [], "matched_skills": [], "missing_skills": []},
            "请求参数错误：job_description 不能为空",
        )

    # 规则层：技能集合求交与差集，得到命中项与能力缺口
    resume_skills = set(extract_skills(resume_text))
    jd_skills = set(extract_skills(jd))
    matched_skills = sorted(resume_skills & jd_skills)
    missing_skills = sorted(jd_skills - resume_skills)

    try:
        data = call_llm_json(
            "你是一名资深招聘顾问。请对比用户简历与目标岗位描述，给出匹配度评分、优势与待改进点。"
            "必须只返回 JSON，且严格遵循如下结构："
            '{"match_score": 78, "advantages": ["优势1", "优势2"], '
            '"improvements": ["待改进1", "待改进2"], '
            '"matched_skills": ["命中技能1"], "missing_skills": ["缺口技能1"]}。'
            "match_score 必须为 0 到 100 之间的整数。不要输出 JSON 以外的任何内容。",
            f"简历文本：\n{resume_text}\n\n目标岗位描述：\n{jd}",
        )
    except Exception as exc:  # noqa: BLE001 - 统一转为 500 友好提示
        print(f"[match] LLM 调用失败: {exc}")
        logger.warning("[match] LLM 调用失败，降级到本地规则: %s", exc)
        # 修复点1：统一降级策略 - 返回 200 + 本地结果 + 警告
        return JSONResponse(
            status_code=200,
            content=error_payload(
                {"match_score": 0, "advantages": [], "improvements": [], "matched_skills": matched_skills, "missing_skills": missing_skills},
                f"{LLM_ERROR_MESSAGE}（已降级使用本地规则匹配）",
            ),
        )

    advantages = data.get("advantages") if isinstance(data.get("advantages"), list) else []
    improvements = data.get("improvements") if isinstance(data.get("improvements"), list) else []
    llm_matched = data.get("matched_skills") if isinstance(data.get("matched_skills"), list) else matched_skills
    llm_missing = data.get("missing_skills") if isinstance(data.get("missing_skills"), list) else missing_skills

    return {
        "match_score": clamp_score(data.get("match_score")),
        "advantages": advantages,
        "improvements": improvements,
        "matched_skills": llm_matched,
        "missing_skills": llm_missing,
        "message": "匹配完成",
    }


# ===== POST /api/optimize：调用 LLM 生成简历优化建议 =====
@app.post("/api/optimize")
def optimize(payload: OptimizeRequest):
    resume_text = payload.resume_text or ""
    jd = payload.job_description or ""
    empty_fields = {"summary": "", "suggestions": [], "missing_keywords": []}
    if not resume_text.strip():
        return error_payload(empty_fields, "请求参数错误：resume_text 不能为空")
    if not jd.strip():
        return error_payload(empty_fields, "请求参数错误：job_description 不能为空")

    try:
        data = call_llm_json(
            "你是一名资深求职顾问。请根据用户提供的简历文本与目标岗位描述，给出简历优化建议。"
            "必须只返回 JSON，且严格遵循如下结构："
            '{"summary": "总体评价", "suggestions": ["建议1", "建议2", "建议3", "建议4"], '
            '"missing_keywords": ["关键词1", "关键词2"]}。'
            "不要输出 JSON 以外的任何内容。",
            f"简历文本：\n{resume_text}\n\n目标岗位描述：\n{jd}",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[optimize] LLM 调用失败: {exc}")
        logger.warning("[optimize] LLM 调用失败，降级到空结果: %s", exc)
        # 修复点1：统一降级策略
        return JSONResponse(
            status_code=200,
            content=error_payload(empty_fields, f"{LLM_ERROR_MESSAGE}（已降级，无法生成优化建议）"),
        )

    return {
        "summary": data.get("summary") or "",
        "suggestions": data.get("suggestions") if isinstance(data.get("suggestions"), list) else [],
        "missing_keywords": data.get("missing_keywords") if isinstance(data.get("missing_keywords"), list) else [],
        "message": "优化建议已生成",
    }


# ===== POST /api/radar：调用 LLM 做多维度能力打分 =====
@app.post("/api/radar")
def radar(payload: RadarRequest):
    resume = payload.resume or ""
    jd = payload.jd or ""
    if not resume.strip():
        return error_payload({"dimensions": []}, "请求参数错误：resume 不能为空")
    if not jd.strip():
        return error_payload({"dimensions": []}, "请求参数错误：jd 不能为空")

    try:
        data = call_llm_json(
            "你是一名资深职业能力评估专家。请根据用户简历与目标岗位描述，从五个维度评估候选人能力。"
            "必须只返回 JSON，且严格遵循如下结构："
            '{"dimensions": [{"name": "技术匹配度", "score": 78}, {"name": "项目经验", "score": 65}, '
            '{"name": "成果量化", "score": 50}, {"name": "表达能力", "score": 72}, {"name": "成长潜力", "score": 80}]}。'
            "每个维度的 score 必须为 0 到 100 之间的整数。不要输出 JSON 以外的任何内容。",
            f"简历文本：\n{resume}\n\n目标岗位描述：\n{jd}",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[radar] LLM 调用失败: {exc}")
        logger.warning("[radar] LLM 调用失败，降级到空结果: %s", exc)
        # 修复点1：统一降级策略
        return JSONResponse(
            status_code=200,
            content=error_payload({"dimensions": []}, f"{LLM_ERROR_MESSAGE}（已降级，无法生成雷达图数据）"),
        )

    raw_dimensions = data.get("dimensions") if isinstance(data.get("dimensions"), list) else []
    dimensions = [
        {"name": str(item.get("name", "")), "score": clamp_score(item.get("score"))}
        for item in raw_dimensions
        if isinstance(item, dict)
    ]

    return {"dimensions": dimensions, "message": "雷达图数据已生成"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)