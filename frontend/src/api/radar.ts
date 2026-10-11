import http from './index'

// POST /api/radar 请求体
export interface RadarRequest {
  resume: string
  jd: string
}

// 单个雷达维度
export interface RadarDimension {
  name: string
  score: number
}

// POST /api/radar 返回体
export interface RadarResponse {
  dimensions: RadarDimension[]
  message: string
}

/**
 * 提交简历与岗位描述生成能力雷达图数据
 */
export function fetchRadar(payload: RadarRequest) {
  return http.post<RadarResponse>('/radar', payload)
}
