import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      redirect: '/home',
    },
    {
      path: '/home',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { requiresAuth: true },
    },
    {
      // Rotas operacionais — usam AppLayout como wrapper
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      meta: { requiresAuth: true, requiresCondominium: true },
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'lancamento',
          name: 'lancamento',
          component: () => import('@/views/LancamentoView.vue'),
        },
        {
          path: 'historico',
          name: 'historico',
          component: () => import('@/views/HistoricoView.vue'),
        },
        {
          path: 'estoque',
          name: 'estoque',
          component: () => import('@/views/EstoqueView.vue'),
        },
        {
          path: 'configuracoes',
          name: 'configuracoes',
          component: () => import('@/views/ConfiguracoesView.vue'),
        },
        {
          path: 'financeiro',
          name: 'financeiro',
          component: () => import('@/views/FinanceiroView.vue'),
        },
      ],
    },
    {
      // Implantação — usa AppLayout mas não exige condomínio ativo (recebe por param)
      path: '/implantacao/:condominiumId',
      name: 'implantacao',
      component: () => import('@/views/ImplantacaoView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
  ],
})

// Navigation guards
router.beforeEach(async (to) => {
  const token = localStorage.getItem('access_token')

  // 1. Se rota pública → permitir
  if (to.meta.public) {
    // Se já autenticado e tentando acessar login → redirecionar
    if (to.name === 'login' && token) {
      return { name: 'home' }
    }
    return
  }

  // 2. Se não autenticado → login
  if (to.meta.requiresAuth && !token) {
    return { name: 'login' }
  }

  // 3. Se autenticado mas user ainda não carregado (ex: refresh de página) → buscar perfil
  if (token) {
    const { useAuthStore } = await import('@/stores/auth')
    const auth = useAuthStore()
    if (!auth.user) {
      try {
        await auth.fetchMe()
      } catch {
        // token inválido → forçar logout
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        return { name: 'login' }
      }
    }
  }

  // 4. Se rota exige condomínio ativo → verificar
  if (to.meta.requiresCondominium) {
    const activeId = localStorage.getItem('active_condominium_id')
    if (!activeId) {
      return { name: 'home' }
    }
  }

  // 5. Se rota exige admin → verificar (simplificado — será refinado quando auth store persistir role)
  // Por agora, a proteção real de admin é feita pelo backend
})

export default router
