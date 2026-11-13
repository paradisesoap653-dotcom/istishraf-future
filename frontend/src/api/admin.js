import service from './index'

/** قائمة المستخدمين (للمدير فقط) */
export const listUsers = () => service.get('/api/auth/users')

/** إيقاف/تفعيل حساب */
export const setUserStatus = (userId, active) =>
  service.post(`/api/auth/users/${userId}/status`, { active })

/** تعديل الحصة اليومية */
export const setUserQuota = (userId, dailyQuota) =>
  service.post(`/api/auth/users/${userId}/quota`, { daily_quota: dailyQuota })

/** حذف حساب */
export const deleteUser = (userId) => service.delete(`/api/auth/users/${userId}`)
