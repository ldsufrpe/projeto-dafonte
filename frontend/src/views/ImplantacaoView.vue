<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const condominiumId = Number(route.params.condominiumId)

// Wizard state
const currentStep = ref(1)
const TOTAL_STEPS = 5

// Step results
const importResidentsResult = ref<{ imported: number; errors_count: number; errors: any[] } | null>(null)
const stockResult = ref<{ created: number } | null>(null)
const legacyResult = ref<{ imported: number; errors_count: number; errors: any[] } | null>(null)
const historyResult = ref<{ imported_billings: number; imported_items: number; errors_count: number; errors: any[] } | null>(null)
const completed = ref(false)

// Step 1 state
const condoInfo = ref<{ name: string; address: string | null; erp_code: string } | null>(null)

// Step 2 state
const residentsFile = ref<File | null>(null)
const residentsLoading = ref(false)
const residentsError = ref('')

// Step 3 state
const stockMonth = ref('')

// Step 4 state
const legacyFile = ref<File | null>(null)
const legacyLoading = ref(false)
const legacyError = ref('')

// Step 5 state
const historyFile = ref<File | null>(null)
const historyLoading = ref(false)
const historyError = ref('')

// Complete state
const completing = ref(false)
const goLiveDate = ref(new Date().toISOString().split('T')[0])

// Operator assignment state (Step 1)
interface OperatorItem { id: number; username: string; full_name: string | null; is_active: boolean; condominium_ids: number[] }
const operators = ref<OperatorItem[]>([])
const selectedOperatorId = ref<number | null>(null)
const initialOperatorId = ref<number | null>(null) // to detect changes
const assignError = ref('')

async function assignOperator() {
  if (selectedOperatorId.value === initialOperatorId.value) return
  assignError.value = ''
  try {
    await apiClient.post(`/assignments/condominiums/${condominiumId}`, { user_id: selectedOperatorId.value })
    initialOperatorId.value = selectedOperatorId.value
  } catch (e: any) {
    assignError.value = e.response?.data?.detail || 'Não foi possível salvar o operador. Continue mesmo assim.'
  }
}

async function nextStep() {
  if (currentStep.value === 1) await assignOperator()
  next()
}

onMounted(async () => {
  // Set default stock month to current
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
})

function next() { if (currentStep.value < TOTAL_STEPS) currentStep.value++ }
function prev() { if (currentStep.value > 1) currentStep.value-- }
function skip() { next() }

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

async function completeOnboarding() {
  completing.value = true
  try {
    await apiClient.post(`/condominiums/${condominiumId}/onboarding/complete`, { go_live_date: goLiveDate.value })
    completed.value = true
  } catch (e: any) {
    alert(e.response?.data?.detail || 'Erro ao ativar condomínio')
  } finally {
    completing.value = false
  }
}

function goToDashboard() {
  router.push('/home')
}

const steps = [
  { n: 1, label: 'Informações' },
  { n: 2, label: 'Moradores' },
  { n: 3, label: 'Estoque' },
  { n: 4, label: 'Débitos' },
  { n: 5, label: 'Histórico' },
]

function stepClass(n: number) {
  if (n < currentStep.value) return 'bg-emerald-500 text-white border-emerald-500'
  if (n === currentStep.value) return 'bg-blue-600 text-white border-blue-600'
  return 'bg-white text-gray-400 border-gray-300'
}
function lineClass(n: number) {
  return n < currentStep.value ? 'bg-emerald-400' : 'bg-gray-200'
}
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
        <!-- Step 1: Informações -->
        <div v-if="currentStep === 1" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 1 — Informações do Condomínio</h2>
          <p class="text-gray-500 text-sm mb-6">Confirme os dados antes de prosseguir.</p>
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
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Código ERP</label>
              <p class="mt-1 font-mono text-gray-700">{{ (condoInfo as any)?.erp_code || '—' }}</p>
            </div>
            <div>
              <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Data de Início de Operação</label>
              <p class="text-xs text-gray-400 mb-1.5">Data em que este condomínio começa a ser gerenciado pelo FonteGest.</p>
              <input v-model="goLiveDate" type="date"
                class="mt-1 block px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"/>
            </div>
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
              <p v-if="assignError" class="mt-1.5 text-xs text-amber-600">⚠ {{ assignError }}</p>
            </div>
          </div>
        </div>

        <!-- Step 2: Moradores -->
        <div v-if="currentStep === 2" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 2 — Importar Moradores</h2>
          <p class="text-gray-500 text-sm mb-2">Faça upload de um arquivo CSV ou XLSX com os moradores.</p>
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

        <!-- Step 3: Estoque Inicial -->
        <div v-if="currentStep === 3" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 3 — Saldo Inicial de Estoque</h2>
          <p class="text-gray-500 text-sm mb-6">Informe o estoque físico contado no momento da implantação.</p>
          <div class="mb-4">
            <label class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Mês de Referência</label>
            <input v-model="stockMonth" type="month" class="mt-1 block px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"/>
          </div>
          <div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-700">
            <p class="font-semibold mb-1">Configure os produtos primeiro</p>
            <p>O saldo inicial por produto é configurado via SQLAdmin ou pela tela de Configurações (Sprint 8). Você pode pular esta etapa e configurar depois.</p>
          </div>
          <p v-if="stockResult" class="mt-3 text-sm text-emerald-600 font-medium">{{ stockResult.created }} entradas de saldo criadas</p>
        </div>

        <!-- Step 4: Débitos Anteriores -->
        <div v-if="currentStep === 4" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 4 — Débitos Anteriores</h2>
          <p class="text-gray-500 text-sm mb-2">Importe débitos de meses anteriores ao go-live.</p>
          <p class="text-xs text-gray-400 mb-2">Colunas: <code class="bg-gray-100 px-1 rounded">unidade, mes_referencia, valor, descricao</code></p>
          <div class="p-3 bg-amber-50 border border-amber-200 rounded-lg mb-6 text-xs text-amber-700">
            Estes valores serão exibidos no Dashboard mas não gerarão novos boletos no sistema.
          </div>

          <div v-if="!legacyResult">
            <label class="block">
              <div class="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
                @dragover.prevent @drop.prevent="(e) => { legacyFile = (e as DragEvent).dataTransfer?.files[0] ?? null }">
                <svg class="w-8 h-8 text-gray-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                </svg>
                <p class="text-sm text-gray-500">{{ legacyFile ? legacyFile.name : 'Arraste ou clique para selecionar' }}</p>
                <input type="file" accept=".csv,.xlsx" class="hidden" @change="(e) => { legacyFile = (e.target as HTMLInputElement).files?.[0] ?? null }"/>
              </div>
            </label>
            <p v-if="legacyError" class="mt-2 text-sm text-red-600">{{ legacyError }}</p>
            <button v-if="legacyFile" @click="uploadLegacy" :disabled="legacyLoading"
              class="mt-4 px-5 py-2 bg-blue-600 text-white rounded-lg font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
              <div v-if="legacyLoading" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
              <span>{{ legacyLoading ? 'Importando...' : 'Importar' }}</span>
            </button>
          </div>
          <div v-else class="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
            <p class="text-sm font-medium text-emerald-700">{{ legacyResult.imported }} débitos importados</p>
            <p v-if="legacyResult.errors_count" class="text-xs text-red-600 mt-1">{{ legacyResult.errors_count }} erros — verifique as linhas com problema</p>
          </div>
        </div>

        <!-- Step 5: Histórico -->
        <div v-if="currentStep === 5" class="p-8">
          <h2 class="text-lg font-bold text-gray-900 mb-1">Etapa 5 — Histórico de Meses Anteriores</h2>
          <p class="text-gray-500 text-sm mb-2">Importe lançamentos de meses já fechados (opcional).</p>
          <p class="text-xs text-gray-400 mb-2">Colunas: <code class="bg-gray-100 px-1 rounded">unidade, mes_referencia, produto, quantidade, preco_unitario, status_pgto</code></p>
          <div class="p-3 bg-blue-50 border border-blue-200 rounded-lg mb-6 text-xs text-blue-700">
            Dados históricos são somente leitura e servem apenas para consulta e relatórios.
          </div>

          <div v-if="!historyResult">
            <label class="block">
              <div class="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
                @dragover.prevent @drop.prevent="(e) => { historyFile = (e as DragEvent).dataTransfer?.files[0] ?? null }">
                <svg class="w-8 h-8 text-gray-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                </svg>
                <p class="text-sm text-gray-500">{{ historyFile ? historyFile.name : 'Arraste ou clique para selecionar' }}</p>
                <input type="file" accept=".csv,.xlsx" class="hidden" @change="(e) => { historyFile = (e.target as HTMLInputElement).files?.[0] ?? null }"/>
              </div>
            </label>
            <button v-if="historyFile" @click="uploadHistory" :disabled="historyLoading"
              class="mt-4 px-5 py-2 bg-blue-600 text-white rounded-lg font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
              <div v-if="historyLoading" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
              <span>{{ historyLoading ? 'Importando...' : 'Importar' }}</span>
            </button>
          </div>
          <div v-else class="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
            <p class="text-sm font-medium text-emerald-700">{{ historyResult.imported_items }} lançamentos em {{ historyResult.imported_billings }} meses</p>
            <p v-if="historyResult.errors_count" class="text-xs text-red-600 mt-1">{{ historyResult.errors_count }} erros</p>
          </div>
        </div>

        <!-- Navigation -->
        <div class="px-8 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
          <button @click="prev" :disabled="currentStep === 1"
            class="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            &larr; Anterior
          </button>
          <div class="flex items-center gap-3">
            <button v-if="currentStep < TOTAL_STEPS" @click="skip"
              class="px-4 py-2 text-gray-400 text-sm font-medium hover:text-gray-600 transition-colors">
              Pular
            </button>
            <button v-if="currentStep < TOTAL_STEPS" @click="nextStep"
              class="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors">
              Próximo &rarr;
            </button>
            <button v-else @click="completeOnboarding" :disabled="completing"
              class="px-6 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700 transition-colors disabled:opacity-50 flex items-center gap-2">
              <div v-if="completing" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
              <span>{{ completing ? 'Ativando...' : 'Ativar Condomínio' }}</span>
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
