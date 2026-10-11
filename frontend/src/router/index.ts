import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/upload-resume',
    name: 'upload-resume',
    component: () => import('@/views/UploadResumeView.vue'),
    meta: { title: '上传简历' },
  },
  {
    path: '/job-match',
    name: 'job-match',
    component: () => import('@/views/JobMatchView.vue'),
    meta: { title: '岗位匹配' },
  },
  {
    path: '/resume-optimize',
    name: 'resume-optimize',
    component: () => import('@/views/ResumeOptimizeView.vue'),
    meta: { title: '简历优化' },
  },
  {
    path: '/radar',
    name: 'radar',
    component: () => import('@/views/RadarView.vue'),
    meta: { title: '能力雷达图' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
