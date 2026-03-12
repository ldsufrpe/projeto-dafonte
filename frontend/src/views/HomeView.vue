<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCondominiumStore } from '@/stores/condominium'
import CondominiumCard from '@/components/CondominiumCard.vue'
import apiClient from '@/api/client'

interface OperatorItem {
  id: number
  username: string
  full_name: string | null
  is_active: boolean
  condominium_ids: number[]
}

const router = useRouter()
const auth = useAuthStore()
const condoStore = useCondominiumStore()

const selectedMonth = ref(condoStore.referenceMonth)
const selectedOperatorId = ref<number | null>(null)
const operators = ref<OperatorItem[]>([])

// ── Assignment popover state ───────────────────────────────────────────────
interface PopoverTarget {
  condoId: number
  condoName: string
  currentOperatorId: number | null
}
const popover = ref<PopoverTarget | null>(null)
const popoverPos = ref({ top: 0, left: 0 })
const pendingUserId = ref<number | null | undefined>(undefined) // undefined = not yet chosen
const savingAssignment = ref(false)

// ── Load ───────────────────────────────────────────────────────────────────
async function loadOperators() {
  if (!auth.isAdmin) return
  try {
    const { data } = await apiClient.get<OperatorItem[]>('/assignments/operators')
    operators.value = data
  } catch {
    // non-critical
  }
}

onMounted(async () => {
  await condoStore.fetchCondominiums(selectedMonth.value)
  await loadOperators()
})

watch(selectedMonth, (m) => {
  condoStore.fetchCondominiums(m, selectedOperatorId.value)
})

watch(selectedOperatorId, (id) => {
  condoStore.fetchCondominiums(selectedMonth.value, id)
})

// ── Sorting ────────────────────────────────────────────────────────────────
const sortedCondominiums = computed(() => {
  const statusOrder: Record<string, number> = {
    not_started: 3,
    in_progress: 1,
    submitted: 2,
    synced: 4,
  }
  return [...condoStore.condominiums].sort((a, b) => {
    if (a.has_stock_alert !== b.has_stock_alert) return a.has_stock_alert ? -1 : 1
    return (statusOrder[a.month_status] ?? 5) - (statusOrder[b.month_status] ?? 5)
  })
})

// ── Selected operator label ────────────────────────────────────────────────
const selectedOperatorName = computed(() => {
  if (!selectedOperatorId.value) return null
  const op = operators.value.find(o => o.id === selectedOperatorId.value)
  return op ? (op.full_name || op.username) : null
})

// ── Navigation ─────────────────────────────────────────────────────────────
async function selectCondominium(id: number) {
  condoStore.setActive(id)
  router.push('/dashboard')
}

// ── Assignment popover ─────────────────────────────────────────────────────
function openAssignPopover(condoId: number, condoName: string, currentOpId: number | null, event: MouseEvent) {
  event.stopPropagation()
  const btn = event.currentTarget as HTMLElement
  const rect = btn.getBoundingClientRect()
  // Position popover below the cell, aligned to left of trigger
  popoverPos.value = {
    top: rect.bottom + window.scrollY + 6,
    left: Math.min(rect.left + window.scrollX, window.innerWidth - 280),
  }
  popover.value = { condoId, condoName, currentOperatorId: currentOpId }
  pendingUserId.value = currentOpId // pre-select current
}

function closePopover() {
  popover.value = null
  pendingUserId.value = undefined
}

async function saveAssignment() {
  if (!popover.value || pendingUserId.value === undefined) return
  savingAssignment.value = true
  try {
    const { data } = await apiClient.post(`/assignments/condominiums/${popover.value.condoId}`, {
      user_id: pendingUserId.value,
    })
    // Update the row locally without refetch
    const condo = condoStore.condominiums.find(c => c.id === popover.value!.condoId)
    if (condo) {
      condo.operator_name = data.operator
        ? (data.operator.full_name || data.operator.username)
        : null
    }
    // Refresh operator list (condominium_ids may have changed)
    await loadOperators()
    closePopover()
  } catch (err: any) {
    alert(err?.response?.data?.detail ?? 'Erro ao salvar atribuição')
  } finally {
    savingAssignment.value = false
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
const statusConfig: Record<string, { label: string; classes: string }> = {
  not_started: { label: 'Não iniciado', classes: 'bg-gray-100 text-gray-600' },
  in_progress:  { label: 'Em andamento', classes: 'bg-amber-100 text-amber-700' },
  submitted:    { label: 'Enviado',       classes: 'bg-blue-100 text-blue-700'  },
  synced:       { label: 'Sincronizado',  classes: 'bg-emerald-100 text-emerald-700' },
}

function fmt(v: number) {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}
function pct(a: number, b: number) {
  if (!b) return '0%'
  return ((a / b) * 100).toFixed(1) + '%'
}

// Derive current operator id from operator_name match (for pre-select in popover)
function getCurrentOperatorId(operatorName: string | null | undefined): number | null {
  if (!operatorName) return null
  const op = operators.value.find(o => (o.full_name || o.username) === operatorName)
  return op?.id ?? null
}
</script>

<template>
  <div class="fade-up">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">
          {{ auth.isAdmin ? 'Painel Gerencial' : 'Painel de Trabalho' }}
        </h1>
        <p class="text-gray-500 text-sm mt-0.5">
          {{ auth.isAdmin
            ? 'Visão consolidada de todos os condomínios'
            : 'Selecione um condomínio para gerenciar' }}
        </p>
        <!-- Active filter badge (admin only) -->
        <div v-if="auth.isAdmin && selectedOperatorName"
          class="mt-2 inline-flex items-center gap-1.5 px-3 py-1 bg-amber-50 border border-amber-200 rounded-full text-xs text-amber-700 font-medium">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z"/>
          </svg>
          Filtrando por: {{ selectedOperatorName }} — {{ condoStore.condominiums.length }} condomínio{{ condoStore.condominiums.length !== 1 ? 's' : '' }}
          <button
            class="ml-1 text-amber-500 hover:text-amber-800 transition-colors"
            title="Limpar filtro"
            @click="selectedOperatorId = null"
          >✕</button>
        </div>
      </div>

      <!-- Controls -->
      <div class="flex items-center gap-2 flex-wrap">
        <input
          v-model="selectedMonth"
          type="month"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
        />
        <!-- Operator filter (admin only) -->
        <select
          v-if="auth.isAdmin"
          v-model="selectedOperatorId"
          class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option :value="null">Todos os operadores</option>
          <option v-for="op in operators" :key="op.id" :value="op.id">
            {{ op.full_name || op.username }}{{ !op.is_active ? ' (inativo)' : '' }}
          </option>
        </select>
        <button
          @click="condoStore.fetchCondominiums(selectedMonth, selectedOperatorId)"
          class="px-4 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 font-medium text-sm transition-colors flex items-center gap-2 bg-white"
        >
          <svg class="w-4 h-4" :class="{ 'animate-spin': condoStore.loading }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Atualizar
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="condoStore.loading && !condoStore.condominiums.length" class="text-center py-12">
      <div class="animate-spin w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full mx-auto mb-3"></div>
      <p class="text-sm text-gray-500">Carregando painel...</p>
    </div>

    <!-- Error -->
    <div v-else-if="condoStore.error" class="bg-red-50 border border-red-200 p-4 rounded-xl text-red-700 text-sm mb-6">
      {{ condoStore.error }}
    </div>

    <template v-else>
      <!-- ══ ADMIN VIEW ══ -->
      <template v-if="auth.isAdmin">
        <!-- Global KPI cards -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #64748b">
            <p class="text-xs text-gray-500 font-medium mb-1">Condomínios</p>
            <p class="text-2xl font-bold text-gray-900">{{ condoStore.condominiums.length }}</p>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #6366f1">
            <p class="text-xs text-gray-500 font-medium mb-1">Total Faturado</p>
            <p class="text-2xl font-bold text-gray-900">{{ fmt(condoStore.totalBilledAll) }}</p>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #22c55e">
            <p class="text-xs text-gray-500 font-medium mb-1">Total Recebido</p>
            <p class="text-2xl font-bold text-emerald-700">{{ fmt(condoStore.totalReceivedAll) }}</p>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4" style="border-left: 4px solid #f59e0b">
            <p class="text-xs text-gray-500 font-medium mb-1">Inadimplência</p>
            <p class="text-2xl font-bold text-amber-700">
              {{ pct(condoStore.totalBilledAll - condoStore.totalReceivedAll, condoStore.totalBilledAll) }}
            </p>
          </div>
        </div>

        <!-- Admin table -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-slate-800 text-white text-xs uppercase tracking-wider">
                  <th class="px-4 py-3 text-left font-semibold">Condomínio</th>
                  <th class="px-4 py-3 text-left font-semibold">Operador</th>
                  <th class="px-4 py-3 text-center font-semibold">Progresso</th>
                  <th class="px-4 py-3 text-center font-semibold">Status</th>
                  <th class="px-4 py-3 text-right font-semibold">Faturado</th>
                  <th class="px-4 py-3 text-right font-semibold">Recebido</th>
                  <th class="px-4 py-3 text-right font-semibold">Comissão</th>
                  <th class="px-4 py-3 text-center font-semibold">Ações</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-if="!condoStore.condominiums.length">
                  <td colspan="8" class="px-4 py-8 text-center text-gray-400">Nenhum condomínio encontrado</td>
                </tr>
                <tr
                  v-for="c in condoStore.condominiums"
                  :key="c.id"
                  class="hover:bg-gray-50 transition-colors cursor-pointer"
                  :class="{ 'bg-red-50/30': c.has_stock_alert }"
                  @click="selectCondominium(c.id)"
                >
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2">
                      <!-- Stock alert indicator -->
                      <span v-if="c.has_stock_alert" class="w-2 h-2 rounded-full bg-red-500 animate-pulse flex-shrink-0" title="Alerta de estoque negativo"></span>
                      <div>
                        <p class="font-semibold text-gray-900">{{ c.name }}</p>
                        <p class="text-xs text-gray-400">{{ c.address || c.erp_code }}</p>
                      </div>
                    </div>
                  </td>

                  <!-- Operator cell with inline assignment -->
                  <td class="px-4 py-3" @click.stop>
                    <!-- Has operator: name chip with edit icon -->
                    <button
                      v-if="c.operator_name"
                      class="group inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-100 hover:bg-blue-100 text-slate-700 hover:text-blue-700 transition-colors text-sm font-medium"
                      title="Clique para reatribuir operador"
                      @click="openAssignPopover(c.id, c.name, getCurrentOperatorId(c.operator_name), $event)"
                    >
                      {{ c.operator_name }}
                      <svg class="w-3 h-3 opacity-40 group-hover:opacity-100 transition-opacity flex-shrink-0"
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round"
                          d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
                      </svg>
                    </button>
                    <!-- No operator: visible "Atribuir" button -->
                    <button
                      v-else
                      class="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-dashed border-gray-300 text-gray-400 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-colors text-xs font-medium"
                      title="Atribuir operador"
                      @click="openAssignPopover(c.id, c.name, null, $event)"
                    >
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
                      </svg>
                      Atribuir
                    </button>
                  </td>

                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2 min-w-[120px]">
                      <div class="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          class="h-full bg-blue-500 rounded-full transition-all"
                          :style="{ width: c.total_units ? (c.units_launched / c.total_units * 100) + '%' : '0%' }"
                        ></div>
                      </div>
                      <span class="text-xs text-gray-500 whitespace-nowrap">{{ c.units_launched }}/{{ c.total_units }}</span>
                    </div>
                  </td>
                  <td class="px-4 py-3 text-center">
                    <span :class="statusConfig[c.month_status]?.classes ?? ''"
                      class="inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap">
                      {{ statusConfig[c.month_status]?.label ?? c.month_status }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-right font-mono text-gray-700">{{ fmt(c.total_billed) }}</td>
                  <td class="px-4 py-3 text-right font-mono text-emerald-700 font-semibold">{{ fmt(c.total_received) }}</td>
                  <td class="px-4 py-3 text-right font-mono text-blue-700">{{ fmt(c.commission_due) }}</td>
                  <td class="px-4 py-3 text-center" @click.stop>
                    <button
                      @click="selectCondominium(c.id)"
                      class="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 transition-colors"
                    >
                      Gerenciar
                    </button>
                    <router-link
                      v-if="!c.onboarding_complete"
                      :to="`/implantacao/${c.id}`"
                      class="ml-2 px-3 py-1.5 bg-amber-500 text-white rounded-lg text-xs font-semibold hover:bg-amber-600 transition-colors inline-block"
                      @click.stop
                    >
                      Implantar
                    </router-link>
                  </td>
                </tr>
              </tbody>
              <!-- Footer totals -->
              <tfoot v-if="condoStore.condominiums.length">
                <tr class="bg-slate-800 text-white text-sm font-semibold">
                  <td colspan="4" class="px-4 py-3">Totais{{ selectedOperatorName ? ` — ${selectedOperatorName}` : '' }}</td>
                  <td class="px-4 py-3 text-right font-mono">{{ fmt(condoStore.totalBilledAll) }}</td>
                  <td class="px-4 py-3 text-right font-mono text-emerald-400">{{ fmt(condoStore.totalReceivedAll) }}</td>
                  <td class="px-4 py-3 text-right font-mono text-blue-300">
                    {{ fmt(condoStore.condominiums.reduce((s, c) => s + c.commission_due, 0)) }}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </template>

      <!-- ══ OPERATOR VIEW ══ -->
      <template v-else>
        <div v-if="!condoStore.condominiums.length" class="text-center py-16 bg-white rounded-2xl border border-gray-100 shadow-sm">
          <p class="text-gray-500 font-medium">Nenhum condomínio atribuído a você.</p>
          <p class="text-gray-400 text-sm mt-1">Solicite ao administrador que vincule condomínios à sua conta.</p>
        </div>
        <div v-else class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          <CondominiumCard
            v-for="condo in sortedCondominiums"
            :key="condo.id"
            :condominium="condo"
            @select="selectCondominium"
          />
        </div>
      </template>
    </template>

    <!-- ══ ASSIGNMENT POPOVER ══ -->
    <Teleport to="body">
      <!-- Transparent overlay to close on outside click -->
      <div
        v-if="popover"
        class="fixed inset-0 z-[50]"
        @click="closePopover"
      />

      <!-- Popover card -->
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-100 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          v-if="popover"
          class="fixed z-[51] w-72 bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden"
          :style="{ top: popoverPos.top + 'px', left: popoverPos.left + 'px' }"
          @click.stop
        >
          <!-- Header -->
          <div class="px-4 py-3 bg-slate-50 border-b border-gray-200">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Atribuir operador</p>
            <p class="text-sm font-bold text-gray-800 mt-0.5 truncate">{{ popover.condoName }}</p>
          </div>

          <!-- Operator list -->
          <div class="max-h-56 overflow-y-auto py-1">
            <!-- No operator option -->
            <label
              class="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer transition-colors"
              :class="{ 'bg-blue-50': pendingUserId === null }"
            >
              <input
                type="radio"
                :value="null"
                v-model="pendingUserId"
                class="accent-blue-600"
              />
              <span class="text-sm text-gray-400 italic">Sem operador</span>
            </label>

            <div class="border-t border-gray-100 my-0.5"/>

            <!-- Operator options -->
            <label
              v-for="op in operators"
              :key="op.id"
              class="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer transition-colors"
              :class="{ 'bg-blue-50': pendingUserId === op.id }"
            >
              <input
                type="radio"
                :value="op.id"
                v-model="pendingUserId"
                class="accent-blue-600"
              />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-800 truncate">{{ op.full_name || op.username }}</p>
                <p class="text-xs text-gray-400">{{ op.username }}</p>
              </div>
              <span
                v-if="!op.is_active"
                class="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded-full font-medium flex-shrink-0"
              >inativo</span>
              <span
                v-else-if="op.condominium_ids.includes(popover!.condoId)"
                class="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded-full font-medium flex-shrink-0"
              >atual</span>
            </label>

            <div v-if="!operators.length" class="px-4 py-3 text-sm text-gray-400 italic text-center">
              Nenhum operador cadastrado
            </div>
          </div>

          <!-- Actions -->
          <div class="px-4 py-3 border-t border-gray-100 flex justify-end gap-2 bg-gray-50">
            <button
              class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 font-medium rounded-lg hover:bg-gray-100 transition-colors"
              @click="closePopover"
            >
              Cancelar
            </button>
            <button
              :disabled="savingAssignment || pendingUserId === undefined"
              class="px-4 py-1.5 text-sm font-semibold rounded-lg transition-colors flex items-center gap-2"
              :class="savingAssignment || pendingUserId === undefined
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'"
              @click="saveAssignment"
            >
              <div v-if="savingAssignment" class="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin"/>
              Confirmar
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
