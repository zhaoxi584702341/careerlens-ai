import http from './index'

// POST /api/analyze-resume 请求体
export interface AnalyzeResumeRequest {
  resume_text: string
}

// POST /api/analyze-resume 返回体
export interface AnalyzeResumeResponse {
  keywords: string[]
  score: number
  message: string
}

/**
 * 提交简历文本进行分析
 */
export function analyzeResume(payload: AnalyzeResumeRequest) {
  return http.post<AnalyzeResumeResponse>('/analyze-resume', payload)
}
