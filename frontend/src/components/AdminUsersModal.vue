<template>
  <div v-if="isAdmin" class="admin-users-wrapper">
    <button
      type="button"
      class="users-trigger-btn"
      :class="{ dark }"
      @click="openModal"
    >
      <span>👥 المستخدمون</span>
      <span v-if="users.length" class="users-count">{{ users.length }}</span>
    </button>

    <Teleport to="body">
      <div v-if="showModal" class="users-backdrop" @click.self="showModal = false">
        <div class="users-card" dir="rtl">
          <div class="users-header">
            <div>
              <h3 class="users-title">إدارة المستخدمين</h3>
              <p class="users-subtitle">أوقف حسابًا، عدّل حصته اليومية، أو احذفه نهائيًا.</p>
            </div>
            <button type="button" class="users-close" @click="showModal = false">×</button>
          </div>

          <div class="users-body">
            <div v-if="loading" class="users-state">جارٍ تحميل المستخدمين…</div>
            <div v-else-if="errorMsg" class="users-error">{{ errorMsg }}</div>
            <div v-else-if="!users.length" class="users-state">لا يوجد مستخدمون بعد.</div>

            <div v-for="u in users" :key="u.id" class="user-row" :class="{ inactive: !u.is_active }">
              <div class="user-main">
                <div class="user-line">
                  <span class="user-name">{{ u.name }}</span>
                  <span v-if="u.role === 'admin'" class="badge badge-admin">مدير</span>
                  <span class="badge" :class="u.is_active ? 'badge-active' : 'badge-off'">
                    {{ u.is_active ? 'نشط' : 'موقوف' }}
                  </span>
                  <span v-if="u.id === currentUserId" class="badge badge-me">أنت</span>
                </div>
                <div class="user-email" dir="ltr">{{ u.email }}</div>
                <div class="user-meta">
                  <span>الحصة اليومية: <strong>{{ u.daily_quota }}</strong></span>
                  <span>استخدم اليوم: <strong>{{ u.used_today }}</strong></span>
                  <span v-if="u.created_at">مسجّل منذ: {{ shortDate(u.created_at) }}</span>
                </div>
              </div>

              <div class="user-actions">
                <button
                  type="button"
                  class="act-btn"
                  :disabled="busyId === u.id || u.id === currentUserId"
                  @click="toggleStatus(u)"
                >
                  {{ u.is_active ? 'إيقاف' : 'تفعيل' }}
                </button>
                <button
                  type="button"
                  class="act-btn"
                  :disabled="busyId === u.id"
                  @click="editQuota(u)"
                >
                  الحصة
                </button>
                <button
                  type="button"
                  class="act-btn act-danger"
                  :disabled="busyId === u.id || u.id === currentUserId"
                  @click="confirmDelete(u)"
                >
                  حذف
                </button>
              </div>
            </div>

            <div v-if="notice" class="users-notice">{{ notice }}</div>
          </div>

          <div class="users-footer">
            <button type="button" class="users-refresh" :disabled="loading" @click="loadUsers">
              تحديث القائمة
            </button>
            <button type="button" class="users-done" @click="showModal = false">إغلاق</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { authState } from '../store/auth'
import { deleteUser, listUsers, setUserQuota, setUserStatus } from '../api/admin'

defineProps({
  dark: { type: Boolean, default: false }
})

const showModal = ref(false)
const users = ref([])
const currentUserId = ref(null)
const loading = ref(false)
const busyId = ref(null)
const errorMsg = ref('')
const notice = ref('')

const isAdmin = computed(() => authState.user?.role === 'admin')

const shortDate = (value) => {
  if (!value) return ''
  const text = String(value)
  return text.slice(0, 10)
}

const loadUsers = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await listUsers()
    const data = res?.data || {}
    users.value = Array.isArray(data.users) ? data.users : []
    currentUserId.value = data.current_user_id ?? authState.user?.id ?? null
  } catch (err) {
    errorMsg.value = err?.message || 'تعذر تحميل قائمة المستخدمين.'
  } finally {
    loading.value = false
  }
}

const openModal = () => {
  showModal.value = true
  notice.value = ''
  loadUsers()
}

const toggleStatus = async (user) => {
  busyId.value = user.id
  notice.value = ''
  try {
    const res = await setUserStatus(user.id, !user.is_active)
    notice.value = res?.message || 'تم التحديث'
    await loadUsers()
  } catch (err) {
    notice.value = err?.message || 'تعذر تنفيذ العملية'
  } finally {
    busyId.value = null
  }
}

const editQuota = async (user) => {
  const answer = window.prompt(`الحصة اليومية الجديدة لـ «${user.name}»`, String(user.daily_quota))
  if (answer === null) return
  const quota = Number(answer)
  if (!Number.isFinite(quota) || quota < 1) {
    notice.value = 'أدخل رقمًا صحيحًا أكبر من صفر.'
    return
  }
  busyId.value = user.id
  notice.value = ''
  try {
    const res = await setUserQuota(user.id, Math.round(quota))
    notice.value = res?.message || 'تم تحديث الحصة'
    await loadUsers()
  } catch (err) {
    notice.value = err?.message || 'تعذر تحديث الحصة'
  } finally {
    busyId.value = null
  }
}

const confirmDelete = async (user) => {
  const ok = window.confirm(
    `حذف حساب «${user.name}» نهائيًا؟\nلن يستطيع الدخول بعد الآن، وتبقى بياناته محفوظة للمدير.`
  )
  if (!ok) return
  busyId.value = user.id
  notice.value = ''
  try {
    const res = await deleteUser(user.id)
    notice.value = res?.message || 'تم حذف الحساب'
    await loadUsers()
  } catch (err) {
    notice.value = err?.message || 'تعذر حذف الحساب'
  } finally {
    busyId.value = null
  }
}
</script>

<style scoped>
.users-trigger-btn,
.users-trigger-btn.dark {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--border-strong, #CBD5E1);
  background: var(--bg-subtle, #F1F5F9);
  color: var(--text-primary, #0F172A);
  transition: border-color 0.2s, background 0.2s;
}

.users-trigger-btn:hover,
.users-trigger-btn.dark:hover {
  border-color: #FF4500;
}

.users-count {
  min-width: 18px;
  text-align: center;
  font-size: 0.7rem;
  padding: 1px 5px;
  border-radius: 999px;
  background: #FF4500;
  color: #fff;
}

.users-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 4000;
}

.users-card {
  width: 100%;
  max-width: 620px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0F172A);
  border-radius: 16px;
  border: 1px solid var(--border-strong, #E2E8F0);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
  overflow: hidden;
}

.users-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 12px;
  border-bottom: 1px solid var(--border-soft, #EDF2F7);
}

.users-title {
  margin: 0 0 4px;
  font-size: 1.05rem;
  font-weight: 800;
}

.users-subtitle {
  margin: 0;
  font-size: 0.78rem;
  color: var(--text-muted, #64748B);
  line-height: 1.8;
}

.users-close {
  border: none;
  background: transparent;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  color: var(--text-muted, #64748B);
}

.users-body {
  padding: 14px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.users-state,
.users-error {
  font-size: 0.82rem;
  color: var(--text-muted, #64748B);
  text-align: center;
  padding: 16px 0;
}

.users-error {
  color: #B91C1C;
}

.user-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--border-soft, #E5EAF2);
  border-radius: 12px;
  background: var(--bg-subtle, #F8FAFC);
}

.user-row.inactive {
  opacity: 0.66;
  border-style: dashed;
}

.user-main {
  flex: 1 1 240px;
  min-width: 0;
}

.user-line {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}

.user-name {
  font-weight: 800;
  font-size: 0.9rem;
}

.badge {
  font-size: 0.66rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  border: 1px solid transparent;
}

.badge-admin {
  background: #FEF3C7;
  color: #92400E;
  border-color: #FCD34D;
}

.badge-active {
  background: #DCFCE7;
  color: #166534;
  border-color: #86EFAC;
}

.badge-off {
  background: #FEE2E2;
  color: #991B1B;
  border-color: #FCA5A5;
}

.badge-me {
  background: #E0E7FF;
  color: #3730A3;
  border-color: #A5B4FC;
}

.user-email {
  font-size: 0.74rem;
  color: var(--text-muted, #64748B);
  margin: 4px 0 6px;
  word-break: break-all;
}

.user-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 0.7rem;
  color: var(--text-muted, #64748B);
}

.user-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.act-btn {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 6px 11px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid var(--border-strong, #CBD5E1);
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0F172A);
}

.act-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.act-danger {
  border-color: #FCA5A5;
  color: #B91C1C;
}

.users-notice {
  font-size: 0.78rem;
  font-weight: 700;
  color: #166534;
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
  border-radius: 10px;
  padding: 8px 12px;
  text-align: center;
}

.users-footer {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border-soft, #EDF2F7);
}

.users-refresh,
.users-done {
  font-size: 0.78rem;
  font-weight: 800;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
}

.users-refresh {
  background: transparent;
  border: 1px solid var(--border-strong, #CBD5E1);
  color: var(--text-primary, #0F172A);
}

.users-done {
  background: #0F172A;
  border: 1px solid #0F172A;
  color: #fff;
}
</style>
