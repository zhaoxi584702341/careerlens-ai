import express, { type Request, type Response } from 'express'
import axios from 'axios'

const app = express()
const port = 3000

const PYTHON_SERVICE_URL = 'http://localhost:8000/api/analyze-resume'
const REQUEST_TIMEOUT = 10_000

app.use(express.json())

// 统一的错误返回结构
function errorResult(message: string) {
  return { keywords: [], score: 0, message }
}

app.post('/api/analyze-resume', async (req: Request, res: Response) => {
  const { resume_text } = req.body ?? {}

  if (!resume_text || typeof resume_text !== 'string') {
    res.json(errorResult('请求参数错误：resume_text 不能为空'))
    return
  }

  try {
    const response = await axios.post(
      PYTHON_SERVICE_URL,
      { resume_text },
      { timeout: REQUEST_TIMEOUT, validateStatus: () => true },
    )

    if (response.status !== 200) {
      res.json(errorResult(`Python 服务返回异常状态码：${response.status}`))
      return
    }

    res.json(response.data)
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNABORTED') {
        res.json(errorResult('请求 Python 服务超时（超过 10 秒）'))
        return
      }
      if (error.code === 'ECONNREFUSED') {
        res.json(errorResult('Python 服务不可用，请确认 http://localhost:8000 已启动'))
        return
      }
      res.json(errorResult(`调用 Python 服务失败：${error.message}`))
      return
    }
    res.json(errorResult('BFF 服务内部错误'))
  }
})

app.post('/api/match-job', (req: Request, res: Response) => {
  const { resume_text, job_description } = req.body ?? {}

  if (!resume_text || typeof resume_text !== 'string') {
    res.json({ match_score: 0, advantages: [], improvements: [], message: '请求参数错误：resume_text 不能为空' })
    return
  }
  if (!job_description || typeof job_description !== 'string') {
    res.json({ match_score: 0, advantages: [], improvements: [], message: '请求参数错误：job_description 不能为空' })
    return
  }

  // ===== 当前返回固定模拟数据 =====
  // TODO: 后续接入真实 LLM 服务（如 Python 服务 /api/match-job 或大模型 API）时，
  //       将下方 mock 数据替换为对真实服务的调用，例如：
  //       const response = await axios.post(LLM_SERVICE_URL, { resume_text, job_description },
  //         { timeout: REQUEST_TIMEOUT, validateStatus: () => true })
  //       并沿用与 /api/analyze-resume 一致的超时 / 连接失败 / 非 200 错误处理逻辑。
  const mockResult = {
    match_score: 78,
    advantages: ['有相关技术栈经验', '项目经历较完整', '具备后端开发能力'],
    improvements: ['缺少云原生相关经验', '项目描述可以更量化', '建议补充系统设计能力'],
    message: '匹配完成',
  }

  res.json(mockResult)
})

app.post('/api/optimize-resume', (req: Request, res: Response) => {
  const { resume_text, job_description } = req.body ?? {}

  if (!resume_text || typeof resume_text !== 'string') {
    res.json({ summary: '', suggestions: [], missing_keywords: [], message: '请求参数错误：resume_text 不能为空' })
    return
  }
  if (!job_description || typeof job_description !== 'string') {
    res.json({ summary: '', suggestions: [], missing_keywords: [], message: '请求参数错误：job_description 不能为空' })
    return
  }

  // ===== 当前返回固定模拟数据 =====
  // TODO: 后续接入真实 LLM 服务（如 Python 服务 /api/optimize-resume 或大模型 API）时，
  //       将下方 mock 数据替换为对真实服务的调用，例如：
  //       const response = await axios.post(LLM_SERVICE_URL, { resume_text, job_description },
  //         { timeout: REQUEST_TIMEOUT, validateStatus: () => true })
  //       并沿用与 /api/analyze-resume 一致的超时 / 连接失败 / 非 200 错误处理逻辑。
  const mockResult = {
    summary: '整体匹配度一般，建议补充量化成果和关键技术关键词。',
    suggestions: [
      '将‘负责后端开发’改为‘独立负责订单服务后端开发，支撑日均 10 万请求’',
      '补充项目中的技术栈关键词，例如 MySQL、Redis、消息队列',
      '增加可量化结果，如性能提升、成本降低、转化率提升',
      '优化项目描述结构，建议采用 背景-行动-结果 的表达方式',
    ],
    missing_keywords: ['Redis', '消息队列', '单元测试', 'CI/CD'],
    message: '优化建议已生成',
  }

  res.json(mockResult)
})

app.post('/api/radar', (req: Request, res: Response) => {
  const { resume, jd } = req.body ?? {}

  if (!resume || typeof resume !== 'string') {
    res.json({ dimensions: [], message: '请求参数错误：resume 不能为空' })
    return
  }
  if (!jd || typeof jd !== 'string') {
    res.json({ dimensions: [], message: '请求参数错误：jd 不能为空' })
    return
  }

  // ===== 当前返回固定模拟数据 =====
  // TODO: 后续接入真实 LLM 服务（如 Python 服务 /api/radar 或大模型 API）时，
  //       将下方 mock 数据替换为对真实服务的调用，例如：
  //       const response = await axios.post(LLM_SERVICE_URL, { resume, jd },
  //         { timeout: REQUEST_TIMEOUT, validateStatus: () => true })
  //       并沿用与 /api/analyze-resume 一致的超时 / 连接失败 / 非 200 错误处理逻辑。
  const mockResult = {
    dimensions: [
      { name: '技术匹配度', score: 78 },
      { name: '项目经验', score: 65 },
      { name: '成果量化', score: 50 },
      { name: '表达能力', score: 72 },
      { name: '成长潜力', score: 80 },
    ],
    message: '雷达图数据已生成',
  }

  res.json(mockResult)
})

app.listen(port, () => {
  console.log(`BFF listening on http://localhost:${port}`)
})
