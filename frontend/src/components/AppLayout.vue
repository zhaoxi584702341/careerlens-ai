<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import UploadStatusBar from './UploadStatusBar.vue'
import { useResumeStore } from '@/stores/resume'
import { useJobDescriptionStore } from '@/stores/jobDescription'

interface NavItem {
  label: string
  to: string
  icon: string[]
}

/** 顶部导航项：与 5 个业务页面一一对应，仅承载视觉与跳转 */
const navItems: NavItem[] = [
  {
    label: '首页',
    to: '/',
    icon: ['M3 12l9-9 9 9', 'M5 10v10h14V10'],
  },
  {
    label: '简历上传',
    to: '/upload-resume',
    icon: ['M14 3v4a1 1 0 0 0 1 1h4', 'M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z', 'M9 13h6', 'M9 17h6'],
  },
  {
    label: '岗位匹配',
    to: '/job-match',
    icon: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z', 'M9 12l2 2 4-4'],
  },
  {
    label: '简历优化',
    to: '/resume-optimize',
    icon: ['M12 20h9', 'M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z'],
  },
  {
    label: '能力雷达',
    to: '/radar',
    icon: ['M12 2v20', 'M2 12h20', 'M12 2l7 10-7 10-7-10z'],
  },
]

const route = useRoute()
const router = useRouter()

// 跨标签页同步简历与 JD 数据：全局仅需注册一次，放在顶层布局中
const resumeStore = useResumeStore()
const jobDescriptionStore = useJobDescriptionStore()
let disposeResumeSync: (() => void) | null = null
let disposeJdSync: (() => void) | null = null

onMounted(() => {
  disposeResumeSync = resumeStore.initSync()
  disposeJdSync = jobDescriptionStore.initSync()
})

onBeforeUnmount(() => {
  disposeResumeSync?.()
  disposeJdSync?.()
})

function go(to: string) {
  if (route.path !== to) router.push(to)
}
</script>

<template>
  <div class="flex min-h-full flex-col bg-canvas">
    <!-- 顶部毛玻璃导航栏 -->
    <header
      class="sticky top-0 z-30 w-full border-b border-gray-200 bg-white/80 backdrop-blur-md"
    >
      <div class="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-6 md:px-8">
        <!-- Logo -->
        <button
          type="button"
          class="flex items-center gap-2.5 text-left transition-transform duration-200 hover:scale-[1.02] focus:outline-none"
          @click="go('/')"
        >
          <span
            class="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 text-base font-bold text-white shadow-md"
          >
            C
          </span>
          <span class="text-lg font-bold tracking-tight text-gray-900">CareerLens</span>
        </button>

        <!-- 路由导航链接 -->
        <nav class="hidden items-center gap-1 md:flex">
          <button
            v-for="item in navItems"
            :key="item.to"
            type="button"
            class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            :class="
              route.path === item.to
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
            "
            @click="go(item.to)"
          >
            <svg
              class="h-[18px] w-[18px] shrink-0"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path v-for="(d, i) in item.icon" :key="i" :d="d" />
            </svg>
            <span>{{ item.label }}</span>
          </button>
        </nav>

        <!-- 用户头像区域 -->
        <div class="flex items-center gap-4">
          <button
            type="button"
            class="hidden h-9 w-9 items-center justify-center rounded-xl text-gray-500 transition-colors duration-200 hover:bg-gray-100 hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 sm:flex"
            aria-label="通知"
          >
            <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
          </button>
          <div class="flex items-center gap-2.5">
            <span
              class="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-purple-600 text-sm font-semibold text-white"
            >
              张
            </span>
            <div class="hidden flex-col leading-tight sm:flex">
              <span class="text-sm font-medium text-gray-900">张同学</span>
              <span class="text-xs text-gray-400">求职中</span>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- 全局简历状态条：所有模块共用同一份简历数据的状态标识 -->
    <UploadStatusBar />

    <!-- 内容区 -->
    <main class="mx-auto flex w-full max-w-7xl flex-1 flex-col px-6 py-8 md:px-8 md:py-12">
      <slot />
    </main>
  </div>
</template>

<style scoped></style>
