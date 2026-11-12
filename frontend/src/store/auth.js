import { reactive } from 'vue'
import service from '../api/index'

export const authState = reactive({
  initialized: false,
  user: null,
  firstUserBecomesAdmin: false,
  modalOpen: false,
  modalTab: 'register',
  pendingAction: null
})

export async function refreshAuthSession() {
  try {
    const res = await service.get('/api/auth/me')
    if (res?.data) {
      authState.user = res.data.user || null
      authState.firstUserBecomesAdmin = Boolean(res.data.first_user_becomes_admin)
      if (!res.data.authenticated) {
        localStorage.removeItem('istishraf_token')
      }
    }
  } catch {
    authState.user = null
  } finally {
    authState.initialized = true
  }
}

export function openAuthModal(tab = 'register', onSuccess = null) {
  authState.modalTab = tab
  authState.pendingAction = onSuccess
  authState.modalOpen = true
}

export function logoutUser() {
  localStorage.removeItem('istishraf_token')
  authState.user = null
  window.dispatchEvent(new CustomEvent('istishraf-auth-changed'))
}
