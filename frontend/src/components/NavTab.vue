<script setup lang="ts">
defineProps<{
  to: string
  label: string
  active?: boolean
  disabled?: boolean
}>()
</script>

<template>
  <router-link
    v-if="!disabled"
    :to="to"
    :class="['nav-tab', { active }]"
    active-class="active"
  >
    <span class="flex items-center gap-2">
      <slot name="icon" />
      {{ label }}
    </span>
  </router-link>
  <span v-else class="nav-tab disabled">
    <span class="flex items-center gap-2">
      <slot name="icon" />
      {{ label }}
    </span>
  </span>
</template>
