#!/usr/bin/env python3
# =============================================================================
# CareerLens AI 契约校验脚本（CI contract 作业调用）
#
# 零第三方依赖，仅用标准库，保证本地与 CI 均可离线运行。
#
# 校验内容：
#   1. contracts/ 下所有 *.schema.json 是合法 JSON 且具备 draft-07 元字段；
#   2. schema 元字段合规（$schema / $id / type=object）；
#   3. error-envelope 的 code 枚举与 error-codes.md 文档一致；
#   4. analysis-response 的必需字段/枚举与代表性样例实例一致（结构断言）。
#
# 用法：python scripts/validate-contracts.py
# 退出码：0 = 全部通过；1 = 存在失败。
# =============================================================================
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"

PASS = 0
FAIL = 0


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"  \033[32mPASS\033[0m {msg}")


def bad(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  \033[31mFAIL\033[0m {msg}")


def check(cond: bool, msg: str) -> None:
    ok(msg) if cond else bad(msg)


def load_schema(path: pathlib.Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_schema_files() -> dict[str, dict]:
    """1. 所有 *.schema.json 必须是合法 JSON。"""
    print("== 1. JSON Schema 合法性 ==")
    schemas: dict[str, dict] = {}
    files = sorted(CONTRACTS.glob("*.schema.json"))
    check(len(files) > 0, f"发现 {len(files)} 个 schema 文件")
    for path in files:
        try:
            schema = load_schema(path)
        except json.JSONDecodeError as exc:
            bad(f"{path.name} 不是合法 JSON：{exc}")
            continue
        if not isinstance(schema, dict):
            bad(f"{path.name} 顶层不是对象")
            continue
        ok(f"{path.name} 是合法 JSON 对象")
        schemas[path.name] = schema
    return schemas


def validate_meta(schemas: dict[str, dict]) -> None:
    """2. 契约元字段合规。"""
    print("== 2. 契约元字段 ==")
    for name, schema in schemas.items():
        check(str(schema.get("$schema", "")).endswith("draft-07/schema#"),
              f"{name} 声明 $schema=draft-07")
        check(isinstance(schema.get("$id"), str) and schema["$id"].startswith("https://"),
              f"{name} 含 https $id")
        check(schema.get("type") == "object", f"{name} 顶层 type=object")


def validate_error_codes(schemas: dict[str, dict]) -> None:
    """3. schema 枚举与 error-codes.md 的一致性。"""
    print("== 3. 错误码一致性 ==")
    envelope = schemas.get("error-envelope.schema.json")
    if envelope is None:
        bad("缺少 error-envelope.schema.json，跳过一致性校验")
        return
    try:
        codes = envelope["properties"]["error"]["properties"]["code"]["enum"]
    except (KeyError, TypeError):
        bad("error-envelope 缺失 code 枚举路径 properties.error.properties.code.enum")
        return
    doc = CONTRACTS / "error-codes.md"
    if not doc.exists():
        bad("缺少 error-codes.md")
        return
    text = doc.read_text(encoding="utf-8")
    missing = [c for c in codes if c not in text]
    check(not missing, f"error-codes.md 覆盖全部 {len(codes)} 个错误码"
                       + (f"（缺失：{missing}）" if missing else ""))


def _resolve_ref(schema: dict, node: dict) -> dict:
    """解析 schema 内部的 $ref（仅支持 #/... 本地引用）。"""
    ref = node.get("$ref")
    if not ref or not ref.startswith("#/"):
        return node
    cur: object = schema
    for part in ref[2:].split("/"):
        cur = cur[part]  # type: ignore[index]
    return cur  # type: ignore[return-value]


def validate_sample_instance(schemas: dict[str, dict]) -> None:
    """4. 用代表性样例实例对 analysis-response 做结构断言。"""
    print("== 4. 样例响应实例结构断言 ==")
    schema = schemas.get("analysis-response.schema.json")
    if schema is None:
        bad("缺少 analysis-response.schema.json")
        return

    required = schema.get("required", [])
    check(set(required) >= {"success", "meta"},
          f"顶层 required 含 success/meta（实际 {required}）")

    meta = _resolve_ref(schema, schema["properties"]["meta"])
    meta_required = set(meta.get("required", []))
    check(meta_required == {"timings", "degraded", "aiMode"},
          f"meta.required = timings/degraded/aiMode（实际 {sorted(meta_required)}）")

    ai_mode_enum = meta["properties"]["aiMode"]["enum"]
    check(ai_mode_enum == ["llm", "hybrid", "rule"],
          f"meta.aiMode 枚举 = llm/hybrid/rule（实际 {ai_mode_enum}）")

    # 代表性合法 / 非法实例的字段级断言
    good = {"success": True,
            "meta": {"timings": {"python": 12, "llm": 0, "total": 12},
                     "degraded": True, "aiMode": "rule"}}
    check(set(good.keys()) >= set(required), "合法实例含全部必需顶层字段")
    check(good["meta"]["aiMode"] in ai_mode_enum, "合法实例 aiMode 在枚举内")

    bad_instance = {"success": True}  # 缺 meta
    check(not set(required) <= set(bad_instance.keys()),
          "缺失 meta 的实例被识别为不合规")

    bad_mode = "magic"
    check(bad_mode not in ai_mode_enum, "非法 aiMode 被识别为不合规")

    # match 打分枚举与契约一致性
    match = _resolve_ref(schema, schema["properties"]["match"])
    levels = match["properties"]["level"]["enum"]
    check(levels == ["EXCELLENT", "GOOD_FIT", "PARTIAL_FIT", "WEAK_FIT"],
          f"match.level 枚举四级完整（实际 {levels}）")

    hits = _resolve_ref(schema, match["properties"]["hits"]["items"])
    hit_types = hits["properties"]["hitType"]["enum"]
    check(hit_types == ["EXACT", "SYNONYM", "INFERRED"],
          f"hits.hitType 枚举含 EXACT/SYNONYM/INFERRED（实际 {hit_types}）")


def main() -> int:
    print("\033[1m[contract] 校验 contracts/ 契约文件\033[0m")
    schemas = validate_schema_files()
    validate_meta(schemas)
    validate_error_codes(schemas)
    validate_sample_instance(schemas)
    print(f"\n\033[1m[contract] 汇总：PASS={PASS}  FAIL={FAIL}\033[0m")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
