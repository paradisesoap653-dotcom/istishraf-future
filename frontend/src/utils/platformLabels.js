// أسماء المنصّات بالعربية + لون لكل منصّة.
// المحرّك يعمل على خمس منصّات: فيسبوك/واتساب/تيك توك/تويتر/ريديت، والواجهة
// تبني بطاقة لكل منصّة وردت من الخادم — لا بطاقتين ثابتتين.

export const PLATFORM_LABELS = {
  facebook: 'فيسبوك',
  whatsapp: 'واتساب',
  tiktok: 'تيك توك',
  twitter: 'تويتر (إكس)',
  reddit: 'ريديت'
}

export const PLATFORM_COLORS = {
  facebook: '#1877f2',
  whatsapp: '#25d366',
  tiktok: '#111111',
  twitter: '#4a5568',
  reddit: '#ff4500'
}

// أنواع المحتوى على كل منصّة (تُعرض في تلميح البطاقة)
export const PLATFORM_FORMS = {
  facebook: ['منشور', 'تعليق', 'مشاركة', 'تفاعل', 'سكوت'],
  whatsapp: ['رسالة مجموعة', 'حالة', 'رسالة صوتية', 'إعادة إرسال', 'سكوت'],
  tiktok: ['فيديو', 'تعليق', 'رد فيديو', 'مشاركة', 'سكوت'],
  twitter: ['تغريدة', 'رد', 'اقتباس', 'إعادة نشر', 'سكوت'],
  reddit: ['منشور', 'تعليق', 'تصويت', 'مشاركة', 'سكوت']
}

export const DEFAULT_PLATFORMS = ['facebook', 'whatsapp', 'tiktok', 'twitter', 'reddit']

export function platformLabel(key) {
  if (!key) return ''
  return PLATFORM_LABELS[key] || key
}

export function platformColor(key) {
  return PLATFORM_COLORS[key] || '#3a4a63'
}

/** يبني قائمة البطاقات من ردّ الخادم (run-status) أو من إعدادات المحاكاة */
export function platformKeysFrom(statusData, fallback = DEFAULT_PLATFORMS) {
  const fromServer = statusData && statusData.platforms
  if (fromServer && typeof fromServer === 'object' && !Array.isArray(fromServer)) {
    const keys = Object.keys(fromServer)
    if (keys.length) return keys
  }
  return [...fallback]
}
