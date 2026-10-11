import http from './index'

// POST /api/match-job 请求体
export interface MatchJobRequest {
  resume_text: string
  job_description: string
}

// POST /api/match-job 返回体
export interface MatchJobResponse {
  match_score: number
  advantages: string[]
  improvements: string[]
  message: string
}

/**
 * 提交简历文本与岗位描述进行匹配
 */
export function matchJob(payload: MatchJobRequest) {
  return http.post<MatchJobResponse>('/match-job', payload)
}
