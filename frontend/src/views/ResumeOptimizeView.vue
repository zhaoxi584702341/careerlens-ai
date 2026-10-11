<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { optimizeResume } from '@/api/resumeOptimize'

const resumeText = ref('')
const jobDescription = ref('')
const loading = ref(false)
const errorMessage = ref('')

const result = reactive<{
  summary: string
  suggestions: string[]
  missingKeywords: string[]
  message: string
}>({
  summary: '',
  suggestions: [],
  missingKeywords: [],
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
    const { data } = await optimizeResume({
      resume_text: resumeText.value.trim(),
      job_description: jobDescription.value.trim(),
    })

    result.summary = data.summary ?? ''
    result.suggestions = data.suggestions ?? []
    result.missingKeywords = data.missing_keywords ?? []
    result.message = data.message ?? ''
    hasResult.value = true
  } catch (error) {
    errorMessage.value = '生成失败，请稍后重试。请确认优化服务已启动。'
    console.error('[optimize-resume] request failed:', error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 px-4 py-12 sm:px-6">
    <header>
      <h1 class="text-3xl font-bold text-gray-900">简历优化建议</h1>
      <p class="mt-2 text-gray-500">粘贴你的简历与目标岗位 JD，快速获取针对性优化建议。</p>
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
        <p v-if="!canSubmit && !loading" class="text-xs text-gray-400">
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
          {{ loading ? '生成中…' : '生成优化建议' }}
        </button>
      </div>

      <p v-if="errorMessage" class="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
        {{ errorMessage }}
      </p>
    </section>

    <section v-if="hasResult" class="flex flex-col gap-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div v-if="result.summary">
        <h2 class="mb-3 text-sm font-semibold text-gray-700">总体优化摘要</h2>
        <p class="rounded-lg bg-blue-50 px-4 py-3 text-sm leading-relaxed text-blue-800">
          {{ result.summary }}
        </p>
      </div>

      <div>
        <h2 class="mb-3 text-sm font-semibold text-gray-700">优化建议</h2>
        <ul class="flex flex-col gap-2">
          <li
            v-for="item in result.suggestions"
            :key="item"
            class="flex items-start gap-2 text-sm text-gray-600"
          >
            <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500"></span>
            <span>{{ item }}</span>
          </li>
          <li v-if="result.suggestions.length === 0" class="text-sm text-gray-400">暂无优化建议</li>
        </ul>
      </div>

      <div>
        <h2 class="mb-3 text-sm font-semibold text-gray-700">缺失关键词</h2>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="keyword in result.missingKeywords"
            :key="keyword"
            class="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700"
          >
            {{ keyword }}
          </span>
          <span v-if="result.missingKeywords.length === 0" class="text-sm text-gray-400">暂无缺失关键词</span>
        </div>
      </div>

      <p v-if="result.message" class="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600">
        {{ result.message }}
      </p>
    </section>
  </main>
</template>

<style scoped></style>
