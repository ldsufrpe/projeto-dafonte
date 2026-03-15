<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const condominiumId = Number(route.params.condominiumId)

// Wizard state
const currentStep = ref(1)
const TOTAL_STEPS = 6

// Step results
const importResidentsResult = ref<{ imported: number; errors_count: number; errors: any[] } | null>(null)
const stockResult = ref<{ created: number } | null>(null)
const legacyResult = ref<{ imported: number; errors_count: number; errors: any[] } | null>(null)
const historyResult = ref<{ imported_billings: number; imported_items: number; errors_count: number; errors: any[] } | null>(null)
const completed = ref(false)

// Step 1 state
const condoInfo = ref<{ name: string; address: string | null; erp_code: string; commission_type?: string; commission_value?: number } | null>(null)

// Step 1: Commission state
const commissionType = ref<string>('fixed')
const commissionValue = ref<number | null>(null)
const perProductRates = ref<{ product_id: number; name: string; value_per_unit: number }[]>([])
const products = ref<{ id: number; name: string; capacity_liters: number }[]>([])
const commissionSaving = ref(false)
const commissionSaved = ref(false)

// Step 1: Operator
interface OperatorItem { id: number; username: string; full_name: string | null; is_active: boolean; condominium_ids: number[] }
const operators = ref<OperatorItem[]>([])
const selectedOperatorId = ref<number | null>(null)
const initialOperatorId = ref<number | null>(null)
const assignError = ref('')

// Step 1: Go-live
const goLiveDate = ref(new Date().toISOString().split('T')[0])

// Step 2: Floor block state
interface FloorBlock { prefix: string; num_floors: number | null; apts_per_floor: number | null; first_apt_example: string }
const floorBlocks = ref<FloorBlock[]>([{ prefix: '', num_floors: null, apts_per_floor: null, first_apt_example: '101' }])
const pendingUnits = ref<string[]>([])   // rascunho local (não salvo no banco)
const generateError = ref('')
const saveLoading = ref(false)
const existingUnits = ref<{ id: number; unit_code: string }[]>([])
const existingUnitsTotal = ref(0)

// Step 3: Residents import
const residentsFile = ref<File | null>(null)
const residentsLoading = ref(false)
const residentsError = ref('')

// Step 4: Stock + Alert thresholds
const stockMonth = ref('')
const globalMinStock = ref<number | null>(null)
const productAlerts = ref<{ product_id: number; name: string; min_quantity: number }[]>([])
const alertsSaving = ref(false)
const alertsSaved = ref(false)

// Step 5: Legacy debts
const legacyFile = ref<File | null>(null)
const legacyLoading = ref(false)
const legacyError = ref('')

// Step 6: History
const historyFile = ref<File | null>(null)
const historyLoading = ref(false)
const historyError = ref('')

// Complete state
const completing = ref(false)
const completeError = ref('')

// Onboarding status (checklist)
interface Requirement { key: string; met: boolean; message: string }
const onboardingStatus = ref<{ requirements: Requirement[]; can_complete: boolean } | null>(null)
const statusLoading = ref(false)

// Tooltip state
const activeTooltip = ref<string | null>(null)
function toggleTooltip(id: string) {
  activeTooltip.value = activeTooltip.value === id ? null : id
}

// Steps definition
const steps = [
  { n: 1, label: 'Informações' },
  { n: 2, label: 'Unidades' },
  { n: 3, label: 'Moradores' },
  { n: 4, label: 'Estoque' },
  { n: 5, label: 'Débitos' },
  { n: 6, label: 'Histórico' },
]

function stepClass(n: number) {
  if (n < currentStep.value) return 'bg-emerald-500 text-white border-emerald-500'
  if (n === currentStep.value) return 'bg-blue-600 text-white border-blue-600'
  return 'bg-white text-gray-400 border-gray-300'
}
function lineClass(n: number) {
  return n < currentStep.value ? 'bg-emerald-400' : 'bg-gray-200'
}

// Navigation
function next() { if (currentStep.value < TOTAL_STEPS) currentStep.value++ }
function prev() { if (currentStep.value > 1) currentStep.value-- }
function skip() { next() }

async function nextStep() {
  if (currentStep.value === 1) {
    await assignOperator()
    await saveCommission()
  }
  if (currentStep.value === 2) {
    const ok = await saveUnitsToDb()
    if (!ok) return  // fica na etapa se houve erro
  }
  if (currentStep.value === 4) {
    await saveStockAlerts()
  }
  next()
  if (currentStep.value === TOTAL_STEPS) await loadOnboardingStatus()
  if (currentStep.value === 2) await loadExistingUnits()
  if (currentStep.value === 4) await initProductAlerts()
}

// ── Step 1: Operator assignment ──────────────────────────────────────

async function assignOperator() {
  if (selectedOperatorId.value === initialOperatorId.value) return
  assignError.value = ''
  try {
    await apiClient.post(`/assignments/condominiums/${condominiumId}`, { user_id: selectedOperatorId.value })
    initialOperatorId.value = selectedOperatorId.value
  } catch (e: any) {
    assignError.value = e.response?.data?.detail || 'Não foi possível salvar o operador.'
  }
}

// ── Step 1: Commission ───────────────────────────────────────────────

async function saveCommission() {
  commissionSaving.value = true
  try {
    const payload: any = {
      commission_type: commissionType.value,
      commission_value: commissionValue.value,
    }
    if (commissionType.value === 'per_unit') {
      payload.per_product_rates = perProductRates.value.map(r => ({
        product_id: r.product_id,
        value_per_unit: r.value_per_unit,
      }))
    }
    await apiClient.patch(`/condominiums/${condominiumId}/onboarding/commission`, payload)
    commissionSaved.value = true
  } catch (e: any) {
    // non-critical: continue
  } finally {
    commissionSaving.value = false
  }
}

async function loadProducts() {
  try {
    const { data } = await apiClient.get('/products')
    products.value = (data.products || data).filter((p: any) => p.is_active !== false)
    perProductRates.value = products.value.map(p => ({ product_id: p.id, name: p.name, value_per_unit: 0 }))
  } catch { /* ignore */ }
}

// ── Step 2: Floor block generation ───────────────────────────────────

function addBlock() {
  floorBlocks.value.push({ prefix: '', num_floors: null, apts_per_floor: null, first_apt_example: '101' })
}

function removeBlock(idx: number) {
  if (floorBlocks.value.length > 1) floorBlocks.value.splice(idx, 1)
}

// Deriva floor_start a partir do exemplo do 1º apartamento (ex: "101" → 1, "1001" → 10)
function floorStartFromExample(example: string): number {
  const n = parseInt(example)
  if (isNaN(n) || n < 100) return 1
  return Math.floor(n / 100)
}

interface BlockPreview { label: string; count: number; firstCode: string; lastCode: string; floorStart: number; floorEnd: number }
const floorPreview = computed<{ blocks: BlockPreview[]; total: number }>(() => {
  const blocks: BlockPreview[] = []
  let total = 0
  for (const b of floorBlocks.value) {
    if (!b.num_floors || !b.apts_per_floor || b.num_floors < 1 || b.apts_per_floor < 1) continue
    const floorStart = floorStartFromExample(b.first_apt_example)
    const floorEnd = floorStart + b.num_floors - 1
    const count = b.num_floors * b.apts_per_floor
    const prefix = b.prefix || ''
    const firstCode = `${prefix}${floorStart * 100 + 1}`
    const lastCode = `${prefix}${floorEnd * 100 + b.apts_per_floor}`
    const blockLabel = prefix ? `Bloco/Torre "${prefix.replace(/-$/, '')}"` : 'Sem prefixo'
    blocks.push({ label: `${blockLabel} — ${b.num_floors} andares`, count, firstCode, lastCode, floorStart, floorEnd })
    total += count
  }
  return { blocks, total }
})

// Gera os códigos localmente (sem chamar a API)
function generateUnits() {
  generateError.value = ''
  if (floorPreview.value.blocks.length === 0) {
    generateError.value = 'Preencha pelo menos um bloco antes de gerar.'
    return
  }
  const codes: string[] = []
  for (const b of floorBlocks.value) {
    if (!b.num_floors || !b.apts_per_floor) continue
    const floorStart = floorStartFromExample(b.first_apt_example)
    const floorEnd = floorStart + b.num_floors - 1
    const prefix = b.prefix || ''
    for (let floor = floorStart; floor <= floorEnd; floor++) {
      for (let apt = 1; apt <= b.apts_per_floor; apt++) {
        codes.push(`${prefix}${floor * 100 + apt}`)
      }
    }
  }
  pendingUnits.value = codes
}

// Limpa o rascunho local (não toca no banco)
function clearPending() {
  pendingUnits.value = []
  floorBlocks.value = [{ prefix: '', num_floors: null, apts_per_floor: null, first_apt_example: '101' }]
  generateError.value = ''
}

// Persiste as unidades pendentes no banco (chamado ao avançar a etapa)
async function saveUnitsToDb(): Promise<boolean> {
  if (pendingUnits.value.length === 0) return true
  generateError.value = ''
  let clear_before = false
  if (existingUnitsTotal.value > 0) {
    clear_before = confirm(
      `Já existem ${existingUnitsTotal.value} unidades no banco.\n\n` +
      `OK → substituir (remove sem moradores e gera as novas)\n` +
      `Cancelar → adicionar às existentes`
    )
  }
  saveLoading.value = true
  try {
    const blocks = floorBlocks.value
      .filter(b => b.num_floors && b.apts_per_floor)
      .map(b => {
        const floor_start = floorStartFromExample(b.first_apt_example)
        return { prefix: b.prefix || '', floor_start, floor_end: floor_start + b.num_floors! - 1, apts_per_floor: b.apts_per_floor! }
      })
    await apiClient.post(`/condominiums/${condominiumId}/onboarding/generate-units-by-floor`, { blocks, clear_before })
    pendingUnits.value = []
    await loadExistingUnits()
    return true
  } catch (e: any) {
    generateError.value = e.response?.data?.detail || 'Erro ao salvar unidades'
    return false
  } finally {
    saveLoading.value = false
  }
}

async function loadExistingUnits() {
  try {
    const { data } = await apiClient.get(`/condominiums/${condominiumId}/onboarding/units`)
    existingUnits.value = data.units
    existingUnitsTotal.value = data.total
  } catch { /* ignore */ }
}

// ── Step 3: Residents import ─────────────────────────────────────────

async function uploadResidents() {
  if (!residentsFile.value) return
  residentsLoading.value = true
  residentsError.value = ''
  const fd = new FormData()
  fd.append('file', residentsFile.value)
  try {
    const { data } = await apiClient.post(`/condominiums/${condominiumId}/onboarding/import-residents`, fd)
    importResidentsResult.value = data
  } catch (e: any) {
    residentsError.value = e.response?.data?.detail || 'Erro ao importar'
  } finally {
    residentsLoading.value = false
  }
}

// ── Step 4: Stock alerts ─────────────────────────────────────────────

async function initProductAlerts() {
  if (products.value.length === 0) await loadProducts()

  // Always (re)initialize with all products, then overlay saved values
  const base = products.value.map(p => ({ product_id: p.id, name: p.name, min_quantity: 0 }))

  try {
    const { data } = await apiClient.get(`/condominiums/${condominiumId}/onboarding/stock-alerts`)
    if (data.global_min != null) globalMinStock.value = data.global_min
    const saved: Record<number, number> = {}
    for (const item of (data.items || [])) saved[item.product_id] = item.min_quantity
    productAlerts.value = base.map(p => ({ ...p, min_quantity: saved[p.product_id] ?? 0 }))
  } catch {
    productAlerts.value = base
  }
}

async function saveStockAlerts() {
  alertsSaving.value = true
  try {
    const payload: any = {}
    if (globalMinStock.value != null && globalMinStock.value > 0) {
      payload.global_min = globalMinStock.value
    }
    const items = productAlerts.value.filter(p => p.min_quantity > 0)
    if (items.length) {
      payload.items = items.map(p => ({ product_id: p.product_id, min_quantity: p.min_quantity }))
    }
    await apiClient.post(`/condominiums/${condominiumId}/onboarding/stock-alerts`, payload)
    alertsSaved.value = true
  } catch { /* ignore */ }
  finally { alertsSaving.value = false }
}

// ── Step 5: Legacy debts ─────────────────────────────────────────────

async function uploadLegacy() {
  if (!legacyFile.value) return
  legacyLoading.value = true
  legacyError.value = ''
  const fd = new FormData()
  fd.append('file', legacyFile.value)
  try {
    const { data } = await apiClient.post(`/condominiums/${condominiumId}/onboarding/legacy-debts`, fd)
    legacyResult.value = data
  } catch (e: any) {
    legacyError.value = e.response?.data?.detail || 'Erro ao importar'
  } finally {
    legacyLoading.value = false
  }
}

// ── Step 6: History import ───────────────────────────────────────────

async function uploadHistory() {
  if (!historyFile.value) return
  historyLoading.value = true
  historyError.value = ''
  const fd = new FormData()
  fd.append('file', historyFile.value)
  try {
    const { data } = await apiClient.post(`/condominiums/${condominiumId}/onboarding/import-history`, fd)
    historyResult.value = data
  } catch (e: any) {
    historyError.value = e.response?.data?.detail || 'Erro ao importar'
  } finally {
    historyLoading.value = false
  }
}

// ── Onboarding status & complete ─────────────────────────────────────

async function loadOnboardingStatus() {
  statusLoading.value = true
  try {
    const { data } = await apiClient.get(`/condominiums/${condominiumId}/onboarding/status`)
    onboardingStatus.value = data
  } catch { /* ignore */ }
  finally { statusLoading.value = false }
}

async function completeOnboarding() {
  completing.value = true
  completeError.value = ''
  try {
    await apiClient.post(`/condominiums/${condominiumId}/onboarding/complete`, { go_live_date: goLiveDate.value })
    completed.value = true
  } catch (e: any) {
    const detail = e.response?.data?.detail
    if (typeof detail === 'object' && detail.unmet) {
      completeError.value = detail.unmet.join('\n')
    } else {
      completeError.value = detail || 'Erro ao ativar condomínio'
    }
    await loadOnboardingStatus()
  } finally {
    completing.value = false
  }
}

function goToDashboard() {
  router.push('/home')
}

// ── Init ─────────────────────────────────────────────────────────────

onMounted(async () => {
  const now = new Date()
  stockMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

  // Load condo info
  try {
    const { data } = await apiClient.get(`/home/overview/${stockMonth.value}`)
    const condo = data.condominiums.find((c: any) => c.id === condominiumId)
    if (condo) condoInfo.value = condo
  } catch { /* ignore */ }

  // Load operators and detect current assignment
  try {
    const { data } = await apiClient.get<OperatorItem[]>('/assignments/operators')
    operators.value = data
    const current = data.find((op: OperatorItem) => op.condominium_ids.includes(condominiumId))
    selectedOperatorId.value = current?.id ?? null
    initialOperatorId.value = current?.id ?? null
  } catch { /* ignore */ }

  // Load saved commission config
  try {
    const { data } = await apiClient.get(`/finance/condominiums/${condominiumId}/commission-config`)
    commissionType.value = data.commission_type || 'fixed'
    commissionValue.value = data.commission_value ?? null
  } catch { /* ignore */ }

  // Load products for commission per_unit
  await loadProducts()
})
</script>

<template>
  <div class="fade-up max-w-3xl mx-auto">
    <!-- Page title -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-gray-900">Wizard de Implantação</h1>
      <p class="text-gray-500 text-sm mt-0.5">
        {{ condoInfo?.name || `Condomínio #${condominiumId}` }} — Ativação guiada
      </p>
    </div>

    <!-- Completion screen -->
    <div v-if="completed" class="bg-white rounded-2xl border border-gray-200 shadow-sm p-10 text-center">
      <div class="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
        </svg>
      </div>
      <h2 class="text-xl font-bold text-gray-900 mb-2">Condomínio Ativado!</h2>
      <p class="text-gray-500 text-sm mb-6">O sistema está pronto para operar este condomínio.</p>
      <div class="grid grid-cols-2 gap-4 mb-6 text-sm text-left max-w-md mx-auto">
        <div v-if="generateResult" class="bg-blue-50 rounded-xl p-3">
          <p class="font-semibold text-blue-700">Unidades</p>
          <p class="text-blue-600">{{ generateResult.total_units }} cadastradas</p>
        </div>
        <div v-if="importResidentsResult" class="bg-emerald-50 rounded-xl p-3">
          <p class="font-semibold text-emerald-700">Moradores</p>
          <p class="text-emerald-600">{{ importResidentsResult.imported }} importados</p>
        </div>
        <div v-if="legacyResult" class="bg-amber-50 rounded-xl p-3">
          <p class="font-semibold text-amber-700">Débitos</p>
          <p class="text-amber-600">{{ legacyResult.imported }} importados</p>
        </div>
        <div v-if="historyResult" class="bg-blue-50 rounded-xl p-3">
          <p class="font-semibold text-blue-700">Histórico</p>
          <p class="text-blue-600">{{ historyResult.imported_items }} lançamentos</p>
        </div>
      </div>
      <button @click="goToDashboard"
        class="px-6 py-2.5 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors">
        Ir para o Painel
      </button>
    </div>

    <template v-else>
      <!-- Step progress indicator -->
      <div class="flex items-center mb-8">
        <template v-for="(step, i) in steps" :key="step.n">
          <div class="flex flex-col items-center">
            <div :class="stepClass(step.n)"
              class="w-9 h-9 rounded-full border-2 flex items-center justify-center text-sm font-bold transition-all">
              <svg v-if="step.n < currentStep" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
              </svg>
              <span v-else>{{ step.n }}</span>
            </div>
            <span class="text-[10px] mt-1 font-medium" :class="step.n === currentStep ? 'text-blue-600' : 'text-gray-400'">
              {{ step.label }}
            </span>
          </div>
          <div v-if="i < steps.length - 1" :class="lineClass(step.n)" class="flex-1 h-0.5 mx-1 mb-4 transition-all"></div>
        </template>
      </div>

      <!-- Step cards -->
      <div class="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">

        <!-- ═══ Step 1: Informações + Comissão + Operador ═══ -->
        <div v-if="currentStep === 1" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 1 — Informações e Comissão</h2>
          <p class="text-gray-500 text-sm mb-6">Confirme os dados e configure a comissão do condomínio.</p>
          <div class="space-y-4">
            <div>
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Nome</label>
              <p class="mt-1 text-gray-900 font-medium">{{ condoInfo?.name || '—' }}</p>
            </div>
            <div>
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Endereço</label>
              <p class="mt-1 text-gray-900">{{ condoInfo?.address || '—' }}</p>
            </div>
            <div>
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Código Retaguarda</label>
              <p class="mt-1 font-mono text-gray-700">{{ (condoInfo as any)?.erp_code || '—' }}</p>
            </div>
            <div>
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Data de Ativação</label>
              <p class="text-xs text-gray-400 mb-1.5">Data em que este condomínio começa a ser gerenciado pelo FonteGest.</p>
              <input v-model="goLiveDate" type="date"
                class="mt-1 block px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"/>
            </div>

            <!-- Operator -->
            <div>
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Operador Responsável</label>
              <p class="text-xs text-gray-400 mb-1.5">O operador terá acesso a este condomínio após a conclusão.</p>
              <select
                v-model="selectedOperatorId"
                class="block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option :value="null">— Sem operador —</option>
                <option v-for="op in operators" :key="op.id" :value="op.id">
                  {{ op.full_name || op.username }}{{ !op.is_active ? ' (inativo)' : '' }}
                </option>
              </select>
              <p v-if="assignError" class="mt-1.5 text-xs text-amber-600">{{ assignError }}</p>
            </div>

            <!-- Commission -->
            <div class="pt-4 border-t border-gray-100">
              <div class="flex items-center gap-2 mb-3">
                <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Tipo de Comissão</label>
                <button @click="toggleTooltip('commission-type')" class="text-gray-400 hover:text-gray-600 transition-colors" type="button">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
                </button>
              </div>
              <div v-if="activeTooltip === 'commission-type'" class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
                Tipo de comissão que a FonteGest receberá por este condomínio.
              </div>
              <select v-model="commissionType" class="block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white">
                <option value="fixed">Valor fixo mensal</option>
                <option value="percent">Percentual sobre faturamento</option>
                <option value="per_unit">Valor por unidade/produto</option>
              </select>
              <p class="text-xs text-gray-400 mt-1">
                <template v-if="commissionType === 'fixed'">Um valor mensal fixo independente do faturamento.</template>
                <template v-else-if="commissionType === 'percent'">Percentual aplicado sobre o total faturado no mês.</template>
                <template v-else>Valor específico por produto entregue em cada unidade.</template>
              </p>
            </div>

            <!-- Commission value (fixed/percent) -->
            <div v-if="commissionType !== 'per_unit'">
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {{ commissionType === 'fixed' ? 'Valor (R$)' : 'Percentual (%)' }}
              </label>
              <input v-model.number="commissionValue" type="number" step="0.01" min="0"
                :placeholder="commissionType === 'fixed' ? '0.00' : '0.00'"
                class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"/>
            </div>

            <!-- Per-product rates -->
            <div v-if="commissionType === 'per_unit' && products.length" class="space-y-2">
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Valor por Produto (R$/unidade)</label>
              <div v-for="rate in perProductRates" :key="rate.product_id"
                class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <span class="text-sm text-gray-700 flex-1">{{ rate.name }}</span>
                <input v-model.number="rate.value_per_unit" type="number" step="0.01" min="0" placeholder="0.00"
                  class="w-28 px-2 py-1.5 border border-gray-300 rounded-lg text-sm text-right focus:ring-2 focus:ring-blue-500"/>
              </div>
            </div>

            <div v-if="commissionSaved" class="flex items-center gap-2 text-xs text-emerald-600">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              Comissão salva
            </div>
          </div>
        </div>

        <!-- ═══ Step 2: Unidades (Por andares) ═══ -->
        <div v-if="currentStep === 2" class="p-8">
          <div class="flex items-center gap-2 mb-1">
            <h2 class="text-lg font-bold text-gray-900">Etapa 2 — Cadastro de Unidades</h2>
            <button @click="toggleTooltip('step2-help')" class="text-gray-400 hover:text-gray-600 transition-colors" type="button">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
            </button>
          </div>
          <div v-if="activeTooltip === 'step2-help'" class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
            Informe o número de andares e quantos apartamentos há por andar. O sistema gera os códigos automaticamente
            usando a numeração padrão brasileira (andar × 100 + posição). Ex: andar 10, apt 3 → 1003.
            Para condomínios com múltiplos blocos ou torres, adicione um bloco por torre.
          </div>
          <p class="text-gray-500 text-sm mb-6">Gere unidades por andares. Esta etapa é obrigatória.</p>

          <!-- Block inputs -->
          <div class="space-y-3 mb-4">
            <div v-for="(b, idx) in floorBlocks" :key="idx"
              class="p-4 bg-gray-50 rounded-xl border border-gray-200">
              <div class="flex items-center justify-between mb-3">
                <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  {{ floorBlocks.length > 1 ? `Bloco/Torre ${idx + 1}` : 'Configuração' }}
                </span>
                <button v-if="floorBlocks.length > 1" @click="removeBlock(idx)"
                  class="p-1 text-red-400 hover:text-red-600 transition-colors" type="button" title="Remover bloco">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
              </div>
              <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <!-- Prefix -->
                <div class="col-span-2 sm:col-span-1">
                  <div class="flex items-center gap-1 mb-1">
                    <label class="text-xs font-semibold text-gray-500">Prefixo</label>
                    <button @click="toggleTooltip(`prefix-${idx}`)" class="text-gray-400 hover:text-gray-600" type="button">
                      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
                    </button>
                  </div>
                  <div v-if="activeTooltip === `prefix-${idx}`" class="mb-1.5 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                    Identificador do bloco ou torre. Ex: "TA-", "BLA-". Deixe vazio para torre única.
                  </div>
                  <input v-model="b.prefix" type="text" placeholder="TA- (opcional)"
                    class="block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white"/>
                </div>
                <!-- Num floors -->
                <div>
                  <div class="flex items-center gap-1 mb-1">
                    <label class="text-xs font-semibold text-gray-500">Nº de Andares</label>
                  </div>
                  <input v-model.number="b.num_floors" type="number" min="1" placeholder="20"
                    class="block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white"/>
                </div>
                <!-- Apts per floor -->
                <div>
                  <div class="flex items-center gap-1 mb-1">
                    <label class="text-xs font-semibold text-gray-500">Apts/Andar</label>
                    <button @click="toggleTooltip(`apts-${idx}`)" class="text-gray-400 hover:text-gray-600" type="button">
                      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
                    </button>
                  </div>
                  <div v-if="activeTooltip === `apts-${idx}`" class="mb-1.5 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                    Quantos apartamentos existem em cada andar. Máximo 99 por andar.
                  </div>
                  <input v-model.number="b.apts_per_floor" type="number" min="1" max="99" placeholder="4"
                    class="block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white"/>
                </div>
                <!-- First apt example -->
                <div>
                  <div class="flex items-center gap-1 mb-1">
                    <label class="text-xs font-semibold text-gray-500">Exemplo do 1º Apt</label>
                    <button @click="toggleTooltip(`example-${idx}`)" class="text-gray-400 hover:text-gray-600" type="button">
                      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
                    </button>
                  </div>
                  <div v-if="activeTooltip === `example-${idx}`" class="mb-1.5 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                    Informe o código do primeiro apartamento do 1º andar. Ex: <strong>101</strong> (centena, andares 1–9)
                    ou <strong>1001</strong> (milhar, andares 10+). O sistema identifica automaticamente a numeração correta.
                  </div>
                  <input v-model="b.first_apt_example" type="text" placeholder="101"
                    class="block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white font-mono"/>
                </div>
              </div>
            </div>
          </div>

          <button @click="addBlock" type="button"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium hover:bg-blue-50 rounded-lg transition-colors mb-5"
            title="Adicione outro bloco para condomínios com múltiplas torres ou blocos com configurações diferentes">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
            Adicionar bloco/torre
          </button>

          <!-- Preview -->
          <div v-if="floorPreview.blocks.length" class="mb-5 p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm">
            <p class="font-semibold text-blue-800 mb-2">Prévia da geração:</p>
            <div class="space-y-1">
              <div v-for="(bp, i) in floorPreview.blocks" :key="i" class="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-blue-700">
                <span>{{ bp.label }}</span>
                <span class="text-xs text-blue-500">(andares {{ bp.floorStart }}–{{ bp.floorEnd }})</span>
                <span class="font-mono text-xs text-blue-600">{{ bp.firstCode }} … {{ bp.lastCode }}</span>
                <span class="font-semibold text-blue-800 ml-auto">{{ bp.count }} un.</span>
              </div>
            </div>
            <div v-if="floorPreview.blocks.length > 1" class="mt-2 pt-2 border-t border-blue-200 flex justify-between font-semibold text-blue-800">
              <span>Total</span>
              <span>{{ floorPreview.total }} unidades</span>
            </div>
          </div>

          <!-- Botões Gerar / Limpar -->
          <div class="flex items-center gap-3">
            <button @click="generateUnits" :disabled="floorPreview.blocks.length === 0"
              class="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50">
              Gerar prévia
            </button>
            <button v-if="pendingUnits.length > 0" @click="clearPending" type="button"
              class="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded-lg transition-colors border border-red-200">
              Limpar
            </button>
          </div>

          <p v-if="generateError" class="mt-2 text-sm text-red-600">{{ generateError }}</p>

          <!-- Rascunho local (pendingUnits) -->
          <div v-if="pendingUnits.length > 0" class="mt-4 p-4 bg-blue-50 rounded-xl border border-blue-200">
            <p class="text-sm font-semibold text-blue-800 mb-2">
              {{ pendingUnits.length }} unidades prontas — serão salvas ao avançar
            </p>
            <div class="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto">
              <span v-for="code in pendingUnits" :key="code"
                class="px-2 py-0.5 bg-white border border-blue-200 rounded text-xs text-blue-700 font-mono">
                {{ code }}
              </span>
            </div>
          </div>

          <!-- Unidades já no banco -->
          <div v-if="existingUnitsTotal > 0" class="mt-6">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Já cadastradas no banco ({{ existingUnitsTotal }})
            </p>
            <div class="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto p-3 bg-gray-50 rounded-xl">
              <span v-for="u in existingUnits" :key="u.id"
                class="px-2 py-0.5 bg-white border border-gray-200 rounded text-xs text-gray-600 font-mono">
                {{ u.unit_code }}
              </span>
            </div>
          </div>

          <!-- Indicador de salvando -->
          <div v-if="saveLoading" class="mt-3 flex items-center gap-2 text-sm text-blue-600">
            <div class="animate-spin w-4 h-4 border-2 border-blue-300 border-t-blue-600 rounded-full"></div>
            Salvando unidades...
          </div>
        </div>

        <!-- ═══ Step 3: Moradores (Importação) ═══ -->
        <div v-if="currentStep === 3" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 3 — Importar Moradores</h2>
          <p class="text-gray-500 text-sm mb-2">Faça upload de um arquivo CSV ou XLSX com os moradores (opcional).</p>
          <p class="text-xs text-gray-400 mb-6">Colunas esperadas: <code class="bg-gray-100 px-1 rounded">unidade, nome, cpf, telefone</code></p>

          <div v-if="!importResidentsResult">
            <label class="block">
              <div class="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
                @dragover.prevent @drop.prevent="(e) => { residentsFile = (e as DragEvent).dataTransfer?.files[0] ?? null }">
                <svg class="w-8 h-8 text-gray-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                </svg>
                <p class="text-sm text-gray-500">{{ residentsFile ? residentsFile.name : 'Arraste o arquivo ou clique para selecionar' }}</p>
                <input type="file" accept=".csv,.xlsx" class="hidden" @change="(e) => { residentsFile = (e.target as HTMLInputElement).files?.[0] ?? null }"/>
              </div>
            </label>
            <p v-if="residentsError" class="mt-2 text-sm text-red-600">{{ residentsError }}</p>
            <button v-if="residentsFile" @click="uploadResidents" :disabled="residentsLoading"
              class="mt-4 px-5 py-2 bg-blue-600 text-white rounded-lg font-semibold text-sm hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-2">
              <div v-if="residentsLoading" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
              <span>{{ residentsLoading ? 'Importando...' : 'Importar' }}</span>
            </button>
          </div>

          <div v-else class="space-y-3">
            <div class="flex items-center gap-3 p-4 bg-emerald-50 rounded-xl border border-emerald-200">
              <svg class="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
              <p class="text-sm font-medium text-emerald-700">{{ importResidentsResult.imported }} moradores importados</p>
            </div>
            <div v-if="importResidentsResult.errors_count" class="p-4 bg-red-50 rounded-xl border border-red-200">
              <p class="text-sm font-semibold text-red-700 mb-2">{{ importResidentsResult.errors_count }} erros encontrados:</p>
              <ul class="text-xs text-red-600 space-y-1 max-h-32 overflow-y-auto">
                <li v-for="e in importResidentsResult.errors" :key="e.row">Linha {{ e.row }}: {{ e.error }}</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- ═══ Step 4: Alertas de Estoque Mínimo ═══ -->
        <div v-if="currentStep === 4" class="p-8">
          <div class="flex items-center gap-2 mb-1">
            <h2 class="text-lg font-bold text-gray-900">Etapa 4 — Alertas de Estoque</h2>
            <button @click="toggleTooltip('stock-alert-help')" class="text-gray-400 hover:text-gray-600 transition-colors" type="button">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
            </button>
          </div>
          <div v-if="activeTooltip === 'stock-alert-help'" class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
            Define o estoque mínimo de cada produto para este condomínio. Quando o saldo ficar abaixo do limite, um alerta aparece no painel e na tela de Estoque.
            Valores por produto têm prioridade sobre o valor global.
          </div>
          <p class="text-gray-500 text-sm mb-6">Opcional — pode ser configurado depois na tela de Estoque.</p>

          <!-- Tabela de alertas -->
          <div class="rounded-xl border border-gray-200 overflow-hidden mb-5">
            <!-- Header -->
            <div class="grid grid-cols-3 gap-4 px-4 py-2 bg-gray-50 border-b border-gray-200">
              <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide col-span-2">Produto</span>
              <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Mínimo (un.)</span>
            </div>

            <!-- Global -->
            <div class="grid grid-cols-3 gap-4 items-center px-4 py-3 bg-blue-50 border-b border-gray-100">
              <div class="col-span-2 flex items-center gap-2">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-700">Global</span>
                <span class="text-sm text-gray-600">Aplica a todos os produtos sem valor individual</span>
                <button @click="toggleTooltip('global-alert')" class="text-gray-400 hover:text-gray-600 flex-shrink-0" type="button">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
                </button>
              </div>
              <input v-model.number="globalMinStock" type="number" min="0" placeholder="0"
                class="w-full px-3 py-1.5 border border-blue-300 rounded-lg text-sm text-right focus:ring-2 focus:ring-blue-500 bg-white"/>
              <div v-if="activeTooltip === 'global-alert'" class="col-span-3 -mt-1 mb-1 px-1">
                <div class="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded p-3 space-y-1.5">
                  <p class="font-semibold">Como funciona o limite global:</p>
                  <p>É comparado individualmente com o saldo de <strong>cada produto</strong> — não é a soma de todos.</p>
                  <p class="font-medium mt-1">Exemplos com Global = 20:</p>
                  <ul class="space-y-0.5 pl-2">
                    <li>• Galão 20L: saldo 18 → <span class="text-red-600 font-medium">alerta</span> (18 &lt; 20)</li>
                    <li>• Galão 10L: saldo 25 → <span class="text-emerald-600 font-medium">ok</span> (25 ≥ 20)</li>
                  </ul>
                  <p class="border-t border-blue-200 pt-1.5">Se um produto tiver valor individual configurado, o individual prevalece sobre o global. Deixe em 0 para não usar limite global.</p>
                </div>
              </div>
            </div>

            <!-- Por produto -->
            <div v-if="productAlerts.length === 0" class="px-4 py-6 text-center text-sm text-gray-400">
              Carregando produtos...
            </div>
            <div v-for="(pa, idx) in productAlerts" :key="pa.product_id"
              :class="idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'"
              class="grid grid-cols-3 gap-4 items-center px-4 py-3 border-b border-gray-100 last:border-0">
              <div class="col-span-2">
                <p class="text-sm font-medium text-gray-800">{{ pa.name }}</p>
                <p class="text-xs text-gray-400 mt-0.5">
                  <span v-if="pa.min_quantity > 0" class="text-amber-600 font-medium">Alerta abaixo de {{ pa.min_quantity }} un.</span>
                  <span v-else>Sem limite individual — usa valor global</span>
                </p>
              </div>
              <input v-model.number="pa.min_quantity" type="number" min="0" placeholder="0"
                class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-right focus:ring-2 focus:ring-blue-500 bg-white"/>
            </div>
          </div>

          <div class="flex items-center gap-4">
            <button @click="saveStockAlerts" :disabled="alertsSaving"
              class="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-2">
              <div v-if="alertsSaving" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
              <span>{{ alertsSaving ? 'Salvando...' : 'Salvar Alertas' }}</span>
            </button>
            <div v-if="alertsSaved" class="flex items-center gap-1.5 text-sm text-emerald-600 font-medium">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              Alertas salvos com sucesso
            </div>
          </div>
        </div>

        <!-- ═══ Step 5: Histórico de Consumo ═══ -->
        <div v-if="currentStep === 5" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 5 — Histórico de Consumo</h2>
          <p class="text-gray-500 text-sm mb-6">Migração de meses anteriores à ativação.</p>

          <div class="rounded-xl border border-blue-200 bg-blue-50 p-5 mb-4">
            <div class="flex gap-3">
              <svg class="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              <div>
                <p class="text-sm font-semibold text-blue-800 mb-1">Esta etapa é feita pelo operador após a ativação</p>
                <p class="text-sm text-blue-700">O operador responsável por este condomínio tem acesso a <strong>todos os meses</strong> na tela de Lançamento — incluindo meses anteriores à ativação.</p>
              </div>
            </div>
          </div>

          <div class="rounded-xl border border-gray-200 divide-y divide-gray-100 text-sm">
            <div class="flex items-start gap-3 p-4">
              <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
              <div>
                <p class="font-medium text-gray-800">Ative o condomínio (próxima etapa)</p>
                <p class="text-gray-500 text-xs mt-0.5">O operador já pode acessar o sistema após a ativação.</p>
              </div>
            </div>
            <div class="flex items-start gap-3 p-4">
              <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
              <div>
                <p class="font-medium text-gray-800">Operador seleciona o mês anterior na tela de Lançamento</p>
                <p class="text-gray-500 text-xs mt-0.5">Ex: seleciona Janeiro/2025 e lança as quantidades de cada unidade.</p>
              </div>
            </div>
            <div class="flex items-start gap-3 p-4">
              <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
              <div>
                <p class="font-medium text-gray-800">Para condôminos com muitas unidades — importar CSV</p>
                <p class="text-gray-500 text-xs mt-0.5">Botão <strong>"Importar Consumo"</strong> disponível na tela de Lançamento. Formato: <code class="bg-gray-100 px-1 rounded">unidade, INDAIA20LT, INDAIA10L, IAIA20L</code></p>
              </div>
            </div>
          </div>
        </div>

        <!-- ═══ Step 6: Checklist + Ativar ═══ -->
        <div v-if="currentStep === 6" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 6 — Ativação</h2>
          <p class="text-gray-500 text-sm mb-6">Verifique os requisitos e ative o condomínio.</p>

          <!-- Checklist -->
          <div v-if="statusLoading" class="py-8 flex justify-center">
            <div class="animate-spin w-6 h-6 border-2 border-blue-200 border-t-blue-600 rounded-full"></div>
          </div>

          <div v-else-if="onboardingStatus" class="space-y-2 mb-6">
            <div v-for="req in onboardingStatus.requirements" :key="req.key"
              class="flex items-center gap-3 p-4 rounded-xl border"
              :class="req.met ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'">
              <div class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                :class="req.met ? 'bg-emerald-100' : 'bg-red-100'">
                <svg v-if="req.met" class="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
                </svg>
                <svg v-else class="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </div>
              <span class="text-sm font-medium" :class="req.met ? 'text-emerald-800' : 'text-red-700'">{{ req.message }}</span>
            </div>
          </div>

          <button @click="loadOnboardingStatus"
            class="text-xs text-blue-600 hover:text-blue-800 font-medium mb-6 inline-flex items-center gap-1 transition-colors">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
            Atualizar checklist
          </button>

          <!-- Error -->
          <div v-if="completeError" class="mb-5 p-4 bg-red-50 border border-red-200 rounded-xl">
            <p class="text-sm font-semibold text-red-700 mb-1">Não foi possível ativar:</p>
            <p class="text-xs text-red-600 whitespace-pre-line">{{ completeError }}</p>
          </div>
        </div>

        <!-- Navigation -->
        <div class="px-8 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
          <button @click="prev" :disabled="currentStep === 1"
            class="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            &larr; Anterior
          </button>
          <div class="flex items-center gap-3">
            <button v-if="currentStep < TOTAL_STEPS && currentStep !== 2" @click="skip"
              class="px-4 py-2 text-gray-400 text-sm font-medium hover:text-gray-600 transition-colors">
              Pular
            </button>
            <button v-if="currentStep < TOTAL_STEPS" @click="nextStep"
              class="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors">
              Próximo &rarr;
            </button>
            <button v-else @click="completeOnboarding"
              :disabled="completing || (!!onboardingStatus && !onboardingStatus.can_complete)"
              class="px-6 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              :title="onboardingStatus && !onboardingStatus.can_complete ? 'Resolva os requisitos pendentes antes de ativar' : ''">
              <div v-if="completing" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
              <span>{{ completing ? 'Ativando...' : 'Ativar Condomínio' }}</span>
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
