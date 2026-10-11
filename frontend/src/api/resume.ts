import http from './index'

// ===== 契约共享类型（contracts/analysis-response.schema.json） =====

/** 元信息：降级标识 / 耗时 / 实际 AI 模式 */
export interface Meta {
  timings?: { bff?: number; java?: number; python?: number; llm?: number; total?: number }
  degraded?: boolean
  aiMode?: 'llm' | 'hybrid' | 'rule'
}

/** 简历结构化质量问题 */
export interface QualityIssue {
  code: string
  severity: 'high' | 'warn' | 'info'
  message: string
  location: string
  suggestion: string
}

/** 技能归一化条目 */
export interface NormalizedSkill {
  canonical: string
  raw: string
  category: string
  confidence: number
}

/** 分节识别结果 */
export interface ResumeSection {
  name: string
  title?: string
  text: string
}

/** match 命中项（附 evidence 溯源） */
export interface MatchHit {
  skill: string
  hitType: 'EXACT' | 'SYNONYM' | 'INFERRED'
  confidence?: number
  evidence: string
  source: string
}

/** match 能力缺口（含学习路径） */
export interface MatchGap {
  skill: string
  importance: 'high' | 'medium' | 'low'
  suggestion: string
  learningPath?: string[]
}

/** match 打分区块 */
export interface MatchBlock {
  score: number
  level: 'EXCELLENT' | 'GOOD_FIT' | 'PARTIAL_FIT' | 'WEAK_FIT'
  breakdown?: { mandatory: number; optional: number; levelFit: number }
  hits?: MatchHit[]
  gaps?: MatchGap[]
}

// POST /api/analyze-resume 请求体
export interface AnalyzeResumeRequest {
  resume_text: string
}

// POST /api/analyze-resume 返回体
export interface AnalyzeResumeResponse {
  success?: boolean
  keywords: string[]
  score: number
  resume?: { cleaned: { sections: ResumeSection[]; wordCount: number; language: string } }
  qualityIssues?: QualityIssue[]
  skills?: { normalized: NormalizedSkill[]; unrecognized: string[] }
  meta?: Meta
  message: string
}

/**
 * 提交简历文本进行分析
 */
export function analyzeResume(payload: AnalyzeResumeRequest) {
  return http.post<AnalyzeResumeResponse>('/analyze-resume', payload)
}
