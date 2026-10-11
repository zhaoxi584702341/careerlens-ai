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
    """健康检查接口返回 ok。"""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "careerlens-ai-python"


# ==================== /api/analyze ====================

def test_analyze_normal(client: TestClient, fake_llm) -> None:
    """正常场景：返回 LLM 语义抽取的关键词与评分，cleaned_text 正确回显。"""
    payload = {"resume_text": "负责公司官网前端页面开发，主导性能调优"}
    resp = client.post("/api/analyze", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "前端开发" in body["keywords"]
    assert body["score"] == 72
    # cleaned_text 应回显输入（清洗后）
    assert body["cleaned_text"] == payload["resume_text"]
    assert "message" in body


def test_analyze_empty_text(client: TestClient) -> None:
    """异常场景：resume_text 为空，返回参数错误且不调用 LLM。"""
    resp = client.post("/api/analyze", json={"resume_text": "   "})
    assert resp.status_code == 200
    body = resp.json()
    assert body["keywords"] == []
    assert body["score"] == 0
    assert "不能为空" in body["message"]


def test_analyze_missing_field(client: TestClient) -> None:
    """异常场景：缺少必填字段，FastAPI 返回 422 校验错误。"""
    resp = client.post("/api/analyze", json={})
    assert resp.status_code == 422


def test_analyze_llm_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """异常场景：LLM 调用失败应返回 500 与友好提示，并携带本地字典兜底关键词。"""

    def _boom(system_prompt: str, user_prompt: str):  # noqa: ANN202
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr(main, "call_llm_json", _boom)
    resp = client.post("/api/analyze", json={"resume_text": "熟悉 Java、MySQL"})
    assert resp.status_code == 500
    body = resp.json()
    assert "LLM 调用失败" in body["message"]
    # 本地字典兜底应命中 Java / MySQL
    assert "Java" in body["keywords"]
    assert "MySQL" in body["keywords"]


# ==================== /api/match ====================

def test_match_normal(client: TestClient, fake_llm) -> None:
    """正常场景：返回匹配度、优势、改进项与技能差异。"""
    payload = {
        "resume_text": "3年前端开发，熟悉Vue3、TypeScript",
        "job_description": "要求React、性能优化",
    }
    resp = client.post("/api/match", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["match_score"] == 65
    assert isinstance(body["advantages"], list) and body["advantages"]
    assert isinstance(body["improvements"], list)
    assert body["message"] == "匹配完成"


def test_match_missing_resume(client: TestClient) -> None:
    """异常场景：resume_text 为空。"""
    resp = client.post("/api/match", json={"resume_text": "", "job_description": "要求React"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["match_score"] == 0
    assert "resume_text" in body["message"]


def test_match_missing_jd(client: TestClient) -> None:
    """异常场景：job_description 为空。"""
    resp = client.post("/api/match", json={"resume_text": "3年前端", "job_description": ""})
    assert resp.status_code == 200
    body = resp.json()
    assert body["match_score"] == 0
    assert "job_description" in body["message"]


def test_match_llm_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """异常场景：LLM 失败返回 500，并携带规则层计算的技能差异兜底。"""

    def _boom(system_prompt: str, user_prompt: str):  # noqa: ANN202
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "call_llm_json", _boom)
    resp = client.post(
        "/api/match",
        json={"resume_text": "熟悉Vue3", "job_description": "要求Vue3和React"},
    )
    assert resp.status_code == 500
    body = resp.json()
    assert "LLM 调用失败" in body["message"]


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
    assert body["summary"]
    assert isinstance(body["suggestions"], list) and len(body["suggestions"]) >= 1
    assert isinstance(body["missing_keywords"], list)
    assert body["message"] == "优化建议已生成"


def test_optimize_empty_resume(client: TestClient) -> None:
    """异常场景：resume_text 为空。"""
    resp = client.post("/api/optimize", json={"resume_text": "", "job_description": "要求React"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == ""
    assert "不能为空" in body["message"]


def test_optimize_llm_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """异常场景：LLM 失败返回 500。"""

    def _boom(system_prompt: str, user_prompt: str):  # noqa: ANN202
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "call_llm_json", _boom)
    resp = client.post("/api/optimize", json={"resume_text": "简历", "job_description": "岗位"})
    assert resp.status_code == 500
    assert "LLM 调用失败" in resp.json()["message"]


# ==================== /api/radar ====================

def test_radar_normal(client: TestClient, fake_llm) -> None:
    """正常场景：返回五个维度的能力评分。"""
    payload = {"resume": "3年前端开发", "jd": "要求React"}
    resp = client.post("/api/radar", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["dimensions"]) == 5
    for dim in body["dimensions"]:
        assert 0 <= dim["score"] <= 100
    assert body["message"] == "雷达图数据已生成"


def test_radar_empty_resume(client: TestClient) -> None:
    """异常场景：resume 为空。"""
    resp = client.post("/api/radar", json={"resume": "", "jd": "要求React"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["dimensions"] == []
    assert "resume" in body["message"]


def test_radar_llm_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """异常场景：LLM 失败返回 500。"""

    def _boom(system_prompt: str, user_prompt: str):  # noqa: ANN202
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "call_llm_json", _boom)
    resp = client.post("/api/radar", json={"resume": "简历", "jd": "岗位"})
    assert resp.status_code == 500
    assert "LLM 调用失败" in resp.json()["message"]


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
