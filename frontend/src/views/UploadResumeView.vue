<script setup lang="ts">
import { computed, ref } from 'vue'
import { analyzeResume, type AnalyzeResumeResponse } from '@/api/resume'
import ScoreGauge from '@/components/ScoreGauge.vue'
import SeverityBadge from '@/components/SeverityBadge.vue'
import DegradedBanner from '@/components/DegradedBanner.vue'
import { useResumeStore } from '@/stores/resume'
import {
  parseResumeFile,
  validateFile,
  detectKind,
  ACCEPT_ATTR,
  KIND_LABEL,
} from '@/utils/resumeParser'

const resumeStore = useResumeStore()

/** 简历正文与全局 Store 双向绑定：任意模块修改都会同步 */
const resumeText = computed({
  get: () => resumeStore.resumeText,
  set: (val: string) => resumeStore.updateText(val),
})

const loading = ref(false)
const errorMessage = ref('')
const result = ref<AnalyzeResumeResponse | null>(null)

/** 拖拽态（纯视觉反馈，不改变上传逻辑） */
const dragging = ref(false)

/** 文件解析态：正在解析 / 解析出的文件名 / 格式 */
const parsing = ref(false)
const parsingName = ref('')

/** 隐藏的原生 file input（点击拖拽区可唤起文件选择） */
const fileInput = ref<HTMLInputElement | null>(null)

const canSubmit = computed(() => !loading.value && !parsing.value && resumeText.value.trim().length > 0)

const issues = computed(() => result.value?.qualityIssues ?? [])
const skills = computed(() => result.value?.skills?.normalized ?? [])

/** 字符数 / 行数预览指标（由 resumeText 派生，纯展示） */
const charCount = computed(() => resumeText.value.trim().length)
const lineCount = computed(() => resumeText.value.split('\n').filter((l) => l.trim()).length)

/** 预览区展示的来源与格式标签（共享自全局 Store） */
const previewName = computed(() => resumeStore.source?.name ?? 'resume.txt')
const previewKind = computed(() =>
  resumeStore.source?.kind ? KIND_LABEL[resumeStore.source.kind] : '文本',
)

/**
 * 统一的文件处理入口：校验 -> 解析 -> 写入全局 Store。
 * 解析在浏览器本地完成（PDF/Word/图片 OCR/文本），失败时给出友好提示。
 * 写入 Store 后，其余三个模块会自动复用同一份简历内容。
 */
async function handleFile(file: File) {
  errorMessage.value = ''

  const invalid = validateFile(file)
  if (invalid) {
    errorMessage.value = invalid
    return
  }

  const kind = detectKind(file)
  if (!kind) {
    errorMessage.value = `不支持的文件格式「${file.name}」，请上传 PDF / Word / 图片 / 文本文件。`
    return
  }

  parsing.value = true
  parsingName.value = file.name
  try {
    const parsed = await parseResumeFile(file)
    // 写入全局 Store（含来源元信息），供所有模块复用
    resumeStore.setResume(parsed.text, {
      name: parsed.name,
      kind: parsed.kind,
      updatedAt: Date.now(),
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : `文件「${file.name}」解析失败，请重试。`
  } finally {
    parsing.value = false
    parsingName.value = ''
  }
}

function onDrop(event: DragEvent) {
  dragging.value = false
  if (loading.value || parsing.value) return
  const file = event.dataTransfer?.files?.[0]
  if (!file) return
  void handleFile(file)
}

function onDragOver() {
  if (loading.value || parsing.value) return
  dragging.value = true
}

function onDragLeave() {
  dragging.value = false
}

/** 点击拖拽区唤起文件选择 */
function openFilePicker() {
  if (loading.value || parsing.value) return
  fileInput.value?.click()
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void handleFile(file)
  // 重置以便重复选择同一文件仍可触发 change
  input.value = ''
}

/** 清除已上传内容，回到初始态（同步清空全局 Store，所有模块一并清空） */
function clearFile() {
  resumeStore.clear()
  result.value = null
  errorMessage.value = ''
}

async function handleSubmit() {
  if (!canSubmit.value) return

  loading.value = true
  errorMessage.value = ''
  result.value = null

  try {
    const { data } = await analyzeResume({ resume_text: resumeText.value.trim() })
    result.value = data
  } catch (error) {
    errorMessage.value = '分析失败，请稍后重试。请确认识别服务已启动。'
    console.error('[analyze-resume] request failed:', error)
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
        <h1 class="text-2xl font-bold tracking-tight text-gray-900">简历上传</h1>
        <span class="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">Resume</span>
      </div>
      <p class="text-sm text-gray-500">拖拽或粘贴简历文本，获取关键词识别与综合评分</p>
    </header>

    <!-- 上传卡 -->
    <section class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg transition-shadow duration-300 hover:shadow-xl">
      <div class="flex flex-col gap-6">
        <!-- 拖拽上传区域 -->
        <div
          class="relative flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-all duration-200"
          :class="[
            dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-gray-50 hover:border-blue-400 hover:bg-blue-50/50',
            (loading || parsing) ? 'pointer-events-none opacity-70' : '',
          ]"
          role="button"
          tabindex="0"
          @dragover.prevent="onDragOver"
          @dragleave.prevent="onDragLeave"
          @drop.prevent="onDrop"
          @click="openFilePicker"
          @keydown.enter.prevent="openFilePicker"
          @keydown.space.prevent="openFilePicker"
        >
          <input
            ref="fileInput"
            type="file"
            class="hidden"
            :accept="ACCEPT_ATTR"
            :disabled="loading || parsing"
            @change="onFileChange"
          />

          <span class="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 text-white shadow-lg">
            <svg
              v-if="!parsing"
              class="h-7 w-7"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M12 16V4M7 9l5-5 5 5" />
              <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
            </svg>
            <svg v-else class="h-7 w-7 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          </span>

          <div class="flex flex-col gap-1">
            <p class="text-base font-semibold text-gray-900">
              {{ parsing ? '正在解析文件…' : '拖拽简历文件到此处，或点击选择' }}
            </p>
            <p v-if="parsing" class="text-sm text-blue-600">正在提取「{{ parsingName }}」的文本内容，请稍候</p>
            <p v-else class="text-sm text-gray-400">
              支持 PDF / Word(.docx) / 图片(PNG·JPG，自动 OCR) / 文本(.txt·.md)，单文件不超过 10MB
            </p>
          </div>
        </div>

        <!-- 文本输入区 -->
        <div class="flex flex-col gap-3">
          <label for="resume-text" class="text-sm font-semibold text-gray-900">简历内容</label>
          <textarea
            id="resume-text"
            v-model="resumeText"
            rows="12"
            placeholder="请在此粘贴你的简历文本内容，例如教育背景、工作经历、项目经验、技能标签等……"
            class="w-full resize-y rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-base leading-relaxed text-gray-700 transition-all placeholder:text-gray-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100"
            :disabled="loading"
          ></textarea>
        </div>

        <!-- 文件预览组件 -->
        <div
          v-if="charCount > 0 || parsing"
          class="flex items-center justify-between gap-4 rounded-xl border border-gray-100 bg-gray-50 p-4"
        >
          <div class="flex min-w-0 items-center gap-4">
            <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-blue-600 shadow-sm">
              <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 3v4a1 1 0 0 0 1 1h4" />
                <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
              </svg>
            </span>
            <div class="flex min-w-0 flex-col">
              <span class="truncate text-sm font-medium text-gray-900">{{ parsing ? parsingName : previewName }}</span>
              <span class="text-xs text-gray-400">
                <template v-if="parsing">解析中…</template>
                <template v-else>{{ previewKind }} · {{ charCount }} 个字符 · {{ lineCount }} 行</template>
              </span>
            </div>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-xl px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-white hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            :disabled="loading"
            @click="clearFile"
          >
            清除
          </button>
        </div>

        <!-- 提交 -->
        <div class="flex items-center justify-end">
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
            {{ loading ? '分析中…' : '提交分析' }}
          </button>
        </div>

        <p v-if="errorMessage" class="rounded-xl bg-red-50 px-4 py-3 text-sm text-danger">{{ errorMessage }}</p>
      </div>
    </section>

    <!-- 分析结果 -->
    <template v-if="result">
      <DegradedBanner
        v-if="result.meta?.degraded"
        :ai-mode="result.meta?.aiMode"
        :timings="result.meta?.timings"
      />

      <section class="flex flex-col items-center gap-8 rounded-2xl border border-gray-100 bg-white p-8 shadow-lg sm:flex-row sm:justify-between">
        <ScoreGauge :score="result.score" label="综合评分" />
        <div class="flex flex-1 flex-col gap-4 sm:pl-8">
          <h2 class="text-2xl font-bold tracking-tight text-gray-900">识别关键词</h2>
          <div class="flex flex-wrap gap-4">
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
      </section>

      <section class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
        <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">简历质量问题（{{ issues.length }}）</h2>
        <ul class="flex flex-col gap-4">
          <li
            v-for="(issue, index) in issues"
            :key="`${issue.code}-${index}`"
            class="flex flex-col gap-2 rounded-xl border border-gray-100 bg-gray-50 p-6"
          >
            <div class="flex items-center gap-3">
              <SeverityBadge :level="issue.severity" />
              <span class="text-base font-medium text-gray-900">{{ issue.message }}</span>
            </div>
            <p class="text-sm text-gray-600 leading-relaxed"><span class="text-gray-400">定位：</span>{{ issue.location }}</p>
            <p class="text-sm text-gray-600 leading-relaxed"><span class="text-gray-400">建议：</span>{{ issue.suggestion }}</p>
          </li>
          <li v-if="issues.length === 0" class="text-sm text-gray-400">未检测到结构性问题</li>
        </ul>
      </section>

      <section v-if="skills.length" class="rounded-2xl border border-gray-100 bg-white p-8 shadow-lg">
        <h2 class="mb-6 text-2xl font-bold tracking-tight text-gray-900">技能归一化（{{ skills.length }}）</h2>
        <div class="flex flex-wrap gap-4">
          <span
            v-for="skill in skills"
            :key="skill.canonical"
            class="inline-flex items-center gap-2 rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600"
          >
            {{ skill.canonical }}
            <span class="text-gray-400">{{ skill.category }}</span>
          </span>
        </div>
      </section>

      <p v-if="result.message" class="rounded-xl border border-gray-100 bg-white px-4 py-3 text-base leading-relaxed text-gray-600 shadow-lg">
        {{ result.message }}
      </p>
    </template>
  </div>
</template>

<style scoped></style>
