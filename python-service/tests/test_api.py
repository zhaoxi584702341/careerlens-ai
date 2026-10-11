"""CareerLens AI Python 服务接口测试。

覆盖四个对外接口的正常场景与核心异常场景：
- POST /api/analyze
- POST /api/match
- POST /api/optimize
- POST /api/radar
- GET  /health

设计原则：
1. 测试可独立运行，不依赖真实 LLM 网络调用——通过 monkeypatch 替换 call_llm_json，
   使断言结果稳定、可离线执行（CI 环境无 API Key 也能通过）。
2. 额外保留一个"真实链路"冒烟测试，仅在设置了 LLM_API_KEY 环境变量时执行
   （通过 pytest.mark.skipif 自动跳过），避免 CI 因缺失密钥失败。

运行方式：
    cd python-service
    pytest -v
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client() -> TestClient:
    """FastAPI 测试客户端。"""
    return TestClient(main.app)


@pytest.fixture()
def fake_llm(monkeypatch: pytest.MonkeyPatch):
    """替换真实 LLM 调用，按接口返回确定性的模拟 JSON。

    通过检查 system_prompt 中的关键词判断当前是哪个接口，返回对应结构，
    保证四个接口都能在无网络环境下得到可断言的稳定结果。
    """

    def _fake(system_prompt: str, user_prompt: str) -> dict:
        if "简历解析专家" in system_prompt:
            return {"keywords": ["前端开发", "性能优化"], "score": 72}
        if "招聘顾问" in system_prompt:
            return {
                "match_score": 65,
                "advantages": ["3年前端开发经验"],
                "improvements": ["缺少 React 经验"],
                "matched_skills": ["Vue"],
                "missing_skills": ["React"],
            }
        if "求职顾问" in system_prompt:
            return {
                "summary": "简历与岗位存在技术栈错位",
                "suggestions": ["补充 React 项目经验", "量化成果"],
                "missing_keywords": ["React", "性能优化"],
            }
        if "职业能力评估专家" in system_prompt:
            return {
                "dimensions": [
                    {"name": "技术匹配度", "score": 65},
                    {"name": "项目经验", "score": 60},
                    {"name": "成果量化", "score": 40},
                    {"name": "表达能力", "score": 70},
                    {"name": "成长潜力", "score": 75},
                ]
            }
        return {}

    monkeypatch.setattr(main, "call_llm_json", _fake)
    return _fake


# ==================== /health ====================

def test_health(client: TestClient) -> None:
    """健康检查接口返回 ok，并暴露 llm_enabled 布尔标记。"""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "careerlens-ai-python"
    # llm_enabled 为布尔标记：是否已初始化 LLM 客户端（与 main.py 契约一致）
    assert body["llm_enabled"] in (True, False)


# ==================== /api/analyze ====================

def test_analyze_normal(client: TestClient, fake_llm) -> None:
    """正常场景：返回 LLM 语义抽取的关键词与评分，并携带规则层结构化字段与 meta。"""
    payload = {"resume_text": "负责公司官网前端页面开发，主导性能调优"}
    resp = client.post("/api/analyze", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "前端开发" in body["keywords"]
    assert body["score"] == 72
    # cleaned_text 为规则层清洗结果（含全角转半角），因此用清洗后的文本比对
    assert body["cleaned_text"] == main.rules_normalize_text(payload["resume_text"])
    # 契约扩展字段：分节 / 质量问题 / 技能归一化 / meta
    assert "sections" in body["resume"]["cleaned"]
    assert isinstance(body["qualityIssues"], list)
    assert isinstance(body["skills"]["normalized"], list)
    assert body["meta"]["degraded"] is False
    assert body["meta"]["aiMode"] == "hybrid"
    assert body["meta"]["timings"]["python"] >= 0


def test_analyze_empty_text(client: TestClient) -> None:
    """异常场景：resume_text 为空，返回参数错误且不调用 LLM。"""
    resp = client.post("/api/analyze", json={"resume_text": "   "})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["keywords"] == []
    assert body["score"] == 0
    assert "不能为空" in body["message"]


def test_analyze_missing_field(client: TestClient) -> None:
    """异常场景：缺少必填字段时，main.py 以空文本处理并返回 200 + 参数错误提示。

    说明：main.py 的 AnalyzeRequest 对 resume_text 做了容错（缺失时按空串处理），
    因此不会触发 FastAPI 的 422 校验错误，而是走「不能为空」的友好分支。
    """
    resp = client.post("/api/analyze", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["keywords"] == []
    assert body["score"] == 0
    assert "不能为空" in body["message"]


def test_analyze_llm_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """异常场景：LLM 调用失败时降级——返回 200 + 规则层结果，meta 标记 degraded/aiMode=rule。"""

    def _boom(system_prompt: str, user_prompt: str):  # noqa: ANN202
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr(main, "call_llm_json", _boom)
    resp = client.post("/api/analyze", json={"resume_text": "熟悉 Java、MySQL"})
    assert resp.status_code == 200
    body = resp.json()
    # 本地字典兜底应命中 Java / MySQL
    assert "Java" in body["keywords"]
    assert "MySQL" in body["keywords"]
    assert body["meta"]["degraded"] is True
    assert body["meta"]["aiMode"] == "rule"
    # 规则层仍应产出结构化质量问题
    assert isinstance(body["qualityIssues"], list)


def test_analyze_rule_mode_produces_contract_fields(client: TestClient) -> None:
    """契约场景：规则层独立产出 hits/gaps 级别的结构化解析（不依赖 LLM）。"""
    resp = client.post(
        "/api/analyze",
        json={"resume_text": "教育背景：本科\n技能：熟悉Vue3、TypeScript\n工作经历：2020.01-2023.06 负责前端页面开发，性能优化提升30%"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["skills"]["normalized"], "规则层应抽取到归一化技能"
    assert body["resume"]["cleaned"]["language"] in {"zh", "en", "mixed"}


# ==================== /api/match ====================

def test_match_normal(client: TestClient, fake_llm) -> None:
    """正常场景：返回匹配度、等级、命中项、能力缺口与 meta。"""
    payload = {
        "resume_text": "3年前端开发，熟悉Vue3、TypeScript",
        "job_description": "要求React、性能优化",
    }
    resp = client.post("/api/match", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["match_score"] == 65
    assert body["level"] in {"EXCELLENT", "GOOD_FIT", "PARTIAL_FIT", "WEAK_FIT"}
    assert isinstance(body["advantages"], list) and body["advantages"]
    assert isinstance(body["improvements"], list)
    assert body["meta"]["aiMode"] == "hybrid"
    assert "breakdown" in body


def test_match_missing_resume(client: TestClient) -> None:
    """异常场景：resume_text 为空。"""
    resp = client.post("/api/match", json={"resume_text": "", "job_description": "要求React"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["match_score"] == 0
    assert "resume_text" in body["message"]


def test_match_missing_jd(client: TestClient) -> None:
    """异常场景：job_description 为空。"""
    resp = client.post("/api/match", json={"resume_text": "3年前端", "job_description": ""})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["match_score"] == 0
    assert "job_description" in body["message"]


def test_match_llm_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """异常场景：LLM 失败降级——返回 200 + 规则层可解释结果（hits/gaps）。"""

    def _boom(system_prompt: str, user_prompt: str):  # noqa: ANN202
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "call_llm_json", _boom)
    resp = client.post(
        "/api/match",
        json={"resume_text": "熟悉Vue3", "job_description": "要求Vue3和React"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["degraded"] is True
    assert body["meta"]["aiMode"] == "rule"
    # 规则层应精确命中 Vue（EXACT/SYNONYM），并给出 React 缺口与学习路径
    assert any(h["skill"] == "Vue" for h in body["hits"])
    assert any(g["skill"] == "React" for g in body["gaps"])
    assert body["gaps"][0]["learningPath"], "能力缺口应带学习路径"
    assert body["level"] in {"EXCELLENT", "GOOD_FIT", "PARTIAL_FIT", "WEAK_FIT"}


def test_match_accepts_camel_case_fields(client: TestClient, fake_llm) -> None:
    """契约场景：Java 转发层使用驼峰 resumeText/jobDescription，应被正确解析。"""
    resp = client.post(
        "/api/match",
        json={"resumeText": "3年前端开发，熟悉Vue3", "jobDescription": "要求React"},
    )
    assert resp.status_code == 200
    assert resp.json()["match_score"] == 65


# ==================== /api/optimize ====================

def test_optimize_normal(client: TestClient, fake_llm) -> None:
    """正常场景：返回总体评价、优化建议与缺失关键词。"""
    payload = {
        "resume_text": "3年前端开发经验，熟悉Vue3",
        "job_description": "要求React、性能优化",
    }
    resp = client.post("/api/optimize", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["summary"]
    assert isinstance(body["suggestions"], list) and len(body["suggestions"]) >= 1
    assert isinstance(body["missing_keywords"], list)
    assert body["meta"]["aiMode"] == "hybrid"


def test_optimize_empty_resume(client: TestClient) -> None:
    """异常场景：resume_text 为空。"""
    resp = client.post("/api/optimize", json={"resume_text": "", "job_description": "要求React"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["summary"] == ""
    assert "不能为空" in body["message"]


def test_optimize_llm_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """异常场景：LLM 失败降级——返回 200 + 规则层缺失关键词兜底，meta 标记 degraded。"""

    def _boom(system_prompt: str, user_prompt: str):  # noqa: ANN202
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "call_llm_json", _boom)
    resp = client.post(
        "/api/optimize",
        json={"resume_text": "熟悉Vue3", "job_description": "要求React、性能优化"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["degraded"] is True
    assert body["meta"]["aiMode"] == "rule"
    # 规则层应给出 React 缺口关键词
    assert "React" in body["missing_keywords"]


# ==================== /api/radar ====================

def test_radar_normal(client: TestClient, fake_llm) -> None:
    """正常场景：返回五个维度的能力评分与 meta。"""
    payload = {"resume": "3年前端开发", "jd": "要求React"}
    resp = client.post("/api/radar", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["dimensions"]) == 5
    for dim in body["dimensions"]:
        assert 0 <= dim["score"] <= 100
    assert body["meta"]["aiMode"] == "hybrid"


def test_radar_empty_resume(client: TestClient) -> None:
    """异常场景：resume 为空。"""
    resp = client.post("/api/radar", json={"resume": "", "jd": "要求React"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["dimensions"] == []
    assert "resume" in body["message"]


def test_radar_llm_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """异常场景：LLM 失败降级——返回 200 + 规则层推导的五维度雷达（非空）。"""

    def _boom(system_prompt: str, user_prompt: str):  # noqa: ANN202
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "call_llm_json", _boom)
    resp = client.post("/api/radar", json={"resume": "熟悉Vue3，3年开发", "jd": "要求Vue3和React"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["degraded"] is True
    assert body["meta"]["aiMode"] == "rule"
    # 降级后仍应产出可绘制的五维度数据，而非空结构
    assert len(body["dimensions"]) == 5
    for dim in body["dimensions"]:
        assert 0 <= dim["score"] <= 100


# ==================== 工具函数单元测试 ====================

def test_normalize_text_removes_noise() -> None:
    """文本清洗：去除零宽字符并压缩多余空白。"""
    raw = "Java\u200b  \t开发\n\n\n\n经验"
    cleaned = main.normalize_text(raw)
    assert "\u200b" not in cleaned
    assert "\n\n\n" not in cleaned


def test_extract_skills_alias_matching() -> None:
    """技能归一化：别名应映射到标准名称。"""
    hits = main.extract_skills("熟悉 k8s 与 postgres")
    assert "Kubernetes" in hits
    assert "PostgreSQL" in hits


def test_clamp_score_bounds() -> None:
    """评分规范化：越界值应被裁剪到 0-100。"""
    assert main.clamp_score(-10) == 0
    assert main.clamp_score(150) == 100
    assert main.clamp_score("not-a-number") == 0
    assert main.clamp_score(72.6) == 73


# ==================== 真实 LLM 冒烟测试（无 Key 时自动跳过） ====================

@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="未设置 LLM_API_KEY，跳过真实 LLM 链路冒烟测试",
)
def test_analyze_real_llm_smoke() -> None:
    """真实链路冒烟：仅在配置了 LLM_API_KEY 时执行，验证端到端可用。"""
    with TestClient(main.app) as live_client:
        resp = live_client.post(
            "/api/analyze",
            json={"resume_text": "5年Java开发，熟悉Spring Boot、MySQL"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["keywords"], list)
        assert 0 <= body["score"] <= 100
