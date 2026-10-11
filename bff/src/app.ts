import express, { type Request, type Response } from 'express'
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
 * 转发请求到 Java 服务（Java 内部再转发到 Python，最终调用 LLM）。
 * 统一处理超时、网络异常与非 2xx 响应，成功时返回解析后的 JSON 数据。
 * 失败时抛出错误，由各接口的 catch 统一转换为 500 友好提示。
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
      throw new Error(`Java 服务返回 ${response.status}: ${text}`)
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

  if (!resume_text || typeof resume_text !== 'string') {
    res.json({ keywords: [], score: 0, message: '请求参数错误：resume_text 不能为空' })
    return
  }

  try {
    // 1. 先将用户输入的原始简历文本写入数据库
    const resumeId = saveResume(resume_text)

    // 2. 调用 Java 服务获取分析结果（Java 内部转发到 Python）
    //    Java DTO 使用驼峰字段 resumeText
    const data = await callJava<{ keywords?: string[]; score?: number; message?: string }>(
      '/api/analyze',
      { resumeText: resume_text },
    )

    const keywords = Array.isArray(data.keywords) ? data.keywords : []
    const score = Math.min(100, Math.max(0, Number(data.score) || 0))

    const result = {
      keywords,
      score,
      message: data.message ?? `共识别到 ${keywords.length} 个关键词，综合评分 ${score} 分。`,
    }

    // 3. 将结构化结果写入数据库，关联已生成的简历 ID
    saveAnalysis(resumeId, JSON.stringify(result))

    // 4. 保持原有响应格式返回给前端
    res.json(result)
  } catch (error) {
    console.error('[analyze-resume] Java 服务调用失败:', error)
    res.status(500).json({ keywords: [], score: 0, message: LLM_ERROR_MESSAGE })
  }
})

// ===== /api/match-job：转发到 Java /api/match =====
app.post('/api/match-job', async (req: Request, res: Response) => {
  const { resume_text, job_description } = req.body ?? {}

  if (!resume_text || typeof resume_text !== 'string') {
    res.json({ match_score: 0, advantages: [], improvements: [], message: '请求参数错误：resume_text 不能为空' })
    return
  }
  if (!job_description || typeof job_description !== 'string') {
    res.json({ match_score: 0, advantages: [], improvements: [], message: '请求参数错误：job_description 不能为空' })
    return
  }

  try {
    // 1. 先将用户输入的原始简历与岗位描述写入数据库
    const resumeId = saveResume(resume_text)
    const jobId = saveJob(job_description)

    // 2. 调用 Java 服务获取匹配结果（Java 内部转发到 Python）
    //    Java DTO 使用驼峰字段 resumeText / jobDescription
    const data = await callJava<{
      match_score?: number
      advantages?: string[]
      improvements?: string[]
      matched_skills?: string[]
      missing_skills?: string[]
      message?: string
    }>('/api/match', { resumeText: resume_text, jobDescription: job_description })

    const result = {
      match_score: Math.min(100, Math.max(0, Number(data.match_score) || 0)),
      advantages: Array.isArray(data.advantages) ? data.advantages : [],
      improvements: Array.isArray(data.improvements) ? data.improvements : [],
      matched_skills: Array.isArray(data.matched_skills) ? data.matched_skills : [],
      missing_skills: Array.isArray(data.missing_skills) ? data.missing_skills : [],
      message: data.message ?? '匹配完成',
    }

    // 3. 将结构化结果写入数据库，关联已生成的简历 ID 与岗位 ID
    saveMatch(resumeId, jobId, JSON.stringify(result))

    // 4. 保持原有响应格式返回给前端
    res.json(result)
  } catch (error) {
    console.error('[match-job] Java 服务调用失败:', error)
    res.status(500).json({
      match_score: 0,
      advantages: [],
      improvements: [],
      message: LLM_ERROR_MESSAGE,
    })
  }
})

// ===== /api/optimize-resume：转发到 Java /api/optimize =====
app.post('/api/optimize-resume', async (req: Request, res: Response) => {
  const { resume_text, job_description } = req.body ?? {}

  if (!resume_text || typeof resume_text !== 'string') {
    res.json({ summary: '', suggestions: [], missing_keywords: [], message: '请求参数错误：resume_text 不能为空' })
    return
  }
  if (!job_description || typeof job_description !== 'string') {
    res.json({ summary: '', suggestions: [], missing_keywords: [], message: '请求参数错误：job_description 不能为空' })
    return
  }

  try {
    // 1. 先将用户输入的原始简历与岗位描述写入数据库
    const resumeId = saveResume(resume_text)
    const jobId = saveJob(job_description)

    // 2. 调用 Java 服务获取优化建议（Java 内部转发到 Python）
    //    Java DTO 使用驼峰字段 resumeText / jobDescription
    const data = await callJava<{
      summary?: string
      suggestions?: string[]
      missing_keywords?: string[]
      message?: string
    }>('/api/optimize', { resumeText: resume_text, jobDescription: job_description })

    const result = {
      summary: data.summary ?? '',
      suggestions: Array.isArray(data.suggestions) ? data.suggestions : [],
      missing_keywords: Array.isArray(data.missing_keywords) ? data.missing_keywords : [],
      message: data.message ?? '优化建议已生成',
    }

    // 3. 将结构化结果写入数据库，关联已生成的简历 ID 与岗位 ID
    saveOptimization(resumeId, jobId, JSON.stringify(result))

    // 4. 保持原有响应格式返回给前端
    res.json(result)
  } catch (error) {
    console.error('[optimize-resume] Java 服务调用失败:', error)
    res.status(500).json({
      summary: '',
      suggestions: [],
      missing_keywords: [],
      message: LLM_ERROR_MESSAGE,
    })
  }
})

// ===== /api/radar：转发到 Java /api/radar =====
app.post('/api/radar', async (req: Request, res: Response) => {
  const { resume, jd } = req.body ?? {}

  if (!resume || typeof resume !== 'string') {
    res.json({ dimensions: [], message: '请求参数错误：resume 不能为空' })
    return
  }
  if (!jd || typeof jd !== 'string') {
    res.json({ dimensions: [], message: '请求参数错误：jd 不能为空' })
    return
  }

  try {
    // 1. 先将用户输入的原始简历与岗位描述写入数据库
    const resumeId = saveResume(resume)
    const jobId = saveJob(jd)

    // 2. 调用 Java 服务获取雷达评估结果（Java 内部转发到 Python）
    //    Java 端 radar DTO 使用 resume / jd 字段（与 Python 一致）
    const data = await callJava<{
      dimensions?: { name?: string; score?: number }[]
      message?: string
    }>('/api/radar', { resume, jd })

    // 规范化维度数据，分数限制在 0-100 范围内
    const dimensions = (Array.isArray(data.dimensions) ? data.dimensions : []).map((item) => ({
      name: String(item?.name ?? ''),
      score: Math.min(100, Math.max(0, Number(item?.score) || 0)),
    }))

    const result = { dimensions, message: data.message ?? '雷达图数据已生成' }

    // 3. 将结构化结果写入数据库，关联已生成的简历 ID 与岗位 ID
    saveRadar(resumeId, jobId, JSON.stringify(result))

    // 4. 保持原有响应格式返回给前端
    res.json(result)
  } catch (error) {
    console.error('[radar] Java 服务调用失败:', error)
    res.status(500).json({
      dimensions: [],
      message: LLM_ERROR_MESSAGE,
    })
  }
})

// ===== GET /api/history 历史记录查询接口 =====
// 支持 limit 参数指定返回记录数量（默认 20），统一返回四类功能的历史记录
app.get('/api/history', (req: Request, res: Response) => {
  // 解析并校验 limit 参数，非法或缺失时使用默认值 20
  const rawLimit = Number(req.query.limit)
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.floor(rawLimit) : 20

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
