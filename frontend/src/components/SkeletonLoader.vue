<template>
  <div
    class="animate-pulse bg-gray-200 dark:bg-gray-700 rounded-md shrink-0"
    :style="{ width, height }"
    :class="className"
  ></div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    width?: string
    height?: string
    className?: string
  }>(),
  {
    width: '100%',
    height: '1rem',
    className: ''
  }
)
</script>
