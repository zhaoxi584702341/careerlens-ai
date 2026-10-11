import axios from 'axios'

// 统一 API 请求实例，默认走 Vite 代理到 BFF/后端
export const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

export default http
