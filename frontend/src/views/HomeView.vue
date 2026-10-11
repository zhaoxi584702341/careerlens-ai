<script setup lang="ts">
import { h } from 'vue'
import type { Component } from 'vue'
import FeatureCard from '@/components/FeatureCard.vue'

/** 统一的线性 SVG 图标组件工厂，避免引入额外图标依赖 */
function createIcon(paths: string[]): Component {
  return {
    name: 'FeatureIcon',
    props: { class: { type: String, default: '' } },
    setup(props) {
      return () =>
        h(
          'svg',
          {
            class: props.class,
            xmlns: 'http://www.w3.org/2000/svg',
            viewBox: '0 0 24 24',
            fill: 'none',
            stroke: 'currentColor',
            'stroke-width': 2,
            'stroke-linecap': 'round',
            'stroke-linejoin': 'round',
          },
          paths.map((d) => h('path', { d })),
        )
    },
  }
}

interface Feature {
  title: string
  description: string
  icon: Component
  to: string
}

const features: Feature[] = [
  {
    title: '简历解析',
    description: '粘贴简历文本，自动提取关键词并给出综合评分。',
    icon: createIcon([
      'M14 3v4a1 1 0 0 0 1 1h4',
      'M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z',
      'M9 13h6',
      'M9 17h6',
    ]),
    to: '/upload-resume',
  },
  {
    title: '岗位匹配',
    description: '对比简历与目标岗位 JD，输出匹配度与改进方向。',
    icon: createIcon([
      'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
      'M9 12l2 2 4-4',
    ]),
    to: '/job-match',
  },
  {
    title: '简历优化',
    description: '针对目标岗位生成优化建议，补齐缺失关键词。',
    icon: createIcon([
      'M12 20h9',
      'M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z',
    ]),
    to: '/resume-optimize',
  },
  {
    title: '能力雷达',
    description: '多维度评估综合能力，雷达图直观呈现短板与优势。',
    icon: createIcon([
      'M12 2v20',
      'M2 12h20',
      'M12 2l7 10-7 10-7-10z',
    ]),
    to: '/radar',
  },
]
</script>

<template>
  <div class="flex min-h-screen flex-col bg-gray-50">
    <main class="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-12 px-4 py-16 sm:px-6 lg:py-24">
      <header class="flex flex-col items-center gap-4 text-center">
        <h1 class="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          CareerLens AI
        </h1>
        <p class="text-base text-gray-500 sm:text-lg">AI 驱动的智能求职助手</p>
      </header>

      <section
        class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4"
        aria-label="功能入口"
      >
        <FeatureCard
          v-for="feature in features"
          :key="feature.to"
          :title="feature.title"
          :description="feature.description"
          :icon="feature.icon"
          :to="feature.to"
        />
      </section>
    </main>

    <footer class="border-t border-gray-200 py-6">
      <p class="text-center text-sm text-gray-400">© 2026 CareerLens AI</p>
    </footer>
  </div>
</template>

<style scoped></style>
