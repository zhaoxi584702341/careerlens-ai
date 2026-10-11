import axios from 'axios'

// 统一 API 请求实例，默认走 Vite 代理到 BFF/后端
// 超时预算逐层递减：前端 90s > BFF 75s > Java 60s > Python→LLM 45s。
// 前端处于最外层，超时必须最大，避免下层仍在处理时前端先超时。
export const http = axios.create({
  baseURL: '/api',
  timeout: 90000,
})

export default http
