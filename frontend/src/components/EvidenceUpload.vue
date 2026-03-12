<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import apiClient from '@/api/client'

interface EvidenceItem {
  id: number
  billing_id: number
  original_filename: string
  file_url: string
  uploaded_at: string
}

const props = defineProps<{
  condominiumId: number
  billingId: number
}>()

const MAX_FILE_SIZE = 30 * 1024 * 1024 // 30 MB

const evidences = ref<EvidenceItem[]>([])
const uploading = ref(false)
const uploadProgress = ref(0)
const lightboxUrl = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const validationError = ref<string | null>(null)

const count = computed(() => evidences.value.length)

async function loadEvidences() {
  try {
    const { data } = await apiClient.get<EvidenceItem[]>(
      `/condominiums/${props.condominiumId}/evidencias/${props.billingId}`
    )
    evidences.value = data
  } catch {
    // silently fail — non-critical
  }
}

function triggerUpload() {
  validationError.value = null
  fileInput.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  // Client-side validation
  if (!file.type.startsWith('image/')) {
    validationError.value = 'Apenas imagens são aceitas (JPEG, PNG, HEIC, etc.)'
    input.value = ''
    return
  }
  if (file.size > MAX_FILE_SIZE) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(0)
    validationError.value = `Arquivo muito grande (${sizeMb} MB). Limite: 30 MB.`
    input.value = ''
    return
  }

  validationError.value = null
  const formData = new FormData()
  formData.append('billing_id', String(props.billingId))
  formData.append('file', file)

  uploading.value = true
  uploadProgress.value = 0

  try {
    await apiClient.post(
      `/condominiums/${props.condominiumId}/evidencias`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) uploadProgress.value = Math.round((e.loaded / e.total) * 100)
        },
      }
    )
    await loadEvidences()
  } catch (err: any) {
    const msg = err?.response?.data?.detail ?? 'Erro ao enviar evidência'
    validationError.value = msg
  } finally {
    uploading.value = false
    uploadProgress.value = 0
    // Reset the input so the same file can be re-uploaded
    input.value = ''
  }
}

function openLightbox(url: string) {
  lightboxUrl.value = url
}

function closeLightbox() {
  lightboxUrl.value = null
}

onMounted(loadEvidences)
</script>

<template>
  <div class="inline-flex flex-col items-start gap-1">
    <div class="inline-flex items-center gap-1.5">
      <!-- Hidden file input -->
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        capture="environment"
        class="hidden"
        @change="onFileSelected"
      />

      <!-- Upload button -->
      <button
        :disabled="uploading"
        class="relative flex items-center justify-center w-7 h-7 rounded-lg transition-all"
        :class="uploading
          ? 'bg-blue-100 cursor-wait'
          : 'bg-gray-100 hover:bg-blue-100 text-gray-500 hover:text-blue-600'"
        title="Enviar evidência de entrega"
        @click="triggerUpload"
      >
        <!-- Camera icon -->
        <svg v-if="!uploading" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round"
            d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/>
          <circle cx="12" cy="13" r="3"/>
        </svg>
        <!-- Spinner while uploading -->
        <div v-else class="w-3.5 h-3.5 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin"/>

        <!-- Upload progress ring -->
        <svg v-if="uploading && uploadProgress > 0" class="absolute inset-0 w-7 h-7 -rotate-90">
          <circle cx="14" cy="14" r="11" fill="none" stroke="#dbeafe" stroke-width="2"/>
          <circle cx="14" cy="14" r="11" fill="none" stroke="#2563eb" stroke-width="2"
            :stroke-dasharray="`${69.1 * uploadProgress / 100} 69.1`"/>
        </svg>
      </button>

      <!-- Count badge + thumbnails -->
      <template v-if="count > 0">
        <div class="flex items-center gap-0.5">
          <button
            v-for="ev in evidences.slice(0, 2)"
            :key="ev.id"
            class="w-7 h-7 rounded-md overflow-hidden border border-gray-200 hover:border-blue-400 transition-colors flex-shrink-0"
            @click="openLightbox(ev.file_url)"
          >
            <img :src="ev.file_url" :alt="ev.original_filename" class="w-full h-full object-cover"/>
          </button>
          <span v-if="count > 2"
            class="text-[10px] font-bold text-gray-400 ml-0.5">+{{ count - 2 }}</span>
        </div>
      </template>
    </div>

    <!-- Inline validation error -->
    <p v-if="validationError" class="text-[10px] text-red-500 max-w-[180px] leading-tight">
      {{ validationError }}
    </p>

    <!-- Lightbox overlay -->
    <Teleport to="body">
      <div
        v-if="lightboxUrl"
        class="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm"
        @click.self="closeLightbox"
      >
        <div class="relative max-w-[90vw] max-h-[90vh]">
          <img :src="lightboxUrl" class="max-w-full max-h-[85vh] rounded-xl shadow-2xl"/>
          <button
            class="absolute -top-3 -right-3 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center text-gray-500 hover:text-gray-800 transition-colors"
            @click="closeLightbox"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>
