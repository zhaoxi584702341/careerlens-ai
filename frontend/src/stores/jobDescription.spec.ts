import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { computed } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useJobDescriptionStore } from './jobDescription'
import { useResumeStore } from './resume'

describe('useJobDescriptionStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    // 仅伪造定时器（保留真实 Date），以便确定性验证防抖落盘时机
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('初始状态为空：hasJD=false、charCount=0、updatedAt=null', () => {
    const store = useJobDescriptionStore()
    expect(store.hasJD).toBe(false)
    expect(store.charCount).toBe(0)
    expect(store.jdText).toBe('')
    expect(store.updatedAt).toBeNull()
  })

  it('updateText 写入正文、刷新时间戳并更新派生状态', () => {
    const store = useJobDescriptionStore()
    store.updateText('前端工程师')

    expect(store.jdText).toBe('前端工程师')
    expect(store.hasJD).toBe(true)
    expect(store.charCount).toBe(5)
    expect(store.updatedAt).toBeGreaterThan(0)
  })

  it('jdText 持久化到 localStorage（含更新时间）', () => {
    const store = useJobDescriptionStore()
    store.updateText('持久化JD内容')
    // 防抖窗口内尚未落盘
    expect(localStorage.getItem('careerlens.jd.v1')).toBeNull()
    vi.advanceTimersByTime(300)

    const raw = localStorage.getItem('careerlens.jd.v1')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw as string)
    expect(parsed.text).toBe('持久化JD内容')
    expect(typeof parsed.updatedAt).toBe('number')
  })

  it('新建 store 时从 localStorage 恢复已有数据', () => {
    localStorage.setItem(
      'careerlens.jd.v1',
      JSON.stringify({ text: '已保存JD', updatedAt: 1700000000000 }),
    )
    setActivePinia(createPinia())
    const store = useJobDescriptionStore()

    expect(store.jdText).toBe('已保存JD')
    expect(store.hasJD).toBe(true)
    expect(store.updatedAt).toBe(1700000000000)
  })

  it('clear 清空正文、更新时间与持久化数据', () => {
    const store = useJobDescriptionStore()
    store.updateText('待清空')
    store.clear()

    expect(store.jdText).toBe('')
    expect(store.hasJD).toBe(false)
    expect(store.updatedAt).toBeNull()
    const parsed = JSON.parse(localStorage.getItem('careerlens.jd.v1') as string)
    expect(parsed.text).toBe('')
  })

  it('localStorage 数据损坏时安全降级为空态', () => {
    localStorage.setItem('careerlens.jd.v1', '{ not valid json')
    setActivePinia(createPinia())
    const store = useJobDescriptionStore()

    expect(store.jdText).toBe('')
    expect(store.hasJD).toBe(false)
    expect(store.updatedAt).toBeNull()
  })

  it('applyExternal 应用跨标签页数据且不回写 localStorage', () => {
    const store = useJobDescriptionStore()
    localStorage.setItem('careerlens.jd.v1', 'sentinel')
    store.applyExternal({ text: '来自其他标签页', updatedAt: 1 })

    expect(store.jdText).toBe('来自其他标签页')
    expect(store.updatedAt).toBe(1)
    // applyExternal 不触发 persist：storage 中的哨兵值应保持不变
    expect(localStorage.getItem('careerlens.jd.v1')).toBe('sentinel')
  })

  it('initSync 监听 storage 事件实现跨标签页同步，且不回写', () => {
    const store = useJobDescriptionStore()
    const dispose = store.initSync()

    localStorage.setItem('careerlens.jd.v1', 'sentinel')
    window.dispatchEvent(
      new StorageEvent('storage', {
        key: 'careerlens.jd.v1',
        newValue: JSON.stringify({ text: '来自另一个标签页', updatedAt: 123 }),
      }),
    )

    expect(store.jdText).toBe('来自另一个标签页')
    expect(store.updatedAt).toBe(123)
    expect(localStorage.getItem('careerlens.jd.v1')).toBe('sentinel')

    dispose()
  })

  it('多组件共享同一 Store 实时同步（与三个视图的 v-model 绑定等价）', () => {
    const store = useJobDescriptionStore()
    // 模拟 JobMatchView / ResumeOptimizeView / RadarView 中各自的双向绑定
    const componentA = computed({ get: () => store.jdText, set: (v: string) => store.updateText(v) })
    const componentB = computed({ get: () => store.jdText, set: (v: string) => store.updateText(v) })

    componentA.value = '岗位：高级前端（React）'
    expect(componentB.value).toBe('岗位：高级前端（React）')
    expect(store.jdText).toBe('岗位：高级前端（React）')

    // 反向更新：B 改动同样实时反映到 A
    componentB.value = '岗位：Node 后端工程师'
    expect(componentA.value).toBe('岗位：Node 后端工程师')
    expect(store.hasJD).toBe(true)
  })

  it('与 resume Store 相互独立，不影响简历内容', () => {
    const jdStore = useJobDescriptionStore()
    const resumeStore = useResumeStore()

    resumeStore.setResume('张三 前端工程师', { name: 'resume.pdf', kind: 'pdf', updatedAt: 1 })
    jdStore.updateText('岗位：高级前端')
    // JD 走防抖落盘，待窗口到期后再校验持久化结果
    vi.advanceTimersByTime(300)

    // 两个 Store 各自独立持久化，互不覆盖
    expect(resumeStore.resumeText).toBe('张三 前端工程师')
    expect(resumeStore.hasResume).toBe(true)
    expect(JSON.parse(localStorage.getItem('careerlens.resume.v1') as string).text).toBe('张三 前端工程师')
    expect(JSON.parse(localStorage.getItem('careerlens.jd.v1') as string).text).toBe('岗位：高级前端')
  })

  it('updateText 防抖落盘：窗口内不写，到期后写入 localStorage', () => {
    const store = useJobDescriptionStore()
    store.updateText('防抖JD')
    expect(localStorage.getItem('careerlens.jd.v1')).toBeNull()

    vi.advanceTimersByTime(300)
    const parsed = JSON.parse(localStorage.getItem('careerlens.jd.v1') as string)
    expect(parsed.text).toBe('防抖JD')
  })

  it('页面隐藏时立即补写未落盘编辑（防抖窗口内切标签页不丢数据）', () => {
    const store = useJobDescriptionStore()
    const dispose = store.initSync()
    store.updateText('未落盘JD')
    expect(localStorage.getItem('careerlens.jd.v1')).toBeNull()

    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    document.dispatchEvent(new Event('visibilitychange'))
    const parsed = JSON.parse(localStorage.getItem('careerlens.jd.v1') as string)
    expect(parsed.text).toBe('未落盘JD')

    // 还原可见性并清理监听，避免污染其他用例
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    dispose()
  })

  it('beforeunload 时立即补写未落盘编辑（防抖窗口内刷新/关闭不丢数据）', () => {
    const store = useJobDescriptionStore()
    const dispose = store.initSync()
    store.updateText('刷新前未落盘')
    expect(localStorage.getItem('careerlens.jd.v1')).toBeNull()

    window.dispatchEvent(new Event('beforeunload'))
    const parsed = JSON.parse(localStorage.getItem('careerlens.jd.v1') as string)
    expect(parsed.text).toBe('刷新前未落盘')

    dispose()
  })
})
