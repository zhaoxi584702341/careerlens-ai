<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { matchJob } from '@/api/jobMatch'

const resumeText = ref('')
const jobDescription = ref('')
const loading = ref(false)
const errorMessage = ref('')

const result = reactive<{
  matchScore: number
  advantages: string[]
  improvements: string[]
  message: string
}>({
  matchScore: 0,
  advantages: [],
  improvements: [],
  message: '',
})

const hasResult = ref(false)

const canSubmit = computed(
  () =>
    !loading.value &&
    resumeText.value.trim().length > 0 &&
    jobDescription.value.trim().length > 0,
)

async function handleSubmit() {
  if (!canSubmit.value) return

  loading.value = true
  errorMessage.value = ''
  hasResult.value = false

  try {
    const { data } = await matchJob({
      resume_text: resumeText.value.trim(),
      job_description: jobDescription.value.trim(),
    })

    result.matchScore = Math.min(100, Math.max(0, data.match_score ?? 0))
    result.advantages = data.advantages ?? []
    result.improvements = data.improvements ?? []
    result.message = data.message ?? ''
    hasResult.value = true
  } catch (error) {
    errorMessage.value = '匹配失败，请稍后重试。请确认匹配服务已启动。'
    console.error('[match-job] request failed:', error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 px-4 py-12 sm:px-6">
    <header>
      <h1 class="text-3xl font-bold text-gray-900">岗位匹配建议</h1>
      <p class="mt-2 text-gray-500">粘贴你的简历与目标岗位 JD，快速获取匹配度与改进建议。</p>
    </header>

    <section class="flex flex-col gap-6">
      <div class="flex flex-col gap-4">
        <label for="resume-text" class="text-sm font-medium text-gray-700">简历内容</label>
        <textarea
          id="resume-text"
          v-model="resumeText"
          placeholder="请在此粘贴你的简历文本内容，例如教育背景、工作经历、项目经验、技能标签等……"
          class="min-h-[200px] w-full resize-y rounded-lg border border-gray-300 bg-white p-4 text-sm leading-relaxed text-gray-900 shadow-sm transition-colors placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 disabled:cursor-not-allowed disabled:bg-gray-100"
          :disabled="loading"
        ></textarea>
      </div>

      <div class="flex flex-col gap-4">
        <label for="job-description" class="text-sm font-medium text-gray-700">岗位描述（JD）</label>
        <textarea
          id="job-description"
          v-model="jobDescription"
          placeholder="请在此粘贴目标岗位的职位描述，例如岗位职责、任职要求、技能要求等……"
          class="min-h-[200px] w-full resize-y rounded-lg border border-gray-300 bg-white p-4 text-sm leading-relaxed text-gray-900 shadow-sm transition-colors placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 disabled:cursor-not-allowed disabled:bg-gray-100"
          :disabled="loading"
        ></textarea>
      </div>

      <div class="flex flex-col items-end gap-2">
        <p
          v-if="!canSubmit && !loading"
          class="text-xs text-gray-400"
        >
          请完整填写简历内容与岗位描述后再提交
        </p>
        <button
          type="button"
          class="inline-flex items-center rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="!canSubmit"
          @click="handleSubmit"
        >
          <svg
            v-if="loading"
            class="-ml-1 mr-2 h-4 w-4 animate-spin text-white"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          {{ loading ? '匹配中…' : '开始匹配' }}
        </button>
      </div>

      <p v-if="errorMessage" class="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
        {{ errorMessage }}
      </p>
    </section>

    <section v-if="hasResult" class="flex flex-col gap-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div>
        <div class="mb-2 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-gray-700">匹配度</h2>
          <span class="text-sm font-semibold text-blue-600">{{ result.matchScore }}%</span>
        </div>
        <div class="h-3 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            class="h-full rounded-full bg-blue-600 transition-all duration-500"
            :style="{ width: `${result.matchScore}%` }"
          ></div>
        </div>
      </div>

      <div>
        <h2 class="mb-3 text-sm font-semibold text-gray-700">优势</h2>
        <ul class="flex flex-col gap-2">
          <li
            v-for="item in result.advantages"
            :key="item"
            class="flex items-start gap-2 text-sm text-gray-600"
          >
            <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-green-500"></span>
            <span>{{ item }}</span>
          </li>
          <li v-if="result.advantages.length === 0" class="text-sm text-gray-400">暂无优势项</li>
        </ul>
      </div>

      <div>
        <h2 class="mb-3 text-sm font-semibold text-gray-700">待改进点</h2>
        <ul class="flex flex-col gap-2">
          <li
            v-for="item in result.improvements"
            :key="item"
            class="flex items-start gap-2 text-sm text-gray-600"
          >
            <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"></span>
            <span>{{ item }}</span>
          </li>
          <li v-if="result.improvements.length === 0" class="text-sm text-gray-400">暂无改进项</li>
        </ul>
      </div>

      <p v-if="result.message" class="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600">
        {{ result.message }}
      </p>
    </section>
  </main>
</template>

<style scoped></style>
