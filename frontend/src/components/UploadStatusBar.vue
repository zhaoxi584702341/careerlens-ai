<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useResumeStore, type ResumeSource } from '@/stores/resume'
import { KIND_LABEL } from '@/utils/resumeParser'

/**
 * 全局简历状态条。
 *
 * 挂载在顶部导航下方，四个模块页面均可见：
 * - 已上传：展示文件名 / 格式 / 字符数 / 最近更新时间；
 * - 未上传：展示引导文案 + 跳转上传页的快捷入口；
 * - 数据丢失兜底：Store 持久化数据为空 but 当前页需要简历时，提示重新上传。
 */

const store = useResumeStore()
const route = useRoute()
const router = useRouter()

/** 是否需要简历的业务页（首页除外） */
const isBusinessPage = computed(() => route.path !== '/')

/** 来源格式展示名 */
const kindLabel = computed(() =>
  store.source?.kind ? KIND_LABEL[store.source.kind] : null,
)

/** 来源描述：文件名优先，其次"手动录入" */
const sourceLabel = computed(() => {
  const src: ResumeSource | null = store.source
  if (!src) return '手动录入'
  return src.name ?? '手动录入'
})

/** 最近更新时间（本地化，精确到分钟） */
const updatedLabel = computed(() => {
  const ts = store.source?.updatedAt
  if (!ts) return ''
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
})

/** 跳到上传页（快捷上传入口） */
function goUpload() {
  if (route.path !== '/upload-resume') router.push('/upload-resume')
}
</script>

<template>
  <div class="border-b border-gray-100 bg-white/60 backdrop-blur-sm">
    <div class="mx-auto w-full max-w-7xl px-6 py-2.5 md:px-8">
      <!-- 已上传：状态标识 -->
      <div v-if="store.hasResume" class="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span class="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-success">
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6L9 17l-5-5" />
          </svg>
          简历已上传
        </span>
        <span class="flex min-w-0 items-center gap-2 text-xs text-gray-500">
          <span class="max-w-[220px] truncate font-medium text-gray-700">{{ sourceLabel }}</span>
          <span v-if="kindLabel" class="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">{{ kindLabel }}</span>
          <span class="text-gray-300">·</span>
          <span>{{ store.charCount }} 个字符</span>
          <template v-if="updatedLabel">
            <span class="text-gray-300">·</span>
            <span>更新于 {{ updatedLabel }}</span>
          </template>
        </span>
      </div>

      <!-- 未上传：引导 + 快捷上传入口（仅业务页显示，避免首页干扰） -->
      <div v-else-if="isBusinessPage" class="flex flex-wrap items-center justify-between gap-3">
        <span class="inline-flex items-center gap-2 text-xs text-gray-500">
          <svg class="h-4 w-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4" />
            <path d="M12 16h.01" />
          </svg>
          尚未上传简历，上传一次即可在所有模块复用
        </span>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          @click="goUpload"
        >
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 16V4M7 9l5-5 5 5" />
            <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
          </svg>
          去上传简历
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped></style>
