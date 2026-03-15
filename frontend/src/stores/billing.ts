import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import apiClient from '@/api/client'

// ── Types ──────────────────────────────────────────────────────────

export interface ProductHeader {
  id: number
  erp_product_code: string
  name: string
  capacity_liters: number
  sort_order: number
  unit_price: number
}

export interface BillingItemData {
  id: number
  product_id: number
  erp_product_code: string
  product_name: string
  quantity: number
  unit_price: number
  line_total: number
}

export interface ResidentInfo {
  id: number | null
  name: string | null
  cpf_masked: string | null
  phone: string | null
}

export interface BillingRow {
  billing_id: number
  unit_id: number
  unit_code: string
  resident: ResidentInfo
  items: BillingItemData[]
  total_amount: number
  status: string
  days_overdue: number
  erp_invoice_id: string | null
  resident_changed: boolean
  has_consumption: boolean
}

export interface BillingSummary {
  total_units: number
  total_faturado: number
  total_arrecadado: number
  total_em_aberto: number
  totals_by_product: Record<number, number>
}

export interface BillingGrid {
  condominium_id: number
  condominium_name: string
  reference_month: string
  products: ProductHeader[]
  rows: BillingRow[]
  summary: BillingSummary
}

// ── Store ──────────────────────────────────────────────────────────

export const useBillingStore = defineStore('billing', () => {
  const grid = ref<BillingGrid | null>(null)
  const loading = ref(false)
  const error = ref('')
  const submitting = ref(false)
  const submitResult = ref<string>('')

  // Getters
  const products = computed(() => grid.value?.products ?? [])
  const rows = computed(() => grid.value?.rows ?? [])
  const summary = computed(() => grid.value?.summary ?? null)
  const referenceMonth = computed(() => grid.value?.reference_month ?? '')
  const condominiumName = computed(() => grid.value?.condominium_name ?? '')

  const canSubmit = computed(() => {
    if (!grid.value) return false
    return grid.value.rows.some(r => r.has_consumption && r.status === 'draft')
  })

  // Actions
  async function fetchGrid(condoId: number, month: string) {
    loading.value = true
    error.value = ''
    try {
      const { data } = await apiClient.get(`/billing/${condoId}/${month}`)
      // Normalize Decimal-as-string fields from FastAPI to actual numbers
      for (const row of data.rows ?? []) {
        row.total_amount = parseFloat(row.total_amount) || 0
        for (const item of row.items ?? []) {
          item.unit_price = parseFloat(item.unit_price) || 0
          item.line_total = parseFloat(item.line_total) || 0
        }
      }
      const s = data.summary
      if (s) {
        s.total_faturado = parseFloat(s.total_faturado) || 0
        s.total_arrecadado = parseFloat(s.total_arrecadado) || 0
        s.total_em_aberto = parseFloat(s.total_em_aberto) || 0
      }
      for (const p of data.products ?? []) {
        p.unit_price = parseFloat(p.unit_price) || 0
      }
      grid.value = data
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = msg || 'Erro ao carregar lançamentos'
    } finally {
      loading.value = false
    }
  }

  async function updateQuantity(itemId: number, quantity: number): Promise<boolean> {
    error.value = ''
    try {
      const { data } = await apiClient.patch(`/billing/item/${itemId}`, { quantity })

      // Update local state
      if (grid.value) {
        for (const row of grid.value.rows) {
          const item = row.items.find(i => i.id === itemId)
          if (item) {
            item.quantity = data.quantity
            item.line_total = parseFloat(data.line_total)
            row.total_amount = parseFloat(data.billing_total)
            row.status = data.billing_status
            row.has_consumption = row.items.some(i => i.quantity > 0)
            break
          }
        }
        // Recalculate summary
        _recalcSummary()
      }
      return true
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = msg || 'Erro ao atualizar quantidade'
      return false
    }
  }

  async function updateResident(billingId: number, data: { name?: string; cpf_masked?: string; phone?: string }): Promise<boolean> {
    error.value = ''
    try {
      const { data: res } = await apiClient.patch(`/billing/${billingId}/resident`, data)

      // Update local state
      if (grid.value) {
        const row = grid.value.rows.find(r => r.billing_id === billingId)
        if (row) {
          row.resident = {
            id: res.resident_id,
            name: res.name,
            cpf_masked: res.cpf_masked,
            phone: res.phone,
          }
          row.resident_changed = true
        }
      }
      return true
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = msg || 'Erro ao atualizar morador'
      return false
    }
  }

  async function submitBilling(condoId: number, month: string): Promise<boolean> {
    submitting.value = true
    submitResult.value = ''
    error.value = ''
    try {
      const { data } = await apiClient.post(`/erp/submit-billing/${condoId}/${month}`)

      // Update statuses locally
      if (grid.value) {
        for (const result of data.results) {
          const row = grid.value.rows.find(r => r.unit_code === result.unit_code)
          if (row && result.success) {
            row.status = 'submitted'
            row.erp_invoice_id = result.erp_invoice_id
          }
        }
      }

      submitResult.value = `Lote enviado: ${data.submitted_count} faturados, ${data.skipped_count} sem consumo`
      return data.success
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      error.value = msg || 'Erro ao enviar faturamento'
      return false
    } finally {
      submitting.value = false
    }
  }

  function _recalcSummary() {
    if (!grid.value) return
    const s = grid.value.summary
    s.total_faturado = 0
    s.total_arrecadado = 0
    s.total_em_aberto = 0
    s.totals_by_product = {}

    for (const row of grid.value.rows) {
      const amt = Number(row.total_amount)
      s.total_faturado += amt
      if (row.status === 'paid') s.total_arrecadado += amt
      if (row.status === 'open' || row.status === 'submitted') s.total_em_aberto += amt
      for (const item of row.items) {
        s.totals_by_product[item.product_id] = (s.totals_by_product[item.product_id] ?? 0) + item.quantity
      }
    }
  }

  return {
    grid,
    loading,
    error,
    submitting,
    submitResult,
    products,
    rows,
    summary,
    referenceMonth,
    condominiumName,
    canSubmit,
    fetchGrid,
    updateQuantity,
    updateResident,
    submitBilling,
  }
})
