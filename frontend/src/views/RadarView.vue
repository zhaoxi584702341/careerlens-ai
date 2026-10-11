<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef } from 'vue'
import * as echarts from 'echarts'
import { fetchRadar, type RadarDimension } from '@/api/radar'

const resumeText = ref('')
const jdText = ref('')
const loading = ref(false)
const errorMessage = ref('')

const dimensions = ref<RadarDimension[]>([])
const message = ref('')
const hasResult = ref(false)

const chartRef = ref<HTMLDivElement | null>(null)
const chartInstance = shallowRef<echarts.ECharts | null>(null)

const canSubmit = computed(
  () =>
    !loading.value &&
    resumeText.value.trim().length > 0 &&
    jdText.value.trim().length > 0,
)

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
      axisName: { color: '#374151', fontSize: 12 },
      splitLine: { lineStyle: { color: '#e5e7eb' } },
      splitArea: { areaStyle: { color: ['#ffffff', '#f9fafb'] } },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '能力评分',
            areaStyle: { color: 'rgba(37, 99, 235, 0.25)' },
            lineStyle: { color: '#2563eb', width: 2 },
            itemStyle: { color: '#2563eb' },
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
  <main class="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-8 px-4 py-12 sm:px-6">
    <header>
      <h1 class="text-3xl font-bold text-gray-900">能力雷达图</h1>
      <p class="mt-2 text-gray-500">粘贴你的简历与目标岗位 JD，生成多维度能力评估雷达图。</p>
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
        <label for="jd-text" class="text-sm font-medium text-gray-700">岗位描述（JD）</label>
        <textarea
          id="jd-text"
          v-model="jdText"
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
          {{ loading ? '生成中…' : '生成雷达图' }}
        </button>
      </div>

      <p v-if="errorMessage" class="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
        {{ errorMessage }}
      </p>
    </section>

    <section v-if="hasResult" class="flex flex-col gap-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <div ref="chartRef" class="h-80 w-full"></div>

      <div>
        <h2 class="mb-3 text-sm font-semibold text-gray-700">维度得分</h2>
        <ul class="flex flex-col gap-2">
          <li
            v-for="item in dimensions"
            :key="item.name"
            class="flex items-center justify-between text-sm text-gray-600"
          >
            <span>{{ item.name }}</span>
            <span class="font-semibold text-blue-600">{{ item.score }} 分</span>
          </li>
          <li v-if="dimensions.length === 0" class="text-sm text-gray-400">暂无维度数据</li>
        </ul>
      </div>

      <p v-if="message" class="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600">
        {{ message }}
      </p>
    </section>
  </main>
</template>

<style scoped></style>
