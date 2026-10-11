<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** 严重程度：high / medium / low / warn / info */
  level: string
}>()

const PRESET: Record<string, { label: string; cls: string }> = {
  high: { label: '高', cls: 'bg-red-50 text-danger border-danger/30' },
  warn: { label: '中', cls: 'bg-amber-50 text-warning border-warning/30' },
  medium: { label: '中', cls: 'bg-amber-50 text-warning border-warning/30' },
  info: { label: '低', cls: 'bg-brand-50 text-brand-600 border-brand-200' },
  low: { label: '低', cls: 'bg-brand-50 text-brand-600 border-brand-200' },
}

const preset = computed(() => PRESET[props.level] ?? { label: props.level, cls: 'bg-ink-100 text-ink-600 border-ink-200' })
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium"
    :class="preset.cls"
  >
    {{ preset.label }}
  </span>
</template>

<style scoped></style>
