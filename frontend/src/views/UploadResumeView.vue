<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { analyzeResume } from '@/api/resume'

const resumeText = ref('')
const loading = ref(false)
const errorMessage = ref('')

const result = reactive<{
  keywords: string[]
  score: number
  message: string
}>({
  keywords: [],
  score: 0,
  message: '',
})

const hasResult = ref(false)

const canSubmit = computed(() => !loading.value && resumeText.value.trim().length > 0)

async function handleSubmit() {
  if (!canSubmit.value) return

  loading.value = true
  errorMessage.value = ''
  hasResult.value = false

  try {
    const { data } = await analyzeResume({ resume_text: resumeText.value.trim() })

    result.keywords = data.keywords ?? []
    result.score = Math.min(100, Math.max(0, data.score ?? 0))
    result.message = data.message ?? ''
    hasResult.value = true
  } catch (error) {
    errorMessage.value = '分析失败，请稍后重试。请确认识别服务已启动。'
    console.error('[analyze-resume] request failed:', error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 px-4 py-12 sm:px-6">
    <header>
      <h1 class="text-3xl font-bold text-gray-900">简历分析</h1>
      <p class="mt-2 text-gray-500">粘贴你的简历文本，快速获取关键词与匹配评分。</p>
    </header>

    <section class="flex flex-col gap-4">
      <label for="resume-text" class="text-sm font-medium text-gray-700">
        简历内容
      </label>
      <textarea
        id="resume-text"
        v-model="resumeText"
        rows="12"
        placeholder="请在此粘贴你的简历文本内容，例如教育背景、工作经历、项目经验、技能标签等……"
        class="w-full resize-y rounded-lg border border-gray-300 bg-white p-4 text-sm leading-relaxed text-gray-900 shadow-sm transition-colors placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 disabled:cursor-not-allowed disabled:bg-gray-100"
        :disabled="loading"
      ></textarea>

      <div class="flex items-center justify-end">
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
          {{ loading ? '分析中…' : '提交分析' }}
        </button>
      </div>

      <p v-if="errorMessage" class="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
        {{ errorMessage }}
      </p>
    </section>

    <section v-if="hasResult" class="flex flex-col gap-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div>
        <h2 class="mb-3 text-sm font-semibold text-gray-700">关键词</h2>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="keyword in result.keywords"
            :key="keyword"
            class="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700"
          >
            {{ keyword }}
          </span>
          <span v-if="result.keywords.length === 0" class="text-sm text-gray-400">暂无关键词</span>
        </div>
      </div>

      <div>
        <div class="mb-2 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-gray-700">匹配评分</h2>
          <span class="text-sm font-semibold text-blue-600">{{ result.score }}%</span>
        </div>
        <div class="h-3 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            class="h-full rounded-full bg-blue-600 transition-all duration-500"
            :style="{ width: `${result.score}%` }"
          ></div>
        </div>
      </div>

      <p v-if="result.message" class="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600">
        {{ result.message }}
      </p>
    </section>
  </main>
</template>

<style scoped></style>
