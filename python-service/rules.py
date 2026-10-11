"""CareerLens AI 规则引擎（checklist 2.1–2.4 / 2.6）。

本模块是「可解释评分重心」的纯规则实现，不依赖任何外部 LLM：
- 文本清洗与全角/半角归一化
- 分节识别（basic / education / work / project / skill / summary / other）
- 时间线抽取与时间断档（> 6 个月）检测
- 简历结构化质量问题检测（qualityIssues）
- 技能归一化与分类（language / framework / database / devops / tool / soft-skill）
- JD 需求解析（skill / level / mandatory / evidence）
- 显式匹配打分公式 + 命中三级判定（EXACT / SYNONYM / INFERRED）+ evidence 溯源

所有函数均为纯函数，便于单测与在 AI_MODE=rule 档位下离线复现。
"""

from __future__ import annotations

import re
from typing import Any, Optional

# ===== 技能同义词典：标准技能名 -> {aliases, category} =====
# category 取值：language / framework / database / devops / tool / soft-skill
SKILL_DICT: dict[str, dict[str, Any]] = {
    # 编程语言
    "JavaScript": {"aliases": ["javascript", "js", "es6", "ecmascript"], "category": "language"},
    "TypeScript": {"aliases": ["typescript", "ts"], "category": "language"},
    "Python": {"aliases": ["python", "py"], "category": "language"},
    "Java": {"aliases": ["java"], "category": "language"},
    "Go": {"aliases": ["golang", "go语言"], "category": "language"},
    "C++": {"aliases": ["c++", "cpp"], "category": "language"},
    "C#": {"aliases": ["c#", "csharp", ".net"], "category": "language"},
    "PHP": {"aliases": ["php"], "category": "language"},
    "Ruby": {"aliases": ["ruby"], "category": "language"},
    "Kotlin": {"aliases": ["kotlin"], "category": "language"},
    "Swift": {"aliases": ["swift"], "category": "language"},
    "SQL": {"aliases": ["sql"], "category": "language"},
    # 前端框架 / 库
    "Vue": {"aliases": ["vue", "vue2", "vue3", "vue.js"], "category": "framework"},
    "React": {"aliases": ["react", "react.js", "reactjs"], "category": "framework"},
    "Angular": {"aliases": ["angular", "angularjs"], "category": "framework"},
    "Node.js": {"aliases": ["node", "node.js", "nodejs"], "category": "framework"},
    "Next.js": {"aliases": ["next.js", "nextjs"], "category": "framework"},
    "jQuery": {"aliases": ["jquery"], "category": "framework"},
    "Element UI": {"aliases": ["element ui", "element-ui", "elementui"], "category": "framework"},
    "ECharts": {"aliases": ["echarts"], "category": "framework"},
    # 后端框架
    "Spring Boot": {"aliases": ["spring boot", "springboot", "spring"], "category": "framework"},
    "Spring Cloud": {"aliases": ["spring cloud", "springcloud"], "category": "framework"},
    "MyBatis": {"aliases": ["mybatis", "mybatis-plus", "mybatisplus"], "category": "framework"},
    "FastAPI": {"aliases": ["fastapi"], "category": "framework"},
    "Django": {"aliases": ["django"], "category": "framework"},
    "Flask": {"aliases": ["flask"], "category": "framework"},
    "Express": {"aliases": ["express", "express.js"], "category": "framework"},
    "Nuxt.js": {"aliases": ["nuxt", "nuxt.js"], "category": "framework"},
    # 数据库
    "MySQL": {"aliases": ["mysql"], "category": "database"},
    "PostgreSQL": {"aliases": ["postgresql", "postgres", "pg"], "category": "database"},
    "Oracle": {"aliases": ["oracle"], "category": "database"},
    "SQL Server": {"aliases": ["sql server", "sqlserver", "mssql"], "category": "database"},
    "Redis": {"aliases": ["redis"], "category": "database"},
    "MongoDB": {"aliases": ["mongodb", "mongo"], "category": "database"},
    "Elasticsearch": {"aliases": ["elasticsearch", "es搜索", "elastic search"], "category": "database"},
    "SQLite": {"aliases": ["sqlite"], "category": "database"},
    # 运维 / 部署
    "Docker": {"aliases": ["docker", "容器化"], "category": "devops"},
    "Kubernetes": {"aliases": ["kubernetes", "k8s"], "category": "devops"},
    "Nginx": {"aliases": ["nginx"], "category": "devops"},
    "Jenkins": {"aliases": ["jenkins"], "category": "devops"},
    "CI/CD": {"aliases": ["ci/cd", "cicd", "持续集成", "持续交付"], "category": "devops"},
    "Linux": {"aliases": ["linux", "unix", "centos", "ubuntu"], "category": "devops"},
    "Shell": {"aliases": ["shell", "bash", "脚本"], "category": "devops"},
    # 工具
    "Git": {"aliases": ["git", "github", "gitlab", "gitee"], "category": "tool"},
    "Webpack": {"aliases": ["webpack"], "category": "tool"},
    "Vite": {"aliases": ["vite"], "category": "tool"},
    "Maven": {"aliases": ["maven"], "category": "tool"},
    "Gradle": {"aliases": ["gradle"], "category": "tool"},
    "Postman": {"aliases": ["postman"], "category": "tool"},
    "Jira": {"aliases": ["jira"], "category": "tool"},
    "RESTful": {"aliases": ["restful", "rest api", "rest接口"], "category": "tool"},
    "GraphQL": {"aliases": ["graphql"], "category": "tool"},
    "gRPC": {"aliases": ["grpc"], "category": "tool"},
    "微服务": {"aliases": ["微服务", "microservice", "micro-services"], "category": "framework"},
    "机器学习": {"aliases": ["机器学习", "machine learning"], "category": "framework"},
    "深度学习": {"aliases": ["深度学习", "deep learning"], "category": "framework"},
    "数据分析": {"aliases": ["数据分析", "data analysis", "data analyst"], "category": "tool"},
    "单元测试": {"aliases": ["单元测试", "unit test", "jest", "vitest", "pytest", "junit"], "category": "tool"},
    "性能优化": {"aliases": ["性能优化", "performance optimization", "性能调优"], "category": "tool"},
    "项目管理": {"aliases": ["项目管理", "project management"], "category": "soft-skill"},
    "团队协作": {"aliases": ["团队协作", "teamwork", "团队合作"], "category": "soft-skill"},
    "沟通能力": {"aliases": ["沟通能力", "沟通", "communication"], "category": "soft-skill"},
    "问题解决": {"aliases": ["问题解决", "problem solving", "排查问题"], "category": "soft-skill"},
    "责任心": {"aliases": ["责任心", "责任感"], "category": "soft-skill"},
    "学习能力": {"aliases": ["学习能力", "self-learning", "自学"], "category": "soft-skill"},
}

# 反查表：别名 -> 标准名（构建一次，供 O(1) 命中）
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _meta in SKILL_DICT.items():
    _ALIAS_TO_CANONICAL[_canonical.lower()] = _canonical
    for _alias in _meta["aliases"]:
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical

# ===== 分节标题关键词 =====
SECTION_PATTERNS: list[tuple[str, list[str]]] = [
    ("education", ["教育背景", "教育经历", "学历", "education", "院校", "学校"]),
    ("work", ["工作经历", "工作经验", "职业经历", "实习经历", "实习经验", "work experience", "employment"]),
    ("project", ["项目经历", "项目经验", "项目描述", "projects", "project experience"]),
    ("skill", ["技能", "专业技能", "技术栈", "技能特长", "skills", "it技能"]),
    ("summary", ["自我评价", "个人评价", "自我描述", "自我介绍", "summary", "about me"]),
    ("basic", ["基本信息", "个人信息", "求职意向", "联系方式", "个人资料", "basic information"]),
]

# ===== 时间区间正则 =====
# 兼容：2021.09–2025.06 / 2021-09 ~ 2025.06 / 2021/09-2025/06 / 2023年6月 - 至今 / 2020年至今
_START = r"(?P<sy>19\d{2}|20\d{2})\s*[.\-/年]\s*(?P<sm>1[0-2]|0?[1-9])?\s*月?"
_END = r"(?P<ey>19\d{2}|20\d{2})\s*[.\-/年]\s*(?P<em>1[0-2]|0?[1-9])?\s*月?"
_RANGE_RE = re.compile(
    _START + r"\s*(?:--|—|–|~|至|-|到)\s*"
    + r"(?:(?P<present>至今|现在|now|present)|" + _END + r")",
    re.IGNORECASE,
)

# 年份提取（用于经验年限估算）
_YEAR_RE = re.compile(r"(19\d{2}|20\d{2})")
# 量化成果关键词（数字 + 百分比 / 倍数 / 用户量等）
_QUANT_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:%|％|倍|万|亿|k|K|w|W|人|次|ms|秒|s\b)|\d+\s*(?:用户|订单|qps|QPS|tps|TPS))")


def normalize_text(text: str) -> str:
    """文本清洗：去掉控制字符 / 零宽字符，全角转半角，规范化中英文间距。"""
    if not text:
        return ""
    # 全角字符 -> 半角（保留中文）
    cleaned = _to_halfwidth(text)
    # 去除零宽字符与不可见控制字符
    cleaned = re.sub(r"[\u200b-\u200f\ufeff\u00ad]", "", cleaned)
    # 中英文之间补充/去重空格
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    # 折叠过多空行
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _to_halfwidth(text: str) -> str:
    """全角字符转半角（ASCII 编码区 0xFF01–0xFF5E 及全角空格）。"""
    result: list[str] = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:  # 全角空格
            result.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(ch)
    return "".join(result)


def canonical_skill(raw_name: str) -> Optional[str]:
    """把单个技能名映射为标准技能名，无法映射返回 None。"""
    if not raw_name:
        return None
    lowered = raw_name.strip().lower()
    return _ALIAS_TO_CANONICAL.get(lowered)


def skill_category(canonical: str) -> str:
    """返回标准技能名所属分类，未知归为 other。"""
    meta = SKILL_DICT.get(canonical)
    return meta["category"] if meta else "other"


# ===== 语义推断规则：自然语言能力描述 -> 标准技能名（INFERRED） =====
# 用于捕捉「未直接写出技能名，但以职责/行为描述表达的能力」，
# 例如“负责前端页面开发”应推断出「Vue/前端开发」相关能力。
# 每条规则为 (正则, 标准技能名)，命中即产生 INFERRED 命中（置信度低于 EXACT/SYNONYM）。
_INFERENCE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(前端|页面|界面).{0,4}(开发|重构|实现)"), "Vue"),
    (re.compile(r"(后端|服务端).{0,4}(开发|接口|实现)"), "Java"),
    (re.compile(r"自动化测试|测试用例|测试框架"), "单元测试"),
    (re.compile(r"(接口|服务).{0,3}(性能|响应).{0,3}(优化|调优|提升)"), "性能优化"),
    (re.compile(r"(容器化|镜像|编排).{0,4}(部署|发布)"), "Docker"),
    (re.compile(r"(持续集成|持续交付|流水线|自动化部署)"), "CI/CD"),
    (re.compile(r"(数据).{0,3}(分析|挖掘|报表|可视化)"), "数据分析"),
    (re.compile(r"(带|管理|协调).{0,3}(团队|小组|成员)"), "团队协作"),
]
# 语义推断的固定置信度：低于 EXACT(1.0) 与 SYNONYM(0.9)，体现不确定性
_INFERRED_CONFIDENCE = 0.7


def _find_alias_position(text_lower: str, alias: str) -> int:
    """在文本中定位别名；对纯 ASCII 别名加词边界，避免 "java" 命中 "javascript"。"""
    if not alias:
        return -1
    if re.fullmatch(r"[a-z0-9+#./ -]+", alias):
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        m = re.search(pattern, text_lower)
        return m.start() if m else -1
    return text_lower.find(alias)


def extract_skill_hits(text: str) -> list[dict[str, Any]]:
    """从文本抽取技能命中项，附原始表述、位置与命中类型。

    返回：[{canonical, raw, category, confidence, position, hitType}]
    - EXACT   ：原始表述与标准名一致
    - SYNONYM ：命中了词典别名
    - INFERRED：未直接出现技能名，但由自然语言职责/行为描述语义推断得到
    """
    if not text:
        return []
    lowered = text.lower()
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for canonical, meta in SKILL_DICT.items():
        if canonical in seen:
            continue
        found: Optional[tuple[str, int]] = None
        # 优先匹配标准名本身（EXACT）
        pos = _find_alias_position(lowered, canonical.lower())
        if pos >= 0:
            found = (canonical, pos)
        else:
            for alias in meta["aliases"]:
                pos = _find_alias_position(lowered, alias.lower())
                if pos >= 0:
                    found = (alias, pos)
                    break
        if found:
            raw, position = found
            hit_type = "EXACT" if raw.lower() == canonical.lower() else "SYNONYM"
            hits.append(
                {
                    "canonical": canonical,
                    "raw": raw,
                    "category": meta["category"],
                    "confidence": 1.0 if hit_type == "EXACT" else 0.9,
                    "position": position,
                    "hitType": hit_type,
                }
            )
            seen.add(canonical)

    # 语义推断：补足未直接命中的技能（INFERRED），置信度低于 EXACT/SYNONYM
    for pattern, canonical in _INFERENCE_RULES:
        if canonical in seen:
            continue
        match = pattern.search(text)
        if not match:
            continue
        hits.append(
            {
                "canonical": canonical,
                "raw": match.group(0),
                "category": skill_category(canonical),
                "confidence": _INFERRED_CONFIDENCE,
                "position": match.start(),
                "hitType": "INFERRED",
            }
        )
        seen.add(canonical)

    hits.sort(key=lambda h: h["position"])
    return hits


def extract_skills(text: str) -> list[str]:
    """返回命中的标准技能名列表（保持原文出现顺序、去重）。"""
    return [h["canonical"] for h in extract_skill_hits(text)]


def detect_language(text: str) -> str:
    """语言识别：zh / en / mixed。"""
    if not text:
        return "zh"
    zh = len(re.findall(r"[\u4e00-\u9fff]", text))
    en = len(re.findall(r"[A-Za-z]", text))
    if zh == 0 and en == 0:
        return "zh"
    if zh > 0 and en > 0:
        # 按占比判断，英文占比不足 15% 视为中文简历
        total = zh + en
        return "mixed" if en / total >= 0.15 else "zh"
    return "zh" if zh > 0 else "en"


def _match_section_title(line: str) -> Optional[tuple[str, str]]:
    """判断某一行是否为章节标题，返回 (section_name, 原始标题)。"""
    stripped = line.strip().strip("：:#：* -【】[]")
    if not stripped or len(stripped) > 20:
        return None
    lowered = stripped.lower()
    for name, keywords in SECTION_PATTERNS:
        for kw in keywords:
            if kw in lowered:
                return name, stripped
    return None


def split_sections(text: str) -> list[dict[str, Any]]:
    """分节识别：按标题关键词把文本切分为若干章节。

    未命中任何标题的内容归入 other；无标题时整篇归为 other。
    """
    lines = text.split("\n")
    sections: list[dict[str, Any]] = []
    current_name = "other"
    current_title = ""
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append({"name": current_name, "title": current_title, "text": body})

    for line in lines:
        matched = _match_section_title(line)
        if matched:
            flush()
            buffer = []
            current_name, current_title = matched
        else:
            buffer.append(line)
    flush()

    if not sections and text.strip():
        sections.append({"name": "other", "title": "", "text": text.strip()})
    return sections


def extract_timeline(text: str) -> list[dict[str, str]]:
    """抽取时间区间，输出 [{start, end}]；end 为 present 表示至今。"""
    items: list[dict[str, str]] = []
    for m in _RANGE_RE.finditer(text):
        group = m.groupdict()
        start = _fmt_month(group.get("sy"), group.get("sm"))
        if not start:
            continue
        if group.get("present"):
            end = "present"
        else:
            end = _fmt_month(group.get("ey"), group.get("em")) or "present"
        items.append({"start": start, "end": end})
    return items


def _fmt_month(year: Optional[str], month: Optional[str]) -> str:
    """把年/月格式化为 YYYY-MM（缺月补 01）。"""
    if not year:
        return ""
    if month:
        return f"{year}-{int(month):02d}"
    return f"{year}-01"


def _month_index(value: str) -> Optional[int]:
    """把 YYYY-MM / YYYY 转成可用于比较的月序号（年*12+月）。"""
    if not value or value == "present":
        return None
    m = re.match(r"(\d{4})(?:-(\d{1,2}))?", value)
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 1
    return year * 12 + month


def _merge_ranges(ranges: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """合并重叠/相接的时间区间，避免并行经历被误判为断档。"""
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda r: (r[0], r[1]))
    merged: list[tuple[int, int, str]] = [ordered[0]]
    for start, end, label in ordered[1:]:
        last_start, last_end, last_label = merged[-1]
        if start <= last_end:  # 重叠或相接：合并，保留覆盖最长的区间标签
            new_end = max(last_end, end)
            new_label = last_label if last_end >= end else label
            merged[-1] = (last_start, new_end, new_label)
        else:
            merged.append((start, end, label))
    return merged


def _collect_employment_ranges(text: str) -> list[tuple[int, int, str]]:
    """抽取用于断档判断的时间线。

    简历中「公司 + 起止时间」常出现在章节标题之前的经历摘要行，
    因此这里不按章节裁剪，而是对全文时间线做合并后再判断断档；
    并行/重叠的区间会被 _merge_ranges 合并，避免误判（假阳性）。
    """
    ranges: list[tuple[int, int, str]] = []
    for item in extract_timeline(text):
        start_idx = _month_index(item["start"])
        end_idx = _month_index(item["end"])
        if start_idx is None:
            continue
        if end_idx is None:  # 至今
            end_idx = 999999
        ranges.append((start_idx, end_idx, f"{item['start']} ~ {item['end']}"))
    return ranges


def detect_employment_gaps(text: str, gap_months: int = 6) -> list[dict[str, Any]]:
    """时间断档检测：相邻经历区间之间空档 > gap_months 个月记为断档。

    先合并重叠/相接的区间（并行经历、项目区间），再判断相邻区间空档，
    避免把同步进行的多段经历误判为断档（假阳性）。

    返回：[{months, after, before, evidence}]
    """
    ranges = _merge_ranges(_collect_employment_ranges(text))

    gaps: list[dict[str, Any]] = []
    for i in range(len(ranges) - 1):
        _, cur_end, cur_label = ranges[i]
        next_start, _, next_label = ranges[i + 1]
        if cur_end >= 999999:
            continue
        months = next_start - cur_end
        if months > gap_months:
            gaps.append(
                {
                    "months": months,
                    "after": cur_label,
                    "before": next_label,
                    "evidence": f"{cur_label} 与 {next_label} 之间空档约 {months} 个月",
                }
            )
    return gaps


def _estimate_years(text: str) -> float:
    """估算经验年限：取所有时间区间的总跨度（去重后按最早起点到最晚终点）。"""
    idxs = []
    for item in extract_timeline(text):
        s = _month_index(item["start"])
        e = _month_index(item["end"])
        if s is not None:
            idxs.append(s)
        if e is not None:
            idxs.append(e)
    if len(idxs) < 2:
        return 0.0
    return round((max(idxs) - min(idxs)) / 12, 1)


def detect_quality_issues(text: str, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """简历结构化质量问题检测（checklist 2.2），每条含 code/severity/message/location/suggestion。"""
    issues: list[dict[str, Any]] = []
    names = {s["name"] for s in sections}
    word_count = len(re.sub(r"\s", "", text))

    # 篇幅异常
    if word_count < 300:
        issues.append(
            {
                "code": "TOO_SHORT",
                "severity": "high",
                "message": f"简历正文仅约 {word_count} 字，篇幅明显偏短，难以体现完整经历",
                "location": "全文",
                "suggestion": "补充工作/项目经历的具体职责与成果，建议正文扩充至 600 字以上",
            }
        )
    elif word_count > 4000:
        issues.append(
            {
                "code": "TOO_LONG",
                "severity": "warn",
                "message": f"简历正文约 {word_count} 字，篇幅偏长，重点易被稀释",
                "location": "全文",
                "suggestion": "精简与目标岗位无关的经历，突出与 JD 强相关的项目，建议压缩至 2000 字以内",
            }
        )

    # 信息量不足
    if word_count < 600:
        issues.append(
            {
                "code": "INSUFFICIENT_DETAIL",
                "severity": "warn",
                "message": "简历信息量不足，关键经历细节缺失",
                "location": "工作/项目经历",
                "suggestion": "针对每段经历补充「做了什么 + 用了什么技术 + 拿到什么结果」三段式描述",
            }
        )

    # 关键章节缺失
    required = {"work": "工作/实习经历", "skill": "专业技能", "education": "教育背景"}
    missing = [label for key, label in required.items() if key not in names]
    if missing:
        issues.append(
            {
                "code": "MISSING_SECTION",
                "severity": "high" if "work" in (set(required) - names) else "warn",
                "message": f"缺少关键章节：{'、'.join(missing)}",
                "location": "文档结构",
                "suggestion": f"补充缺失章节：{'、'.join(missing)}，保证简历结构完整",
            }
        )

    # 量化成果缺失（工作 / 项目章节无任何数字指标）
    work_project = "\n".join(s["text"] for s in sections if s["name"] in {"work", "project"})
    if work_project and not _QUANT_RE.search(work_project):
        issues.append(
            {
                "code": "NO_QUANTIFIED_IMPACT",
                "severity": "high",
                "message": "工作/项目经历缺少可量化成果，说服力不足",
                "location": "工作/项目经历",
                "suggestion": "用数字量化成果，例如「接口平均响应时间从 800ms 降至 200ms」「订单转化率提升 15%」",
            }
        )

    # 技能纯罗列无实践支撑：技能章节有内容，但工作/项目章节未出现该技能
    skill_section = "\n".join(s["text"] for s in sections if s["name"] == "skill")
    if skill_section:
        listed = set(extract_skills(skill_section))
        practiced = set(extract_skills(work_project)) if work_project else set()
        only_listed = listed - practiced
        if listed and len(only_listed) == len(listed) and len(listed) >= 3:
            issues.append(
                {
                    "code": "SKILL_LIST_WITHOUT_DEPTH",
                    "severity": "warn",
                    "message": "技能以纯罗列呈现，工作/项目经历中缺少对应实践支撑",
                    "location": "专业技能",
                    "suggestion": "为列出的核心技能补充实际使用场景与项目案例，避免「只列不用」",
                }
            )

    # 时间断档
    for gap in detect_employment_gaps(text):
        issues.append(
            {
                "code": "EMPLOYMENT_GAP",
                "severity": "warn",
                "message": f"检测到约 {gap['months']} 个月的时间断档",
                "location": "工作经历时间线",
                "suggestion": "如为学习/进修/空窗期，建议在简历中简要说明，避免 HR 产生疑虑",
            }
        )

    return issues


# ===== JD 需求解析 =====
_LEVEL_KEYWORDS = ["精通", "熟练", "熟悉", "了解"]
_MANDATORY_MARKERS = ["必备", "必须", "要求", "任职要求", "岗位要求", "需具备", "至少"]
_OPTIONAL_MARKERS = ["加分", "优先", "plus", "bonus", "有...更佳", "更佳"]


def parse_jd_requirements(jd: str) -> list[dict[str, Any]]:
    """JD 需求解析：输出 [{skill, level, mandatory, evidence}]。

    - skill：归一化后的标准技能名
    - level：从 精通/熟练/熟悉/了解 中取，缺省为 了解
    - mandatory：按所在句子是否含「必备/要求」等标记判定，缺省为 True
    - evidence：JD 原文中该技能所在的行
    """
    if not jd:
        return []
    lines = [ln.strip() for ln in jd.split("\n") if ln.strip()]
    # 加分项区块起始行，其后默认非必备
    optional_zone = False
    requirements: list[dict[str, Any]] = []
    seen: set[str] = set()

    for line in lines:
        lowered = line.lower()
        if any(mk in line for mk in ["加分", "优先", "更佳"]) or "bonus" in lowered or "plus" in lowered:
            optional_zone = True
        hits = extract_skill_hits(line)
        for hit in hits:
            canonical = hit["canonical"]
            if canonical in seen:
                continue
            level = _detect_level_for_pos(line, hit["position"])
            mandatory = not optional_zone
            if any(mk in line for mk in ["加分", "优先", "更佳"]):
                mandatory = False
            requirements.append(
                {
                    "skill": canonical,
                    "level": level,
                    "mandatory": mandatory,
                    "evidence": line,
                }
            )
            seen.add(canonical)
    return requirements


def _detect_level_for_pos(line: str, pos: int) -> str:
    """识别某个技能前的最近一个熟练度关键词，缺省为「了解」。

    例如「精通Java，熟悉Spring Boot」，Java -> 精通，Spring Boot -> 熟悉。
    """
    best_kw = "了解"
    best_idx = -1
    for kw in _LEVEL_KEYWORDS:
        idx = line.rfind(kw, 0, pos)
        if idx > best_idx:
            best_idx = idx
            best_kw = kw
    return best_kw


def _detect_level(line: str) -> str:
    """从一行文本中识别熟练度要求，缺省为「了解」。"""
    for kw in _LEVEL_KEYWORDS:
        if kw in line:
            return kw
    return "了解"


# ===== 显式匹配打分（checklist 2.4） =====
LEVEL_BANDS = [
    (85, "EXCELLENT"),
    (70, "GOOD_FIT"),
    (50, "PARTIAL_FIT"),
    (0, "WEAK_FIT"),
]

# 学习路径模板：按技能分类给出可执行步骤
LEARNING_PATH_TEMPLATES: dict[str, list[str]] = {
    "language": ["补齐该语言的基础语法与常用标准库", "用该语言完成一个练手项目并开源", "在简历中以项目形式体现使用经历"],
    "framework": ["阅读官方文档完成 Hello World 与核心概念", "基于该框架实现一个含 CRUD 的完整小项目", "提炼项目亮点并写入简历项目经历"],
    "database": ["掌握基础 SQL 与索引原理", "在本地搭建实例并完成建表/查询/优化练习", "结合项目说明数据建模与性能优化经验"],
    "devops": ["理解核心概念与典型使用场景", "在本地或云主机完成一次部署/编排实践", "把部署流程沉淀为简历中的工程化亮点"],
    "tool": ["熟悉该工具的核心工作流", "在日常开发中持续使用并记录收益", "在简历中体现为提效或质量保障成果"],
    "soft-skill": ["在项目中主动承担相关职责并复盘", "用具体事例（STAR 法则）准备面试话术", "将协作成果量化后写入简历"],
    "other": ["系统学习该技能的核心知识", "完成一个可展示的实践项目", "在简历中补充对应项目证据"],
}


def build_learning_path(skill: str) -> list[str]:
    """根据技能分类生成学习路径步骤。"""
    category = skill_category(skill)
    return LEARNING_PATH_TEMPLATES.get(category, LEARNING_PATH_TEMPLATES["other"])


def _importance_for(req: dict[str, Any]) -> str:
    """缺口重要度：必备 + 熟练度要求高 -> high。"""
    if req.get("mandatory") and req.get("level") in {"精通", "熟练"}:
        return "high"
    if req.get("mandatory"):
        return "medium"
    return "low"


def compute_match(
    resume_text: str,
    jd_text: str,
    years_override: Optional[float] = None,
) -> dict[str, Any]:
    """显式可复现打分，返回契约中的 match 区块。

    score = round(100 × (0.6×mandatory + 0.3×optional + 0.1×levelFit))
    """
    requirements = parse_jd_requirements(jd_text)
    mandatory_reqs = [r for r in requirements if r["mandatory"]]
    optional_reqs = [r for r in requirements if not r["mandatory"]]

    # 简历侧技能命中（带 evidence 溯源）
    resume_hits = extract_skill_hits(resume_text)
    resume_skill_map = {h["canonical"]: h for h in resume_hits}
    resume_skills = set(resume_skill_map)

    # 必备 / 加分命中率
    mandatory_hit = [r for r in mandatory_reqs if r["skill"] in resume_skills]
    optional_hit = [r for r in optional_reqs if r["skill"] in resume_skills]
    mandatory_rate = len(mandatory_hit) / len(mandatory_reqs) if mandatory_reqs else 1.0
    optional_rate = len(optional_hit) / len(optional_reqs) if optional_reqs else 1.0  # 无加分项按 1.0

    # 经验年限匹配度：默认认为 JD 期望 3 年，超出不计罚
    resume_years = years_override if years_override is not None else _estimate_years(resume_text)
    expected_years = 3.0
    level_fit = min(resume_years / expected_years, 1.0) if expected_years else 1.0

    score = round(100 * (0.6 * mandatory_rate + 0.3 * optional_rate + 0.1 * level_fit))
    score = max(0, min(100, score))
    level = next(band for threshold, band in LEVEL_BANDS if score >= threshold)

    # 命中项：必备 + 加分命中，附 evidence 与 source 定位
    hits: list[dict[str, Any]] = []
    matched_skills: set[str] = set()
    for req in mandatory_reqs + optional_reqs:
        skill = req["skill"]
        if skill in resume_skills and skill not in matched_skills:
            hit = resume_skill_map[skill]
            hits.append(
                {
                    "skill": skill,
                    "hitType": hit["hitType"],
                    "confidence": hit["confidence"],
                    "evidence": _evidence_snippet(resume_text, hit["raw"]),
                    "source": f"resume.skills.normalized[{skill}]",
                }
            )
            matched_skills.add(skill)

    # 能力缺口：JD 要求但简历未覆盖
    gaps: list[dict[str, Any]] = []
    for req in mandatory_reqs + optional_reqs:
        skill = req["skill"]
        if skill not in resume_skills:
            gaps.append(
                {
                    "skill": skill,
                    "importance": _importance_for(req),
                    "suggestion": f"简历中未见「{skill}」相关经历，建议补充该技能的项目实践并在简历中体现",
                    "learningPath": build_learning_path(skill),
                }
            )

    return {
        "score": score,
        "level": level,
        "breakdown": {
            "mandatory": round(mandatory_rate, 4),
            "optional": round(optional_rate, 4),
            "levelFit": round(level_fit, 4),
        },
        "hits": hits,
        "gaps": gaps,
        "matched_skills": sorted(matched_skills),
        "missing_skills": sorted({g["skill"] for g in gaps}),
        "requirements": requirements,
    }


def _evidence_snippet(text: str, raw: str, radius: int = 40) -> str:
    """从原文截取包含命中技能的一小段作为 evidence（可解释性硬指标）。"""
    if not text or not raw:
        return ""
    lowered = text.lower()
    pos = lowered.find(raw.lower())
    if pos < 0:
        return ""
    left = max(0, pos - radius)
    right = min(len(text), pos + len(raw) + radius)
    snippet = text[left:right].replace("\n", " ").strip()
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{snippet}{suffix}"
