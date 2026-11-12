<template>
  <div class="auth-widget">
    <!-- Logged-out button -->
    <button
      v-if="!authState.user"
      type="button"
      class="auth-trigger-btn"
      :class="{ dark: dark }"
      @click="openAuthModal(authState.firstUserBecomesAdmin ? 'register' : 'login')"
    >
      <span>👤 {{ $t('auth.loginBtn') }}</span>
    </button>

    <!-- Logged-in user pill -->
    <div v-else class="user-pill" :class="{ dark: dark }">
      <span class="role-chip" :class="{ admin: authState.user.role === 'admin' }">
        {{ authState.user.role === 'admin' ? $t('auth.adminBadge') : $t('auth.userBadge') }}
      </span>
      <span class="user-name">{{ authState.user.name }}</span>
      <button type="button" class="logout-mini-btn" @click="handleLogout">
        {{ $t('auth.logoutBtn') }}
      </button>
    </div>

    <!-- Login / Register Modal -->
    <Teleport to="body">
      <div
        v-if="authState.modalOpen"
        class="auth-backdrop"
        @click.self="authState.modalOpen = false"
      >
        <div class="auth-card">
          <div class="auth-header">
            <div>
              <h3 class="auth-title">{{ $t('auth.modalTitle') }}</h3>
              <p class="auth-subtitle">{{ $t('auth.modalSubtitle') }}</p>
            </div>
            <button type="button" class="auth-close" @click="authState.modalOpen = false">×</button>
          </div>

          <div class="auth-tabs">
            <button
              type="button"
              class="auth-tab"
              :class="{ active: authState.modalTab === 'register' }"
              @click="switchTab('register')"
            >
              {{ $t('auth.registerTab') }}
            </button>
            <button
              type="button"
              class="auth-tab"
              :class="{ active: authState.modalTab === 'login' }"
              @click="switchTab('login')"
            >
              {{ $t('auth.loginTab') }}
            </button>
          </div>

          <form class="auth-body" @submit.prevent="submitForm">
            <div
              v-if="authState.firstUserBecomesAdmin && authState.modalTab === 'register'"
              class="first-admin-banner"
            >
              🛡️ {{ $t('auth.firstAdminBanner') }}
            </div>

            <div v-if="authState.modalTab === 'register'" class="field-block">
              <label>{{ $t('auth.nameLabel') }}</label>
              <input
                v-model="form.name"
                type="text"
                required
                :placeholder="$t('auth.namePlaceholder')"
              />
            </div>

            <div class="field-block">
              <label>{{ $t('auth.emailLabel') }}</label>
              <input
                v-model="form.email"
                type="email"
                dir="ltr"
                required
                :placeholder="$t('auth.emailPlaceholder')"
              />
            </div>

            <div class="field-block">
              <label>{{ $t('auth.passwordLabel') }}</label>
              <input
                v-model="form.password"
                type="password"
                dir="ltr"
                required
                minlength="6"
                :placeholder="$t('auth.passwordPlaceholder')"
              />
            </div>

            <div v-if="errorMsg" class="auth-error">{{ errorMsg }}</div>

            <button type="submit" class="auth-submit-btn" :disabled="submitting">
              <span v-if="submitting">{{ $t('auth.submitting') }}</span>
              <span v-else>
                {{ authState.modalTab === 'register' ? $t('auth.submitRegister') : $t('auth.submitLogin') }}
              </span>
            </button>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import service from '../api/index'
import { authState, refreshAuthSession, openAuthModal, logoutUser } from '../store/auth'

defineProps({
  dark: {
    type: Boolean,
    default: false
  }
})

const submitting = ref(false)
const errorMsg = ref('')

const form = reactive({
  name: '',
  email: '',
  password: ''
})

const switchTab = (tab) => {
  authState.modalTab = tab
  errorMsg.value = ''
}

const submitForm = async () => {
  submitting.value = true
  errorMsg.value = ''
  try {
    const endpoint = authState.modalTab === 'register' ? '/api/auth/register' : '/api/auth/login'
    const payload =
      authState.modalTab === 'register'
        ? { name: form.name, email: form.email, password: form.password }
        : { email: form.email, password: form.password }

    const res = await service.post(endpoint, payload)
    if (res?.data?.token) {
      localStorage.setItem('istishraf_token', res.data.token)
      authState.user = res.data.user
      authState.firstUserBecomesAdmin = false
      authState.modalOpen = false
      form.password = ''
      window.dispatchEvent(new CustomEvent('istishraf-auth-changed'))
      if (typeof authState.pendingAction === 'function') {
        const fn = authState.pendingAction
        authState.pendingAction = null
        fn()
      }
    }
  } catch (err) {
    errorMsg.value = err.message || 'تعذر إتمام العملية'
  } finally {
    submitting.value = false
  }
}

const handleLogout = () => {
  logoutUser()
}

onMounted(() => {
  if (!authState.initialized) {
    refreshAuthSession()
  }
})
</script>

<style scoped>
.auth-trigger-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #222;
  background: #FFF;
  color: #111;
  transition: all 0.2s;
}

.auth-trigger-btn.dark {
  background: rgba(255, 255, 255, 0.12);
  color: #FFF;
  border-color: rgba(255, 255, 255, 0.4);
}

.auth-trigger-btn.dark:hover {
  background: rgba(255, 255, 255, 0.22);
}

.user-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 5px;
  border: 1px solid #DDD;
  background: #F8F8F8;
  font-size: 0.8rem;
}

.user-pill.dark {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.28);
  color: #FFF;
}

.role-chip {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  background: #E5E7EB;
  color: #1F2937;
}

.role-chip.admin {
  background: #FF4500;
  color: #FFF;
}

.user-name {
  font-weight: 600;
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-mini-btn {
  background: transparent;
  border: none;
  color: inherit;
  opacity: 0.75;
  cursor: pointer;
  font-size: 0.75rem;
  text-decoration: underline;
}

.logout-mini-btn:hover {
  opacity: 1;
}

.auth-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 3200;
}

.auth-card {
  background: #FFF;
  color: #111;
  width: 100%;
  max-width: 460px;
  border-radius: 10px;
  border: 2px solid #000;
  box-shadow: 0 24px 55px rgba(0, 0, 0, 0.35);
  overflow: hidden;
}

.auth-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 20px 22px 14px;
  background: #FAFAFA;
}

.auth-title {
  font-size: 1.15rem;
  font-weight: 700;
  margin-bottom: 4px;
}

.auth-subtitle {
  font-size: 0.83rem;
  color: #555;
  line-height: 1.55;
}

.auth-close {
  background: none;
  border: none;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  color: #444;
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-top: 1px solid #E5E5E5;
  border-bottom: 1px solid #E5E5E5;
}

.auth-tab {
  padding: 11px;
  border: none;
  background: #F5F5F5;
  font-size: 0.88rem;
  font-weight: 600;
  color: #666;
  cursor: pointer;
}

.auth-tab.active {
  background: #FFF;
  color: #FF4500;
  box-shadow: inset 0 -2px 0 #FF4500;
}

.auth-body {
  padding: 20px 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.first-admin-banner {
  background: #FFF7ED;
  border: 1px solid #FDBA74;
  color: #9A3412;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 0.8rem;
  line-height: 1.55;
}

.field-block label {
  display: block;
  font-size: 0.82rem;
  font-weight: 600;
  margin-bottom: 5px;
  color: #222;
}

.field-block input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #CCC;
  border-radius: 6px;
  font-size: 0.9rem;
}

.field-block input:focus {
  outline: none;
  border-color: #000;
}

.auth-error {
  padding: 9px 12px;
  background: #FEE2E2;
  color: #991B1B;
  border-radius: 6px;
  font-size: 0.83rem;
  font-weight: 600;
}

.auth-submit-btn {
  width: 100%;
  padding: 12px;
  background: #000;
  color: #FFF;
  border: none;
  border-radius: 6px;
  font-size: 0.94rem;
  font-weight: 700;
  cursor: pointer;
  margin-top: 4px;
}

.auth-submit-btn:hover {
  background: #FF4500;
}
</style>
