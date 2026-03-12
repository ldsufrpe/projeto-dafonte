<template>
  <div class="flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 w-full h-full min-h-[250px] shadow-sm">
    <div class="mb-4 text-gray-400 dark:text-gray-500">
      <slot name="icon">
        <svg class="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      </slot>
    </div>
    
    <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">{{ title }}</h3>
    <p class="text-sm text-gray-500 dark:text-gray-400 max-w-sm mx-auto">{{ description }}</p>
    
    <div v-if="$slots.action" class="mt-6">
      <slot name="action"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>
