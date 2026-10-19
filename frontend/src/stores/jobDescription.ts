import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * 全局岗位描述（JD）Store，与 `resume` Store 同构。
 *
 * 职责：让目标 JD 只录入一次，即可被三个模块（岗位匹配、简历优化、能力雷达）
 * 复用；任意模块对 JD 的修改都会实时同步到其他模块。
 *
 * 数据流：
 * - 内存态：`jdText`（纯文本正文）、`updatedAt`（最近更新时间）。
 * - 持久化：写入 localStorage，刷新/关闭浏览器后仍保留。
 * - 跨标签页：监听 window `storage` 事件，多标签页之间保持同步。
 *
 * 与 `resume` Store 的差异：JD 只能手动录入，不存在文件上传，因此不携带
 * `source`（文件名/格式）元信息，仅保留 `updatedAt`；对应地也不提供
 * `setResume(text, meta)` 那类"替换来源"的方法，仅提供 `updateText`。
 *
 * 契约不变：各模块提交时仍只向后端传 `job_description` 字符串，本 Store 只负责前端共享。
 */

const STORAGE_KEY = 'careerlens.jd.v1'

interface PersistShape {
  text: string
  updatedAt: number | null
}

/** 从 localStorage 读取初始数据（失败时静默降级为空，避免阻塞应用启动） */
function loadFromStorage(): PersistShape {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { text: '', updatedAt: null }
    const parsed = JSON.parse(raw) as Partial<PersistShape>
    return {
      text: typeof parsed.text === 'string' ? parsed.text : '',
      updatedAt: typeof parsed.updatedAt === 'number' ? parsed.updatedAt : null,
    }
  } catch {
    return { text: '', updatedAt: null }
  }
}

export const useJobDescriptionStore = defineStore('jobDescription', () => {
  const initial = loadFromStorage()

  /** JD 正文（三个模块共享的单一数据源） */
  const jdText = ref<string>(initial.text)
  /** 最近一次更新时间（毫秒时间戳）；无内容时为 null */
  const updatedAt = ref<number | null>(initial.updatedAt)

  /** 是否已录入 JD（供全局状态标识与提交按钮禁用态使用） */
  const hasJD = computed(() => jdText.value.trim().length > 0)
  /** 正文字符数（去空白） */
  const charCount = computed(() => jdText.value.trim().length)

  /** 持久化当前状态到 localStorage */
  function persist() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ text: jdText.value, updatedAt: updatedAt.value } satisfies PersistShape),
      )
    } catch {
      // 存储不可用（隐私模式/超配额）时忽略，仅保留内存态
    }
  }

  /** 主动更新正文（各模块输入框双向绑定调用），同时刷新更新时间 */
  function updateText(text: string) {
    jdText.value = text
    updatedAt.value = Date.now()
    persist()
  }

  /** 清空 JD（清除按钮/数据丢失时调用） */
  function clear() {
    jdText.value = ''
    updatedAt.value = null
    persist()
  }

  /**
   * 应用外部的持久化数据（跨标签页同步用）。
   * 直接替换内存态，不再回写 localStorage，避免 ping-pong。
   */
  function applyExternal(data: PersistShape) {
    jdText.value = data.text
    updatedAt.value = data.updatedAt
  }

  /** 注册跨标签页同步：仅在浏览器环境下生效 */
  function initSync() {
    if (typeof window === 'undefined') return () => {}
    const handler = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY) return
      try {
        const data = event.newValue
          ? (JSON.parse(event.newValue) as PersistShape)
          : { text: '', updatedAt: null }
        applyExternal(data)
      } catch {
        // 忽略非法数据
      }
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }

  return {
    jdText,
    updatedAt,
    hasJD,
    charCount,
    updateText,
    clear,
    applyExternal,
    initSync,
  }
})
