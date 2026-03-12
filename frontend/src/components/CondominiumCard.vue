<script setup lang="ts">
import { computed } from 'vue'
import Badge from './Badge.vue'
import ProgBar from './ProgBar.vue'
import type { CondominiumOverview } from '@/stores/condominium'

const props = defineProps<{
  condominium: CondominiumOverview
}>()

const emit = defineEmits<{
  select: [id: number]
}>()

const DEFAULT_STATUS = { variant: 'neutral' as const, label: 'Pendente', action: 'Lançar' }

const statusConfig = computed(() => {
  const map: Record<string, { variant: 'neutral' | 'warning' | 'info' | 'paid'; label: string; action: string }> = {
    not_started: { variant: 'neutral', label: 'Pendente', action: 'Lançar' },
    in_progress: { variant: 'warning', label: 'Em andamento', action: 'Continuar' },
    submitted: { variant: 'info', label: 'Enviado', action: 'Sincronizar' },
    synced: { variant: 'paid', label: 'Sincronizado', action: 'Ver Dashboard' },
  }
  return map[props.condominium.month_status] ?? DEFAULT_STATUS
})

const progress = computed(() => {
  if (props.condominium.total_units === 0) return 0
  return (props.condominium.units_launched / props.condominium.total_units) * 100
})

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

function handleClick() {
  emit('select', props.condominium.id)
}
</script>

<template>
  <div
    class="card p-5 cursor-pointer hover:shadow-lg transition-all duration-200 hover:-translate-y-0.5"
    @click="handleClick"
  >
    <!-- Header -->
    <div class="flex items-start justify-between mb-3">
      <div class="min-w-0 flex-1">
        <h3 class="text-base font-bold text-gray-800 truncate">{{ condominium.name }}</h3>
        <p v-if="condominium.address" class="text-xs text-gray-400 truncate mt-0.5">{{ condominium.address }}</p>
      </div>
      <div class="flex items-center gap-2 ml-3 flex-shrink-0">
        <!-- Stock alert -->
        <span
          v-if="condominium.has_stock_alert"
          class="w-6 h-6 bg-red-50 text-red-500 rounded-full flex items-center justify-center font-bold text-xs border border-red-100"
          title="Alerta de estoque (exemplo)"
        >
          !
        </span>
        <Badge :variant="statusConfig.variant" :label="statusConfig.label" />
      </div>
    </div>

    <!-- Progress -->
    <div class="mb-4">
      <div class="flex items-center justify-between mb-1.5">
        <span class="text-xs text-gray-400">Progresso do lançamento</span>
        <span class="text-xs font-semibold text-gray-600">
          {{ condominium.units_launched }} / {{ condominium.total_units }} unid.
        </span>
      </div>
      <ProgBar :percent="progress" :color="statusConfig.variant === 'paid' ? 'bg-green-500' : 'bg-blue-500'" />
    </div>

    <!-- Totals -->
    <div class="grid grid-cols-3 gap-3 mb-4">
      <div class="text-center bg-slate-50 border border-slate-100 rounded-lg py-2">
        <p class="text-[9px] text-gray-400 font-bold tracking-widest uppercase">Faturado</p>
        <p class="text-sm font-bold text-gray-700 mt-0.5">{{ formatCurrency(condominium.total_billed) }}</p>
      </div>
      <div class="text-center bg-green-50 border border-green-100 rounded-lg py-2">
        <p class="text-[9px] text-green-600 font-bold tracking-widest uppercase">Recebido</p>
        <p class="text-sm font-bold text-green-700 mt-0.5">{{ formatCurrency(condominium.total_received) }}</p>
      </div>
      <div class="text-center bg-blue-50 border border-blue-100 rounded-lg py-2">
        <p class="text-[9px] text-blue-500 font-bold tracking-widest uppercase">Comissão</p>
        <p class="text-sm font-bold text-blue-700 mt-0.5">{{ formatCurrency(condominium.commission_due) }}</p>
      </div>
    </div>

    <!-- Action button -->
    <button
      class="w-full px-4 py-2.5 bg-blue-600 border border-transparent text-white rounded-lg text-sm hover:bg-blue-700 transition-colors font-medium shadow-sm"
      @click.stop="handleClick"
    >
      {{ statusConfig.action }}
    </button>
  </div>
</template>
