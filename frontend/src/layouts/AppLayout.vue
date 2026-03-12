<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCondominiumStore } from '@/stores/condominium'
import NavTab from '@/components/NavTab.vue'
import apiClient from '@/api/client'

const router = useRouter()
const auth = useAuthStore()
const condoStore = useCondominiumStore()
const isMockMode = ref(false)

onMounted(async () => {
  if (!auth.user) {
    await auth.fetchMe()
  }
  if (condoStore.condominiums.length === 0) {
    await condoStore.fetchCondominiums()
  }
  try {
    const { data } = await apiClient.get('/erp/mode')
    isMockMode.value = data.is_mock
  } catch {
    // silently ignore — indicator simply won't show
  }
})

function handleCondoChange(event: Event) {
  const id = Number((event.target as HTMLSelectElement).value)
  condoStore.setActive(id)
}

async function handleLogout() {
  await auth.logout()
  condoStore.clearActive()
  router.push('/login')
}

const userInitial = () => {
  const name = auth.user?.full_name || auth.user?.username || '?'
  return name.charAt(0).toUpperCase()
}
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <!-- ═══════ HEADER ═══════ -->
    <header class="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
      <div class="max-w-screen-xl mx-auto px-6">

        <!-- Top bar -->
        <div class="flex items-center justify-between h-16">

          <!-- Logo → home -->
          <router-link to="/home" class="flex items-center gap-3 hover:opacity-80 transition-opacity shrink-0">
            <div class="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center shadow">
              <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C12 2 4 10.5 4 15a8 8 0 0016 0C20 10.5 12 2 12 2z"/>
              </svg>
            </div>
            <div class="leading-tight hidden sm:block">
              <p class="text-lg font-bold text-gray-900 leading-none">FonteGest</p>
              <p class="text-[10px] text-blue-500 font-medium tracking-wide">GESTÃO DE ÁGUA</p>
            </div>
          </router-link>

          <!-- Breadcrumb: Painel › Condomínio (desktop) -->
          <div v-if="condoStore.activeCondominium" class="hidden md:flex items-center gap-1.5 min-w-0">
            <!-- Back link -->
            <router-link
              to="/home"
              class="flex items-center gap-1.5 text-sm text-gray-400 hover:text-blue-600 hover:bg-blue-50 px-2.5 py-1.5 rounded-lg transition-colors whitespace-nowrap"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
                <polyline points="9 22 9 12 15 12 15 22" stroke="currentColor" stroke-width="2"
                  stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span class="font-medium">Painel</span>
            </router-link>

            <!-- Separator -->
            <svg class="w-3.5 h-3.5 text-gray-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7"/>
            </svg>

            <!-- Active condominium selector -->
            <div class="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 min-w-0">
              <svg class="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-2 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
              </svg>
              <select
                v-if="condoStore.hasMultiple"
                :value="condoStore.activeCondominiumId"
                @change="handleCondoChange"
                class="text-sm font-semibold text-slate-700 bg-transparent border-none focus:outline-none cursor-pointer max-w-[180px] truncate"
              >
                <option v-for="c in condoStore.condominiums" :key="c.id" :value="c.id">
                  {{ c.name }}
                </option>
              </select>
              <span v-else class="text-sm font-semibold text-slate-700 truncate max-w-[180px]">
                {{ condoStore.activeCondominium.name }}
              </span>
              <span v-if="isMockMode" class="w-2 h-2 bg-amber-400 rounded-full shrink-0" title="Modo local (mock)"></span>
            </div>
          </div>

          <!-- User area -->
          <div class="flex items-center gap-3">
            <div class="text-right hidden md:block">
              <p class="text-sm font-medium text-gray-700">{{ auth.user?.full_name || auth.user?.username }}</p>
              <p class="text-xs text-gray-400">{{ auth.user?.role === 'admin' ? 'Administrador' : 'Operador' }}</p>
            </div>
            <button
              @click="handleLogout"
              class="w-9 h-9 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center text-white font-bold text-sm shadow hover:opacity-90 transition-opacity"
              title="Sair"
            >
              {{ userInitial() }}
            </button>
          </div>
        </div>

        <!-- Navigation tabs -->
        <nav class="flex -mb-px overflow-x-auto">
          <!-- Back to panel — always visible on mobile, hidden on md+ (breadcrumb handles it there) -->
          <router-link
            v-if="condoStore.activeCondominium"
            to="/home"
            class="md:hidden flex items-center gap-1.5 px-3 py-3 text-xs font-medium text-gray-400 hover:text-blue-600 border-b-2 border-transparent whitespace-nowrap shrink-0 transition-colors"
          >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
            </svg>
            Painel
          </router-link>

          <NavTab to="/dashboard" label="Dashboard">
            <template #icon>
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
              </svg>
            </template>
          </NavTab>

          <NavTab to="/lancamento" label="Lançamento">
            <template #icon>
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
              </svg>
            </template>
          </NavTab>

          <NavTab to="/historico" label="Histórico">
            <template #icon>
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
              </svg>
            </template>
          </NavTab>

          <NavTab to="/estoque" label="Estoque">
            <template #icon>
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>
              </svg>
            </template>
          </NavTab>

          <NavTab to="/financeiro" label="Financeiro">
            <template #icon>
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </template>
          </NavTab>

          <NavTab to="/configuracoes" label="Configurações">
            <template #icon>
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
              </svg>
            </template>
          </NavTab>
        </nav>
      </div>
    </header>

    <!-- Onboarding banner -->
    <div v-if="condoStore.activeCondominium && !condoStore.activeCondominium.onboarding_complete"
      class="bg-amber-50 border-b border-amber-200 px-6 py-2.5 flex items-center gap-3">
      <svg class="w-4 h-4 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
      </svg>
      <span class="text-sm text-amber-800 font-medium">
        Implantação em andamento —
        <router-link :to="`/implantacao/${condoStore.activeCondominiumId}`" class="underline hover:text-amber-900">
          complete o wizard para ativar este condomínio
        </router-link>
      </span>
    </div>

    <!-- ═══════ MAIN CONTENT ═══════ -->
    <main class="max-w-screen-xl mx-auto px-6 py-8">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" class="fade-up" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
