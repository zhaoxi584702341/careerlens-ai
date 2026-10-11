<script setup lang="ts">
withDefaults(
  defineProps<{
    /** meta.aiMode：本次实际生效的 AI 模式 */
    aiMode?: string
    /** meta.timings：各层耗时（毫秒） */
    timings?: Record<string, number>
  }>(),
  { aiMode: 'rule', timings: () => ({}) },
)

const MODE_LABEL: Record<string, string> = {
  llm: 'LLM 语义模式',
  hybrid: '混合模式',
  rule: '规则引擎',
}
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-control border border-warning/30 bg-amber-50 px-4 py-3 text-sm text-amber-800"
    role="status"
  >
    <span class="inline-flex items-center gap-2 font-medium">
      <span class="h-2 w-2 shrink-0 rounded-full bg-warning"></span>
      LLM 暂不可用，已自动降级为规则引擎结果（可复现、无编造）
    </span>
    <span class="text-xs text-amber-700/80">
      当前模式：{{ MODE_LABEL[aiMode] ?? aiMode }}
    </span>
    <span v-if="timings.total" class="text-xs text-amber-700/80">
      耗时 {{ timings.total }} ms
    </span>
  </div>
</template>

<style scoped></style>
