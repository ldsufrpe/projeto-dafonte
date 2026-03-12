<script setup lang="ts">
defineProps<{
  percent: number
  color?: string
}>()
</script>

<template>
  <div class="prog-bg">
    <div
      :class="['prog-fill', color || 'bg-blue-500']"
      :style="{ width: Math.min(Math.max(percent, 0), 100) + '%' }"
    />
  </div>
</template>
