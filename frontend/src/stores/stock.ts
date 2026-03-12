import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

// ── Types ─────────────────────────────────────────────────────────────

export interface ProductStockOverview {
  product_id: number
  product_name: string
  capacity_liters: number
  saldo_anterior: number
  entradas: number
  consumo_lancado: number
  saldo_atual: number
  is_negative: boolean
}

export interface StockEntry {
  id: number
  product_id: number
  product_name: string
  reference_month: string
  quantity: number
  entry_type: string
  notes: string | null
  created_at: string
}

export interface StockOverview {
  condominium_id: number
  condominium_name: string
  reference_month: string
  products: ProductStockOverview[]
  entries: StockEntry[]
}

export interface StockChartData {
  months: string[]
  series: Record<string, number[]>
}

// ── Store ─────────────────────────────────────────────────────────────

export const useStockStore = defineStore('stock', () => {
  const overview = ref<StockOverview | null>(null)
  const chartData = ref<StockChartData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchOverview(condominiumId: number, referenceMonth: string) {
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get<StockOverview>(
        `/stock/${condominiumId}/${referenceMonth}`
      )
      overview.value = data
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? 'Erro ao carregar estoque'
    } finally {
      loading.value = false
    }
  }

  async function fetchChart(condominiumId: number, referenceMonth: string, months = 6) {
    try {
      const { data } = await apiClient.get<StockChartData>(
        `/stock/${condominiumId}/chart`,
        { params: { reference_month: referenceMonth, months } }
      )
      chartData.value = data
    } catch {
      chartData.value = null
    }
  }

  async function createEntry(payload: {
    condominium_id: number
    product_id: number
    reference_month: string
    quantity: number
    entry_type: string
    notes?: string
  }): Promise<StockEntry> {
    const { data } = await apiClient.post<StockEntry>('/stock/entries', payload)
    return data
  }

  async function updateEntry(
    entryId: number,
    payload: { quantity?: number; notes?: string }
  ): Promise<StockEntry> {
    const { data } = await apiClient.put<StockEntry>(`/stock/entries/${entryId}`, payload)
    return data
  }

  async function deleteEntry(entryId: number): Promise<void> {
    await apiClient.delete(`/stock/entries/${entryId}`)
  }

  return {
    overview,
    chartData,
    loading,
    error,
    fetchOverview,
    fetchChart,
    createEntry,
    updateEntry,
    deleteEntry,
  }
})
