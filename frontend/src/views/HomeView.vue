<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const startJobHunting = () => {
  router.push('/upload-resume')
}
</script>

<template>
  <main class="flex min-h-screen flex-col items-center justify-center bg-gray-50">
    <h1 class="mb-10 text-5xl font-bold tracking-tight text-gray-900">
      CareerLens AI 求职平台
    </h1>
    <button
      type="button"
      class="rounded-lg bg-blue-600 px-8 py-3 text-lg font-medium text-white shadow-md transition-colors duration-200 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
      @click="startJobHunting"
    >
      开始求职
    </button>
  </main>
</template>

<style scoped></style>
