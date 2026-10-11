<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  breakdown?: { mandatory?: number; optional?: number; levelFit?: number } | null
}>()

interface Row {
  key: string
  label: string
  weight: number
  rate: number
  color: string
}

const rows = computed<Row[]>(() => {
  const b = props.breakdown ?? {}
  return [
    { key: 'mandatory', label: '必备技能命中率', weight: 0.6, rate: b.mandatory ?? 0, color: 'bg-gradient-to-r from-blue-600 to-blue-500' },
    { key: 'optional', label: '加分技能命中率', weight: 0.3, rate: b.optional ?? 0, color: 'bg-gradient-to-r from-blue-500 to-purple-500' },
    { key: 'levelFit', label: '经验年限匹配度', weight: 0.1, rate: b.levelFit ?? 0, color: 'bg-gradient-to-r from-purple-500 to-purple-400' },
  ]
})
</script>

<template>
  <div class="flex flex-col gap-3">
    <div
      v-for="row in rows"
      :key="row.key"
      class="flex flex-col gap-2"
    >
      <div class="flex items-baseline justify-between text-sm">
        <span class="text-gray-600">
          {{ row.label }}
          <span class="ml-1 text-xs text-gray-400">权重 {{ Math.round(row.weight * 100) }}%</span>
        </span>
        <span class="font-semibold tabular-nums text-gray-900">{{ Math.round(row.rate * 100) }}%</span>
      </div>
      <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          class="h-full rounded-full transition-all duration-500"
          :class="row.color"
          :style="{ width: `${Math.min(100, Math.max(0, row.rate * 100))}%` }"
        ></div>
      </div>
    </div>
    <p class="mt-1 rounded-xl bg-gray-50 px-4 py-3 text-xs leading-relaxed text-gray-500">
      评分公式：<code class="text-gray-700">round(100 × (0.6×必备 + 0.3×加分 + 0.1×年限))</code>，完全由规则引擎计算，可复现、无编造。
    </p>
  </div>
</template>

<style scoped></style>
