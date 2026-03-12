import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import apiClient from '@/api/client'

export interface ProductWithPrice {
    id: number
    name: string
    capacity_liters: number
    erp_product_code: string | null
    is_active: boolean
    sort_order: number
    current_price: number | null
}

export interface ProductPrice {
    id: number
    product_id: number
    condominium_id: number | null
    valid_from: string
    unit_price: number
    source: string
}

export const useProductStore = defineStore('product', () => {
    const products = ref<ProductWithPrice[]>([])
    const priceHistory = ref<Record<number, ProductPrice[]>>({})

    const activeProducts = computed(() =>
        [...products.value].filter(p => p.is_active).sort((a, b) => a.sort_order - b.sort_order)
    )

    async function fetchProducts(condominiumId: number) {
        const { data } = await apiClient.get(`/products?condominium_id=${condominiumId}`)
        products.value = data
    }

    async function toggleActive(id: number, isActive: boolean) {
        const { data } = await apiClient.patch(`/products/${id}/active`, { is_active: isActive })
        const idx = products.value.findIndex(p => p.id === id)
        if (idx >= 0) products.value[idx] = data
        return data
    }

    async function createPrice(productId: number, body: { condominium_id?: number; valid_from: string; unit_price: number }) {
        const { data } = await apiClient.post(`/products/${productId}/prices`, body)
        return data
    }

    async function fetchPriceHistory(productId: number) {
        const { data } = await apiClient.get(`/products/${productId}/prices`)
        priceHistory.value[productId] = data
        return data
    }

    return {
        products,
        activeProducts,
        priceHistory,
        fetchProducts,
        toggleActive,
        createPrice,
        fetchPriceHistory,
    }
})
