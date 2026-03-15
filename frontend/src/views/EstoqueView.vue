<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { useCondominiumStore } from '@/stores/condominium'
import { useStockStore, type StockEntry } from '@/stores/stock'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler)

const condoStore = useCondominiumStore()
const stock = useStockStore()

// ── Month selector ────────────────────────────────────────────────────
const now = new Date()
const currentMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)

// ── Modal state ───────────────────────────────────────────────────────
const showModal = ref(false)
const editingEntry = ref<StockEntry | null>(null)
const modalForm = ref({
  product_id: 0,
  quantity: 1,
  entry_type: 'purchase',
  notes: '',
})
const modalError = ref('')
const modalSaving = ref(false)

// ── Load ──────────────────────────────────────────────────────────────
async function load() {
  const id = condoStore.activeCondominiumId
  if (!id) return
  await stock.fetchOverview(id, currentMonth.value)
  await stock.fetchChart(id, currentMonth.value, 6)
}

watch([() => condoStore.activeCondominiumId, currentMonth], () => load(), { immediate: true })

// ── Computed: threshold alerts ────────────────────────────────────────
const alerts = computed(() =>
  (stock.overview?.products ?? []).filter(p => p.is_below_threshold || p.is_negative)
)

// ── Product color palette ─────────────────────────────────────────────
const PALETTE = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6']

function productColor(idx: number): string {
  return PALETTE[idx % PALETTE.length] ?? '#6366f1'
}

// ── Chart ─────────────────────────────────────────────────────────────
const chartData = computed(() => {
  const cd = stock.chartData
  if (!cd) return { labels: [], datasets: [] }
  const datasets = Object.entries(cd.series).map(([name, values], idx) => ({
    label: name,
    data: values,
    borderColor: productColor(idx),
    backgroundColor: productColor(idx) + '20',
    tension: 0.3,
    fill: false,
    pointRadius: 4,
  }))
  return { labels: cd.months, datasets }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { boxWidth: 12, padding: 16 } },
  },
  scales: {
    y: { beginAtZero: false, ticks: { stepSize: 1 } },
  },
}

// ── Modal helpers ─────────────────────────────────────────────────────
function openCreateModal() {
  editingEntry.value = null
  modalForm.value = {
    product_id: stock.overview?.products[0]?.product_id ?? 0,
    quantity: 1,
    entry_type: 'purchase',
    notes: '',
  }
  modalError.value = ''
  showModal.value = true
}

function openEditModal(entry: StockEntry) {
  editingEntry.value = entry
  modalForm.value = {
    product_id: entry.product_id,
    quantity: entry.quantity,
    entry_type: entry.entry_type,
    notes: entry.notes ?? '',
  }
  modalError.value = ''
  showModal.value = true
}

async function saveModal() {
  const condoId = condoStore.activeCondominiumId
  if (!condoId) return
  if (!modalForm.value.product_id) {
    modalError.value = 'Selecione um produto'
    return
  }
  if (modalForm.value.quantity <= 0) {
    modalError.value = 'Quantidade deve ser maior que zero'
    return
  }

  modalSaving.value = true
  modalError.value = ''
  try {
    if (editingEntry.value) {
      await stock.updateEntry(editingEntry.value.id, {
        quantity: modalForm.value.quantity,
        notes: modalForm.value.notes || undefined,
      })
    } else {
      await stock.createEntry({
        condominium_id: condoId,
        product_id: modalForm.value.product_id,
        reference_month: currentMonth.value,
        quantity: modalForm.value.quantity,
        entry_type: modalForm.value.entry_type,
        notes: modalForm.value.notes || undefined,
      })
    }
    showModal.value = false
    await load()
  } catch (e: any) {
    modalError.value = e?.response?.data?.detail ?? 'Erro ao salvar'
  } finally {
    modalSaving.value = false
  }
}

async function handleDelete(entryId: number) {
  if (!confirm('Excluir este lançamento de estoque?')) return
  try {
    await stock.deleteEntry(entryId)
    await load()
  } catch (e: any) {
    alert(e?.response?.data?.detail ?? 'Erro ao excluir')
  }
}

// ── Formatting ────────────────────────────────────────────────────────
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const entryTypeLabel: Record<string, string> = {
  purchase: 'Compra',
  initial: 'Saldo Inicial',
}
</script>

<template>
  <div class="fade-up">
    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-4 mb-7">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Controle de Estoque</h1>
        <p class="text-gray-500 text-sm mt-0.5">
          {{ stock.overview?.condominium_name ?? condoStore.activeCondominium?.name }} — Auditoria por produto
        </p>
      </div>
      <div class="flex items-center gap-3">
        <input
          v-model="currentMonth"
          type="month"
          class="input text-sm"
          style="width:160px"
        />
        <button class="btn-primary text-sm" @click="openCreateModal">
          + Registrar Abastecimento
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="stock.loading" class="space-y-6 py-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <SkeletonLoader v-for="i in 3" :key="i" class="h-40 !rounded-xl" />
      </div>
      <SkeletonLoader class="h-64 !rounded-xl" />
      <SkeletonLoader class="h-48 !rounded-xl" />
    </div>

    <template v-else-if="stock.overview">

      <!-- Fraud alerts -->
      <div v-if="alerts.length" class="space-y-2 mb-6">
        <div
          v-for="a in alerts"
          :key="a.product_id"
          class="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-50 border border-red-200 animate-pulse"
        >
          <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
          </svg>
          <span class="text-sm font-semibold text-red-700">
            <template v-if="a.is_negative">Divergência de Estoque — {{ a.product_name }} — Verifique desvios</template>
            <template v-else>Estoque Baixo — {{ a.product_name }} — Abaixo do mínimo ({{ a.min_stock_alert }} un.)</template>
            <span class="font-normal ml-2">(Saldo atual: {{ a.saldo_atual }})</span>
          </span>
        </div>
      </div>

      <!-- Product cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <div
          v-for="(p, idx) in stock.overview.products"
          :key="p.product_id"
          class="card p-5"
          :class="p.is_negative ? 'border-2 border-red-300' : p.is_below_threshold ? 'border-2 border-amber-300' : ''"
        >
          <!-- Product header -->
          <div class="flex items-center gap-3 mb-4">
            <div
              class="w-3 h-3 rounded-full flex-shrink-0"
              :style="{ backgroundColor: productColor(idx) }"
            />
            <div>
              <p class="font-semibold text-gray-800">{{ p.product_name }}</p>
              <p class="text-xs text-gray-400">{{ p.capacity_liters }}L</p>
            </div>
          </div>

          <!-- Ledger rows -->
          <div class="space-y-1 text-sm">
            <div class="flex justify-between text-gray-500">
              <span>Saldo anterior</span>
              <span class="font-mono">{{ p.saldo_anterior }}</span>
            </div>
            <div class="flex justify-between text-emerald-600">
              <span>+ Entradas</span>
              <span class="font-mono">{{ p.entradas }}</span>
            </div>
            <div class="flex justify-between text-orange-500">
              <span>− Consumo lançado</span>
              <span class="font-mono">{{ p.consumo_lancado }}</span>
            </div>
            <div class="border-t border-gray-100 pt-2 mt-2 flex justify-between font-bold"
              :class="p.is_negative ? 'text-red-600' : p.is_below_threshold ? 'text-amber-600' : 'text-gray-900'">
              <span>Saldo atual</span>
              <span class="font-mono">{{ p.saldo_atual }}</span>
            </div>
            <div v-if="p.is_below_threshold && !p.is_negative && p.min_stock_alert != null" class="mt-1.5">
              <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-700">
                Abaixo do mínimo ({{ p.min_stock_alert }} un.)
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- History chart -->
      <div v-if="stock.chartData && stock.chartData.months.length > 1" class="card p-5 mb-8">
        <h2 class="text-sm font-semibold text-gray-700 mb-4">Histórico de Saldo (últimos 6 meses)</h2>
        <div style="height: 220px">
          <Line :data="chartData" :options="chartOptions" />
        </div>
      </div>

      <!-- Entries table -->
      <div class="card overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 class="text-sm font-semibold text-gray-700">
            Lançamentos do mês
            <span class="ml-2 text-xs font-normal text-gray-400">({{ stock.overview.entries.length }})</span>
          </h2>
        </div>

        <div v-if="stock.overview.entries.length === 0" class="py-8">
          <EmptyState
            title="Nenhum lançamento no mês"
            description="Não houve abastecimentos ou saldos iniciais registrados neste período."
          >
            <template #action>
              <button class="btn-primary text-sm shadow-sm" @click="openCreateModal">Registrar Abastecimento</button>
            </template>
          </EmptyState>
        </div>

        <table v-else class="w-full text-sm">
          <thead class="bg-gray-50 text-xs uppercase text-gray-500 tracking-wide">
            <tr>
              <th class="px-5 py-3 text-left">Data</th>
              <th class="px-5 py-3 text-left">Produto</th>
              <th class="px-5 py-3 text-left">Tipo</th>
              <th class="px-5 py-3 text-right">Qtd</th>
              <th class="px-5 py-3 text-left">Observação</th>
              <th class="px-5 py-3 text-center">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <tr
              v-for="entry in stock.overview.entries"
              :key="entry.id"
              class="hover:bg-gray-50 transition-colors"
            >
              <td class="px-5 py-3 text-gray-500 whitespace-nowrap">{{ formatDate(entry.created_at) }}</td>
              <td class="px-5 py-3 font-medium text-gray-800">{{ entry.product_name }}</td>
              <td class="px-5 py-3">
                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                  :class="entry.entry_type === 'initial' ? 'bg-purple-50 text-purple-700' : 'bg-emerald-50 text-emerald-700'">
                  {{ entryTypeLabel[entry.entry_type] ?? entry.entry_type }}
                </span>
              </td>
              <td class="px-5 py-3 text-right font-mono font-semibold text-gray-800">{{ entry.quantity }}</td>
              <td class="px-5 py-3 text-gray-500 max-w-xs truncate">{{ entry.notes ?? '—' }}</td>
              <td class="px-5 py-3 text-center">
                <div class="flex items-center justify-center gap-2">
                  <button
                    class="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                    @click="openEditModal(entry)"
                  >
                    Editar
                  </button>
                  <span class="text-gray-200">|</span>
                  <button
                    class="text-xs text-red-500 hover:text-red-700 font-medium"
                    @click="handleDelete(entry.id)"
                  >
                    Excluir
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </template>

    <!-- Error state -->
    <div v-else-if="stock.error" class="card p-8 text-center text-red-500 text-sm">
      {{ stock.error }}
    </div>

    <!-- No condo selected -->
    <div v-else class="py-12">
      <EmptyState
        title="Nenhum condomínio selecionado"
        description="Por favor, selecione um condomínio no menu principal para visualizar o controle de estoque."
      />
    </div>

    <!-- ── Modal ──────────────────────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
        @click.self="showModal = false"
      >
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
          <h3 class="text-lg font-bold text-gray-900 mb-5">
            {{ editingEntry ? 'Editar lançamento' : 'Registrar abastecimento' }}
          </h3>

          <div class="space-y-4">
            <!-- Product selector (only for new entries) -->
            <div v-if="!editingEntry">
              <label class="block text-xs font-medium text-gray-600 mb-1">Produto</label>
              <select v-model="modalForm.product_id" class="input w-full">
                <option v-for="p in stock.overview?.products" :key="p.product_id" :value="p.product_id">
                  {{ p.product_name }}
                </option>
              </select>
            </div>

            <!-- Type (only for new entries) -->
            <div v-if="!editingEntry">
              <label class="block text-xs font-medium text-gray-600 mb-1">Tipo</label>
              <select v-model="modalForm.entry_type" class="input w-full">
                <option value="purchase">Compra</option>
                <option value="initial">Saldo Inicial</option>
              </select>
            </div>

            <!-- Quantity -->
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">Quantidade</label>
              <input
                v-model.number="modalForm.quantity"
                type="number"
                min="1"
                class="input w-full"
                placeholder="0"
              />
            </div>

            <!-- Notes -->
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">Observação (opcional)</label>
              <input
                v-model="modalForm.notes"
                type="text"
                class="input w-full"
                placeholder="Ex: NF 12345"
              />
            </div>

            <!-- Error -->
            <p v-if="modalError" class="text-xs text-red-500">{{ modalError }}</p>
          </div>

          <!-- Buttons -->
          <div class="flex justify-end gap-3 mt-6">
            <button class="btn-secondary text-sm" @click="showModal = false">Cancelar</button>
            <button class="btn-primary text-sm" :disabled="modalSaving" @click="saveModal">
              {{ modalSaving ? 'Salvando…' : 'Salvar' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
