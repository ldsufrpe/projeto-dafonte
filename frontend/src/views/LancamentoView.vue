<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { useCondominiumStore } from '@/stores/condominium'
import { useBillingStore, type BillingRow } from '@/stores/billing'
import apiClient from '@/api/client'
import EvidenceUpload from '@/components/EvidenceUpload.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const condoStore = useCondominiumStore()
const billing = useBillingStore()

// Dynamic table height — fills remaining viewport below the table card
const tableWrapperRef = ref<HTMLElement | null>(null)
const tableMaxHeight = ref('500px')

function updateTableHeight() {
  const el = tableWrapperRef.value
  if (!el) return
  const top = el.getBoundingClientRect().top
  tableMaxHeight.value = `${Math.max(300, window.innerHeight - top - 24)}px`
}

onMounted(() => {
  nextTick(updateTableHeight)
  window.addEventListener('resize', updateTableHeight)
})

// Month selector
const now = new Date()
const currentMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)

function prevMonth() {
  const [y, m] = currentMonth.value.split('-').map(Number)
  const d = new Date(y, m - 2, 1)
  currentMonth.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
function nextMonth() {
  const [y, m] = currentMonth.value.split('-').map(Number)
  const d = new Date(y, m, 1)
  currentMonth.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
function monthLabel(ym: string): string {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })
}
const isFutureMonth = ref(false)
watch(currentMonth, (val) => {
  const [y, m] = val.split('-').map(Number)
  isFutureMonth.value = new Date(y, m - 1, 1) > new Date(now.getFullYear(), now.getMonth(), 1)
})

// Editing state
const editingResident = ref<number | null>(null)
const editForm = ref({ name: '', cpf_masked: '', phone: '' })
const editErrors = ref<string[]>([])

// Load data when condo or month changes
async function loadGrid() {
  const condoId = condoStore.activeCondominiumId
  if (!condoId) return
  await billing.fetchGrid(condoId, currentMonth.value)
}

watch([() => condoStore.activeCondominiumId, currentMonth], async () => {
  await loadGrid()
  nextTick(updateTableHeight)
}, { immediate: true })

// Quantity change handler
async function onQuantityChange(itemId: number, event: Event) {
  const input = event.target as HTMLInputElement
  const qty = Math.max(0, parseInt(input.value) || 0)
  input.value = String(qty)
  await billing.updateQuantity(itemId, qty)
}

// ── Resident editing ──────────────────────────────────────────────────

function isMaskedCpf(cpf: string): boolean {
  return cpf.includes('*')
}

function validateCpf(cpf: string): boolean {
  if (!cpf || isMaskedCpf(cpf)) return true
  const digits = cpf.replace(/[^\d]/g, '')
  if (digits.length !== 11 || /^(\d)\1{10}$/.test(digits)) return false
  let s1 = 0
  for (let i = 0; i < 9; i++) s1 += parseInt(digits[i] ?? '0') * (10 - i)
  let d1 = 11 - (s1 % 11); if (d1 >= 10) d1 = 0
  let s2 = 0
  for (let i = 0; i < 10; i++) s2 += parseInt(digits[i] ?? '0') * (11 - i)
  let d2 = 11 - (s2 % 11); if (d2 >= 10) d2 = 0
  return parseInt(digits[9] ?? '0') === d1 && parseInt(digits[10] ?? '0') === d2
}

function validatePhone(phone: string): boolean {
  if (!phone) return true
  const digits = phone.replace(/[^\d]/g, '')
  return digits.length === 10 || digits.length === 11
}

function startEditResident(row: BillingRow) {
  editingResident.value = row.billing_id
  editErrors.value = []
  editForm.value = {
    name: row.resident.name || '',
    cpf_masked: row.resident.cpf_masked || '',
    phone: row.resident.phone || '',
  }
}

async function saveResident(billingId: number) {
  editErrors.value = []
  const errs: string[] = []
  if (editForm.value.cpf_masked && !validateCpf(editForm.value.cpf_masked))
    errs.push('CPF inválido. Verifique os dígitos verificadores.')
  if (editForm.value.phone && !validatePhone(editForm.value.phone))
    errs.push('Telefone inválido. Informe 10 ou 11 dígitos (ex: (82) 99999-9999).')
  if (errs.length) { editErrors.value = errs; return }
  await billing.updateResident(billingId, editForm.value)
  editingResident.value = null
}

function cancelEdit() {
  editingResident.value = null
  editErrors.value = []
}

// ── Import residents modal ────────────────────────────────────────────

interface ImportWarning { row: number; unit: string; name: string; warnings: string[] }
interface ImportError   { row: number; unit: string; error: string }
interface ImportResult  {
  imported: number
  warnings_count: number
  errors_count: number
  warnings: ImportWarning[]
  errors: ImportError[]
}

const showImportModal = ref(false)
const importFile = ref<File | null>(null)
const importLoading = ref(false)
const importResult = ref<ImportResult | null>(null)
const importError = ref('')

function openImportModal() {
  showImportModal.value = true
  importFile.value = null
  importResult.value = null
  importError.value = ''
}

function closeImportModal() {
  showImportModal.value = false
  if (importResult.value?.imported) loadGrid()
}

async function runImport() {
  if (!importFile.value || !condoStore.activeCondominiumId) return
  importLoading.value = true
  importError.value = ''
  importResult.value = null
  const fd = new FormData()
  fd.append('file', importFile.value)
  try {
    const { data } = await apiClient.post<ImportResult>(
      `/condominiums/${condoStore.activeCondominiumId}/residents/import`, fd
    )
    importResult.value = data
  } catch (e: any) {
    importError.value = e.response?.data?.detail || 'Erro ao importar'
  } finally {
    importLoading.value = false
  }
}

// ── Import consumption modal ──────────────────────────────────────────

interface ConsumptionImportResult { updated: number; skipped: number; errors_count: number; errors: { row: number; unit: string; error: string }[] }
const showConsumptionModal = ref(false)
const consumptionFile = ref<File | null>(null)
const consumptionLoading = ref(false)
const consumptionResult = ref<ConsumptionImportResult | null>(null)
const consumptionError = ref('')

function openConsumptionModal() {
  showConsumptionModal.value = true
  consumptionFile.value = null
  consumptionResult.value = null
  consumptionError.value = ''
}

function downloadConsumptionTemplate() {
  const rows = billing.rows
  if (!rows.length) return
  // Derive product columns from the first row's items (same for all rows)
  const productCodes = rows[0].items.map(i => i.erp_product_code)
  const header = ['unidade', ...productCodes].join(',')
  const lines = rows.map(r => [r.unit_code, ...r.items.map(() => '0')].join(','))
  const csv = '\uFEFF' + [header, ...lines].join('\r\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `consumo_${currentMonth.value}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
function closeConsumptionModal() {
  showConsumptionModal.value = false
  if (consumptionResult.value?.updated) loadGrid()
}
async function runConsumptionImport() {
  if (!consumptionFile.value || !condoStore.activeCondominiumId) return
  consumptionLoading.value = true
  consumptionError.value = ''
  consumptionResult.value = null
  const fd = new FormData()
  fd.append('file', consumptionFile.value)
  try {
    const { data } = await apiClient.post<ConsumptionImportResult>(
      `/billing/${condoStore.activeCondominiumId}/${currentMonth.value}/import-consumption`, fd
    )
    consumptionResult.value = data
  } catch (e: any) {
    consumptionError.value = e.response?.data?.detail || 'Erro ao importar consumo'
  } finally {
    consumptionLoading.value = false
  }
}

// Submit billing
async function handleSubmit() {
  const condoId = condoStore.activeCondominiumId
  if (!condoId) return
  if (!confirm('Deseja finalizar o faturamento e enviar à Retaguarda?')) return
  await billing.submitBilling(condoId, currentMonth.value)
}

// Status helpers
const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: 'Em edição', color: 'text-gray-600', bg: 'bg-gray-100' },
  pending_submission: { label: 'Pronto', color: 'text-amber-700', bg: 'bg-amber-50' },
  submitted: { label: 'Enviado', color: 'text-blue-700', bg: 'bg-blue-50' },
  open: { label: 'Em Aberto', color: 'text-amber-700', bg: 'bg-amber-50' },
  paid: { label: 'Pago', color: 'text-emerald-700', bg: 'bg-emerald-50' },
  no_consumption: { label: 'Sem Consumo', color: 'text-gray-500', bg: 'bg-gray-50' },
}

function rowClass(row: BillingRow): string {
  if (row.status === 'paid') return 'bg-emerald-50/40'
  if (row.status === 'open') return 'bg-amber-50/40'
  if (row.status === 'no_consumption') return 'bg-gray-50/40'
  return ''
}

function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}
</script>

<template>
  <div class="fade-up">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
      <h1 class="text-base font-bold text-gray-900">Lançamento de Consumo</h1>
      <div class="flex items-center gap-2 flex-wrap">
        <!-- Importar Moradores -->
        <button v-if="condoStore.activeCondominiumId" @click="openImportModal"
          class="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
          title="Importar lista de moradores via CSV">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20H5a2 2 0 01-2-2V6a2 2 0 012-2h7m5 0v4m0 0l-3-3m3 3l3-3M9 12h6m-6 4h4"/>
          </svg>
          Moradores
        </button>
        <!-- Importar Consumo -->
        <button v-if="condoStore.activeCondominiumId" @click="openConsumptionModal"
          class="inline-flex items-center gap-2 px-3 py-2 border border-blue-300 rounded-lg text-sm font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 transition-colors"
          title="Importar consumo via CSV — útil para migração de meses anteriores">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"/>
          </svg>
          Importar Consumo
        </button>
        <!-- Navegação de mês -->
        <div class="flex items-center gap-1 bg-white border border-gray-300 rounded-lg overflow-hidden">
          <button @click="prevMonth" class="px-2 py-2 hover:bg-gray-100 transition-colors text-gray-600" title="Mês anterior">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
          </button>
          <input v-model="currentMonth" type="month"
            class="px-2 py-1.5 text-sm focus:ring-0 border-0 focus:outline-none w-36 text-center"/>
          <button @click="nextMonth" class="px-2 py-2 hover:bg-gray-100 transition-colors text-gray-600" title="Próximo mês">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
          </button>
        </div>
        <span v-if="isFutureMonth" class="text-xs text-amber-600 font-medium bg-amber-50 px-2 py-1 rounded-lg border border-amber-200">
          Mês futuro
        </span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="billing.loading" class="space-y-4 py-6">
      <div class="flex gap-3 mb-4 flex-wrap">
        <SkeletonLoader class="w-24 h-8 !rounded-lg" />
        <SkeletonLoader class="w-24 h-8 !rounded-lg" />
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden p-4">
        <SkeletonLoader v-for="i in 8" :key="i" class="w-full h-12 mb-2 !rounded" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="billing.error" class="card p-6 border-red-200 bg-red-50">
      <p class="text-red-700 text-sm font-medium">{{ billing.error }}</p>
    </div>

    <!-- No condominium selected -->
    <div v-else-if="!condoStore.activeCondominiumId" class="py-12">
      <EmptyState
        title="Nenhum condomínio selecionado"
        description="Por favor, selecione um condomínio no menu principal para visualizar e registrar os lançamentos de consumo."
      />
    </div>

    <!-- Grid -->
    <template v-else-if="billing.grid">
      <!-- Submit result banner -->
      <div v-if="billing.submitResult" class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2">
        <svg class="w-5 h-5 text-blue-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span class="text-sm text-blue-700">{{ billing.submitResult }}</span>
      </div>

      <!-- Summary bar (above table) -->
      <div class="mb-2 flex flex-wrap items-center gap-2">
        <div class="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-1.5">
          <span class="text-xs text-emerald-600">Arrecadado</span>
          <span class="text-sm font-bold text-emerald-700">{{ formatCurrency(billing.summary?.total_arrecadado ?? 0) }}</span>
        </div>
        <div class="flex items-center gap-1.5 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5">
          <span class="text-xs text-amber-600">Em Aberto</span>
          <span class="text-sm font-bold text-amber-700">{{ formatCurrency(billing.summary?.total_em_aberto ?? 0) }}</span>
        </div>
        <div class="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
          <span class="text-xs text-slate-500">Total Faturado</span>
          <span class="text-sm font-bold text-slate-700">{{ formatCurrency(billing.summary?.total_faturado ?? 0) }}</span>
        </div>
        <button
          @click="handleSubmit"
          :disabled="!billing.canSubmit || billing.submitting"
          class="ml-auto px-4 py-1.5 bg-blue-600 text-white rounded-lg font-semibold text-sm hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed shadow-sm flex items-center gap-2"
        >
          <div v-if="billing.submitting" class="animate-spin w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full"></div>
          <template v-else>
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
            </svg>
            Finalizar Faturamento
          </template>
        </button>
      </div>

      <!-- Table -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div ref="tableWrapperRef" class="overflow-auto" :style="{ maxHeight: tableMaxHeight }">
          <table class="w-full text-sm">
            <!-- Header -->
            <thead class="sticky top-0 z-20">
              <tr class="bg-white border-b-2 border-gray-100 text-xs uppercase tracking-wider text-gray-500 shadow-sm">
                <th class="px-3 py-3 text-left font-semibold sticky left-0 bg-white z-30">Apto</th>
                <th class="px-3 py-3 text-left font-semibold">CPF</th>
                <th class="px-3 py-3 text-left font-semibold">Nome</th>
                <th class="px-3 py-3 text-left font-semibold">Tel</th>
                <th v-for="p in billing.products" :key="p.id"
                  class="px-3 py-3 text-center font-semibold whitespace-nowrap">
                  {{ p.name.replace('Galão ', '').replace('INDAIÁ', 'IND').replace('IAIÁ', 'IAI') }}
                  <br><span class="text-[10px] font-normal text-gray-400">{{ formatCurrency(p.unit_price) }}</span>
                </th>
                <th class="px-3 py-3 text-right font-semibold">Total</th>
                <th class="px-3 py-3 text-center font-semibold">Status</th>
                <th class="px-3 py-3 text-center font-semibold">Ações</th>
              </tr>
            </thead>

            <!-- Body -->
            <tbody class="divide-y divide-gray-100">
              <tr v-for="row in billing.rows" :key="row.billing_id"
                :class="[rowClass(row), 'hover:bg-gray-50/80 transition-colors']">

                <!-- Apto -->
                <td class="px-3 py-2 font-mono font-semibold text-gray-800 sticky left-0 bg-inherit z-10 whitespace-nowrap">
                  {{ row.unit_code }}
                </td>

                <!-- CPF (editable) -->
                <td class="px-3 py-2">
                  <template v-if="editingResident === row.billing_id">
                    <input v-model="editForm.cpf_masked"
                      :class="editErrors.some(e => e.includes('CPF')) ? 'border-red-400' : 'border-gray-300'"
                      class="w-28 px-1.5 py-1 border rounded text-xs" placeholder="CPF" />
                  </template>
                  <template v-else>
                    <span class="text-xs text-gray-500">{{ row.resident.cpf_masked || '—' }}</span>
                  </template>
                </td>

                <!-- Nome (editable) -->
                <td class="px-3 py-2 max-w-[180px]">
                  <template v-if="editingResident === row.billing_id">
                    <div>
                      <input v-model="editForm.name" class="w-full px-1.5 py-1 border border-gray-300 rounded text-xs" placeholder="Nome" />
                      <!-- Validation errors shown under Nome (widest cell) -->
                      <div v-if="editErrors.length" class="mt-1 space-y-0.5">
                        <p v-for="e in editErrors" :key="e" class="text-[10px] text-red-600 leading-tight">{{ e }}</p>
                      </div>
                    </div>
                  </template>
                  <template v-else>
                    <div class="flex items-center gap-1">
                      <span class="text-gray-700 truncate text-xs">{{ row.resident.name || '—' }}</span>
                      <span v-if="!row.resident.name && row.has_consumption"
                        class="shrink-0 px-1.5 py-0.5 text-[10px] font-bold bg-amber-100 text-amber-700 rounded">
                        NOVO
                      </span>
                    </div>
                  </template>
                </td>

                <!-- Tel (editable) -->
                <td class="px-3 py-2">
                  <template v-if="editingResident === row.billing_id">
                    <input v-model="editForm.phone"
                      :class="editErrors.some(e => e.includes('Telefone')) ? 'border-red-400' : 'border-gray-300'"
                      class="w-28 px-1.5 py-1 border rounded text-xs" placeholder="(82) 99999-9999" />
                  </template>
                  <template v-else>
                    <span class="text-xs text-gray-500">{{ row.resident.phone || '—' }}</span>
                  </template>
                </td>

                <!-- Product quantity columns -->
                <td v-for="p in billing.products" :key="p.id" class="px-2 py-2 text-center">
                  <input
                    type="number"
                    min="0"
                    :value="row.items.find(i => i.product_id === p.id)?.quantity ?? 0"
                    @change="onQuantityChange(row.items.find(i => i.product_id === p.id)!.id, $event)"
                    @wheel.prevent
                    :disabled="row.status === 'submitted' || row.status === 'paid'"
                    class="w-14 px-1.5 py-1 text-center border border-gray-200 rounded text-sm font-mono focus:ring-2 focus:ring-blue-400 focus:border-blue-400 disabled:bg-gray-100 disabled:opacity-50"
                  />
                </td>

                <!-- Total -->
                <td class="px-3 py-2 text-right font-semibold whitespace-nowrap"
                  :class="row.total_amount > 0 ? 'text-gray-900' : 'text-gray-300'">
                  {{ formatCurrency(row.total_amount) }}
                </td>

                <!-- Status badge -->
                <td class="px-3 py-2 text-center">
                  <span :class="[statusConfig[row.status]?.bg, statusConfig[row.status]?.color]"
                    class="inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap">
                    {{ statusConfig[row.status]?.label ?? row.status }}
                  </span>
                </td>

                <!-- Actions -->
                <td class="px-3 py-2 text-center">
                  <template v-if="editingResident === row.billing_id">
                    <button @click="saveResident(row.billing_id)"
                      class="p-1 text-emerald-600 hover:bg-emerald-50 rounded" title="Salvar">
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                      </svg>
                    </button>
                    <button @click="cancelEdit"
                      class="p-1 text-gray-400 hover:bg-gray-100 rounded ml-1" title="Cancelar">
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                      </svg>
                    </button>
                  </template>
                  <template v-else>
                    <div class="flex items-center justify-center gap-1">
                      <button @click="startEditResident(row)"
                        class="p-1 text-gray-500 hover:bg-gray-100 rounded" title="Editar dados do morador">
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
                        </svg>
                      </button>
                      <EvidenceUpload
                        v-if="condoStore.activeCondominiumId"
                        :condominium-id="condoStore.activeCondominiumId"
                        :billing-id="row.billing_id"
                      />
                    </div>
                  </template>
                </td>
              </tr>
            </tbody>

            <!-- Footer totals -->
            <tfoot>
              <tr class="bg-gray-50 border-t-2 border-gray-200 text-xs text-gray-500">
                <td class="px-3 py-2.5 sticky left-0 bg-gray-50 z-10 font-medium uppercase tracking-wider text-gray-400">
                  {{ billing.summary?.total_units ?? 0 }} unidades
                </td>
                <td colspan="3"></td>
                <td v-for="p in billing.products" :key="p.id" class="px-3 py-2.5 text-center">
                  <span class="font-bold text-gray-700">{{ billing.summary?.totals_by_product[p.id] ?? 0 }}</span>
                  <span class="text-gray-400 ml-0.5">un.</span>
                </td>
                <td class="px-3 py-2.5 text-right">
                  <span class="font-bold text-gray-800 text-sm">{{ formatCurrency(billing.summary?.total_faturado ?? 0) }}</span>
                </td>
                <td colspan="2"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

    </template>
  </div>

  <!-- ═══ Import Residents Modal ═══ -->
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="showImportModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
        @click.self="closeImportModal">
        <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col">

          <!-- Modal header -->
          <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 class="text-base font-bold text-gray-900">Importar Moradores</h2>
              <p class="text-xs text-gray-500 mt-0.5">
                CSV ou XLSX — colunas: <code class="bg-gray-100 px-1 rounded">unidade, nome, cpf, telefone</code>
              </p>
            </div>
            <button @click="closeImportModal" class="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <!-- Modal body -->
          <div class="px-6 py-5 overflow-y-auto flex-1 space-y-4">

            <!-- Info notice -->
            <div class="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 space-y-1">
              <p class="font-semibold">Dados usados para cobrança e contato via WhatsApp pela Retaguarda.</p>
              <p>CPF e telefone são validados automaticamente. Linhas com dados inválidos são importadas com aviso.</p>
              <p>CPFs mascarados vindos da Retaguarda (***.***.***-XX) são aceitos sem validação.</p>
            </div>

            <!-- File upload -->
            <div v-if="!importResult">
              <label class="block cursor-pointer">
                <div
                  class="border-2 border-dashed rounded-xl p-6 text-center transition-colors"
                  :class="importFile ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400'"
                  @dragover.prevent
                  @drop.prevent="(e) => { importFile = (e as DragEvent).dataTransfer?.files[0] ?? null }">
                  <svg class="w-8 h-8 mx-auto mb-2 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"/>
                  </svg>
                  <p class="text-sm text-gray-600">
                    {{ importFile ? importFile.name : 'Arraste o arquivo ou clique para selecionar' }}
                  </p>
                  <p v-if="!importFile" class="text-xs text-gray-400 mt-1">Formatos aceitos: .csv, .xlsx</p>
                  <input type="file" accept=".csv,.xlsx" class="hidden"
                    @change="(e) => { importFile = (e.target as HTMLInputElement).files?.[0] ?? null }" />
                </div>
              </label>

              <p v-if="importError" class="mt-2 text-sm text-red-600">{{ importError }}</p>
            </div>

            <!-- Results -->
            <div v-else class="space-y-3">
              <!-- Summary -->
              <div class="grid grid-cols-3 gap-3 text-center">
                <div class="bg-emerald-50 rounded-xl p-3 border border-emerald-200">
                  <p class="text-xl font-bold text-emerald-700">{{ importResult.imported }}</p>
                  <p class="text-xs text-emerald-600">Importados</p>
                </div>
                <div :class="importResult.warnings_count > 0 ? 'bg-amber-50 border-amber-200' : 'bg-gray-50 border-gray-200'"
                  class="rounded-xl p-3 border">
                  <p class="text-xl font-bold" :class="importResult.warnings_count > 0 ? 'text-amber-700' : 'text-gray-400'">
                    {{ importResult.warnings_count }}
                  </p>
                  <p class="text-xs" :class="importResult.warnings_count > 0 ? 'text-amber-600' : 'text-gray-400'">Avisos</p>
                </div>
                <div :class="importResult.errors_count > 0 ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'"
                  class="rounded-xl p-3 border">
                  <p class="text-xl font-bold" :class="importResult.errors_count > 0 ? 'text-red-700' : 'text-gray-400'">
                    {{ importResult.errors_count }}
                  </p>
                  <p class="text-xs" :class="importResult.errors_count > 0 ? 'text-red-600' : 'text-gray-400'">Erros</p>
                </div>
              </div>

              <!-- Warnings list -->
              <div v-if="importResult.warnings.length" class="bg-amber-50 border border-amber-200 rounded-xl p-3">
                <p class="text-xs font-semibold text-amber-700 mb-2">
                  Avisos — dados importados mas com problemas de validação:
                </p>
                <ul class="space-y-1.5 max-h-40 overflow-y-auto text-xs">
                  <li v-for="w in importResult.warnings" :key="w.row" class="text-amber-700">
                    <span class="font-semibold">Linha {{ w.row }} — Unid. {{ w.unit }}</span>
                    <span v-if="w.name" class="text-amber-600"> ({{ w.name }})</span>
                    <ul class="ml-3 mt-0.5 list-disc list-inside text-amber-600">
                      <li v-for="wm in w.warnings" :key="wm">{{ wm }}</li>
                    </ul>
                  </li>
                </ul>
              </div>

              <!-- Errors list -->
              <div v-if="importResult.errors.length" class="bg-red-50 border border-red-200 rounded-xl p-3">
                <p class="text-xs font-semibold text-red-700 mb-2">
                  Erros — linhas não importadas:
                </p>
                <ul class="space-y-1 max-h-40 overflow-y-auto text-xs">
                  <li v-for="e in importResult.errors" :key="e.row" class="text-red-700">
                    <span class="font-semibold">Linha {{ e.row }}</span>
                    <span v-if="e.unit"> — Unid. {{ e.unit }}</span>:
                    {{ e.error }}
                  </li>
                </ul>
              </div>

              <button @click="() => { importResult = null; importFile = null }"
                class="text-xs text-blue-600 hover:text-blue-800 font-medium">
                ← Importar outro arquivo
              </button>
            </div>
          </div>

          <!-- Modal footer -->
          <div class="px-6 py-4 border-t border-gray-100 flex items-center justify-between">
            <button @click="closeImportModal"
              class="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              {{ importResult ? 'Fechar' : 'Cancelar' }}
            </button>
            <button v-if="!importResult"
              @click="runImport"
              :disabled="!importFile || importLoading"
              class="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-2">
              <div v-if="importLoading" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
              <span>{{ importLoading ? 'Importando...' : 'Importar' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- ── Modal: Importar Consumo ── -->
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="showConsumptionModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        @click.self="closeConsumptionModal">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[85vh]">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <div>
              <h2 class="text-base font-bold text-gray-900">Importar Consumo</h2>
              <p class="text-xs text-gray-500 mt-0.5">{{ monthLabel(currentMonth) }}</p>
            </div>
            <button @click="closeConsumptionModal" class="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>

          <div class="px-6 py-4 overflow-y-auto flex-1">
            <div v-if="!consumptionResult">
              <!-- Download template -->
              <div class="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                <div class="flex items-start justify-between gap-3">
                  <div class="text-xs text-emerald-700">
                    <p class="font-semibold mb-0.5">Baixe o template com os códigos exatos do sistema</p>
                    <p>Preencha apenas as quantidades e importe de volta. Evita erros de código de unidade.</p>
                  </div>
                  <button @click="downloadConsumptionTemplate" :disabled="!billing.rows.length"
                    class="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white text-xs font-semibold rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors">
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                    </svg>
                    Baixar Template
                  </button>
                </div>
              </div>

              <!-- Formato -->
              <div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 space-y-1">
                <p class="font-semibold">Formato esperado (CSV):</p>
                <code class="block bg-white border border-blue-200 rounded px-2 py-1.5 text-blue-800 font-mono text-xs whitespace-pre">unidade,INDAIA20LT,INDAIA10L,IAIA20L
TB-101,2,0,0
TB-201,5,3,0</code>
                <p class="mt-1">Use os códigos exatos do sistema. Deixe 0 para produtos sem consumo.</p>
              </div>

              <!-- Drop zone -->
              <label class="block cursor-pointer">
                <div class="border-2 border-dashed rounded-xl p-6 text-center transition-colors"
                  :class="consumptionFile ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400'"
                  @dragover.prevent @drop.prevent="(e) => { consumptionFile = (e as DragEvent).dataTransfer?.files[0] ?? null }">
                  <svg class="w-8 h-8 mx-auto mb-2" :class="consumptionFile ? 'text-blue-500' : 'text-gray-400'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"/>
                  </svg>
                  <p class="text-sm" :class="consumptionFile ? 'text-blue-700 font-medium' : 'text-gray-500'">
                    {{ consumptionFile ? consumptionFile.name : 'Arraste o CSV ou clique para selecionar' }}
                  </p>
                  <input type="file" accept=".csv" class="hidden" @change="(e) => { consumptionFile = (e.target as HTMLInputElement).files?.[0] ?? null }"/>
                </div>
              </label>
              <p v-if="consumptionError" class="mt-2 text-sm text-red-600">{{ consumptionError }}</p>
            </div>

            <!-- Result -->
            <div v-else class="space-y-3">
              <div class="p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
                <p class="text-sm font-semibold text-emerald-700">{{ consumptionResult.updated }} unidades atualizadas</p>
                <p v-if="consumptionResult.skipped" class="text-xs text-gray-500 mt-1">{{ consumptionResult.skipped }} unidades sem alteração (consumo igual)</p>
              </div>
              <div v-if="consumptionResult.errors_count" class="p-4 bg-red-50 border border-red-200 rounded-xl">
                <p class="text-sm font-semibold text-red-700 mb-2">{{ consumptionResult.errors_count }} erros:</p>
                <ul class="space-y-1">
                  <li v-for="e in consumptionResult.errors" :key="e.row" class="text-xs text-red-600">
                    Linha {{ e.row }} ({{ e.unit || '—' }}): {{ e.error }}
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button @click="closeConsumptionModal" class="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
              {{ consumptionResult ? 'Fechar' : 'Cancelar' }}
            </button>
            <button v-if="!consumptionResult" @click="runConsumptionImport"
              :disabled="!consumptionFile || consumptionLoading"
              class="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2 transition-colors">
              <div v-if="consumptionLoading" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
              {{ consumptionLoading ? 'Importando...' : 'Importar' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
