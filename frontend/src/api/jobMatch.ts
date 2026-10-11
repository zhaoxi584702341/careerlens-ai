import http from './index'
import type { MatchBlock, MatchGap, MatchHit, Meta } from './resume'

// POST /api/match-job 请求体
export interface MatchJobRequest {
  resume_text: string
  job_description: string
}

// POST /api/match-job 返回体（BFF 透传 Python match 契约字段）
export interface MatchJobResponse {
  success?: boolean
  match_score: number
  level?: MatchBlock['level']
  breakdown?: MatchBlock['breakdown']
  hits?: MatchHit[]
  gaps?: MatchGap[]
  advantages: string[]
  improvements: string[]
  matched_skills?: string[]
  missing_skills?: string[]
  meta?: Meta
  message: string
}

/**
 * 提交简历文本与岗位描述进行匹配
 */
export function matchJob(payload: MatchJobRequest) {
  return http.post<MatchJobResponse>('/match-job', payload)
}
