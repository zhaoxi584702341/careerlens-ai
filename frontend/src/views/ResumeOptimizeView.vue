<script setup lang="ts">
import { computed, ref } from 'vue'
import { optimizeResume, type OptimizeResumeResponse } from '@/api/resumeOptimize'
import DegradedBanner from '@/components/DegradedBanner.vue'
import { useResumeStore } from '@/stores/resume'
import { useJobDescriptionStore } from '@/stores/jobDescription'

const resumeStore = useResumeStore()
const jobDescriptionStore = useJobDescriptionStore()

/** 简历正文与全局 Store 双向绑定：无需重复上传，修改即全局同步 */
const resumeText = computed({
  get: () => resumeStore.resumeText,
  set: (val: string) => resumeStore.updateText(val),
})

/** JD 与全局 Store 双向绑定：与其他模块共用同一份 JD，修改即全局同步 */
const jobDescription = computed({
  get: () => jobDescriptionStore.jdText,
  set: (val: string) => jobDescriptionStore.updateText(val),
})

const loading = ref(false)
const errorMessage = ref('')
const result = ref<OptimizeResumeResponse | null>(null)

const canSubmit = computed(
  () => !loading.value && resumeText.value.trim().length > 0 && jobDescription.value.trim().length > 0,
)

async function handleSubmit() {
  if (!canSubmit.value) return

  loading.value = true
  errorMessage.value = ''
  result.value = null

  try {
    const { data } = await optimizeResume({
      resume_text: resumeText.value.trim(),
      job_description: jobDescription.value.trim(),
    })
    result.value = data
  } catch (error) {
    errorMessage.value = '生成失败，请稍后重试。请确认优化服务已启动。'
    console.error('[optimize-resume] request failed:', error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-8">
    <!-- 页头 -->
    <header class="flex flex-col gap-2">
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-bold tracking-tight text-gray-900">简历优化</h1>
        <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">Optimize</span>
      </div>
      <p class="text-sm text-gray-500">针对目标岗位生成可执行的优化建议并补齐缺失关键词</p>
    </header>

    <!-- 输入卡 -->
    <section class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg transition-shadow duration-300 hover:shadow-xl">
      <div class="flex flex-col gap-6">
        <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div class="flex flex-col gap-3">
            <label for="resume-text" class="text-sm font-semibold text-gray-900">简历内容</label>
            <textarea
              id="resume-text"
              v-model="resumeText"
              placeholder="请在此粘贴你的简历文本内容，例如教育背景、工作经历、项目经验、技能标签等……"
              class="min-h-[200px] w-full resize-y rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-base leading-relaxed text-gray-700 transition-all placeholder:text-gray-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100"
              :disabled="loading"
            ></textarea>
          </div>

          <div class="flex flex-col gap-3">
            <label for="job-description" class="text-sm font-semibold text-gray-900">岗位描述（JD）</label>
            <textarea
              id="job-description"
              v-model="jobDescription"
              placeholder="请在此粘贴目标岗位的职位描述，例如岗位职责、任职要求、技能要求等……"
              class="min-h-[200px] w-full resize-y rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-base leading-relaxed text-gray-700 transition-all placeholder:text-gray-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100"
              :disabled="loading"
            ></textarea>
          </div>
        </div>

        <div class="flex flex-col items-end gap-4">
          <p v-if="!canSubmit && !loading" class="text-xs text-gray-400">请完整填写简历内容与岗位描述后再提交</p>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-8 py-3 text-sm font-semibold text-white shadow-lg transition-all duration-200 hover:scale-105 hover:shadow-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
            :disabled="!canSubmit"
            @click="handleSubmit"
          >
            <svg v-if="loading" class="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            {{ loading ? '生成中…' : '生成优化建议' }}
          </button>
        </div>

        <p v-if="errorMessage" class="rounded-xl bg-red-50 px-4 py-3 text-sm text-danger">{{ errorMessage }}</p>
      </div>
    </section>

    <!-- 结果区 -->
    <template v-if="result">
      <DegradedBanner
        v-if="result.meta?.degraded"
        :ai-mode="result.meta?.aiMode"
        :timings="result.meta?.timings"
      />

      <section v-if="result.summary" class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
        <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">总体优化摘要</h2>
        <p class="rounded-xl bg-blue-50 p-6 text-base leading-relaxed text-gray-700">
          {{ result.summary }}
        </p>
      </section>

      <!-- 优化建议时间线 -->
      <section class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
        <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">优化建议</h2>
        <ol class="relative flex flex-col gap-6 border-l-2 border-gray-100 pl-8">
          <li
            v-for="(item, index) in result.suggestions"
            :key="index"
            class="relative flex items-start gap-3 text-base leading-relaxed text-gray-700"
          >
            <span class="absolute -left-[41px] top-0 flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-purple-600 text-xs font-semibold text-white">
              {{ index + 1 }}
            </span>
            <span class="pt-0.5">{{ item }}</span>
          </li>
          <li v-if="result.suggestions.length === 0" class="text-sm text-gray-400">暂无优化建议</li>
        </ol>
      </section>

      <section class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
        <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">缺失关键词</h2>
        <div class="flex flex-wrap gap-4">
          <span
            v-for="keyword in result.missing_keywords"
            :key="keyword"
            class="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-warning"
          >
            {{ keyword }}
          </span>
          <span v-if="result.missing_keywords.length === 0" class="text-sm text-gray-400">暂无缺失关键词</span>
        </div>
      </section>

      <p v-if="result.message" class="rounded-xl border border-gray-100 bg-white px-4 py-3 text-base leading-relaxed text-gray-600 shadow-lg">
        {{ result.message }}
      </p>
    </template>
  </div>
</template>

<style scoped></style>
