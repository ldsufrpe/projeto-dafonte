import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

export interface TopUnit {
  unit_code: string
  resident_name: string | null
  total_amount: number
  total_qty: number
}

export interface Defaulter {
  unit_code: string
  resident_name: string | null
  total_amount: number
  days_overdue: number
  status: string
}

export interface DashboardData {
  condominium_id: number
  condominium_name: string
  reference_month: string
  total_billed: number
  total_collected: number
  total_open: number
  qty_billed: number
  qty_paid: number
  qty_open: number
  qty_submitted: number
  qty_no_consumption: number
  qty_draft: number
  default_rate: number
  has_submitted_waiting: boolean
  top5: TopUnit[]
  defaulters: Defaulter[]
}

export const useDashboardStore = defineStore('dashboard', () => {
  const data = ref<DashboardData | null>(null)
  const loading = ref(false)
  const error = ref('')
  const syncing = ref(false)
  const syncMessage = ref('')

  async function fetchDashboard(condoId: number, month: string) {
    loading.value = true
    error.value = ''
    try {
      const { data: res } = await apiClient.get<DashboardData>(`/dashboard/${condoId}/${month}`)
      data.value = res
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = msg || 'Erro ao carregar dashboard'
    } finally {
      loading.value = false
    }
  }

  async function syncPayments(condoId: number, month: string): Promise<string> {
    syncing.value = true
    syncMessage.value = ''
    try {
      const { data: res } = await apiClient.post(`/erp/sync-payments/${condoId}/${month}`)
      syncMessage.value = `Sincronizado: ${res.updated} unidades atualizadas`
      await fetchDashboard(condoId, month)
      return syncMessage.value
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      syncMessage.value = msg || 'Erro na sincronização'
      return syncMessage.value
    } finally {
      syncing.value = false
    }
  }

  return { data, loading, error, syncing, syncMessage, fetchDashboard, syncPayments }
})
