<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Doughnut, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
} from 'chart.js'
import { useCondominiumStore } from '@/stores/condominium'
import { useDashboardStore } from '@/stores/dashboard'
import apiClient from '@/api/client'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title)

interface TrendPoint {
  reference_month: string
  total_billed: number
  total_collected: number
  total_open: number
  default_rate: number
}

interface CommissionData {
  commission_due: number
  total_received: number
}

const condoStore = useCondominiumStore()
const dash = useDashboardStore()

const now = new Date()
const currentMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const isMockMode = ref(false)
const toastMessage = ref('')
const toastVisible = ref(false)
const trend = ref<TrendPoint[]>([])
const commission = ref<CommissionData | null>(null)

function showToast(msg: string) {
  toastMessage.value = msg
  toastVisible.value = true
  setTimeout(() => { toastVisible.value = false }, 3500)
}

async function load() {
  const id = condoStore.activeCondominiumId
  if (!id) return
  await dash.fetchDashboard(id, currentMonth.value)
  try {
    const { data } = await apiClient.get<{ points: TrendPoint[] }>(`/dashboard/trend/${id}`)
    trend.value = data.points ?? []
  } catch { /* optional */ }
  try {
    const { data } = await apiClient.get<CommissionData>(`/finance/commission/${id}/${currentMonth.value}`)
    commission.value = data
  } catch { /* optional */ }
}

onMounted(async () => {
  try {
    const { data } = await apiClient.get('/erp/mode')
    isMockMode.value = data.is_mock
  } catch { /* ignore */ }
})

watch([() => condoStore.activeCondominiumId, currentMonth], () => load(), { immediate: true })

async function handleSync() {
  const id = condoStore.activeCondominiumId
  if (!id) return
  if (isMockMode.value) {
    showToast('Sincronização simulada — Retaguarda não conectada (modo local)')
    return
  }
  const msg = await dash.syncPayments(id, currentMonth.value)
  showToast(msg)
}

function handleExportPDF() {
  window.print()
}

// Chart data
const chartData = computed(() => ({
  labels: ['Pagos', 'Em Aberto'],
  datasets: [{
    data: [dash.data?.qty_paid ?? 0, (dash.data?.qty_open ?? 0) + (dash.data?.qty_submitted ?? 0)],
    backgroundColor: ['#10b981', '#f59e0b'],
    borderWidth: 0,
    hoverOffset: 4,
  }],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { boxWidth: 12, padding: 16 } },
    tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.label}: ${ctx.parsed} unidades` } },
  },
  cutout: '68%',
}

function fmt(v: number) {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatMonth(ym: string): string {
  if (!ym) return ''
  const [year, month] = ym.split('-')
  const names = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
  return `${names[parseInt(month || '1') - 1]}/${year?.slice(2)}`
}

const trendChartData = computed(() => ({
  labels: trend.value.map(p => formatMonth(p.reference_month)),
  datasets: [
    {
      label: 'Faturado',
      data: trend.value.map(p => p.total_billed),
      backgroundColor: '#6366f1bb',
      borderRadius: 4,
    },
    {
      label: 'Arrecadado',
      data: trend.value.map(p => p.total_collected),
      backgroundColor: '#10b981bb',
      borderRadius: 4,
    },
  ],
}))

const trendChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { boxWidth: 12, padding: 16 } },
    title: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
          ` ${ctx.dataset.label}: ${(ctx.parsed.y ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}`,
      },
    },
  },
  scales: {
    x: { grid: { display: false } },
    y: {
      ticks: {
        callback: (v: string | number) =>
          Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }),
      },
    },
  },
}

const medals = ['🥇', '🥈', '🥉', '4', '5']

function defaulterBadge(d: { status: string; days_overdue: number }): { label: string; classes: string } {
  if (d.status === 'submitted') return { label: 'Aguardando Retaguarda', classes: 'bg-blue-100 text-blue-700' }
  if (d.days_overdue > 30) return { label: `Atrasado ${d.days_overdue}d`, classes: 'bg-red-100 text-red-700' }
  if (d.days_overdue > 0) return { label: `Atrasado ${d.days_overdue}d`, classes: 'bg-amber-100 text-amber-700' }
  return { label: 'Em Aberto', classes: 'bg-amber-100 text-amber-700' }
}
</script>

<template>
  <div class="fade-up">
    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p class="text-gray-500 text-sm mt-0.5">
          {{ dash.data?.condominium_name || condoStore.activeCondominium?.name }} — Visão analítica do mês
        </p>
      </div>
      <div class="flex items-center gap-2">
        <input
          v-model="currentMonth"
          type="month"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
        />
        <button
          @click="handleSync"
          :disabled="dash.syncing"
          class="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 shadow-sm"
        >
          <svg class="w-4 h-4" :class="{ 'animate-spin': dash.syncing }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Sincronizar
        </button>
        <button
          @click="handleExportPDF"
          class="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors shadow-sm"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          Exportar PDF
        </button>
      </div>
    </div>

    <!-- Toast notification -->
    <transition name="toast">
      <div v-if="toastVisible"
        class="fixed bottom-6 right-6 z-50 flex items-center gap-3 bg-gray-900 text-white px-5 py-3 rounded-xl shadow-xl text-sm font-medium">
        <svg class="w-4 h-4 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        {{ toastMessage }}
      </div>
    </transition>

    <!-- Loading -->
    <div v-if="dash.loading" class="flex items-center justify-center py-16">
      <div class="animate-spin w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full"></div>
    </div>

    <!-- Error -->
    <div v-else-if="dash.error" class="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm mb-6">
      {{ dash.error }}
    </div>

    <!-- No condo -->
    <div v-else-if="!condoStore.activeCondominiumId" class="text-center py-16 text-gray-400">
      Selecione um condomínio para ver o Dashboard.
    </div>

    <template v-else-if="dash.data">
      <!-- Submitted waiting pill -->
      <div v-if="dash.data.has_submitted_waiting"
        class="mb-5 flex items-center gap-2.5 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
        <svg class="w-4 h-4 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span class="text-sm text-amber-800 font-medium">
          <strong>{{ dash.data.qty_submitted }}</strong> unidade{{ dash.data.qty_submitted !== 1 ? 's' : '' }}
          aguardando confirmação da Retaguarda — clique em Sincronizar para atualizar
        </span>
      </div>

      <!-- KPI Cards -->
      <div class="grid grid-cols-2 gap-4 mb-6" :class="commission ? 'lg:grid-cols-5' : 'lg:grid-cols-4'">
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #10b981">
          <p class="text-xs text-gray-500 font-medium mb-1">Total Arrecadado</p>
          <p class="text-2xl font-bold text-emerald-700">{{ fmt(dash.data.total_collected) }}</p>
          <p class="text-xs text-gray-400 mt-1">{{ dash.data.qty_paid }} unid. pagas</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #f59e0b">
          <p class="text-xs text-gray-500 font-medium mb-1">Inadimplência</p>
          <p class="text-2xl font-bold text-amber-700">{{ dash.data.default_rate }}%</p>
          <p class="text-xs text-gray-400 mt-1">{{ dash.data.qty_open }} unid. em aberto</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #64748b">
          <p class="text-xs text-gray-500 font-medium mb-1">Total em Aberto</p>
          <p class="text-2xl font-bold text-slate-700">{{ fmt(dash.data.total_open) }}</p>
          <p class="text-xs text-gray-400 mt-1">{{ dash.data.qty_open + dash.data.qty_submitted }} unid.</p>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #6366f1">
          <p class="text-xs text-gray-500 font-medium mb-1">Consumo do Mês</p>
          <p class="text-2xl font-bold text-indigo-700">{{ fmt(dash.data.total_billed) }}</p>
          <p class="text-xs text-gray-400 mt-1">{{ dash.data.qty_billed }} unid. faturadas</p>
        </div>
        <div v-if="commission" class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #0ea5e9">
          <p class="text-xs text-gray-500 font-medium mb-1">Comissão do Mês</p>
          <p class="text-2xl font-bold text-sky-700">{{ fmt(commission.commission_due) }}</p>
          <p class="text-xs text-gray-400 mt-1">sobre {{ fmt(commission.total_received) }}</p>
        </div>
      </div>

      <!-- Trend chart -->
      <div v-if="trend.length > 0" class="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-5">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Evolução dos Últimos 6 Meses</h3>
        <div class="h-52">
          <Bar :data="trendChartData" :options="trendChartOptions" />
        </div>
      </div>

      <!-- Middle row: Donut + Top 5 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <!-- Donut chart -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h3 class="text-sm font-semibold text-gray-700 mb-4">Distribuição de Pagamentos</h3>
          <div class="relative h-52">
            <Doughnut
              v-if="dash.data.qty_billed > 0"
              :data="chartData"
              :options="chartOptions"
            />
            <div v-else class="flex items-center justify-center h-full text-gray-400 text-sm">
              Nenhum faturamento no mês
            </div>
            <!-- Center label -->
            <div v-if="dash.data.qty_billed > 0"
              class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <p class="text-2xl font-bold text-gray-800">{{ dash.data.qty_paid }}</p>
              <p class="text-xs text-gray-400">pagos</p>
            </div>
          </div>
        </div>

        <!-- Top 5 -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h3 class="text-sm font-semibold text-gray-700 mb-4">Top 5 Consumidores</h3>
          <div v-if="dash.data.top5.length === 0" class="flex items-center justify-center h-40 text-gray-400 text-sm">
            Nenhum dado disponível
          </div>
          <div v-else class="space-y-3">
            <div v-for="(unit, idx) in dash.data.top5" :key="unit.unit_code" class="flex items-center gap-3">
              <span class="text-lg w-7 text-center shrink-0">{{ medals[idx] }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between mb-1">
                  <div class="min-w-0">
                    <span class="text-xs font-mono font-semibold text-gray-700">{{ unit.unit_code }}</span>
                    <span v-if="unit.resident_name" class="text-xs text-gray-400 ml-1.5 truncate">{{ unit.resident_name }}</span>
                  </div>
                  <span class="text-xs font-semibold text-gray-700 ml-2 shrink-0">{{ fmt(unit.total_amount) }}</span>
                </div>
                <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all"
                    :class="idx === 0 ? 'bg-yellow-400' : idx === 1 ? 'bg-gray-400' : idx === 2 ? 'bg-amber-600' : 'bg-blue-400'"
                    :style="{ width: (dash.data!.top5[0]?.total_amount ?? 0) > 0 ? (unit.total_amount / (dash.data!.top5[0]?.total_amount ?? 1) * 100) + '%' : '0%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Defaulters table -->
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-gray-700">
            Inadimplentes e Pendentes
            <span v-if="dash.data.defaulters.length" class="ml-2 px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs">
              {{ dash.data.defaulters.length }}
            </span>
          </h3>
        </div>
        <div v-if="dash.data.defaulters.length === 0" class="px-5 py-8 text-center text-gray-400 text-sm">
          Nenhuma inadimplência no mês —
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-100 text-xs uppercase text-gray-500 tracking-wider">
                <th class="px-4 py-3 text-left font-semibold">Unidade</th>
                <th class="px-4 py-3 text-left font-semibold">Morador</th>
                <th class="px-4 py-3 text-right font-semibold">Valor</th>
                <th class="px-4 py-3 text-center font-semibold">Situação</th>
                <th class="px-4 py-3 text-center font-semibold">Ação</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-for="d in dash.data.defaulters" :key="d.unit_code"
                class="hover:bg-gray-50 transition-colors">
                <td class="px-4 py-3 font-mono font-semibold text-gray-800">{{ d.unit_code }}</td>
                <td class="px-4 py-3 text-gray-600 max-w-[160px] truncate">{{ d.resident_name || '—' }}</td>
                <td class="px-4 py-3 text-right font-semibold text-gray-800">{{ fmt(d.total_amount) }}</td>
                <td class="px-4 py-3 text-center">
                  <span :class="defaulterBadge(d).classes"
                    class="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap">
                    {{ defaulterBadge(d).label }}
                  </span>
                </td>
                <td class="px-4 py-3 text-center">
                  <button class="px-3 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors border border-blue-200">
                    Acionar
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(10px); }
</style>
