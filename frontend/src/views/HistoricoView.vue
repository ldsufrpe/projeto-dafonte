<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useCondominiumStore } from '@/stores/condominium'
import { useAuthStore } from '@/stores/auth'
import apiClient from '@/api/client'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

interface BillingItemRow {
  product_name: string
  quantity: number
  unit_price: number
}

interface BillingRow {
  billing_id: number
  unit_code: string
  resident_name: string | null
  status: string
  total_amount: number
  evidence_count: number
  items: BillingItemRow[]
}

interface MonthSummary {
  reference_month: string
  total_billed: number
  total_received: number
  total_units: number
  qty_per_product: Record<string, number>
  status_counts: Record<string, number>
  is_current: boolean
}

interface MonthDetail {
  summary: MonthSummary
  billings: BillingRow[]
}

const condoStore = useCondominiumStore()
const auth = useAuthStore()

const months = ref<MonthSummary[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const drawerOpen = ref(false)
const drawerLoading = ref(false)
const selectedDetail = ref<MonthDetail | null>(null)

const confirmReopen = ref(false)
const reopenLoading = ref(false)
const reopenError = ref<string | null>(null)

// ── Status config ─────────────────────────────────────────────────────
const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: 'Em edição', color: 'text-gray-600', bg: 'bg-gray-100' },
  pending_submission: { label: 'Pronto', color: 'text-amber-700', bg: 'bg-amber-50' },
  submitted: { label: 'Enviado', color: 'text-blue-700', bg: 'bg-blue-50' },
  open: { label: 'Em Aberto', color: 'text-amber-700', bg: 'bg-amber-50' },
  paid: { label: 'Pago', color: 'text-emerald-700', bg: 'bg-emerald-50' },
  no_consumption: { label: 'Sem Consumo', color: 'text-gray-500', bg: 'bg-gray-50' },
}

function statusLabel(s: string): string {
  return statusConfig[s]?.label ?? s
}

function statusClasses(s: string): string {
  const cfg = statusConfig[s] ?? { color: 'text-gray-600', bg: 'bg-gray-100' }
  return `${cfg.color} ${cfg.bg} text-xs font-medium px-2 py-0.5 rounded-full`
}

// ── Helpers ───────────────────────────────────────────────────────────
function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatMonth(ym: string): string {
  if (!ym) return ''
  const [year, month] = ym.split('-')
  const names = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
  return `${names[parseInt(month || '1') - 1]} ${year}`
}

function formatMonthFull(ym: string): string {
  if (!ym) return ''
  const [year, month] = ym.split('-')
  const names = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
  return `${names[parseInt(month || '1') - 1]} ${year}`
}

function dominantStatus(summary: MonthSummary): string {
  const c = summary.status_counts
  if ((c['paid'] ?? 0) === summary.total_units) return 'paid'
  if ((c['open'] ?? 0) > 0 || (c['submitted'] ?? 0) > 0) return 'open'
  if ((c['pending_submission'] ?? 0) > 0) return 'pending_submission'
  return 'draft'
}

// ── Data loading ──────────────────────────────────────────────────────
async function loadMonths() {
  const condoId = condoStore.activeCondominiumId
  if (!condoId) return
  loading.value = true
  error.value = null
  try {
    const { data } = await apiClient.get<MonthSummary[]>(`/history/${condoId}`)
    months.value = data
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    error.value = msg || 'Erro ao carregar histórico'
  } finally {
    loading.value = false
  }
}

async function openDrawer(month: string) {
  const condoId = condoStore.activeCondominiumId
  if (!condoId) return
  drawerOpen.value = true
  drawerLoading.value = true
  selectedDetail.value = null
  confirmReopen.value = false
  reopenError.value = null
  try {
    const { data } = await apiClient.get<MonthDetail>(`/history/${condoId}/${month}`)
    selectedDetail.value = data
  } catch {
    drawerOpen.value = false
  } finally {
    drawerLoading.value = false
  }
}

function closeDrawer() {
  drawerOpen.value = false
  confirmReopen.value = false
  reopenError.value = null
}

async function reopenMonth() {
  if (!selectedDetail.value) return
  const condoId = condoStore.activeCondominiumId
  if (!condoId) return
  reopenLoading.value = true
  reopenError.value = null
  try {
    await apiClient.post(
      `/history/${condoId}/${selectedDetail.value.summary.reference_month}/reopen`
    )
    closeDrawer()
    await loadMonths()
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    reopenError.value = msg || 'Erro ao reabrir mês'
  } finally {
    reopenLoading.value = false
  }
}

// ── CSV Export ────────────────────────────────────────────────────────
function exportDetailCsv(detail: MonthDetail) {
  const rows: string[] = [
    ['Unidade', 'Morador', 'Status', 'Valor Total', 'Evidências'].join(';')
  ]
  for (const b of detail.billings) {
    rows.push(
      [b.unit_code, b.resident_name ?? '', statusLabel(b.status),
       formatCurrency(b.total_amount), String(b.evidence_count)].join(';')
    )
  }
  triggerCsvDownload('\ufeff' + rows.join('\r\n'), `historico-${detail.summary.reference_month}.csv`)
}

function exportMonthsCsv() {
  const rows: string[] = [
    ['Mês', 'Faturado', 'Arrecadado', 'Unidades'].join(';')
  ]
  for (const m of months.value) {
    rows.push(
      [formatMonth(m.reference_month), formatCurrency(m.total_billed),
       formatCurrency(m.total_received), String(m.total_units)].join(';')
    )
  }
  const name = condoStore.activeCondominium?.name ?? 'condo'
  triggerCsvDownload('\ufeff' + rows.join('\r\n'), `historico-${name}.csv`)
}

function triggerCsvDownload(csv: string, filename: string) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

watch(() => condoStore.activeCondominiumId, () => loadMonths(), { immediate: true })
</script>

<template>
  <div class="fade-up">
    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-4 mb-7">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Histórico de Lançamentos</h1>
        <p class="text-gray-500 text-sm mt-0.5">
          {{ condoStore.activeCondominium?.name }} — Consulta de meses anteriores
        </p>
      </div>
      <button
        v-if="months.length > 0"
        @click="exportMonthsCsv"
        class="btn-outline flex items-center gap-1.5 text-sm"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
        </svg>
        Exportar CSV
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4 py-4">
      <SkeletonLoader v-for="i in 4" :key="i" class="h-16 w-full !rounded-xl" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card p-8 text-center text-red-500 text-sm">{{ error }}</div>

    <!-- Empty state -->
    <div v-else-if="months.length === 0" class="py-12">
      <EmptyState
        title="Nenhum histórico encontrado"
        description="Os lançamentos aparecerão aqui após o primeiro mês de operação."
      />
    </div>

    <!-- Months table -->
    <div v-else class="card overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200 bg-gray-50/60">
            <th class="text-left px-5 py-3 font-medium text-gray-600">Mês</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600">Faturado</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600">Arrecadado</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600">Unidades</th>
            <th class="text-center px-5 py-3 font-medium text-gray-600">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="m in months"
            :key="m.reference_month"
            @click="openDrawer(m.reference_month)"
            class="border-b border-gray-100 last:border-0 hover:bg-blue-50/40 cursor-pointer transition-colors"
            :class="{ 'bg-blue-50/20': m.is_current }"
          >
            <td class="px-5 py-3 font-medium text-gray-800">
              {{ formatMonth(m.reference_month) }}
              <span
                v-if="m.is_current"
                class="ml-2 text-xs font-medium text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded-full"
              >Atual</span>
            </td>
            <td class="px-4 py-3 text-right text-gray-700">{{ formatCurrency(m.total_billed) }}</td>
            <td class="px-4 py-3 text-right text-gray-700">{{ formatCurrency(m.total_received) }}</td>
            <td class="px-4 py-3 text-right text-gray-500">{{ m.total_units }}</td>
            <td class="px-5 py-3 text-center">
              <span :class="statusClasses(dominantStatus(m))">
                {{ statusLabel(dominantStatus(m)) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Drawer -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-opacity duration-200"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-150"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div v-if="drawerOpen" class="fixed inset-0 bg-black/30 z-40" @click="closeDrawer" />
      </Transition>

      <Transition
        enter-active-class="transition-transform duration-250 ease-out"
        enter-from-class="translate-x-full"
        enter-to-class="translate-x-0"
        leave-active-class="transition-transform duration-200 ease-in"
        leave-from-class="translate-x-0"
        leave-to-class="translate-x-full"
      >
        <div
          v-if="drawerOpen"
          class="fixed right-0 top-0 h-full w-full max-w-xl bg-white shadow-2xl z-50 flex flex-col"
        >
          <!-- Drawer header -->
          <div class="flex items-center justify-between px-5 py-4 border-b border-gray-200">
            <div class="flex items-center gap-3">
              <button @click="closeDrawer" class="text-gray-400 hover:text-gray-600 transition-colors">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
                </svg>
              </button>
              <div>
                <h2 class="text-base font-bold text-gray-900">
                  {{ selectedDetail ? formatMonthFull(selectedDetail.summary.reference_month) : '...' }}
                </h2>
                <p v-if="selectedDetail" class="text-xs text-gray-500 mt-0.5">
                  {{ formatCurrency(selectedDetail.summary.total_billed) }} faturado
                  · {{ formatCurrency(selectedDetail.summary.total_received) }} recebido
                </p>
              </div>
            </div>
            <button
              v-if="selectedDetail"
              @click="exportDetailCsv(selectedDetail)"
              class="btn-outline text-xs flex items-center gap-1"
            >
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              CSV
            </button>
          </div>

          <!-- Drawer body -->
          <div class="flex-1 overflow-y-auto">
            <div v-if="drawerLoading" class="p-6 space-y-3">
              <SkeletonLoader v-for="i in 8" :key="i" class="h-12 w-full !rounded-lg" />
            </div>

            <table v-else-if="selectedDetail" class="w-full text-sm">
              <thead>
                <tr class="border-b border-gray-200 bg-gray-50/60 sticky top-0">
                  <th class="text-left px-5 py-3 font-medium text-gray-600">Unid.</th>
                  <th class="text-left px-4 py-3 font-medium text-gray-600">Morador</th>
                  <th class="text-center px-4 py-3 font-medium text-gray-600">Status</th>
                  <th class="text-right px-5 py-3 font-medium text-gray-600">Valor</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="b in selectedDetail.billings"
                  :key="b.billing_id"
                  class="border-b border-gray-100 last:border-0"
                  :class="{
                    'bg-emerald-50/30': b.status === 'paid',
                    'bg-amber-50/30': b.status === 'open',
                  }"
                >
                  <td class="px-5 py-2.5 font-medium text-gray-800">{{ b.unit_code }}</td>
                  <td class="px-4 py-2.5 text-gray-600">
                    {{ b.resident_name ?? '—' }}
                    <span
                      v-if="b.evidence_count > 0"
                      class="ml-1 text-xs text-blue-500"
                      :title="`${b.evidence_count} evidência(s)`"
                    >📎 {{ b.evidence_count }}</span>
                  </td>
                  <td class="px-4 py-2.5 text-center">
                    <span :class="statusClasses(b.status)">{{ statusLabel(b.status) }}</span>
                  </td>
                  <td class="px-5 py-2.5 text-right text-gray-700">{{ formatCurrency(b.total_amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Drawer footer — Admin reopen -->
          <div
            v-if="selectedDetail && auth.isAdmin && !selectedDetail.summary.is_current"
            class="border-t border-gray-200 px-5 py-4"
          >
            <div v-if="!confirmReopen">
              <button
                @click="confirmReopen = true"
                class="w-full text-center text-sm font-medium text-amber-700 border border-amber-300 rounded-lg py-2 hover:bg-amber-50 transition-colors"
              >
                Reabrir este mês para edição
              </button>
            </div>

            <div v-else class="space-y-3">
              <p class="text-sm text-gray-700">
                Todos os lançamentos de
                <strong>{{ formatMonthFull(selectedDetail.summary.reference_month) }}</strong>
                voltarão para rascunho. Esta ação não pode ser desfeita facilmente.
              </p>
              <p v-if="reopenError" class="text-xs text-red-600">{{ reopenError }}</p>
              <div class="flex gap-2">
                <button
                  @click="confirmReopen = false; reopenError = null"
                  class="flex-1 btn-outline text-sm py-2"
                  :disabled="reopenLoading"
                >
                  Cancelar
                </button>
                <button
                  @click="reopenMonth"
                  class="flex-1 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg py-2 transition-colors disabled:opacity-50"
                  :disabled="reopenLoading"
                >
                  {{ reopenLoading ? 'Reabrindo...' : 'Confirmar reabertura' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
