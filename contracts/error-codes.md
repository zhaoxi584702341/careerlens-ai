# 统一错误码枚举表（Error Codes）

> 本表为四层链路（Vue → BFF → Java → Python）错误码的唯一权威来源。
> 所有对外接口的错误响应必须遵循 `contracts/error-envelope.schema.json`，
> 其中 `error.code` 字段取值必须来自本表。

## 1. 错误信封结构

```json
{
  "requestId": "b7c2f1e0-...",
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数错误：resume_text 不能为空",
    "degraded": false
  }
}
```

- `requestId`：由 BFF 生成并逐层透传（header `X-Request-Id`），用于全链路排查。
- `success`：布尔值，`true` 表示业务成功，`false` 表示业务失败（含降级）。
- `error.degraded`：布尔值；`true` 表示本次结果由规则引擎兜底产出（未使用 LLM）。

## 2. 错误码取值

| Code | HTTP | 含义 | 触发位置 | 前端处理建议 |
|---|---|---|---|---|
| `VALIDATION_ERROR` | 400 | 入参缺失 / 类型错误 / 超长 | BFF 入参校验、Java JSR-380 | 高亮表单字段，提示修正 |
| `EMPTY_INPUT` | 200 | 必填文本为空（业务降级） | Python 各接口 | 提示补充简历 / JD 文本 |
| `UPSTREAM_TIMEOUT` | 504 | 下游服务调用超时 | BFF / Java | 提示稍后重试 + requestId |
| `UPSTREAM_ERROR` | 502 | 下游服务返回 5xx | BFF / Java | 提示服务异常 + requestId |
| `SERVICE_UNAVAILABLE` | 503 | 下游服务不可达（连接失败） | BFF / Java | 提示服务不可用 |
| `LLM_ERROR` | 200 | LLM 调用失败，已降级为规则引擎 | Python | 展示降级提示条（不伪装为 LLM 结果） |
| `INTERNAL_ERROR` | 500 | 未归类的服务端异常 | 任意层 | 提示系统错误 + requestId |

## 3. 「降级」与「错误」的语义区分（重要）

本项目对 **LLM 失败** 采取 **HTTP 200 + 降级** 策略（见 DELIVERY.md 架构取舍 ④）：

- LLM 超时 / 429 / 非法 JSON / 不可用 → **不返回 5xx**，而是返回 HTTP 200，
  携带规则引擎兜底结果，并在 `error.code = LLM_ERROR`、`error.degraded = true` 中标注。
- 原因：现场演示生命线。前端必须能明确区分「LLM 结果」与「规则引擎降级结果」，
  通过 `meta.degraded` / `error.degraded` 驱动降级提示条，**不得伪装成 LLM 结果**。

而真正的**参数错误**（空文本）虽然也返回 200（保持前端容错），但 `error.code = EMPTY_INPUT`、
`error.degraded = false`，语义上属于「业务拒绝」而非「降级」。

## 4. 与各层实现的对应关系

| 层 | 文件 | 责任 |
|---|---|---|
| Python | `python-service/main.py` | 产出 `EMPTY_INPUT` / `LLM_ERROR`，填充 `meta.degraded` |
| Java | `java-service/.../CareerController.java` | 超时/5xx/不可达标映射为 `UPSTREAM_*` |
| BFF | `bff/src/app.ts` | 入参校验 `VALIDATION_ERROR`，透传降级标识 |
| 前端 | `frontend/src/...` | 依据 `error.code` 渲染错误态 / 降级态 |
