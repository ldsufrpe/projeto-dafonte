import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '@/api/client'

export interface CommissionResult {
    condominium_id: number
    condominium_name: string
    reference_month: string
    commission_type: string
    commission_value: number | null
    total_received: number
    commission_due: number
}

export interface OperatorPerformanceItem {
    condominium_id: number
    condominium_name: string
    total_billed: number
    total_received: number
    success_rate: number
    commission_due: number
}

export interface CommissionRate {
    id: number
    condominium_id: number
    product_id: number
    product_name: string | null
    value_per_unit: number
    valid_from: string
}

export const useFinanceStore = defineStore('finance', () => {
    const commission = ref<CommissionResult | null>(null)
    const performance = ref<OperatorPerformanceItem[]>([])
    const commissionRates = ref<CommissionRate[]>([])
    const loading = ref(false)

    async function fetchCommission(condominiumId: number, month: string) {
        loading.value = true
        try {
            const { data } = await apiClient.get(`/finance/commission/${condominiumId}/${month}`)
            commission.value = data
        } finally {
            loading.value = false
        }
    }

    async function fetchPerformance(month: string) {
        loading.value = true
        try {
            const { data } = await apiClient.get(`/finance/operator-performance/${month}`)
            performance.value = data
        } finally {
            loading.value = false
        }
    }

    async function updateCommissionConfig(condominiumId: number, config: { commission_type: string; commission_value: number | null }) {
        const { data } = await apiClient.put(`/finance/condominiums/${condominiumId}/commission-config`, config)
        return data
    }

    async function fetchCommissionRates(condominiumId: number) {
        const { data } = await apiClient.get(`/finance/condominiums/${condominiumId}/commission-rates`)
        commissionRates.value = data
        return data
    }

    async function createCommissionRate(condominiumId: number, body: { product_id: number; value_per_unit: number; valid_from: string }) {
        const { data } = await apiClient.post(`/finance/condominiums/${condominiumId}/commission-rates`, body)
        commissionRates.value.unshift(data)
        return data
    }

    return {
        commission,
        performance,
        commissionRates,
        loading,
        fetchCommission,
        fetchPerformance,
        updateCommissionConfig,
        fetchCommissionRates,
        createCommissionRate,
    }
})
