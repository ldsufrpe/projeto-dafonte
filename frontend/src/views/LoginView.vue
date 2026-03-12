<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCondominiumStore } from '@/stores/condominium'

const router = useRouter()
const auth = useAuthStore()
const condoStore = useCondominiumStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const showPassword = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    await condoStore.fetchCondominiums()

    const [first] = condoStore.condominiums
    if (condoStore.condominiums.length === 1 && first) {
      condoStore.setActive(first.id)
      router.push('/dashboard')
    } else {
      router.push('/home')
    }
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    error.value = detail || 'Usuário ou senha inválidos'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-root">

    <!-- ═══ LEFT PANEL — Brand ═══ -->
    <div class="brand-panel">
      <!-- Animated blobs -->
      <div class="blob blob-1" />
      <div class="blob blob-2" />
      <div class="blob blob-3" />

      <div class="brand-content">
        <!-- Logo -->
        <div class="logo-mark">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C12 2 4 10.5 4 15a8 8 0 0016 0C20 10.5 12 2 12 2z"/>
          </svg>
        </div>

        <h1 class="brand-name">FonteGest</h1>
        <p class="brand-tagline">GESTÃO DE ÁGUA MINERAL</p>

        <div class="brand-divider" />

        <p class="brand-desc">
          Plataforma de gestão operacional e financeira para condomínios.
          Controle consumo, estoque e cobranças em um só lugar.
        </p>

        <!-- Features -->
        <ul class="feature-list">
          <li>
            <span class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </span>
            Lançamento de consumo por unidade
          </li>
          <li>
            <span class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </span>
            Controle de estoque antifraude
          </li>
          <li>
            <span class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </span>
            Sincronização com Sistema Retaguarda
          </li>
        </ul>
      </div>

      <!-- Bottom badge -->
      <a href="https://uniquesistemas.com.br/" target="_blank" rel="noopener" class="brand-footer">
        Desenvolvido por Unique Sistemas · uniquesistemas.com.br
      </a>
    </div>

    <!-- ═══ RIGHT PANEL — Form ═══ -->
    <div class="form-panel">
      <div class="form-card">
        <!-- Header -->
        <div class="form-header">
          <div class="form-logo-sm">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C12 2 4 10.5 4 15a8 8 0 0016 0C20 10.5 12 2 12 2z"/>
            </svg>
          </div>
          <div class="form-header-text">
            <h2 class="form-title">Bem-vindo de volta</h2>
            <p class="form-subtitle">Entre com suas credenciais para acessar</p>
          </div>
        </div>

        <!-- Form -->
        <form @submit.prevent="handleLogin" class="form-body" novalidate>

          <!-- Username -->
          <div class="field-group">
            <label class="field-label">Usuário</label>
            <div class="input-wrapper">
              <span class="input-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                </svg>
              </span>
              <input
                v-model="username"
                type="text"
                autocomplete="username"
                required
                class="field-input"
                placeholder="seu_usuario"
              />
            </div>
          </div>

          <!-- Password -->
          <div class="field-group">
            <label class="field-label">Senha</label>
            <div class="input-wrapper">
              <span class="input-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                </svg>
              </span>
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                required
                class="field-input"
                placeholder="••••••••"
              />
              <button
                type="button"
                class="input-eye"
                @click="showPassword = !showPassword"
                :title="showPassword ? 'Ocultar senha' : 'Mostrar senha'"
              >
                <!-- Eye open -->
                <svg v-if="!showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
                <!-- Eye off -->
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- Error -->
          <transition name="shake">
            <div v-if="error" class="error-box">
              <svg class="error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
              </svg>
              {{ error }}
            </div>
          </transition>

          <!-- Submit -->
          <button type="submit" :disabled="loading" class="btn-login">
            <span v-if="!loading" class="btn-login-inner">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"/>
              </svg>
              Entrar
            </span>
            <span v-else class="btn-login-inner">
              <svg class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              Autenticando...
            </span>
          </button>
        </form>

        <!-- Dev credit inside card -->
        <div class="card-footer">
          Desenvolvido por
          <a href="https://uniquesistemas.com.br/" target="_blank" rel="noopener">Unique Sistemas</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ─── Layout ─── */
.login-root {
  display: flex;
  min-height: 100vh;
  background: #f8fafc;
}

/* ─── Left brand panel ─── */
.brand-panel {
  position: relative;
  display: none;
  flex: 1;
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 40%, #1e3a8a 100%);
  padding: 3rem;
  overflow: hidden;
  flex-direction: column;
  justify-content: space-between;
}

@media (min-width: 900px) {
  .brand-panel { display: flex; }
}

/* Animated blobs */
.blob {
  position: absolute;
  border-radius: 50%;
  opacity: 0.15;
  filter: blur(60px);
  animation: drift 12s ease-in-out infinite alternate;
}
.blob-1 {
  width: 400px; height: 400px;
  background: #60a5fa;
  top: -100px; left: -100px;
  animation-delay: 0s;
}
.blob-2 {
  width: 300px; height: 300px;
  background: #38bdf8;
  bottom: -80px; right: -80px;
  animation-delay: -4s;
}
.blob-3 {
  width: 250px; height: 250px;
  background: #818cf8;
  top: 40%; left: 40%;
  animation-delay: -8s;
}

@keyframes drift {
  from { transform: translate(0, 0) scale(1); }
  to   { transform: translate(30px, -30px) scale(1.05); }
}

/* Brand content */
.brand-content {
  position: relative;
  z-index: 1;
}

.logo-mark {
  width: 64px; height: 64px;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.25);
  border-radius: 20px;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(8px);
  margin-bottom: 1.5rem;
}
.logo-mark svg {
  width: 36px; height: 36px;
  color: #fff;
}

.brand-name {
  font-size: 2.5rem;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.03em;
  margin: 0;
}
.brand-tagline {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.2em;
  color: #93c5fd;
  margin: 0.3rem 0 0;
}
.brand-divider {
  width: 48px; height: 3px;
  background: linear-gradient(to right, #60a5fa, transparent);
  border-radius: 2px;
  margin: 1.5rem 0;
}
.brand-desc {
  color: #bfdbfe;
  font-size: 0.95rem;
  line-height: 1.7;
  max-width: 340px;
  margin: 0 0 2rem;
}

.feature-list {
  list-style: none;
  padding: 0; margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}
.feature-list li {
  display: flex; align-items: center; gap: 0.75rem;
  font-size: 0.875rem;
  color: #dbeafe;
  font-weight: 500;
}
.feature-icon {
  width: 22px; height: 22px;
  color: #60a5fa;
  flex-shrink: 0;
}
.feature-icon svg { width: 100%; height: 100%; }

.brand-footer {
  position: relative; z-index: 1;
  font-size: 0.72rem;
  color: rgba(255,255,255,0.5);
  letter-spacing: 0.04em;
  margin: 0;
  text-decoration: none;
  transition: color 0.15s;
}
.brand-footer:hover { color: rgba(255,255,255,0.85); }

/* ─── Right form panel ─── */
.form-panel {
  flex: none;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1.5rem;
  background: #f8fafc;
}

@media (min-width: 900px) {
  .form-panel {
    flex: 0 0 480px;
    padding: 2rem 3rem;
  }
}

.form-card {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 8px 32px rgba(0,0,0,.08);
  padding: 2.5rem;
  animation: slideUp 0.4s ease-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Form header */
.form-header {
  display: flex;
  align-items: center;
  gap: 0.875rem;
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #f1f5f9;
  flex-wrap: nowrap;
}

.form-header-text { min-width: 0; }

.form-logo-sm {
  width: 44px; height: 44px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(37,99,235,.3);
  flex-shrink: 0;
}
.form-logo-sm svg {
  width: 22px; height: 22px;
  color: white;
}

.form-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}
.form-subtitle {
  font-size: 0.82rem;
  color: #94a3b8;
  margin: 0.15rem 0 0;
}

/* Form body */
.form-body {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.field-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #475569;
  letter-spacing: 0.02em;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 13px;
  display: flex;
  color: #94a3b8;
  pointer-events: none;
}
.input-icon svg { width: 17px; height: 17px; }

.field-input {
  width: 100%;
  border: 1.5px solid #e2e8f0;
  border-radius: 11px;
  padding: 0.725rem 2.75rem 0.725rem 2.6rem;
  font-size: 0.875rem;
  color: #1e293b;
  background: #f8fafc;
  transition: border-color 0.18s, box-shadow 0.18s, background 0.18s;
  outline: none;
}
.field-input::placeholder { color: #cbd5e1; }
.field-input:focus {
  border-color: #3b82f6;
  background: #fff;
  box-shadow: 0 0 0 4px rgba(59,130,246,.12);
}

.input-eye {
  position: absolute;
  right: 12px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: #94a3b8;
  border-radius: 6px;
  display: flex;
  transition: color 0.15s;
}
.input-eye svg { width: 17px; height: 17px; }
.input-eye:hover { color: #3b82f6; }

/* Error */
.error-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  font-size: 0.82rem;
  font-weight: 500;
  padding: 0.625rem 0.875rem;
  border-radius: 10px;
}
.error-icon { width: 16px; height: 16px; flex-shrink: 0; }

/* Shake animation for error */
.shake-enter-active { animation: shake 0.4s ease; }
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%       { transform: translateX(-6px); }
  40%       { transform: translateX(6px); }
  60%       { transform: translateX(-4px); }
  80%       { transform: translateX(4px); }
}

/* Submit button */
.btn-login {
  width: 100%;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #fff;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  border: none;
  border-radius: 11px;
  padding: 0.8rem;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.15s, box-shadow 0.15s;
  box-shadow: 0 4px 14px rgba(37,99,235,.35);
  margin-top: 0.25rem;
}
.btn-login:hover:not(:disabled) {
  opacity: 0.93;
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(37,99,235,.4);
}
.btn-login:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(37,99,235,.3);
}
.btn-login:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-login-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}
.btn-login-inner svg { width: 17px; height: 17px; }

/* Spinner */
.spin {
  animation: rotate 0.9s linear infinite;
}
@keyframes rotate {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* Card footer credit */
.card-footer {
  margin-top: 1.5rem;
  padding-top: 1.25rem;
  border-top: 1px solid #f1f5f9;
  text-align: center;
  font-size: 0.75rem;
  color: #94a3b8;
}
.card-footer a {
  color: #004014;
  font-weight: 700;
  text-decoration: none;
  transition: color 0.15s;
}
.card-footer a:hover { color: #006b22; text-decoration: underline; }
</style>
