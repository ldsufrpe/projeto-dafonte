import { onMounted, ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useCondominiumStore } from '@/stores/condominium'
import { useFinanceStore } from '@/stores/finance'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

// ... resto do seu código ...
import { onMounted, ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useCondominiumStore } from '@/stores/condominium'
import { useFinanceStore } from '@/stores/finance'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const auth = useAuthStore()
const condoStore = useCondominiumStore()
const financeStore = useFinanceStore()

const loading = ref(true)
const currentMonth = ref(new Date().toISOString().slice(0, 7))  // YYYY-MM

const condoId = computed(() => condoStore.activeCondominiumId)

function fmCurrency(v: number | null | undefined): string {
    if (v == null || isNaN(v)) return 'R$ 0,00'
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
}

function fmPct(v: number | null | undefined): string {
    if (v == null || isNaN(v)) return '0%'
    return `${Number(v).toFixed(1)}%`
}

const commTypeLabel: Record<string, string> = {
    fixed: 'Fixo Mensal',
    percent: 'Percentual',
    per_unit: 'Por Unidade',
}

async function loadAll() {
    loading.value = true
    try {
        if (condoId.value) {
            await financeStore.fetchCommission(condoId.value, currentMonth.value)
        }
        await financeStore.fetchPerformance(currentMonth.value)
    } finally {
        loading.value = false
    }
}

onMounted(loadAll)

watch([condoId, currentMonth], loadAll)

// ── Computed KPIs ───────────────────────────────────
const totalBilled = computed(() =>
    financeStore.performance.reduce((s, p) => s + Number(p.total_billed), 0)
)
const totalReceived = computed(() =>
    financeStore.performance.reduce((s, p) => s + Number(p.total_received), 0)
)
const overallSuccess = computed(() => {
    if (totalBilled.value === 0) return 0
    return (totalReceived.value / totalBilled.value) * 100
})
const totalCommission = computed(() =>
    financeStore.performance.reduce((s, p) => s + Number(p.commission_due), 0)
)
const totalOpen = computed(() => totalBilled.value - totalReceived.value)

const monthLabel = computed(() => {
    const parts = currentMonth.value.split('-')
    const y = parts[0] || ''
    const m = parts[1] || '01'
    const months = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    return `${months[parseInt(m)] || ''} ${y}`
})
</script>

<template>
  <div class="fade-up">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-7">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Financeiro</h1>
        <p class="text-gray-500 text-sm mt-0.5">Indicadores de eficiência e comissionamento — {{ monthLabel }}</p>
      </div>
      <div class="flex items-center gap-3">
        <input v-model="currentMonth" type="month"
          class="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
      </div>
    </div>

    <div v-if="loading" class="space-y-7">
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <SkeletonLoader v-for="i in 5" :key="i" class="h-24 !rounded-xl" />
      </div>
      <SkeletonLoader class="h-40 !rounded-xl" />
      <SkeletonLoader class="h-64 !rounded-xl" />
    </div>

    <div v-else-if="financeStore.performance.length === 0" class="py-10">
      <EmptyState
        title="Nenhum dado financeiro encontrado"
        description="Não há registros de faturamento ou comissionamento para este período."
      />
    </div>

    <div v-else class="space-y-7">

      <!-- ═══ KPI Cards ═══ -->
      <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div class="card p-5">
          <p class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Total Faturado</p>
          <p class="text-xl font-bold text-gray-800 mt-1">{{ fmCurrency(totalBilled) }}</p>
        </div>

        <div class="card p-5 border-l-4 border-l-green-500">
          <p class="text-[10px] text-green-600 font-bold uppercase tracking-widest">Total Recebido</p>
          <p class="text-xl font-bold text-green-700 mt-1">{{ fmCurrency(totalReceived) }}</p>
        </div>

        <div class="card p-5 border-l-4 border-l-amber-400">
          <p class="text-[10px] text-amber-600 font-bold uppercase tracking-widest">Em Aberto</p>
          <p class="text-xl font-bold text-amber-700 mt-1">{{ fmCurrency(totalOpen) }}</p>
        </div>

        <div class="card p-5 border-l-4 border-l-blue-500">
          <p class="text-[10px] text-blue-500 font-bold uppercase tracking-widest">Taxa de Sucesso</p>
          <p class="text-xl font-bold text-blue-700 mt-1">{{ fmPct(overallSuccess) }}</p>
        </div>

        <div class="card p-5 border-l-4 border-l-purple-500">
          <p class="text-[10px] text-purple-500 font-bold uppercase tracking-widest">Comissão Total</p>
          <p class="text-xl font-bold text-purple-700 mt-1">{{ fmCurrency(totalCommission) }}</p>
        </div>
      </div>

      <!-- ═══ Commission detail card ═══ -->
      <div v-if="financeStore.commission" class="card p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-bold text-gray-800">
            Comissão — {{ financeStore.commission.condominium_name }}
          </h2>
          <span class="px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-xs font-bold">
            {{ commTypeLabel[financeStore.commission.commission_type] || financeStore.commission.commission_type }}
          </span>
        </div>

        <div class="grid grid-cols-3 gap-5">
          <div class="bg-slate-50 rounded-xl p-4 text-center">
            <p class="text-[9px] text-gray-400 font-bold uppercase tracking-widest">Valor/Taxa</p>
            <p class="text-lg font-bold text-gray-700 mt-1">
              {{ financeStore.commission.commission_type === 'percent'
                  ? `${financeStore.commission.commission_value}%`
                  : fmCurrency(Number(financeStore.commission.commission_value))
              }}
            </p>
          </div>
          <div class="bg-green-50 rounded-xl p-4 text-center">
            <p class="text-[9px] text-green-600 font-bold uppercase tracking-widest">Recebido (ERP)</p>
            <p class="text-lg font-bold text-green-700 mt-1">{{ fmCurrency(Number(financeStore.commission.total_received)) }}</p>
          </div>
          <div class="bg-purple-50 rounded-xl p-4 text-center">
            <p class="text-[9px] text-purple-600 font-bold uppercase tracking-widest">Comissão Devida</p>
            <p class="text-lg font-bold text-purple-700 mt-1">{{ fmCurrency(Number(financeStore.commission.commission_due)) }}</p>
          </div>
        </div>

        <div v-if="Number(financeStore.commission.total_received) === 0" class="mt-4 flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3">
          <svg class="w-4 h-4 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
          <span class="text-xs text-amber-700 font-medium">Nenhum pagamento confirmado pela Retaguarda — sincronize para atualizar.</span>
        </div>
      </div>

      <!-- ═══ Performance table ═══ -->
      <div class="card">
        <div class="p-5 border-b border-gray-100">
          <h2 class="text-base font-bold text-gray-800">Performance por Condomínio</h2>
          <p class="text-xs text-gray-400 mt-0.5">{{ monthLabel }} — {{ auth.isAdmin ? 'Visão administrativa' : 'Seus condomínios' }}</p>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-slate-50 border-b border-gray-100">
              <tr>
                <th class="text-left px-5 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Condomínio</th>
                <th class="text-right px-4 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Faturado</th>
                <th class="text-right px-4 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Recebido</th>
                <th class="text-center px-4 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Taxa</th>
                <th class="text-right px-5 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Comissão</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in financeStore.performance" :key="item.condominium_id"
                class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                <td class="px-5 py-3 font-semibold text-gray-800">{{ item.condominium_name }}</td>
                <td class="px-4 py-3 text-right text-gray-600">{{ fmCurrency(Number(item.total_billed)) }}</td>
                <td class="px-4 py-3 text-right font-semibold text-green-700">{{ fmCurrency(Number(item.total_received)) }}</td>
                <td class="px-4 py-3 text-center">
                  <span :class="Number(item.success_rate) >= 80 ? 'text-green-700 bg-green-50' : Number(item.success_rate) >= 50 ? 'text-amber-700 bg-amber-50' : 'text-red-600 bg-red-50'"
                    class="inline-flex px-2.5 py-0.5 rounded-full text-xs font-bold">
                    {{ fmPct(Number(item.success_rate)) }}
                  </span>
                </td>
                <td class="px-5 py-3 text-right font-semibold text-purple-700">{{ fmCurrency(Number(item.commission_due)) }}</td>
              </tr>
            </tbody>
            <tfoot class="bg-slate-800 text-white">
              <tr>
                <td class="px-5 py-3 font-bold text-sm">Total</td>
                <td class="px-4 py-3 text-right font-bold text-sm">{{ fmCurrency(totalBilled) }}</td>
                <td class="px-4 py-3 text-right font-bold text-sm">{{ fmCurrency(totalReceived) }}</td>
                <td class="px-4 py-3 text-center font-bold text-sm">{{ fmPct(overallSuccess) }}</td>
                <td class="px-5 py-3 text-right font-bold text-sm">{{ fmCurrency(totalCommission) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
