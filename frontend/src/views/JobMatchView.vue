<script setup lang="ts">
import { computed, ref } from 'vue'
import { matchJob, type MatchJobResponse } from '@/api/jobMatch'
import ScoreGauge from '@/components/ScoreGauge.vue'
import BreakdownBars from '@/components/BreakdownBars.vue'
import SeverityBadge from '@/components/SeverityBadge.vue'
import DegradedBanner from '@/components/DegradedBanner.vue'
import { useResumeStore } from '@/stores/resume'

const HIT_TYPE_LABEL: Record<string, string> = {
  EXACT: '精确命中',
  SYNONYM: '同义命中',
  INFERRED: '语义推断',
}

const resumeStore = useResumeStore()

/** 简历正文与全局 Store 双向绑定：无需重复上传，修改即全局同步 */
const resumeText = computed({
  get: () => resumeStore.resumeText,
  set: (val: string) => resumeStore.updateText(val),
})

const jobDescription = ref('')
const loading = ref(false)
const errorMessage = ref('')
const result = ref<MatchJobResponse | null>(null)

const canSubmit = computed(
  () => !loading.value && resumeText.value.trim().length > 0 && jobDescription.value.trim().length > 0,
)

const hits = computed(() => result.value?.hits ?? [])
const gaps = computed(() => result.value?.gaps ?? [])

async function handleSubmit() {
  if (!canSubmit.value) return

  loading.value = true
  errorMessage.value = ''
  result.value = null

  try {
    const { data } = await matchJob({
      resume_text: resumeText.value.trim(),
      job_description: jobDescription.value.trim(),
    })
    result.value = data
  } catch (error) {
    errorMessage.value = '匹配失败，请稍后重试。请确认匹配服务已启动。'
    console.error('[match-job] request failed:', error)
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
        <h1 class="text-2xl font-bold tracking-tight text-gray-900">岗位匹配</h1>
        <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">Match</span>
      </div>
      <p class="text-sm text-gray-500">对比简历与 JD，输出可解释的匹配度与改进方向</p>
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
            {{ loading ? '匹配中…' : '开始匹配' }}
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

      <!-- 匹配度 + 进度条 -->
      <section class="flex flex-col items-center gap-8 rounded-2xl border border-gray-100 bg-white p-8 shadow-lg sm:flex-row">
        <ScoreGauge :score="result.match_score" :level="result.level" label="岗位匹配度" />
        <div class="flex-1 sm:pl-8">
          <BreakdownBars :breakdown="result.breakdown" />
        </div>
      </section>

      <!-- 岗位/技能卡片网格 -->
      <section v-if="hits.length" class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
        <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">命中项 · 证据溯源（{{ hits.length }}）</h2>
        <div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          <article
            v-for="hit in hits"
            :key="hit.skill"
            class="flex flex-col gap-3 rounded-xl border border-blue-100 bg-blue-50/50 p-6 transition-shadow duration-200 hover:shadow-md"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-base font-semibold text-gray-900">{{ hit.skill }}</span>
              <span class="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-success">
                {{ HIT_TYPE_LABEL[hit.hitType] ?? hit.hitType }}
              </span>
            </div>
            <p class="text-sm italic leading-relaxed text-gray-600">“{{ hit.evidence }}”</p>
            <p class="text-xs text-gray-400">来源：{{ hit.source }}</p>
          </article>
        </div>
      </section>

      <!-- 能力缺口 · 学习路线时间线 -->
      <section v-if="gaps.length" class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
        <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">能力缺口 · 学习路径（{{ gaps.length }}）</h2>
        <ol class="relative flex flex-col gap-8 border-l-2 border-gray-100 pl-8">
          <li
            v-for="gap in gaps"
            :key="gap.skill"
            class="relative flex flex-col gap-3"
          >
            <span class="absolute -left-[41px] top-1 h-4 w-4 rounded-full border-2 border-white bg-gradient-to-br from-blue-600 to-purple-600"></span>
            <div class="flex items-center gap-3">
              <SeverityBadge :level="gap.importance === 'high' ? 'high' : gap.importance === 'medium' ? 'medium' : 'low'" />
              <span class="text-base font-semibold text-gray-900">{{ gap.skill }}</span>
            </div>
            <p class="text-sm leading-relaxed text-gray-600">{{ gap.suggestion }}</p>
            <div v-if="gap.learningPath?.length" class="flex flex-col gap-2 rounded-xl bg-gray-50 p-4">
              <span class="text-xs font-medium text-gray-400">学习路线</span>
              <ol class="flex flex-col gap-2 text-sm text-gray-600">
                <li
                  v-for="(step, index) in gap.learningPath"
                  :key="index"
                  class="flex items-start gap-3"
                >
                  <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700">
                    {{ index + 1 }}
                  </span>
                  <span class="pt-0.5 leading-relaxed">{{ step }}</span>
                </li>
              </ol>
            </div>
          </li>
        </ol>
      </section>

      <!-- 优势 / 待改进 -->
      <section class="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
          <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">优势</h2>
          <ul class="flex flex-col gap-4">
            <li v-for="item in result.advantages" :key="item" class="flex items-start gap-3 text-base leading-relaxed text-gray-700">
              <span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-success"></span>
              <span>{{ item }}</span>
            </li>
            <li v-if="result.advantages.length === 0" class="text-sm text-gray-400">暂无优势项</li>
          </ul>
        </div>

        <div class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
          <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">待改进点</h2>
          <ul class="flex flex-col gap-4">
            <li v-for="item in result.improvements" :key="item" class="flex items-start gap-3 text-base leading-relaxed text-gray-700">
              <span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-warning"></span>
              <span>{{ item }}</span>
            </li>
            <li v-if="result.improvements.length === 0" class="text-sm text-gray-400">暂无改进项</li>
          </ul>
        </div>
      </section>

      <p v-if="result.message" class="rounded-xl border border-gray-100 bg-white px-4 py-3 text-base leading-relaxed text-gray-600 shadow-lg">
        {{ result.message }}
      </p>
    </template>
  </div>
</template>

<style scoped></style>
