"""CareerLens AI Python 服务。

链路：Vue 前端 → BFF(Node) → Python(FastAPI) → LLM

对外提供四个接口：
- POST /api/analyze  简历文本清洗、技能归一化，返回结构化解析结果
- POST /api/match    简历 + JD 技能匹配分析，返回匹配度、命中项、能力缺口
- POST /api/optimize 简历 + JD，调用 LLM 生成简历优化建议
- POST /api/radar    简历 + JD，调用 LLM 做多维度能力打分
"""

import json
import logging
import os
import re
from typing import Any, Optional

import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel

# ===== 接入纯规则引擎（rules.py）：提供可解释的命中/缺口/质量问题，LLM 失败时作为降级档位 =====
from rules import (
    SKILL_DICT,
    build_learning_path,
    compute_match,
    detect_language,
    detect_quality_issues,
    extract_skill_hits,
    normalize_text as rules_normalize_text,
    split_sections,
)

# AI_MODE 档位：可配置为 rule（纯规则，用于离线复现）/ llm / hybrid（默认）
AI_MODE = os.getenv("AI_MODE", "hybrid").strip().lower()

# 加载 .env（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）
load_dotenv()

# 日志配置：统一使用模块级 logger，便于排查 LLM 调用与降级情况
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("careerlens.python")

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
# Java 转发层使用驼峰字段（resumeText / jobDescription），前端/BFF 对外使用蛇形字段，
# 因此这里同时声明两种别名，保证任一形式的入参都能被正确解析。
class AnalyzeRequest(BaseModel):
    resume_text: Optional[str] = None
    resumeText: Optional[str] = None

    def get_resume_text(self) -> Optional[str]:
        return self.resume_text or self.resumeText


class MatchRequest(BaseModel):
    resume_text: Optional[str] = None
    resumeText: Optional[str] = None
    job_description: Optional[str] = None
    jobDescription: Optional[str] = None

    def get_resume_text(self) -> str:
        return self.resume_text or self.resumeText or ""

    def get_job_description(self) -> str:
        return self.job_description or self.jobDescription or ""


class OptimizeRequest(BaseModel):
    resume_text: Optional[str] = None
    resumeText: Optional[str] = None
    job_description: Optional[str] = None
    jobDescription: Optional[str] = None

    def get_resume_text(self) -> str:
        return self.resume_text or self.resumeText or ""

    def get_job_description(self) -> str:
        return self.job_description or self.jobDescription or ""


class RadarRequest(BaseModel):
    resume: str
    jd: str


# ===== 统一错误返回工具 =====
def error_payload(fields: dict[str, Any], message: str) -> dict[str, Any]:
    return {**fields, "message": message}


LLM_ERROR_MESSAGE = "LLM 调用失败，请检查 Python 服务 .env 中的 API Key、Base URL 与模型名称配置后重试"


# ===== 契约 meta 构造：timings / degraded / aiMode =====
# python 为本地计算耗时；llm 为调用大模型耗时（本地规则档位恒为 0），
# total 供上游（Java/BFF）读取并累加自身耗时。bff / java 由各自上层补齐。
def build_meta(python_ms: int, llm_ms: int, degraded: bool, ai_mode: str) -> dict[str, Any]:
    return {
        "timings": {
            "python": python_ms,
            "llm": llm_ms,
            "total": python_ms + llm_ms,
        },
        "degraded": degraded,
        "aiMode": ai_mode,
    }


# ===== LLM 语义结果归一化工具 =====
def _as_str_list(value: Any) -> list[str]:
    """把 LLM 返回值规范化为字符串列表（去空、去重、保序）。"""
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _from_llm_hits(raw_hits: Any, ai_mode: str) -> list[dict[str, Any]]:
    """把 LLM 返回的命中项规范化为契约 hits 结构，缺字段时补默认值。"""
    result: list[dict[str, Any]] = []
    if not isinstance(raw_hits, list):
        return result
    for item in raw_hits:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "skill": str(item.get("skill", "")),
                "hitType": item.get("hitType") if item.get("hitType") in {"EXACT", "SYNONYM", "INFERRED"} else "INFERRED",
                "confidence": item.get("confidence", 0.7),
                "evidence": str(item.get("evidence", "")),
                "source": str(item.get("source", f"llm.{ai_mode}")),
            }
        )
    return result


def _from_llm_gaps(raw_gaps: Any) -> list[dict[str, Any]]:
    """把 LLM 返回的能力缺口规范化为契约 gaps 结构，学习路径缺失时按分类模板补齐。"""
    result: list[dict[str, Any]] = []
    if not isinstance(raw_gaps, list):
        return result
    for item in raw_gaps:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill", ""))
        importance = item.get("importance") if item.get("importance") in {"high", "medium", "low"} else "medium"
        learning_path = _as_str_list(item.get("learningPath")) or build_learning_path(skill)
        result.append(
            {
                "skill": skill,
                "importance": importance,
                "suggestion": str(item.get("suggestion", "")),
                "learningPath": learning_path,
            }
        )
    return result


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "careerlens-ai-python", "llm_enabled": llm_enabled}


# ===== POST /api/analyze：规则层结构化解析 + LLM 语义抽取，返回可解释的简历解析结果 =====
@app.post("/api/analyze")
def analyze(payload: AnalyzeRequest):
    started = time.perf_counter()
    text = payload.get_resume_text() or ""
    if not text.strip():
        return error_payload(
            {"success": False, "keywords": [], "score": 0},
            "请求参数错误：resume_text 不能为空",
        )

    # 规则层：文本清洗（含全角转半角）、分节识别、技能归一化、结构化质量问题检测
    cleaned = rules_normalize_text(text)
    sections = split_sections(cleaned)
    skill_hits = extract_skill_hits(cleaned)
    normalized = [
        {
            "canonical": h["canonical"],
            "raw": h["raw"],
            "category": h["category"],
            "confidence": h["confidence"],
        }
        for h in skill_hits
    ]
    rule_keywords = [h["canonical"] for h in skill_hits]
    quality_issues = detect_quality_issues(cleaned, sections)
    language = detect_language(cleaned)

    keywords: list[str] = list(rule_keywords)
    llm_ms = 0
    llm_keywords: list[str] = []
    llm_score: Optional[int] = None

    if AI_MODE != "rule":
        llm_started = time.perf_counter()
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
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            llm_keywords = normalize_llm_skills(data.get("keywords"))
            if data.get("score") is not None:
                llm_score = clamp_score(data.get("score"))
            for skill in llm_keywords:
                if skill not in keywords:
                    keywords.append(skill)
        except Exception as exc:  # noqa: BLE001 - 统一转为降级结果
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            logger.warning("[analyze] LLM 调用失败，降级到本地规则: %s", exc)
            llm_keywords = []
            llm_score = None

    # 命中 LLM 时以 LLM 评分为准，否则使用本地规则的可复现评分
    score = llm_score if llm_score is not None else rule_score(dict.fromkeys(keywords), cleaned)
    ai_mode = "rule" if not llm_keywords and llm_score is None else "hybrid"

    python_ms = int((time.perf_counter() - started) * 1000)
    return {
        "success": True,
        "keywords": keywords,
        "score": score,
        "cleaned_text": cleaned,
        "resume": {
            "cleaned": {
                "sections": sections,
                "wordCount": len(re.sub(r"\s", "", cleaned)),
                "language": language,
            }
        },
        "qualityIssues": quality_issues,
        "skills": {
            "normalized": normalized,
            "unrecognized": [],
        },
        "meta": build_meta(python_ms, llm_ms, degraded=ai_mode == "rule", ai_mode=ai_mode),
        "message": f"共识别到 {len(keywords)} 个关键词，综合评分 {score} 分。",
    }


def rule_score(keywords: Any, cleaned: str) -> int:
    """本地规则评分：核心技能命中数 + 简历篇幅的加权，保证离线可复现。"""
    core_hits = len([k for k in keywords if k in CORE_SKILLS])
    return clamp_score(min(core_hits * 8, 80) + min(len(cleaned) // 100, 20))


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


# ===== POST /api/match：规则层可解释匹配 + LLM 语义匹配，返回匹配度、命中项与能力缺口 =====
@app.post("/api/match")
def match(payload: MatchRequest):
    started = time.perf_counter()
    resume_text = payload.get_resume_text()
    jd = payload.get_job_description()
    empty_fields: dict[str, Any] = {
        "success": False,
        "match_score": 0,
        "advantages": [],
        "improvements": [],
        "matched_skills": [],
        "missing_skills": [],
    }
    if not resume_text.strip():
        return error_payload(empty_fields, "请求参数错误：resume_text 不能为空")
    if not jd.strip():
        return error_payload(empty_fields, "请求参数错误：job_description 不能为空")

    # 规则层：显式可复现打分，产出 level / breakdown / hits / gaps
    rule_match = compute_match(resume_text, jd)

    expected = _estimate_expected_dimensions(rule_match)
    result: dict[str, Any] = dict(expected)
    llm_ms = 0
    ai_mode = "rule"

    if AI_MODE != "rule":
        llm_started = time.perf_counter()
        try:
            data = call_llm_json(
                "你是一名资深招聘顾问。请对比用户简历与目标岗位描述，给出匹配度评分、优势、待改进点、"
                "命中项（含 hitType: EXACT/SYNONYM/INFERRED 与 evidence 原文证据）以及能力缺口"
                "（含 importance: high/medium/low、suggestion 与 learningPath 学习路径数组）。"
                "必须只返回 JSON，且严格遵循如下结构："
                '{"match_score": 78, "level": "GOOD_FIT", "advantages": ["优势1"], '
                '"improvements": ["待改进1"], "matched_skills": ["命中技能1"], "missing_skills": ["缺口技能1"], '
                '"hits": [{"skill": "Vue", "hitType": "EXACT", "evidence": "熟悉Vue3", "source": "resume"}], '
                '"gaps": [{"skill": "React", "importance": "high", "suggestion": "补充React项目", "learningPath": ["学习React基础"]}]}。'
                "match_score 必须为 0 到 100 之间的整数；level 取值 EXCELLENT/GOOD_FIT/PARTIAL_FIT/WEAK_FIT。"
                "不要输出 JSON 以外的任何内容。",
                f"简历文本：\n{resume_text}\n\n目标岗位描述：\n{jd}",
            )
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            ai_mode = "hybrid"
            score = clamp_score(data.get("match_score"))
            level = data.get("level") if data.get("level") in {"EXCELLENT", "GOOD_FIT", "PARTIAL_FIT", "WEAK_FIT"} else _level_for_score(score)
            result.update(
                {
                    "match_score": score,
                    "level": level,
                    "advantages": _as_str_list(data.get("advantages")) or expected["advantages"],
                    "improvements": _as_str_list(data.get("improvements")) or expected["improvements"],
                    "matched_skills": _as_str_list(data.get("matched_skills")) or expected["matched_skills"],
                    "missing_skills": _as_str_list(data.get("missing_skills")) or expected["missing_skills"],
                    "hits": _from_llm_hits(data.get("hits"), ai_mode) or expected["hits"],
                    "gaps": _from_llm_gaps(data.get("gaps")) or expected["gaps"],
                }
            )
        except Exception as exc:  # noqa: BLE001 - 统一转为降级结果
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            logger.warning("[match] LLM 调用失败，降级到本地规则: %s", exc)
            ai_mode = "rule"

    python_ms = int((time.perf_counter() - started) * 1000)
    result["success"] = True
    result["meta"] = build_meta(python_ms, llm_ms, degraded=ai_mode == "rule", ai_mode=ai_mode)
    result["message"] = (
        f"{LLM_ERROR_MESSAGE}（已降级使用本地规则匹配）" if ai_mode == "rule" else "匹配完成"
    )
    return result


def _level_for_score(score: int) -> str:
    """按分数区间映射匹配等级，与 rules.LEVEL_BANDS 保持一致。"""
    for threshold, band in ((85, "EXCELLENT"), (70, "GOOD_FIT"), (50, "PARTIAL_FIT"), (0, "WEAK_FIT")):
        if score >= threshold:
            return band
    return "WEAK_FIT"


def _estimate_expected_dimensions(rule_match: dict[str, Any]) -> dict[str, Any]:
    """基于规则层命中/缺口生成 advantages / improvements 的降级文案。"""
    advantages = [f"已具备岗位要求的 {skill}" for skill in rule_match["matched_skills"][:5]]
    improvements = [
        f"补齐「{gap['skill']}」相关经历（{gap['importance']} 优先级）" for gap in rule_match["gaps"][:5]
    ]
    return {
        "match_score": rule_match["score"],
        "level": rule_match["level"],
        "breakdown": rule_match["breakdown"],
        "hits": rule_match["hits"],
        "gaps": rule_match["gaps"],
        "matched_skills": rule_match["matched_skills"],
        "missing_skills": rule_match["missing_skills"],
        "advantages": advantages,
        "improvements": improvements,
    }


# ===== POST /api/optimize：调用 LLM 生成简历优化建议，附规则层命中的缺失关键词 =====
@app.post("/api/optimize")
def optimize(payload: OptimizeRequest):
    started = time.perf_counter()
    resume_text = payload.get_resume_text()
    jd = payload.get_job_description()
    empty_fields: dict[str, Any] = {"success": False, "summary": "", "suggestions": [], "missing_keywords": []}
    if not resume_text.strip():
        return error_payload(empty_fields, "请求参数错误：resume_text 不能为空")
    if not jd.strip():
        return error_payload(empty_fields, "请求参数错误：job_description 不能为空")

    # 规则层：命中缺失关键词，作为降级兜底与 LLM 结果的补充
    rule_match = compute_match(resume_text, jd)
    rule_missing = rule_match["missing_skills"]

    summary = ""
    suggestions: list[str] = []
    missing_keywords: list[str] = list(rule_missing)
    llm_ms = 0
    ai_mode = "rule"

    if AI_MODE != "rule":
        llm_started = time.perf_counter()
        try:
            data = call_llm_json(
                "你是一名资深求职顾问。请根据用户提供的简历文本与目标岗位描述，给出简历优化建议。"
                "必须只返回 JSON，且严格遵循如下结构："
                '{"summary": "总体评价", "suggestions": ["建议1", "建议2", "建议3", "建议4"], '
                '"missing_keywords": ["关键词1", "关键词2"]}。'
                "不要输出 JSON 以外的任何内容。",
                f"简历文本：\n{resume_text}\n\n目标岗位描述：\n{jd}",
            )
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            ai_mode = "hybrid"
            summary = str(data.get("summary") or "")
            suggestions = _as_str_list(data.get("suggestions"))
            llm_missing = _as_str_list(data.get("missing_keywords"))
            # 合并 LLM 与规则层缺失关键词，去重保序
            for kw in llm_missing:
                if kw not in missing_keywords:
                    missing_keywords.append(kw)
        except Exception as exc:  # noqa: BLE001
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            logger.warning("[optimize] LLM 调用失败，降级到规则结果: %s", exc)
            ai_mode = "rule"

    python_ms = int((time.perf_counter() - started) * 1000)
    return {
        "success": True,
        "summary": summary,
        "suggestions": suggestions,
        "missing_keywords": missing_keywords,
        "meta": build_meta(python_ms, llm_ms, degraded=ai_mode == "rule", ai_mode=ai_mode),
        "message": f"{LLM_ERROR_MESSAGE}（已降级，仅返回规则层缺口关键词）" if ai_mode == "rule" else "优化建议已生成",
    }


# ===== POST /api/radar：调用 LLM 做多维度能力打分，降级时按规则层指标构造雷达维度 =====
@app.post("/api/radar")
def radar(payload: RadarRequest):
    started = time.perf_counter()
    resume = payload.resume or ""
    jd = payload.jd or ""
    if not resume.strip():
        return error_payload({"success": False, "dimensions": []}, "请求参数错误：resume 不能为空")
    if not jd.strip():
        return error_payload({"success": False, "dimensions": []}, "请求参数错误：jd 不能为空")

    dimensions: list[dict[str, Any]] = []
    llm_ms = 0
    ai_mode = "rule"

    if AI_MODE != "rule":
        llm_started = time.perf_counter()
        try:
            data = call_llm_json(
                "你是一名资深职业能力评估专家。请根据用户简历与目标岗位描述，从五个维度评估候选人能力。"
                "必须只返回 JSON，且严格遵循如下结构："
                '{"dimensions": [{"name": "技术匹配度", "score": 78}, {"name": "项目经验", "score": 65}, '
                '{"name": "成果量化", "score": 50}, {"name": "表达能力", "score": 72}, {"name": "成长潜力", "score": 80}]}。'
                "每个维度的 score 必须为 0 到 100 之间的整数。不要输出 JSON 以外的任何内容。",
                f"简历文本：\n{resume}\n\n目标岗位描述：\n{jd}",
            )
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            ai_mode = "hybrid"
            raw_dimensions = data.get("dimensions") if isinstance(data.get("dimensions"), list) else []
            dimensions = [
                {"name": str(item.get("name", "")), "score": clamp_score(item.get("score"))}
                for item in raw_dimensions
                if isinstance(item, dict)
            ]
        except Exception as exc:  # noqa: BLE001
            llm_ms = int((time.perf_counter() - llm_started) * 1000)
            logger.warning("[radar] LLM 调用失败，降级到规则维度: %s", exc)
            ai_mode = "rule"

    if ai_mode == "rule":
        dimensions = _rule_radar_dimensions(resume, jd)

    python_ms = int((time.perf_counter() - started) * 1000)
    return {
        "success": True,
        "dimensions": dimensions,
        "meta": build_meta(python_ms, llm_ms, degraded=ai_mode == "rule", ai_mode=ai_mode),
        "message": f"{LLM_ERROR_MESSAGE}（已降级，基于规则层指标生成雷达）" if ai_mode == "rule" else "雷达图数据已生成",
    }


def _rule_radar_dimensions(resume: str, jd: str) -> list[dict[str, Any]]:
    """降级雷达：由规则层匹配度与命中/缺口推导五个维度的分数，保证可复现且非空。"""
    rule_match = compute_match(resume, jd)
    score = rule_match["score"]
    matched = len(rule_match["matched_skills"])
    total_required = matched + len(rule_match["missing_skills"])
    coverage = round(100 * matched / total_required) if total_required else score
    tech = score
    return [
        {"name": "技术匹配度", "score": clamp_score(tech)},
        {"name": "项目经验", "score": clamp_score(round((tech + coverage) / 2))},
        {"name": "成果量化", "score": clamp_score(round(coverage * 0.8))},
        {"name": "表达能力", "score": clamp_score(round((tech + 60) / 2))},
        {"name": "成长潜力", "score": clamp_score(round((tech + coverage + 100) / 3))},
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)