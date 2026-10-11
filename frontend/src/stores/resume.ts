import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { ResumeFileKind } from '@/utils/resumeParser'

/**
 * 全局简历 Store。
 *
 * 职责：让简历内容只上传/录入一次，即可被四个模块（上传、岗位匹配、简历优化、能力雷达）
 * 复用；任意模块对简历的修改都会实时同步到其他模块。
 *
 * 数据流：
 * - 内存态：`resumeText`（纯文本正文）、`source`（来源元信息）。
 * - 持久化：写入 localStorage，刷新/关闭浏览器后仍保留。
 * - 跨标签页：监听 window `storage` 事件，多标签页之间保持同步。
 *
 * 契约不变：各模块提交时仍只向后端传 `resume_text` 字符串，本 Store 只负责前端共享。
 */

const STORAGE_KEY = 'careerlens.resume.v1'

/** 简历来源元信息（用于"是否已上传"状态标识展示） */
export interface ResumeSource {
  /** 文件名；手动粘贴时为 null */
  name: string | null
  /** 文件格式大类；手动粘贴时为 null */
  kind: ResumeFileKind | null
  /** 最近一次更新时间（毫秒时间戳） */
  updatedAt: number
}

interface PersistShape {
  text: string
  source: ResumeSource | null
}

/** 从 localStorage 读取初始数据（失败时静默降级为空，避免阻塞应用启动） */
function loadFromStorage(): PersistShape {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { text: '', source: null }
    const parsed = JSON.parse(raw) as Partial<PersistShape>
    return {
      text: typeof parsed.text === 'string' ? parsed.text : '',
      source: parsed.source ?? null,
    }
  } catch {
    return { text: '', source: null }
  }
}

export const useResumeStore = defineStore('resume', () => {
  const initial = loadFromStorage()

  /** 简历正文（四个模块共享的单一数据源） */
  const resumeText = ref<string>(initial.text)
  /** 来源元信息；无内容时为 null */
  const source = ref<ResumeSource | null>(initial.source)

  /** 是否已上传/已录入简历（供全局状态标识使用） */
  const hasResume = computed(() => resumeText.value.trim().length > 0)
  /** 正文字符数（去空白） */
  const charCount = computed(() => resumeText.value.trim().length)

  /** 持久化当前状态到 localStorage */
  function persist() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ text: resumeText.value, source: source.value } satisfies PersistShape),
      )
    } catch {
      // 存储不可用（隐私模式/超配额）时忽略，仅保留内存态
    }
  }

  /**
   * 写入简历内容（来自文件解析或手动编辑）。
   * @param text 简历正文
   * @param meta 来源元信息；手动编辑时传 null 表示不再关联具体文件
   */
  function setResume(text: string, meta: ResumeSource | null = null) {
    resumeText.value = text
    source.value = meta
    persist()
  }

  /** 主动更新正文（各模块输入框双向绑定调用），保留已有来源信息 */
  function updateText(text: string) {
    resumeText.value = text
    // 编辑后刷新时间戳，便于状态条展示"最近更新"
    if (source.value) source.value = { ...source.value, updatedAt: Date.now() }
    persist()
  }

  /** 清空简历（清除按钮/数据丢失时调用） */
  function clear() {
    resumeText.value = ''
    source.value = null
    persist()
  }

  /**
   * 应用外部的持久化数据（跨标签页同步用）。
   * 直接替换内存态，不再回写 localStorage，避免 ping-pong。
   */
  function applyExternal(data: PersistShape) {
    resumeText.value = data.text
    source.value = data.source
  }

  /** 注册跨标签页同步：仅在浏览器环境下生效 */
  function initSync() {
    if (typeof window === 'undefined') return () => {}
    const handler = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY) return
      try {
        const data = event.newValue ? (JSON.parse(event.newValue) as PersistShape) : { text: '', source: null }
        applyExternal(data)
      } catch {
        // 忽略非法数据
      }
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }

  return {
    resumeText,
    source,
    hasResume,
    charCount,
    setResume,
    updateText,
    clear,
    applyExternal,
    initSync,
  }
})
