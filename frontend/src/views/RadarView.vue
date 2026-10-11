<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef } from 'vue'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'
import { fetchRadar, type RadarDimension } from '@/api/radar'
import type { Meta } from '@/api/resume'
import DegradedBanner from '@/components/DegradedBanner.vue'
import { useResumeStore } from '@/stores/resume'

echarts.use([RadarChart, TooltipComponent, CanvasRenderer])

const resumeStore = useResumeStore()

/** 简历正文与全局 Store 双向绑定：无需重复上传，修改即全局同步 */
const resumeText = computed({
  get: () => resumeStore.resumeText,
  set: (val: string) => resumeStore.updateText(val),
})

const jdText = ref('')
const loading = ref(false)
const errorMessage = ref('')

const dimensions = ref<RadarDimension[]>([])
const message = ref('')
const meta = ref<Meta | null>(null)
const hasResult = ref(false)

const chartRef = ref<HTMLDivElement | null>(null)
const chartInstance = shallowRef<ECharts | null>(null)

const canSubmit = computed(
  () =>
    !loading.value &&
    resumeText.value.trim().length > 0 &&
    jdText.value.trim().length > 0,
)

/** 平均分（由维度派生，纯展示） */
const averageScore = computed(() => {
  if (dimensions.value.length === 0) return 0
  const total = dimensions.value.reduce((sum, item) => sum + clampScore(item.score), 0)
  return Math.round(total / dimensions.value.length)
})

// 将分数限制在 0-100 范围内，避免越界渲染
function clampScore(score: number): number {
  return Math.min(100, Math.max(0, score))
}

function renderChart() {
  if (!chartRef.value) return

  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }

  const indicator = dimensions.value.map((item) => ({ name: item.name, max: 100 }))
  const values = dimensions.value.map((item) => clampScore(item.score))

  chartInstance.value.setOption({
    tooltip: {},
    radar: {
      indicator,
      radius: '65%',
      splitNumber: 5,
      axisName: { color: '#334155', fontSize: 12 },
      splitLine: { lineStyle: { color: '#e2e8f0' } },
      splitArea: { areaStyle: { color: ['#ffffff', '#f8fafc'] } },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '能力评分',
            areaStyle: { color: 'rgba(59, 130, 246, 0.22)' },
            lineStyle: { color: '#3b82f6', width: 2 },
            itemStyle: { color: '#8b5cf6' },
          },
        ],
      },
    ],
  })
}

function handleResize() {
  chartInstance.value?.resize()
}

async function handleSubmit() {
  if (!canSubmit.value) return

  loading.value = true
  errorMessage.value = ''
  hasResult.value = false

  try {
    const { data } = await fetchRadar({
      resume: resumeText.value.trim(),
      jd: jdText.value.trim(),
    })

    dimensions.value = (data.dimensions ?? []).map((item) => ({
      name: item.name,
      score: clampScore(item.score),
    }))
    message.value = data.message ?? ''
    meta.value = data.meta ?? null
    hasResult.value = true

    await nextTick()
    renderChart()
    window.addEventListener('resize', handleResize)
  } catch (error) {
    errorMessage.value = '生成失败，请稍后重试。请确认雷达图服务已启动。'
    console.error('[radar] request failed:', error)
  } finally {
    loading.value = false
  }
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance.value?.dispose()
  chartInstance.value = null
})
</script>

<template>
  <div class="flex flex-col gap-8">
    <!-- 页头 -->
    <header class="flex flex-col gap-2">
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-bold tracking-tight text-gray-900">能力雷达</h1>
        <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">Radar</span>
      </div>
      <p class="text-sm text-gray-500">多维度评估能力，直观呈现短板与优势</p>
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
            <label for="jd-text" class="text-sm font-semibold text-gray-900">岗位描述（JD）</label>
            <textarea
              id="jd-text"
              v-model="jdText"
              placeholder="请在此粘贴目标岗位的职位描述，例如岗位职责、任职要求、技能要求等……"
              class="min-h-[200px] w-full resize-y rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-base leading-relaxed text-gray-700 transition-all placeholder:text-gray-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100"
              :disabled="loading"
            ></textarea>
          </div>
        </div>

        <div class="flex flex-col items-end gap-4">
          <p v-if="!canSubmit && !loading" class="text-xs text-gray-400">
            请完整填写简历内容与岗位描述后再提交
          </p>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-8 py-3 text-sm font-semibold text-white shadow-lg transition-all duration-200 hover:scale-105 hover:shadow-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
            :disabled="!canSubmit"
            @click="handleSubmit"
          >
            <svg
              v-if="loading"
              class="h-4 w-4 animate-spin text-white"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            {{ loading ? '生成中…' : '生成雷达图' }}
          </button>
        </div>

        <p v-if="errorMessage" class="rounded-xl bg-red-50 px-4 py-3 text-sm text-danger">
          {{ errorMessage }}
        </p>
      </div>
    </section>

    <!-- 结果区 -->
    <template v-if="hasResult">
      <DegradedBanner v-if="meta?.degraded" :ai-mode="meta?.aiMode" :timings="meta?.timings" />

      <section class="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <!-- 技能雷达图 -->
        <div class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg lg:col-span-2">
          <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">技能雷达图</h2>
          <div ref="chartRef" class="h-80 w-full"></div>
        </div>

        <!-- 维度得分 -->
        <div class="flex flex-col gap-6 rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
          <div class="flex items-center justify-between">
            <h2 class="text-2xl font-bold tracking-tight text-gray-900">维度得分</h2>
            <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">均分 {{ averageScore }}</span>
          </div>
          <ul class="flex flex-col gap-6">
            <li
              v-for="item in dimensions"
              :key="item.name"
              class="flex flex-col gap-2"
            >
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-600">{{ item.name }}</span>
                <span class="font-semibold text-blue-700">{{ item.score }} 分</span>
              </div>
              <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                <div
                  class="h-full rounded-full bg-gradient-to-r from-blue-600 to-purple-600 transition-all duration-500"
                  :style="{ width: `${item.score}%` }"
                ></div>
              </div>
            </li>
            <li v-if="dimensions.length === 0" class="text-sm text-gray-400">暂无维度数据</li>
          </ul>
        </div>
      </section>

      <p v-if="message" class="rounded-xl border border-gray-100 bg-white px-4 py-3 text-base leading-relaxed text-gray-600 shadow-lg">
        {{ message }}
      </p>
    </template>
  </div>
</template>

<style scoped></style>
