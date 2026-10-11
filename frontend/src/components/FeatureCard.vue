<script setup lang="ts">
import type { Component } from 'vue'
import { useRouter } from 'vue-router'

defineProps<{
  /** 功能标题 */
  title: string
  /** 功能简短描述 */
  description: string
  /** 卡片图标组件 */
  icon: Component
  /** 点击后跳转的路由路径 */
  to: string
}>()

const router = useRouter()

function go(to: string) {
  router.push(to)
}
</script>

<template>
  <button
    type="button"
    class="group flex w-full flex-col items-start gap-4 rounded-xl border border-gray-200 bg-white p-6 text-left shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-blue-200 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
    @click="go(to)"
  >
    <span
      class="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50 text-blue-600 transition-colors duration-200 group-hover:bg-blue-600 group-hover:text-white"
    >
      <component :is="icon" class="h-6 w-6" />
    </span>
    <span class="flex flex-col gap-1.5">
      <span class="text-base font-semibold text-gray-900">{{ title }}</span>
      <span class="text-sm leading-relaxed text-gray-500">{{ description }}</span>
    </span>
  </button>
</template>

<style scoped></style>
