<script setup lang="ts">
defineProps<{
  modelValue: string
  disabled?: boolean
  placeholder?: string
  inputStyle?: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <input
    type="text"
    class="tbl-input"
    :style="inputStyle"
    :value="modelValue"
    :disabled="disabled"
    :placeholder="placeholder"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>
