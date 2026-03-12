import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import apiClient from '@/api/client'

export type MonthStatus = 'not_started' | 'in_progress' | 'submitted' | 'synced'

export interface CondominiumOverview {
  id: number
  name: string
  address: string | null
  erp_code: string
  onboarding_complete: boolean
  month_status: MonthStatus
  units_launched: number
  total_units: number
  total_billed: number
  total_received: number
  commission_due: number
  has_stock_alert: boolean
  operator_name?: string | null
}

export interface HomeOverview {
  reference_month: string
  condominiums: CondominiumOverview[]
  total_billed_all: number
  total_received_all: number
}

function currentYearMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export const useCondominiumStore = defineStore('condominium', () => {
  const condominiums = ref<CondominiumOverview[]>([])
  const referenceMonth = ref(currentYearMonth())
  const loading = ref(false)
  const error = ref<string | null>(null)
  const totalBilledAll = ref(0)
  const totalReceivedAll = ref(0)

  // Restore activeCondominiumId from localStorage on store init
  const activeCondominiumId = ref<number | null>(
    (() => {
      const stored = localStorage.getItem('active_condominium_id')
      return stored ? Number(stored) : null
    })()
  )

  const activeCondominium = computed(
    () => condominiums.value.find(c => c.id === activeCondominiumId.value) ?? null
  )

  const hasMultiple = computed(() => condominiums.value.length > 1)

  async function fetchCondominiums(month?: string, operatorId?: number | null) {
    const m = month ?? referenceMonth.value
    loading.value = true
    error.value = null
    try {
      const params = operatorId != null ? { operator_id: operatorId } : {}
      const { data } = await apiClient.get<HomeOverview>(`/home/overview/${m}`, { params })
      condominiums.value = data.condominiums
      referenceMonth.value = data.reference_month
      totalBilledAll.value = data.total_billed_all
      totalReceivedAll.value = data.total_received_all
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = msg || 'Erro ao carregar condomínios'
    } finally {
      loading.value = false
    }
  }

  function setActive(id: number) {
    activeCondominiumId.value = id
    localStorage.setItem('active_condominium_id', String(id))
  }

  function clearActive() {
    activeCondominiumId.value = null
    localStorage.removeItem('active_condominium_id')
  }

  return {
    condominiums,
    referenceMonth,
    loading,
    error,
    totalBilledAll,
    totalReceivedAll,
    activeCondominiumId,
    activeCondominium,
    hasMultiple,
    fetchCondominiums,
    setActive,
    clearActive,
  }
})
