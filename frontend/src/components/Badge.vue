<script setup lang="ts">
defineProps<{
  variant: 'paid' | 'open' | 'danger' | 'neutral' | 'info' | 'warning'
  label: string
}>()

const variantClasses: Record<string, string> = {
  paid: 'bg-green-100 text-green-700',
  open: 'bg-amber-100 text-amber-700',
  danger: 'bg-red-100 text-red-700',
  neutral: 'bg-slate-100 text-slate-500',
  info: 'bg-blue-100 text-blue-700',
  warning: 'bg-amber-100 text-amber-700',
}
</script>

<template>
  <span :class="['badge', variantClasses[variant] || variantClasses.neutral]">
    {{ label }}
  </span>
</template>
