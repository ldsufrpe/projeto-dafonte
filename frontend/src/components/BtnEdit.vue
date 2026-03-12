<script setup lang="ts">
defineProps<{
  editing: boolean
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <button class="btn-edit" @click="$emit('click')" :title="editing ? 'Salvar alterações' : 'Editar dados do morador'">
    <!-- Pencil icon -->
    <svg v-if="!editing" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
    </svg>
    <!-- Checkmark when editing -->
    <svg v-else class="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
    </svg>
  </button>
</template>
