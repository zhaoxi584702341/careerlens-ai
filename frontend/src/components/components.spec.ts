import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ScoreGauge from './ScoreGauge.vue'
import SeverityBadge from './SeverityBadge.vue'
import BreakdownBars from './BreakdownBars.vue'
import DegradedBanner from './DegradedBanner.vue'

describe('ScoreGauge', () => {
  it('渲染分数并做 0-100 夹取（超过 100 显示 100）', () => {
    const over = mount(ScoreGauge, { props: { score: 130 } })
    expect(over.text()).toContain('100')

    const under = mount(ScoreGauge, { props: { score: -20 } })
    expect(under.text()).toContain('0')
  })

  it('四舍五入分数并展示默认标签', () => {
    const w = mount(ScoreGauge, { props: { score: 76.6 } })
    expect(w.text()).toContain('77')
    expect(w.text()).toContain('综合评分')
  })

  it('level 映射为中文文案', () => {
    const w = mount(ScoreGauge, { props: { score: 90, level: 'EXCELLENT' } })
    expect(w.text()).toContain('高度匹配')
  })

  it('按分档应用配色类（≥85 绿 / ≥70 靛蓝 / ≥50 琥珀 / 其余红）', () => {
    expect(mount(ScoreGauge, { props: { score: 90 } }).find('.text-success').exists()).toBe(true)
    expect(mount(ScoreGauge, { props: { score: 72 } }).find('.text-brand-600').exists()).toBe(true)
    expect(mount(ScoreGauge, { props: { score: 55 } }).find('.text-warning').exists()).toBe(true)
    expect(mount(ScoreGauge, { props: { score: 30 } }).find('.text-danger').exists()).toBe(true)
  })
})

describe('SeverityBadge', () => {
  it.each([
    ['high', '高', 'text-danger'],
    ['warn', '中', 'text-warning'],
    ['medium', '中', 'text-warning'],
    ['info', '低', 'text-brand-600'],
    ['low', '低', 'text-brand-600'],
  ])('level=%s 显示标签 %s 且应用类 %s', (level, label, cls) => {
    const w = mount(SeverityBadge, { props: { level } })
    expect(w.text()).toBe(label)
    expect(w.classes().join(' ')).toContain(cls)
  })

  it('未知 level 回退为原样文本', () => {
    const w = mount(SeverityBadge, { props: { level: 'critical' } })
    expect(w.text()).toBe('critical')
  })
})

describe('BreakdownBars', () => {
  it('渲染三个区块及权重文案与公式说明', () => {
    const w = mount(BreakdownBars, {
      props: { breakdown: { mandatory: 0.8, optional: 0.5, levelFit: 1 } },
    })
    const t = w.text()
    expect(t).toContain('必备技能命中率')
    expect(t).toContain('加分技能命中率')
    expect(t).toContain('经验年限匹配度')
    expect(t).toContain('权重 60%')
    expect(t).toContain('权重 30%')
    expect(t).toContain('权重 10%')
    expect(t).toContain('round(100 × (0.6×必备 + 0.3×加分 + 0.1×年限))')
  })

  it('百分比按四舍五入展示', () => {
    const w = mount(BreakdownBars, {
      props: { breakdown: { mandatory: 0.667, optional: 0.333, levelFit: 1 } },
    })
    const t = w.text()
    expect(t).toContain('67%')
    expect(t).toContain('33%')
    expect(t).toContain('100%')
  })

  it('缺省 breakdown 时全部按 0 渲染且不报错', () => {
    const w = mount(BreakdownBars, { props: {} })
    expect(w.text()).toContain('0%')
  })
})

describe('DegradedBanner', () => {
  it('展示降级提示并映射 aiMode 文案', () => {
    const w = mount(DegradedBanner, { props: { aiMode: 'rule' } })
    expect(w.text()).toContain('LLM 暂不可用，已自动降级为规则引擎结果')
    expect(w.text()).toContain('规则引擎')
  })

  it('llm / hybrid 模式文案映射正确', () => {
    expect(mount(DegradedBanner, { props: { aiMode: 'llm' } }).text()).toContain('LLM 语义模式')
    expect(mount(DegradedBanner, { props: { aiMode: 'hybrid' } }).text()).toContain('混合模式')
  })

  it('默认 aiMode 为 rule', () => {
    expect(mount(DegradedBanner).text()).toContain('规则引擎')
  })
})
