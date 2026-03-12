<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useCondominiumStore } from '@/stores/condominium'
import { useBillingStore, type BillingRow } from '@/stores/billing'
import EvidenceUpload from '@/components/EvidenceUpload.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

const condoStore = useCondominiumStore()
const billing = useBillingStore()

// Month selector
const now = new Date()
const currentMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)

// Editing state
const editingResident = ref<number | null>(null)
const editForm = ref({ name: '', cpf_masked: '', phone: '' })

// Load data when condo or month changes
async function loadGrid() {
  const condoId = condoStore.activeCondominiumId
  if (!condoId) return
  await billing.fetchGrid(condoId, currentMonth.value)
}

onMounted(() => loadGrid())
watch([() => condoStore.activeCondominiumId, currentMonth], () => loadGrid())

// Quantity change handler
async function onQuantityChange(itemId: number, event: Event) {
  const input = event.target as HTMLInputElement
  const qty = Math.max(0, parseInt(input.value) || 0)
  input.value = String(qty)
  await billing.updateQuantity(itemId, qty)
}

// Resident editing
function startEditResident(row: BillingRow) {
  editingResident.value = row.billing_id
  editForm.value = {
    name: row.resident.name || '',
    cpf_masked: row.resident.cpf_masked || '',
    phone: row.resident.phone || '',
  }
}

async function saveResident(billingId: number) {
  await billing.updateResident(billingId, editForm.value)
  editingResident.value = null
}

function cancelEdit() {
  editingResident.value = null
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
    <div class="flex flex-wrap items-start justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Lançamento de Consumo</h1>
        <p class="text-gray-500 text-sm mt-0.5">
          {{ billing.condominiumName || condoStore.activeCondominium?.name }} — Registre as entregas mensais por unidade
        </p>
      </div>
      <div class="flex items-center gap-3">
        <input
          v-model="currentMonth"
          type="month"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
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
      <!-- Product prices bar -->
      <div v-if="billing.products.length" class="flex gap-3 mb-4 flex-wrap">
        <div v-for="p in billing.products" :key="p.id"
          class="flex items-center gap-2 bg-white border border-gray-200 rounded-lg px-3 py-1.5 shadow-sm text-sm">
          <span class="font-medium text-gray-700">{{ p.name }}</span>
          <span class="text-blue-600 font-semibold">{{ formatCurrency(p.unit_price) }}</span>
        </div>
      </div>

      <!-- Submit result banner -->
      <div v-if="billing.submitResult" class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2">
        <svg class="w-5 h-5 text-blue-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span class="text-sm text-blue-700">{{ billing.submitResult }}</span>
      </div>

      <!-- Table -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <!-- Header -->
            <thead>
              <tr class="bg-slate-800 text-white text-xs uppercase tracking-wider">
                <th class="px-3 py-3 text-left font-semibold sticky left-0 bg-slate-800 z-10">Apto</th>
                <th class="px-3 py-3 text-left font-semibold">CPF</th>
                <th class="px-3 py-3 text-left font-semibold">Nome</th>
                <th class="px-3 py-3 text-left font-semibold">Tel</th>
                <th v-for="p in billing.products" :key="p.id"
                  class="px-3 py-3 text-center font-semibold whitespace-nowrap">
                  {{ p.name.replace('Galão ', '').replace('INDAIÁ', 'IND').replace('IAIÁ', 'IAI') }}
                  <br><span class="text-[10px] font-normal opacity-70">{{ formatCurrency(p.unit_price) }}</span>
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
                    <input v-model="editForm.cpf_masked" class="w-28 px-1.5 py-1 border rounded text-xs" placeholder="CPF" />
                  </template>
                  <template v-else>
                    <span class="text-xs text-gray-500" :class="{ 'opacity-40': !row.has_consumption }">
                      {{ row.resident.cpf_masked || '—' }}
                    </span>
                  </template>
                </td>

                <!-- Nome (editable) -->
                <td class="px-3 py-2 max-w-[180px]">
                  <template v-if="editingResident === row.billing_id">
                    <input v-model="editForm.name" class="w-full px-1.5 py-1 border rounded text-xs" placeholder="Nome" />
                  </template>
                  <template v-else>
                    <div class="flex items-center gap-1">
                      <span class="text-gray-700 truncate text-xs" :class="{ 'opacity-40': !row.has_consumption }">
                        {{ row.resident.name || '—' }}
                      </span>
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
                    <input v-model="editForm.phone" class="w-28 px-1.5 py-1 border rounded text-xs" placeholder="Telefone" />
                  </template>
                  <template v-else>
                    <span class="text-xs text-gray-500" :class="{ 'opacity-40': !row.has_consumption }">
                      {{ row.resident.phone || '—' }}
                    </span>
                  </template>
                </td>

                <!-- Product quantity columns -->
                <td v-for="p in billing.products" :key="p.id" class="px-2 py-2 text-center">
                  <input
                    type="number"
                    min="0"
                    :value="row.items.find(i => i.product_id === p.id)?.quantity ?? 0"
                    @change="onQuantityChange(row.items.find(i => i.product_id === p.id)!.id, $event)"
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
                        :disabled="!row.has_consumption"
                        :class="row.has_consumption ? 'text-gray-500 hover:bg-gray-100' : 'text-gray-300 cursor-not-allowed'"
                        class="p-1 rounded" title="Editar morador">
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
              <tr class="bg-slate-800 text-white text-sm font-semibold">
                <td class="px-3 py-3 sticky left-0 bg-slate-800 z-10">Totais</td>
                <td colspan="3"></td>
                <td v-for="p in billing.products" :key="p.id" class="px-3 py-3 text-center font-mono">
                  {{ billing.summary?.totals_by_product[p.id] ?? 0 }}
                </td>
                <td class="px-3 py-3 text-right font-mono">{{ formatCurrency(billing.summary?.total_faturado ?? 0) }}</td>
                <td colspan="2"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Summary bar -->
      <div class="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div class="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3">
          <p class="text-xs text-emerald-600 font-medium">Arrecadado</p>
          <p class="text-lg font-bold text-emerald-700">{{ formatCurrency(billing.summary?.total_arrecadado ?? 0) }}</p>
        </div>
        <div class="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
          <p class="text-xs text-amber-600 font-medium">Em Aberto</p>
          <p class="text-lg font-bold text-amber-700">{{ formatCurrency(billing.summary?.total_em_aberto ?? 0) }}</p>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3">
          <p class="text-xs text-slate-500 font-medium">Total Faturado</p>
          <p class="text-lg font-bold text-slate-700">{{ formatCurrency(billing.summary?.total_faturado ?? 0) }}</p>
        </div>
        <div class="flex items-center">
          <button
            @click="handleSubmit"
            :disabled="!billing.canSubmit || billing.submitting"
            class="w-full px-4 py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed shadow-sm flex items-center justify-center gap-2"
          >
            <div v-if="billing.submitting" class="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full"></div>
            <template v-else>
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
              </svg>
              Finalizar Faturamento
            </template>
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
