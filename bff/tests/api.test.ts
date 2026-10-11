/**
 * CareerLens AI BFF 服务接口测试。
 *
 * 覆盖 BFF 层四个业务接口 + 历史查询接口的正常与异常场景：
 * - POST /api/analyze-resume
 * - POST /api/match-job
 * - POST /api/optimize-resume
 * - POST /api/radar
 * - GET  /api/history
 *
 * 设计原则：
 * 1. BFF 依赖下游 Java/Python/LLM，为保证测试可独立、可离线运行，
 *    测试通过替换 callJavaHolder.callJava（下游转发）来注入确定性响应，
 *    只验证 BFF 自身的参数校验、结果规范化、错误处理与持久化写入逻辑。
 * 2. 使用独立的临时 SQLite 数据库（通过 DB_PATH 环境变量注入），
 *    避免污染开发库 bff/data/careerlens.db。
 *
 * 运行方式：
 *     cd bff
 *     npm test
 */
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import request from 'supertest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

// 在导入应用前指定独立的临时数据库，隔离测试数据
const tmpDir = mkdtempSync(join(tmpdir(), 'careerlens-bff-test-'))
process.env.DB_PATH = join(tmpDir, 'test.db')
process.env.NODE_ENV = 'test'

// 动态导入以确保 DB_PATH 在模块加载前生效
const { app, callJavaHolder } = await import('../src/app.js')

// 统一的转发 mock：默认返回空对象，各用例按需 mockResolvedValueOnce / mockRejectedValueOnce
const callJavaMock = vi.fn()
callJavaHolder.callJava = callJavaMock as unknown as typeof callJavaHolder.callJava

beforeAll(() => {
  vi.clearAllMocks()
})

beforeEach(() => {
  callJavaMock.mockReset()
})

afterAll(() => {
  // 清理临时数据库目录。
  // Windows 上 better-sqlite3 会保持文件句柄，可能短暂锁定文件，
  // 因此清理失败时忽略，交由系统回收临时目录，避免影响测试结果。
  try {
    rmSync(tmpDir, { recursive: true, force: true })
  } catch {
    // 忽略清理失败（临时目录由操作系统回收）
  }
})

describe('GET /api/history', () => {
  it('未传 limit 时返回默认结构与记录数组', async () => {
    const res = await request(app).get('/api/history')
    expect(res.status).toBe(200)
    expect(res.body).toHaveProperty('total')
    expect(res.body).toHaveProperty('limit', 20)
    expect(Array.isArray(res.body.records)).toBe(true)
  })

  it('非法 limit 回退到默认值 20', async () => {
    const res = await request(app).get('/api/history?limit=abc')
    expect(res.status).toBe(200)
    expect(res.body.limit).toBe(20)
  })

  it('显式 limit 生效', async () => {
    const res = await request(app).get('/api/history?limit=5')
    expect(res.status).toBe(200)
    expect(res.body.limit).toBe(5)
  })
})

describe('POST /api/analyze-resume', () => {
  it('缺少 resume_text 返回参数错误', async () => {
    const res = await request(app).post('/api/analyze-resume').send({})
    expect(res.status).toBe(200)
    expect(res.body.keywords).toEqual([])
    expect(res.body.score).toBe(0)
    expect(res.body.message).toContain('resume_text')
  })

  it('正常请求返回规范化结果并持久化', async () => {
    callJavaMock.mockResolvedValueOnce({ keywords: ['Java', 'MySQL'], score: 72, message: 'ok' })
    const res = await request(app)
      .post('/api/analyze-resume')
      .send({ resume_text: '5年Java开发，熟悉MySQL' })
    expect(res.status).toBe(200)
    expect(res.body.keywords).toEqual(['Java', 'MySQL'])
    expect(res.body.score).toBe(72)

    // 验证已写入历史记录
    const history = await request(app).get('/api/history?limit=1')
    expect(history.body.records[0].type).toBe('analysis')
    expect(history.body.records[0].resume_text).toContain('Java')
  })

  it('下游失败返回 500 与友好提示', async () => {
    callJavaMock.mockRejectedValueOnce(new Error('java down'))
    const res = await request(app)
      .post('/api/analyze-resume')
      .send({ resume_text: '简历文本' })
    expect(res.status).toBe(500)
    expect(res.body.message).toContain('LLM 调用失败')
  })

  it('score 越界被裁剪到 0-100', async () => {
    callJavaMock.mockResolvedValueOnce({ keywords: [], score: 999, message: '' })
    const res = await request(app)
      .post('/api/analyze-resume')
      .send({ resume_text: '简历' })
    expect(res.body.score).toBe(100)
  })
})

describe('POST /api/match-job', () => {
  it('缺少 resume_text 返回参数错误', async () => {
    const res = await request(app).post('/api/match-job').send({ job_description: '岗位' })
    expect(res.status).toBe(200)
    expect(res.body.match_score).toBe(0)
    expect(res.body.message).toContain('resume_text')
  })

  it('缺少 job_description 返回参数错误', async () => {
    const res = await request(app).post('/api/match-job').send({ resume_text: '简历' })
    expect(res.status).toBe(200)
    expect(res.body.message).toContain('job_description')
  })

  it('正常请求返回完整匹配结构', async () => {
    callJavaMock.mockResolvedValueOnce({
      match_score: 65,
      advantages: ['3年前端开发经验'],
      improvements: ['缺少React'],
      matched_skills: ['Vue'],
      missing_skills: ['React'],
      message: '匹配完成',
    })
    const res = await request(app)
      .post('/api/match-job')
      .send({ resume_text: '3年前端', job_description: '要求React' })
    expect(res.status).toBe(200)
    expect(res.body.match_score).toBe(65)
    expect(res.body.matched_skills).toEqual(['Vue'])
    expect(res.body.missing_skills).toEqual(['React'])
  })

  it('下游失败时缺失字段为空数组（结构稳定）', async () => {
    callJavaMock.mockRejectedValueOnce(new Error('java down'))
    const res = await request(app)
      .post('/api/match-job')
      .send({ resume_text: '简历', job_description: '岗位' })
    expect(res.status).toBe(500)
    expect(res.body.advantages).toEqual([])
    expect(res.body.improvements).toEqual([])
  })
})

describe('POST /api/optimize-resume', () => {
  it('缺少 resume_text 返回参数错误', async () => {
    const res = await request(app).post('/api/optimize-resume').send({ job_description: '岗位' })
    expect(res.status).toBe(200)
    expect(res.body.summary).toBe('')
    expect(res.body.message).toContain('resume_text')
  })

  it('正常请求返回评价/建议/缺失关键词', async () => {
    callJavaMock.mockResolvedValueOnce({
      summary: '技术栈错位',
      suggestions: ['补充React经验'],
      missing_keywords: ['React'],
      message: '优化建议已生成',
    })
    const res = await request(app)
      .post('/api/optimize-resume')
      .send({ resume_text: '3年前端', job_description: '要求React' })
    expect(res.status).toBe(200)
    expect(res.body.summary).toBe('技术栈错位')
    expect(res.body.suggestions).toEqual(['补充React经验'])
    expect(res.body.missing_keywords).toEqual(['React'])
  })

  it('下游失败返回 500', async () => {
    callJavaMock.mockRejectedValueOnce(new Error('java down'))
    const res = await request(app)
      .post('/api/optimize-resume')
      .send({ resume_text: '简历', job_description: '岗位' })
    expect(res.status).toBe(500)
    expect(res.body.message).toContain('LLM 调用失败')
  })
})

describe('POST /api/radar', () => {
  it('缺少 resume 返回参数错误（注意：radar 使用 resume/jd 契约）', async () => {
    const res = await request(app).post('/api/radar').send({ jd: '岗位' })
    expect(res.status).toBe(200)
    expect(res.body.dimensions).toEqual([])
    expect(res.body.message).toContain('resume')
  })

  it('缺少 jd 返回参数错误', async () => {
    const res = await request(app).post('/api/radar').send({ resume: '简历' })
    expect(res.status).toBe(200)
    expect(res.body.message).toContain('jd')
  })

  it('正常请求返回五维度并裁剪越界分数', async () => {
    callJavaMock.mockResolvedValueOnce({
      dimensions: [
        { name: '技术匹配度', score: 65 },
        { name: '项目经验', score: 150 },
        { name: '成果量化', score: -20 },
        { name: '表达能力', score: 70 },
        { name: '成长潜力', score: 75 },
      ],
      message: '雷达图数据已生成',
    })
    const res = await request(app).post('/api/radar').send({ resume: '简历', jd: '岗位' })
    expect(res.status).toBe(200)
    expect(res.body.dimensions).toHaveLength(5)
    expect(res.body.dimensions[1].score).toBe(100)
    expect(res.body.dimensions[2].score).toBe(0)
  })

  it('下游失败返回 500 且 dimensions 为空', async () => {
    callJavaMock.mockRejectedValueOnce(new Error('java down'))
    const res = await request(app).post('/api/radar').send({ resume: '简历', jd: '岗位' })
    expect(res.status).toBe(500)
    expect(res.body.dimensions).toEqual([])
  })
})
