import { describe, it, expect, beforeEach, vi } from 'vitest'
import http from './index'
import { analyzeResume } from './resume'
import { matchJob } from './jobMatch'
import { optimizeResume } from './resumeOptimize'
import { fetchRadar } from './radar'

describe('api/http 实例', () => {
  it('baseURL 为 /api，且超时预算为 90s（前端处于最外层需最大）', () => {
    expect(http.defaults.baseURL).toBe('/api')
    expect(http.defaults.timeout).toBe(90000)
  })
})

describe('API 层请求编排', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('analyzeResume 向 /analyze-resume POST 简历文本', async () => {
    const post = vi.spyOn(http, 'post').mockResolvedValue({ data: {} })
    await analyzeResume({ resume_text: '张三，前端工程师' })
    expect(post).toHaveBeenCalledWith('/analyze-resume', { resume_text: '张三，前端工程师' })
  })

  it('matchJob 向 /match-job POST 简历与岗位描述', async () => {
    const post = vi.spyOn(http, 'post').mockResolvedValue({ data: {} })
    await matchJob({ resume_text: 'r', job_description: 'j' })
    expect(post).toHaveBeenCalledWith('/match-job', { resume_text: 'r', job_description: 'j' })
  })

  it('optimizeResume 向 /optimize-resume POST 简历与岗位描述', async () => {
    const post = vi.spyOn(http, 'post').mockResolvedValue({ data: {} })
    await optimizeResume({ resume_text: 'r', job_description: 'j' })
    expect(post).toHaveBeenCalledWith('/optimize-resume', { resume_text: 'r', job_description: 'j' })
  })

  it('fetchRadar 向 /radar POST 简历与岗位描述', async () => {
    const post = vi.spyOn(http, 'post').mockResolvedValue({ data: {} })
    await fetchRadar({ resume: 'r', jd: 'j' })
    expect(post).toHaveBeenCalledWith('/radar', { resume: 'r', jd: 'j' })
  })
})
