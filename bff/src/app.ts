import express, { type Request, type Response } from 'express'
import { randomUUID } from 'node:crypto'
// ===== 引入 dotenv（仅用于配置 Java 服务地址等少量环境变量，BFF 不再直接调 LLM） =====
import 'dotenv/config'
// ===== 引入 SQLite 持久化方法 =====
import {
  saveResume,
  saveJob,
  saveAnalysis,
  saveMatch,
  saveOptimization,
  saveRadar,
  getRecentRecords,
} from './db.js'

export const app = express()

// ===== Java 服务地址与转发超时配置 =====
// 注意：链路为 Vue → BFF → Java → Python → LLM，BFF 现在调用的是 Java 服务
// 容器内通过服务名 java-service 通信；本地开发回退到 localhost:8080
const JAVA_SERVICE_URL = process.env.JAVA_SERVICE_URL || 'http://localhost:8080'
// LLM 链路较长，超时时间放宽到 120s
const JAVA_TIMEOUT = Number(process.env.JAVA_TIMEOUT) || 120_000

app.use(express.json())

// 统一的 BFF 端调用失败提示（Java → Python → LLM 任一环节失败均归入此提示）
const LLM_ERROR_MESSAGE = 'LLM 调用失败，请检查 Java / Python 服务配置与 .env 中的 API Key、Base URL 与模型名称后重试'

/**
 * 契约 meta 组装：BFF 在网关层补齐自身耗时，并把下游（Python/Java）已产出的
 * timings / degraded / aiMode 向上透传，保证前端拿到的 meta 是链路完整视图。
 * 若下游未返回 meta（老版本/异常），则按降级处理，aiMode 回退为 rule。
 */
function withBffMeta<T extends Record<string, unknown>>(data: T, bffMs: number, degradedFallback: boolean): T & {
  success: boolean
  meta: Record<string, unknown>
} {
  const upstreamMeta = (data.meta as Record<string, unknown> | undefined) ?? {}
  const upstreamTimings = (upstreamMeta.timings as Record<string, number> | undefined) ?? {}
  const aiMode = (upstreamMeta.aiMode as string | undefined) ?? (degradedFallback ? 'rule' : 'hybrid')
  const degraded = (upstreamMeta.degraded as boolean | undefined) ?? degradedFallback
  const total = Number(upstreamTimings.total ?? 0) + bffMs
  return {
    ...data,
    success: (data.success as boolean | undefined) ?? !degraded,
    meta: {
      timings: { ...upstreamTimings, bff: bffMs, total },
      degraded,
      aiMode,
    },
  }
}

/**
 * 参数校验失败：返回契约统一错误信封（见 contracts/error-envelope.schema.json）。
 * 契约要求 requestId + success:false + error{code,message,degraded}，HTTP 400，
 * 与 Java 层 GlobalExceptionHandler 的 VALIDATION_ERROR 语义保持一致。
 */
function sendValidationError(req: Request, res: Response, message: string): void {
  const requestId = req.header('X-Request-Id') ?? randomUUID()
  res.setHeader('X-Request-Id', requestId)
  res.status(400).json({
    requestId,
    success: false,
    error: { code: 'VALIDATION_ERROR', message, degraded: false },
  })
}

/**
 * 校验必填文本字段：缺失或非字符串时返回 400 错误信封并结束响应。
 * 返回 true 表示校验通过。四接口共用，避免校验逻辑重复。
 */
function requireText(req: Request, res: Response, value: unknown, fieldName: string): value is string {
  if (!value || typeof value !== 'string') {
    sendValidationError(req, res, `请求参数错误：${fieldName} 不能为空`)
    return false
  }
  return true
}

/** 契约错误信封（见 contracts/error-envelope.schema.json） */
type ErrorEnvelope = {
  requestId?: string
  success?: boolean
  error?: { code?: string; message?: string; degraded?: boolean }
}

/**
 * 下游调用错误：携带 Java 返回的 HTTP 状态与错误信封，便于网关层原样透传。
 * 与普通 Error 区分，用于判定「下游已给出结构化错误」还是「连接失败/超时」。
 */
export class UpstreamError extends Error {
  readonly status: number
  readonly envelope: ErrorEnvelope | null

  constructor(status: number, envelope: ErrorEnvelope | null) {
    super(`下游服务返回 HTTP ${status}`)
    this.name = 'UpstreamError'
    this.status = status
    this.envelope = envelope
  }
}

/** 尝试把下游响应体解析为错误信封；结构不符时返回 null。 */
function parseErrorEnvelope(text: string): ErrorEnvelope | null {
  try {
    const parsed = JSON.parse(text) as ErrorEnvelope
    return parsed && typeof parsed === 'object' && parsed.error ? parsed : null
  } catch {
    return null
  }
}

/**
 * 下游失败：按 contracts/error-codes.md 返回统一错误信封（HTTP 400/502/503/504）。
 * - Java 已返回错误信封 → 透传其状态与 error.code（UPSTREAM_ERROR / UPSTREAM_TIMEOUT / SERVICE_UNAVAILABLE）
 * - 超时（AbortError）→ 504 UPSTREAM_TIMEOUT
 * - 连接失败等未归类异常 → 503 SERVICE_UNAVAILABLE
 */
function sendUpstreamError(req: Request, res: Response, error: unknown): void {
  const requestId = req.header('X-Request-Id') ?? randomUUID()
  res.setHeader('X-Request-Id', requestId)

  if (error instanceof UpstreamError && error.envelope?.error) {
    res.status(error.status).json({
      requestId,
      success: false,
      error: {
        code: error.envelope.error.code ?? 'UPSTREAM_ERROR',
        message: error.envelope.error.message ?? '下游服务调用失败',
        degraded: error.envelope.error.degraded ?? false,
      },
    })
    return
  }

  const timedOut = error instanceof Error && error.name === 'AbortError'
  res.status(timedOut ? 504 : 503).json({
    requestId,
    success: false,
    error: {
      code: timedOut ? 'UPSTREAM_TIMEOUT' : 'SERVICE_UNAVAILABLE',
      message: timedOut ? '下游服务响应超时，请稍后重试' : LLM_ERROR_MESSAGE,
      degraded: false,
    },
  })
}

/**
 * 转发请求到 Java 服务（Java 内部再转发到 Python，最终调用 LLM）。
 * 统一处理超时、网络异常与非 2xx 响应，成功时返回解析后的 JSON 数据。
 * 失败时抛出 UpstreamError（非 2xx）或原始异常（连接失败/超时），
 * 由各接口的 catch 经 sendUpstreamError 统一转换为契约错误信封。
 *
 * 说明：本函数通过对象属性导出（callJavaImpl），便于测试中以 vi.spyOn 替换，
 * 从而在不依赖真实下游服务的情况下验证 BFF 自身逻辑。
 */
export async function callJavaImpl<T>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), JAVA_TIMEOUT)

  try {
    const response = await fetch(`${JAVA_SERVICE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })

    const text = await response.text()
    if (!response.ok) {
      throw new UpstreamError(response.status, parseErrorEnvelope(text))
    }
    return text ? (JSON.parse(text) as T) : ({} as T)
  } finally {
    clearTimeout(timer)
  }
}

/**
 * 可被测试替换的转发函数容器。
 * 生产代码统一通过 callJavaHolder.callJava 调用；测试中替换 callJavaHolder.callJava 即可。
 */
export const callJavaHolder = {
  callJava: callJavaImpl as <T>(path: string, body: unknown) => Promise<T>,
}

// 便捷引用（保持下方接口代码简洁）
const callJava = <T>(path: string, body: unknown): Promise<T> => callJavaHolder.callJava<T>(path, body)

// ===== /api/analyze-resume：转发到 Java /api/analyze（Java → Python /api/analyze） =====
app.post('/api/analyze-resume', async (req: Request, res: Response) => {
  const { resume_text } = req.body ?? {}

  if (!requireText(req, res, resume_text, 'resume_text')) return

  try {
    // 1. 调用 Java 服务获取分析结果（Java 内部转发到 Python）
    //    Java DTO 使用驼峰字段 resumeText
    const javaStarted = Date.now()
    const data = await callJava<{
      success?: boolean
      keywords?: string[]
      score?: number
      cleaned_text?: string
      resume?: unknown
      qualityIssues?: unknown[]
      skills?: unknown
      meta?: unknown
      message?: string
    }>('/api/analyze', { resumeText: resume_text })
    const bffMs = Date.now() - javaStarted

    const keywords = Array.isArray(data.keywords) ? data.keywords : []
    const score = Math.min(100, Math.max(0, Number(data.score) || 0))

    // 3. 透传 Python 契约字段（结构化解析 / 质量问题 / 归一化技能），并补齐 BFF 层 meta
    const result = withBffMeta(
      {
        success: data.success,
        keywords,
        score,
        cleaned_text: data.cleaned_text ?? resume_text,
        resume: data.resume,
        qualityIssues: Array.isArray(data.qualityIssues) ? data.qualityIssues : [],
        skills: data.skills ?? { normalized: [], unrecognized: [] },
        meta: data.meta,
        message: data.message ?? `共识别到 ${keywords.length} 个关键词，综合评分 ${score} 分。`,
      },
      bffMs,
      false,
    )

    // 4. 调用成功后再落库，避免下游失败时留下孤儿简历记录
    const resumeId = saveResume(resume_text)
    saveAnalysis(resumeId, JSON.stringify(result))

    // 5. 返回给前端
    res.json(result)
  } catch (error) {
    console.error('[analyze-resume] Java 服务调用失败:', error)
    sendUpstreamError(req, res, error)
  }
})

// ===== /api/match-job：转发到 Java /api/match =====
app.post('/api/match-job', async (req: Request, res: Response) => {
  const { resume_text, job_description } = req.body ?? {}

  if (!requireText(req, res, resume_text, 'resume_text')) return
  if (!requireText(req, res, job_description, 'job_description')) return

  try {
    // 1. 调用 Java 服务获取匹配结果（Java 内部转发到 Python）
    //    Java DTO 使用驼峰字段 resumeText / jobDescription
    const javaStarted = Date.now()
    const data = await callJava<{
      success?: boolean
      match_score?: number
      level?: string
      breakdown?: unknown
      hits?: unknown[]
      gaps?: unknown[]
      advantages?: string[]
      improvements?: string[]
      matched_skills?: string[]
      missing_skills?: string[]
      meta?: unknown
      message?: string
    }>('/api/match', { resumeText: resume_text, jobDescription: job_description })
    const bffMs = Date.now() - javaStarted

    // 3. 透传 Python 契约字段（匹配等级 / 维度分解 / 命中 / 缺口），并补齐 BFF 层 meta
    const result = withBffMeta(
      {
        success: data.success,
        match_score: Math.min(100, Math.max(0, Number(data.match_score) || 0)),
        level: data.level ?? '',
        breakdown: data.breakdown,
        hits: Array.isArray(data.hits) ? data.hits : [],
        gaps: Array.isArray(data.gaps) ? data.gaps : [],
        advantages: Array.isArray(data.advantages) ? data.advantages : [],
        improvements: Array.isArray(data.improvements) ? data.improvements : [],
        matched_skills: Array.isArray(data.matched_skills) ? data.matched_skills : [],
        missing_skills: Array.isArray(data.missing_skills) ? data.missing_skills : [],
        meta: data.meta,
        message: data.message ?? '匹配完成',
      },
      bffMs,
      false,
    )

    // 4. 调用成功后再落库，避免下游失败时留下孤儿记录
    const resumeId = saveResume(resume_text)
    const jobId = saveJob(job_description)
    saveMatch(resumeId, jobId, JSON.stringify(result))

    // 5. 返回给前端
    res.json(result)
  } catch (error) {
    console.error('[match-job] Java 服务调用失败:', error)
    sendUpstreamError(req, res, error)
  }
})

// ===== /api/optimize-resume：转发到 Java /api/optimize =====
app.post('/api/optimize-resume', async (req: Request, res: Response) => {
  const { resume_text, job_description } = req.body ?? {}

  if (!requireText(req, res, resume_text, 'resume_text')) return
  if (!requireText(req, res, job_description, 'job_description')) return

  try {
    // 1. 调用 Java 服务获取优化建议（Java 内部转发到 Python）
    //    Java DTO 使用驼峰字段 resumeText / jobDescription
    const javaStarted = Date.now()
    const data = await callJava<{
      success?: boolean
      summary?: string
      suggestions?: string[]
      missing_keywords?: string[]
      meta?: unknown
      message?: string
    }>('/api/optimize', { resumeText: resume_text, jobDescription: job_description })
    const bffMs = Date.now() - javaStarted

    // 3. 透传 Python 契约字段（summary / 建议 / 缺失关键词），并补齐 BFF 层 meta
    const result = withBffMeta(
      {
        success: data.success,
        summary: data.summary ?? '',
        suggestions: Array.isArray(data.suggestions) ? data.suggestions : [],
        missing_keywords: Array.isArray(data.missing_keywords) ? data.missing_keywords : [],
        meta: data.meta,
        message: data.message ?? '优化建议已生成',
      },
      bffMs,
      false,
    )

    // 4. 调用成功后再落库，避免下游失败时留下孤儿记录
    const resumeId = saveResume(resume_text)
    const jobId = saveJob(job_description)
    saveOptimization(resumeId, jobId, JSON.stringify(result))

    // 5. 返回给前端
    res.json(result)
  } catch (error) {
    console.error('[optimize-resume] Java 服务调用失败:', error)
    sendUpstreamError(req, res, error)
  }
})

// ===== /api/radar：转发到 Java /api/radar =====
app.post('/api/radar', async (req: Request, res: Response) => {
  const { resume, jd } = req.body ?? {}

  if (!requireText(req, res, resume, 'resume')) return
  if (!requireText(req, res, jd, 'jd')) return

  try {
    // 1. 调用 Java 服务获取雷达评估结果（Java 内部转发到 Python）
    //    Java 端 radar DTO 使用 resume / jd 字段（与 Python 一致）
    const javaStarted = Date.now()
    const data = await callJava<{
      success?: boolean
      dimensions?: { name?: string; score?: number }[]
      meta?: unknown
      message?: string
    }>('/api/radar', { resume, jd })
    const bffMs = Date.now() - javaStarted

    // 规范化维度数据，分数限制在 0-100 范围内
    const dimensions = (Array.isArray(data.dimensions) ? data.dimensions : []).map((item) => ({
      name: String(item?.name ?? ''),
      score: Math.min(100, Math.max(0, Number(item?.score) || 0)),
    }))

    // 3. 透传 Python 契约字段（维度 / meta），并补齐 BFF 层 meta
    const result = withBffMeta(
      {
        success: data.success,
        dimensions,
        meta: data.meta,
        message: data.message ?? '雷达图数据已生成',
      },
      bffMs,
      false,
    )

    // 4. 调用成功后再落库，避免下游失败时留下孤儿记录
    const resumeId = saveResume(resume)
    const jobId = saveJob(jd)
    saveRadar(resumeId, jobId, JSON.stringify(result))

    // 5. 返回给前端
    res.json(result)
  } catch (error) {
    console.error('[radar] Java 服务调用失败:', error)
    sendUpstreamError(req, res, error)
  }
})

// ===== GET /api/history 历史记录查询接口 =====
// 支持 limit 参数指定返回记录数量（默认 20），统一返回四类功能的历史记录
app.get('/api/history', (req: Request, res: Response) => {
  // 解析并校验 limit 参数，非法或缺失时使用默认值 20
  const rawLimit = Number(req.query.limit)
  // 上限 100，避免超大 limit 造成不必要的查询压力
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(100, Math.floor(rawLimit)) : 20

  try {
    const records = getRecentRecords(limit)
    res.json({
      total: records.length,
      limit,
      records,
    })
  } catch (error) {
    // 完整的异常捕获：查询失败时返回 500 与友好提示
    console.error('[history] 查询历史记录失败:', error)
    res.status(500).json({ total: 0, limit, records: [], message: '历史记录查询失败，请稍后重试' })
  }
})

export { JAVA_SERVICE_URL }
