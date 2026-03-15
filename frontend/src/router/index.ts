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
      // Rotas com AppLayout (header + nav)
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: 'home',
          name: 'home',
          component: () => import('@/views/HomeView.vue'),
        },
        {
          path: 'dashboard',
          meta: { requiresCondominium: true },
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'lancamento',
          name: 'lancamento',
          meta: { requiresCondominium: true },
          component: () => import('@/views/LancamentoView.vue'),
        },
        {
          path: 'historico',
          name: 'historico',
          meta: { requiresCondominium: true },
          component: () => import('@/views/HistoricoView.vue'),
        },
        {
          path: 'estoque',
          name: 'estoque',
          meta: { requiresCondominium: true },
          component: () => import('@/views/EstoqueView.vue'),
        },
        {
          path: 'configuracoes',
          name: 'configuracoes',
          meta: { requiresCondominium: true },
          component: () => import('@/views/ConfiguracoesView.vue'),
        },
        {
          path: 'financeiro',
          name: 'financeiro',
          meta: { requiresCondominium: true },
          component: () => import('@/views/FinanceiroView.vue'),
        },
        {
          // Implantação — não exige condomínio ativo (recebe por param)
          path: '/implantacao/:condominiumId',
          name: 'implantacao',
          meta: { requiresAdmin: true },
          component: () => import('@/views/ImplantacaoView.vue'),
        },
      ],
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

  // 5. Se rota exige admin → verificar
  if (to.meta.requiresAdmin) {
    const { useAuthStore } = await import('@/stores/auth')
    const auth = useAuthStore()
    if (!auth.isAdmin) {
      return { name: 'home' }
    }
  }
})

export default router
