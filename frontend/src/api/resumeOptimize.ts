import http from './index'
import type { Meta } from './resume'

// POST /api/optimize-resume 请求体
export interface OptimizeResumeRequest {
  resume_text: string
  job_description: string
}

// POST /api/optimize-resume 返回体
export interface OptimizeResumeResponse {
  success?: boolean
  summary: string
  suggestions: string[]
  missing_keywords: string[]
  meta?: Meta
  message: string
}

/**
 * 提交简历文本与岗位描述生成优化建议
 */
export function optimizeResume(payload: OptimizeResumeRequest) {
  return http.post<OptimizeResumeResponse>('/optimize-resume', payload)
}
