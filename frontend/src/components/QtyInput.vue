<script setup lang="ts">
defineProps<{
  modelValue: number
  disabled?: boolean
  min?: number
}>()

defineEmits<{
  'update:modelValue': [value: number]
}>()
</script>

<template>
  <input
    type="number"
    class="qty-input"
    :value="modelValue"
    :disabled="disabled"
    :min="min ?? 0"
    @input="$emit('update:modelValue', Number(($event.target as HTMLInputElement).value) || 0)"
  />
</template>
