<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useCondominiumStore } from '@/stores/condominium'
import { useProductStore } from '@/stores/product'
import { useFinanceStore } from '@/stores/finance'
import apiClient from '@/api/client'

const auth = useAuthStore()
const condoStore = useCondominiumStore()
const productStore = useProductStore()
const financeStore = useFinanceStore()

const loading = ref(true)

// ── Price history expand ────────────────────────────
const expandedPrices = ref<Record<number, boolean>>({})

// ── Commission config ───────────────────────────────
const commType = ref<string>('fixed')
const commValue = ref<number | null>(null)
const savingConfig = ref(false)
const configSaved = ref(false)

// ── Commission rate modal ───────────────────────────
const showRateModal = ref(false)
const rateForm = ref({ product_id: 0, value_per_unit: 0, valid_from: '' })
const savingRate = ref(false)

// ── Stock alerts ─────────────────────────────────────
const globalMinStock = ref<number | null>(null)
const productAlerts = ref<{ product_id: number; name: string; min_quantity: number }[]>([])
const alertsSaving = ref(false)
const alertsSaved = ref(false)

const condoId = computed(() => condoStore.activeCondominiumId)

function fmCurrency(v: number | null | undefined): string {
    if (v == null || isNaN(v)) return 'R$ 0,00'
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v)
}

async function loadAll() {
    if (!condoId.value) return
    loading.value = true
    try {
        await productStore.fetchProducts(condoId.value)

        const [commRes, alertRes] = await Promise.all([
            apiClient.get(`/finance/condominiums/${condoId.value}/commission-config`),
            apiClient.get(`/condominiums/${condoId.value}/onboarding/stock-alerts`),
        ])

        commType.value = commRes.data.commission_type || 'fixed'
        commValue.value = commRes.data.commission_value ?? null

        globalMinStock.value = alertRes.data.global_min ?? null
        const saved: Record<number, number> = {}
        for (const item of (alertRes.data.items || [])) saved[item.product_id] = item.min_quantity
        productAlerts.value = productStore.products.map(p => ({
            product_id: p.id,
            name: p.name,
            min_quantity: saved[p.id] ?? 0,
        }))

        await financeStore.fetchCommissionRates(condoId.value)
    } finally {
        loading.value = false
    }
}

onMounted(loadAll)

watch(condoId, () => { if (condoId.value) loadAll() }, { immediate: true })

async function togglePriceHistory(productId: number) {
    if (expandedPrices.value[productId]) {
        expandedPrices.value[productId] = false
    } else {
        await productStore.fetchPriceHistory(productId)
        expandedPrices.value[productId] = true
    }
}

// ── Commission config ───────────────────────────────
async function saveCommissionConfig() {
    if (!condoId.value) return
    savingConfig.value = true
    configSaved.value = false
    try {
        await financeStore.updateCommissionConfig(condoId.value, {
            commission_type: commType.value,
            commission_value: commValue.value,
        })
        configSaved.value = true
        setTimeout(() => configSaved.value = false, 3000)
    } finally {
        savingConfig.value = false
    }
}

// ── Commission rate actions ─────────────────────────
function openNewRate() {
    const firstProduct = productStore.activeProducts[0]
    rateForm.value = {
        product_id: firstProduct?.id || 0,
        value_per_unit: 0,
        valid_from: new Date().toISOString().slice(0, 10),
    }
    showRateModal.value = true
}

async function saveRate() {
    if (!condoId.value) return
    savingRate.value = true
    try {
        await financeStore.createCommissionRate(condoId.value, {
            product_id: rateForm.value.product_id,
            value_per_unit: rateForm.value.value_per_unit,
            valid_from: rateForm.value.valid_from,
        })
        showRateModal.value = false
    } finally {
        savingRate.value = false
    }
}

async function saveStockAlerts() {
    if (!condoId.value) return
    alertsSaving.value = true
    alertsSaved.value = false
    try {
        const payload: any = {}
        if (globalMinStock.value != null && globalMinStock.value > 0) payload.global_min = globalMinStock.value
        const items = productAlerts.value.filter(p => p.min_quantity > 0)
        if (items.length) payload.items = items.map(p => ({ product_id: p.product_id, min_quantity: p.min_quantity }))
        await apiClient.post(`/condominiums/${condoId.value}/onboarding/stock-alerts`, payload)
        alertsSaved.value = true
        setTimeout(() => alertsSaved.value = false, 3000)
    } finally {
        alertsSaving.value = false
    }
}

const commTypeLabel: Record<string, string> = {
    fixed: 'Fixo Mensal',
    percent: 'Percentual sobre recebido',
    per_unit: 'Por unidade vendida',
}

const activeTooltip = ref<string | null>(null)
function toggleTooltip(id: string) {
    activeTooltip.value = activeTooltip.value === id ? null : id
}
</script>

<template>
  <div class="fade-up">
    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-4 mb-7">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Configurações</h1>
        <p class="text-gray-500 text-sm mt-0.5">
          {{ condoStore.activeCondominium?.name }} — Produtos, preços e comissionamento
        </p>
      </div>
    </div>

    <div v-if="!auth.isAdmin" class="card p-8 text-center">
      <p class="text-gray-500">Apenas administradores têm acesso a esta tela.</p>
    </div>

    <template v-else>
      <div v-if="loading" class="text-center py-12">
        <div class="animate-spin w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full mx-auto mb-3"></div>
        <p class="text-sm text-gray-500">Carregando configurações...</p>
      </div>

      <div v-else class="space-y-8">

        <!-- ═══ SECTION 1: PRODUTOS ═══ -->
        <div class="card">
          <div class="p-5 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 class="text-lg font-bold text-gray-800">Catálogo de Produtos</h2>
              <p class="text-xs text-gray-400 mt-0.5">Preços sincronizados via Retaguarda — somente visualização</p>
            </div>
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-200">
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
              Gerenciado pela Retaguarda
            </span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 border-b border-gray-100">
                <tr>
                  <th class="text-left px-5 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Produto</th>
                  <th class="text-center px-3 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Capacidade</th>
                  <th class="text-center px-3 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Cód. Retaguarda</th>
                  <th class="text-right px-3 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Preço Vigente</th>
                  <th class="text-center px-3 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Status</th>
                  <th class="text-center px-5 py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Histórico</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in productStore.products" :key="p.id"
                  class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
                  :class="{ 'opacity-50': !p.is_active }">
                  <td class="px-5 py-3 font-semibold text-gray-800">{{ p.name }}</td>
                  <td class="px-3 py-3 text-center text-gray-600">{{ p.capacity_liters }}L</td>
                  <td class="px-3 py-3 text-center text-gray-400 font-mono text-xs">{{ p.erp_product_code || '—' }}</td>
                  <td class="px-3 py-3 text-right font-semibold" :class="p.current_price ? 'text-green-700' : 'text-gray-400'">
                    {{ p.current_price ? fmCurrency(Number(p.current_price)) : 'Sem preço' }}
                  </td>
                  <td class="px-3 py-3 text-center">
                    <span :class="p.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold">
                      {{ p.is_active ? 'Ativo' : 'Inativo' }}
                    </span>
                  </td>
                  <td class="px-5 py-3 text-center">
                    <button @click="togglePriceHistory(p.id)"
                      class="px-2.5 py-1 text-xs font-medium text-gray-500 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors">
                      {{ expandedPrices[p.id] ? 'Fechar' : 'Ver' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Price history expansion -->
          <template v-for="p in productStore.products" :key="'ph-' + p.id">
            <div v-if="expandedPrices[p.id]" class="px-5 py-4 bg-slate-50 border-t border-gray-100">
              <h4 class="text-xs font-bold text-gray-500 uppercase mb-2">Histórico de Preços — {{ p.name }}</h4>
              <div v-if="productStore.priceHistory[p.id]?.length" class="space-y-1">
                <div v-for="pr in productStore.priceHistory[p.id]" :key="pr.id" class="flex items-center justify-between text-xs">
                  <span class="text-gray-500">Vigência: {{ pr.valid_from }}</span>
                  <span class="font-semibold text-gray-700">{{ fmCurrency(Number(pr.unit_price)) }}</span>
                  <span class="text-gray-400 font-mono">{{ pr.source === 'erp' ? 'Retaguarda' : 'Manual' }}</span>
                </div>
              </div>
              <p v-else class="text-xs text-gray-400">Nenhum preço registrado.</p>
            </div>
          </template>
        </div>

        <!-- ═══ SECTION 2: COMISSIONAMENTO ═══ -->
        <div class="card">
          <div class="p-5 border-b border-gray-100 flex items-start justify-between gap-3">
            <div>
              <h2 class="text-lg font-bold text-gray-800">Comissionamento</h2>
              <p class="text-xs text-gray-400 mt-0.5">Configure o tipo e valor da comissão para este condomínio</p>
            </div>
            <button @click="toggleTooltip('comm-section')" class="text-gray-400 hover:text-gray-600 transition-colors mt-0.5 flex-shrink-0" type="button">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
            </button>
          </div>
          <div v-if="activeTooltip === 'comm-section'" class="mx-5 mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 space-y-1">
            <p><strong>Fixo Mensal:</strong> A FonteGest recebe um valor fixo por mês, independente do faturamento do condomínio.</p>
            <p><strong>Percentual:</strong> A comissão é calculada como % do total recebido (boletos pagos) no mês.</p>
            <p><strong>Por unidade vendida:</strong> Comissão calculada pela quantidade de cada produto entregue, com taxa configurável por produto.</p>
          </div>

          <div class="p-5 space-y-5">
            <!-- Type selector -->
            <div>
              <div class="flex items-center gap-2 mb-2">
                <label class="text-sm font-semibold text-gray-700">Tipo de Comissão</label>
                <button @click="toggleTooltip('comm-type')" class="text-gray-400 hover:text-gray-600 transition-colors" type="button">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
                </button>
              </div>
              <div v-if="activeTooltip === 'comm-type'" class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
                Selecione como a FonteGest será remunerada por este condomínio. A alteração tem efeito a partir do próximo cálculo financeiro.
              </div>
              <div class="flex flex-wrap gap-3">
                <button
                  v-for="(label, key) in commTypeLabel" :key="key"
                  @click="commType = key"
                  :class="commType === key ? 'bg-blue-600 text-white border-blue-600 shadow-sm' : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'"
                  class="px-4 py-2.5 rounded-xl text-sm font-medium border transition-all"
                >{{ label }}</button>
              </div>
            </div>

            <!-- Fixed -->
            <div v-if="commType === 'fixed'" class="flex items-end gap-4">
              <div class="flex-1">
                <label class="text-xs font-bold text-gray-500 uppercase block mb-1.5">Valor Mensal (R$)</label>
                <input v-model.number="commValue" type="number" step="0.01" min="0"
                  class="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm font-medium focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
              </div>
            </div>

            <!-- Percent -->
            <div v-if="commType === 'percent'" class="flex items-end gap-4">
              <div class="flex-1">
                <label class="text-xs font-bold text-gray-500 uppercase block mb-1.5">Alíquota (%)</label>
                <input v-model.number="commValue" type="number" step="0.1" min="0" max="100"
                  class="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm font-medium focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
              </div>
            </div>

            <!-- Per unit → rate table -->
            <div v-if="commType === 'per_unit'" class="space-y-4">
              <div class="flex items-center justify-between">
                <label class="text-sm font-semibold text-gray-700">Taxas por Produto</label>
                <button @click="openNewRate" class="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-xs font-medium hover:bg-blue-100 transition-colors">
                  + Novo Período
                </button>
              </div>
              <div v-if="financeStore.commissionRates.length" class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead class="bg-slate-50">
                    <tr>
                      <th class="text-left px-4 py-2 text-xs font-bold text-gray-500 uppercase">Produto</th>
                      <th class="text-right px-4 py-2 text-xs font-bold text-gray-500 uppercase">R$/Unidade</th>
                      <th class="text-center px-4 py-2 text-xs font-bold text-gray-500 uppercase">Vigência</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="r in financeStore.commissionRates" :key="r.id" class="border-b border-gray-50">
                      <td class="px-4 py-2 font-medium text-gray-700">{{ r.product_name }}</td>
                      <td class="px-4 py-2 text-right font-semibold text-green-700">{{ fmCurrency(Number(r.value_per_unit)) }}</td>
                      <td class="px-4 py-2 text-center text-gray-500">{{ r.valid_from }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="text-sm text-gray-400 text-center py-4">Nenhuma taxa cadastrada.</p>
            </div>

            <!-- Save config button -->
            <div class="flex items-center gap-4 pt-2">
              <button
                @click="saveCommissionConfig"
                :disabled="savingConfig"
                class="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {{ savingConfig ? 'Salvando...' : 'Salvar Configuração' }}
              </button>
              <span v-if="configSaved" class="text-sm text-green-600 font-medium flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                Salvo com sucesso!
              </span>
            </div>
          </div>
        </div>

        <!-- ═══ SECTION 3: ALERTAS DE ESTOQUE ═══ -->
        <div class="card">
          <div class="p-5 border-b border-gray-100 flex items-start justify-between gap-3">
            <div>
              <h2 class="text-lg font-bold text-gray-800">Alertas de Estoque</h2>
              <p class="text-xs text-gray-400 mt-0.5">Defina o estoque mínimo por produto. Um alerta é exibido no painel quando o saldo ficar abaixo do limite.</p>
            </div>
            <button @click="toggleTooltip('stock-section')" class="text-gray-400 hover:text-gray-600 transition-colors mt-0.5 flex-shrink-0" type="button">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 16v-4m0-4h.01"/></svg>
            </button>
          </div>
          <div v-if="activeTooltip === 'stock-section'" class="mx-5 mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 space-y-1">
            <p><strong>Global:</strong> Valor padrão aplicado a todos os produtos sem limite individual. Ex: 10 → alerta quando qualquer produto tiver menos de 10 unidades.</p>
            <p><strong>Individual:</strong> Sobrescreve o global para aquele produto específico. Ex: Galão 20L com mínimo 5 → alerta apenas quando este produto tiver menos de 5 un.</p>
            <p><strong>Zero:</strong> Produto sem limite — alerta somente se o saldo ficar negativo.</p>
          </div>

          <div class="p-5 space-y-4">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 border-b border-gray-100">
                <tr>
                  <th class="text-left px-4 py-2 text-xs font-bold text-gray-500 uppercase">Produto</th>
                  <th class="text-center px-4 py-2 text-xs font-bold text-gray-500 uppercase">Mínimo (un.)</th>
                  <th class="text-left px-4 py-2 text-xs font-bold text-gray-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <!-- Global row -->
                <tr class="bg-blue-50/40">
                  <td class="px-4 py-2.5 font-semibold text-gray-700">Global (todos os produtos)</td>
                  <td class="px-4 py-2.5 text-center">
                    <input v-model.number="globalMinStock" type="number" min="0" placeholder="0"
                      class="w-24 px-2 py-1 border border-gray-200 rounded-lg text-sm text-center focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                  </td>
                  <td class="px-4 py-2.5 text-xs text-gray-400">Aplicado quando não há limite individual</td>
                </tr>
                <!-- Per-product rows -->
                <tr v-for="pa in productAlerts" :key="pa.product_id">
                  <td class="px-4 py-2.5 text-gray-700">{{ pa.name }}</td>
                  <td class="px-4 py-2.5 text-center">
                    <input v-model.number="pa.min_quantity" type="number" min="0" placeholder="0"
                      class="w-24 px-2 py-1 border border-gray-200 rounded-lg text-sm text-center focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                  </td>
                  <td class="px-4 py-2.5 text-xs">
                    <span v-if="pa.min_quantity > 0" class="text-amber-600 font-medium">Alerta abaixo de {{ pa.min_quantity }} un.</span>
                    <span v-else class="text-gray-400">Sem limite individual</span>
                  </td>
                </tr>
              </tbody>
            </table>

            <div class="flex items-center gap-4 pt-1">
              <button @click="saveStockAlerts" :disabled="alertsSaving"
                class="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
                {{ alertsSaving ? 'Salvando...' : 'Salvar Alertas' }}
              </button>
              <span v-if="alertsSaved" class="text-sm text-green-600 font-medium flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                Alertas salvos!
              </span>
            </div>
          </div>
        </div>

      </div>
    </template>

    <!-- ═══ MODALS ═══ -->

    <!-- New Rate modal -->
    <Teleport to="body">
      <div v-if="showRateModal" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" @click.self="showRateModal = false">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
          <h3 class="text-lg font-bold text-gray-800 mb-5">Nova Taxa de Comissão</h3>
          <div class="space-y-4">
            <div>
              <label class="text-xs font-bold text-gray-500 uppercase block mb-1">Produto</label>
              <select v-model.number="rateForm.product_id" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm">
                <option v-for="p in productStore.activeProducts" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs font-bold text-gray-500 uppercase block mb-1">R$ por Unidade</label>
              <input v-model.number="rateForm.value_per_unit" type="number" step="0.01" min="0" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            </div>
            <div>
              <label class="text-xs font-bold text-gray-500 uppercase block mb-1">Vigência a partir de</label>
              <input v-model="rateForm.valid_from" type="date" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
            </div>
          </div>
          <div class="flex justify-end gap-3 mt-6">
            <button @click="showRateModal = false" class="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 font-medium">Cancelar</button>
            <button @click="saveRate" :disabled="savingRate" class="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {{ savingRate ? 'Salvando...' : 'Salvar Taxa' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
