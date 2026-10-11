<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 0-100 的分数 */
    score: number
    /** 环形直径（px） */
    size?: number
    /** 中心标签文案 */
    label?: string
    /** 等级文案（EXCELLENT 等），有则展示在分数下方 */
    level?: string
  }>(),
  { size: 160, label: '综合评分', level: '' },
)

const clamped = computed(() => Math.min(100, Math.max(0, Math.round(props.score))))
const stroke = 12
const radius = computed(() => (props.size - stroke) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const dashOffset = computed(() => circumference.value * (1 - clamped.value / 100))

const levelText = computed(() => {
  const map: Record<string, string> = {
    EXCELLENT: '高度匹配',
    GOOD_FIT: '较为匹配',
    PARTIAL_FIT: '部分匹配',
    WEAK_FIT: '匹配较弱',
  }
  return map[props.level] ?? ''
})

/** 分数分档配色 */
const tone = computed(() => {
  if (clamped.value >= 85) return { from: '#16a34a', to: '#4ade80', text: 'text-success' }
  if (clamped.value >= 70) return { from: '#3b82f6', to: '#8b5cf6', text: 'text-brand-600' }
  if (clamped.value >= 50) return { from: '#d97706', to: '#fbbf24', text: 'text-warning' }
  return { from: '#dc2626', to: '#f87171', text: 'text-danger' }
})
</script>

<template>
  <div class="flex flex-col items-center gap-4">
    <div class="relative" :style="{ width: `${size}px`, height: `${size}px` }">
      <svg :width="size" :height="size" class="-rotate-90">
        <defs>
          <linearGradient :id="`gauge-${clamped}`" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" :stop-color="tone.from" />
            <stop offset="100%" :stop-color="tone.to" />
          </linearGradient>
        </defs>
        <circle
          :cx="size / 2"
          :cy="size / 2"
          :r="radius"
          fill="none"
          stroke="#e2e8f0"
          :stroke-width="stroke"
        />
        <circle
          :cx="size / 2"
          :cy="size / 2"
          :r="radius"
          fill="none"
          :stroke="`url(#gauge-${clamped})`"
          :stroke-width="stroke"
          stroke-linecap="round"
          :stroke-dasharray="circumference"
          :stroke-dashoffset="dashOffset"
          class="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div class="absolute inset-0 flex flex-col items-center justify-center">
        <span class="text-4xl font-bold tabular-nums" :class="tone.text">{{ clamped }}</span>
        <span v-if="levelText" class="mt-0.5 text-xs font-medium text-gray-500">{{ levelText }}</span>
      </div>
    </div>
    <span v-if="label" class="text-sm font-medium text-gray-500">{{ label }}</span>
  </div>
</template>

<style scoped></style>
