import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useResumeStore } from './resume'

describe('useResumeStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('初始状态为空：hasResume=false、charCount=0', () => {
    const store = useResumeStore()
    expect(store.hasResume).toBe(false)
    expect(store.charCount).toBe(0)
    expect(store.resumeText).toBe('')
    expect(store.source).toBeNull()
  })

  it('setResume 写入正文与来源元信息，并更新派生状态', () => {
    const store = useResumeStore()
    store.setResume('张三 前端工程师', { name: 'resume.pdf', kind: 'pdf', updatedAt: 1700000000000 })

    expect(store.resumeText).toBe('张三 前端工程师')
    expect(store.hasResume).toBe(true)
    expect(store.charCount).toBe(8)
    expect(store.source?.name).toBe('resume.pdf')
    expect(store.source?.kind).toBe('pdf')
  })

  it('resumeText 持久化到 localStorage', () => {
    const store = useResumeStore()
    store.setResume('持久化内容')

    const raw = localStorage.getItem('careerlens.resume.v1')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw as string)
    expect(parsed.text).toBe('持久化内容')
  })

  it('新建 store 时从 localStorage 恢复已有数据', () => {
    localStorage.setItem(
      'careerlens.resume.v1',
      JSON.stringify({ text: '已保存简历', source: { name: 'a.docx', kind: 'word', updatedAt: 1 } }),
    )
    setActivePinia(createPinia())
    const store = useResumeStore()

    expect(store.resumeText).toBe('已保存简历')
    expect(store.hasResume).toBe(true)
    expect(store.source?.kind).toBe('word')
  })

  it('updateText 更新正文并刷新来源时间戳', () => {
    const store = useResumeStore()
    store.setResume('原文', { name: 'r.txt', kind: 'text', updatedAt: 1 })
    store.updateText('修改后的内容')

    expect(store.resumeText).toBe('修改后的内容')
    expect(store.source?.updatedAt).toBeGreaterThan(1)
  })

  it('updateText 在无来源时也可用，且不虚构来源', () => {
    const store = useResumeStore()
    store.updateText('手动录入内容')

    expect(store.resumeText).toBe('手动录入内容')
    expect(store.hasResume).toBe(true)
    expect(store.source).toBeNull()
  })

  it('clear 清空正文、来源与持久化数据', () => {
    const store = useResumeStore()
    store.setResume('待清空')
    store.clear()

    expect(store.resumeText).toBe('')
    expect(store.hasResume).toBe(false)
    expect(store.source).toBeNull()
    const parsed = JSON.parse(localStorage.getItem('careerlens.resume.v1') as string)
    expect(parsed.text).toBe('')
  })

  it('localStorage 数据损坏时安全降级为空态', () => {
    localStorage.setItem('careerlens.resume.v1', '{ not valid json')
    setActivePinia(createPinia())
    const store = useResumeStore()

    expect(store.resumeText).toBe('')
    expect(store.hasResume).toBe(false)
  })

  it('applyExternal 应用跨标签页数据且不回写 localStorage', () => {
    const store = useResumeStore()
    localStorage.setItem('careerlens.resume.v1', 'sentinel')
    store.applyExternal({ text: '来自其他标签页', source: null })

    expect(store.resumeText).toBe('来自其他标签页')
    // applyExternal 不触发 persist：storage 中的哨兵值应保持不变
    expect(localStorage.getItem('careerlens.resume.v1')).toBe('sentinel')
  })
})
