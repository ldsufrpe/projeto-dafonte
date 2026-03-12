<script setup lang="ts">
defineProps<{
  title: string
  value: string
  subtitle?: string
  borderColor?: string
}>()
</script>

<template>
  <div :class="['stat-card border-l-4', borderColor || 'border-blue-500']">
    <div class="flex items-center justify-between mb-3">
      <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">{{ title }}</span>
      <div class="w-9 h-9 rounded-xl flex items-center justify-center">
        <slot name="icon" />
      </div>
    </div>
    <p class="text-3xl font-bold text-gray-900">
      {{ value }}
      <span v-if="$slots.unit" class="text-base text-gray-400 font-medium">
        <slot name="unit" />
      </span>
    </p>
    <slot name="extra" />
    <p v-if="subtitle" class="text-xs font-medium mt-2">
      <slot name="subtitle">{{ subtitle }}</slot>
    </p>
  </div>
</template>
