<template>
  <div class="report-download" :class="{ compact }" ref="rootEl" @click.stop>
    <button
      class="dl-trigger"
      type="button"
      :disabled="busy || !reportId"
      :aria-expanded="open ? 'true' : 'false'"
      @click.stop="toggle"
    >
      <svg v-if="!busy" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="7 10 12 15 17 10"></polyline>
        <line x1="12" y1="15" x2="12" y2="3"></line>
      </svg>
      <span v-else class="spinner" aria-hidden="true"></span>
      <span>{{ busy ? 'جارٍ التجهيز…' : (compact ? 'تحميل' : 'تحميل التقرير') }}</span>
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    <!-- القائمة تُلحق بجسم الصفحة حتى لا تُقصّ داخل البطاقات ولا تتأثر بأي تحريك للحاوية -->
    <Teleport to="body">
      <div v-if="open" class="dl-backdrop" @click.stop="open = false"></div>
      <div
        v-if="open"
        class="dl-menu"
        :class="{ 'is-sheet': pos.sheet }"
        :style="menuStyle"
        role="menu"
        dir="rtl"
        @click.stop
      >
        <div class="dl-head">
          <span>اختر الصيغة</span>
          <button class="dl-close" type="button" @click.stop="open = false" aria-label="إغلاق">✕</button>
        </div>
        <button
          v-for="f in formats"
          :key="f.id"
          class="dl-item"
          type="button"
          :disabled="busy"
          @click.stop="download(f.id)"
        >
          <span class="dl-icon" :class="'is-' + f.id">{{ f.badge }}</span>
          <span class="dl-text">
            <span class="dl-label">{{ f.label }}</span>
            <span class="dl-hint">{{ f.hint }}</span>
          </span>
        </button>
      </div>
    </Teleport>

    <p v-if="message" class="dl-msg" :class="error ? 'is-error' : 'is-ok'">{{ message }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import service from '../api'

const props = defineProps({
  reportId: { type: String, required: true },
  fileName: { type: String, default: '' },
  // نسخة مصغّرة تُستخدم داخل القوائم والبطاقات
  compact: { type: Boolean, default: false }
})

const formats = [
  { id: 'pdf', label: 'PDF', hint: 'جاهز للطباعة والمشاركة', badge: 'PDF' },
  { id: 'docx', label: 'Word', hint: 'قابل للتعديل (.docx)', badge: 'DOC' },
  { id: 'html', label: 'صفحة ويب', hint: 'ملف واحد بلا إنترنت', badge: 'HTML' },
  { id: 'md', label: 'Markdown', hint: 'للمحررين والأنظمة', badge: 'MD' },
  { id: 'txt', label: 'نص عادي', hint: 'خفيف بلا تنسيق', badge: 'TXT' }
]

const open = ref(false)
const busy = ref(false)
const message = ref('')
const error = ref(false)
const rootEl = ref(null)
const pos = ref({ sheet: false, top: 0, left: 0, width: 250 })

const menuStyle = computed(() => {
  if (pos.value.sheet) return {}
  return {
    top: pos.value.top + 'px',
    left: pos.value.left + 'px',
    width: pos.value.width + 'px'
  }
})

// نُثبّت القائمة بإحداثيات محسوبة من الزر، لأن أي transform على الحاويات
// يُفسد position:fixed ويجعل القائمة تظهر خارج الشاشة (وهو ما كان يحدث على الهاتف).
const place = () => {
  const trigger = rootEl.value?.querySelector('.dl-trigger')
  if (!trigger) return
  const r = trigger.getBoundingClientRect()
  const vw = window.innerWidth
  const vh = window.innerHeight
  if (vw <= 640) {
    pos.value = { sheet: true, top: 0, left: 0, width: 0 }
    return
  }
  const width = props.compact ? 235 : 260
  const rtl = getComputedStyle(document.documentElement).direction === 'rtl'
  let left = rtl ? r.right - width : r.left
  left = Math.max(8, Math.min(left, vw - width - 8))
  const heightEstimate = 330
  const below = r.bottom + 8
  const top = below + heightEstimate > vh - 8 ? Math.max(8, r.top - heightEstimate - 8) : below
  pos.value = { sheet: false, top, left, width }
}

const toggle = async () => {
  if (busy.value) return
  if (open.value) { open.value = false; return }
  message.value = ''
  open.value = true
  await nextTick()
  place()
}

const closeMenu = (event) => {
  if (!open.value) return
  if (rootEl.value && rootEl.value.contains(event.target)) return
  if (event.target?.closest?.('.dl-menu')) return
  open.value = false
}

const onViewportChange = () => { if (open.value) place() }

onMounted(() => {
  document.addEventListener('click', closeMenu)
  window.addEventListener('scroll', onViewportChange, true)
  window.addEventListener('resize', onViewportChange)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', closeMenu)
  window.removeEventListener('scroll', onViewportChange, true)
  window.removeEventListener('resize', onViewportChange)
})

const safeName = (ext) => {
  const base = (props.fileName || `تقرير-${props.reportId}`).replace(/[\\/:*?"<>|]+/g, '-').trim()
  return `${base}.${ext}`
}

const saveBlob = (blob, name) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

const download = async (format) => {
  if (!props.reportId || busy.value) return
  busy.value = true
  error.value = false
  message.value = ''
  try {
    const data = await service.get(`/api/report/${props.reportId}/download`, {
      params: { format },
      responseType: 'blob'
    })
    const blob = data instanceof Blob ? data : new Blob([data])
    if (blob.type && blob.type.includes('json')) {
      const text = await blob.text()
      let msg = 'تعذر تجهيز الملف'
      try { msg = JSON.parse(text).error || msg } catch (e) { /* نص غير متوقع */ }
      throw new Error(msg)
    }
    saveBlob(blob, safeName(format))
    message.value = 'تم تنزيل الملف'
    open.value = false
    setTimeout(() => { message.value = '' }, 3500)
  } catch (err) {
    error.value = true
    message.value = err?.message || 'تعذر تنزيل الملف'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.report-download { position: relative; display: inline-flex; flex-direction: column; align-items: flex-start; }

/* زر واضح لا يُشبه المعطّل */
.dl-trigger {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: 12px; cursor: pointer;
  border: 1px solid rgba(190, 45, 0, .35);
  background: linear-gradient(180deg, #FF5A17, #E63C00);
  color: #fff; font-family: inherit; font-size: 14.5px; font-weight: 700;
  box-shadow: 0 4px 14px rgba(230, 60, 0, .28);
  transition: transform .12s ease, box-shadow .12s ease, filter .12s ease;
}
.dl-trigger:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 22px rgba(230, 60, 0, .32); filter: brightness(1.04); }
.dl-trigger:active:not(:disabled) { transform: translateY(0) scale(.99); }
.dl-trigger:disabled { opacity: .55; cursor: not-allowed; box-shadow: none; }

.compact .dl-trigger { padding: 5px 10px; border-radius: 9px; font-size: 12.5px; gap: 5px; box-shadow: none; }
.compact .dl-trigger svg { width: 14px; height: 14px; }

.spinner {
  width: 15px; height: 15px; border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, .45); border-top-color: #fff;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.dl-backdrop { position: fixed; inset: 0; background: rgba(10, 15, 30, .38); z-index: 9998; }

.dl-menu {
  position: fixed; z-index: 9999;
  padding: 6px; border-radius: 14px;
  background: #fff; color: #1b1d22;
  border: 1px solid rgba(0, 0, 0, .08);
  box-shadow: 0 18px 45px rgba(10, 15, 30, .22);
  font-family: 'Fustat', 'Inter', system-ui, sans-serif;
  max-height: 70vh; overflow-y: auto;
}

.dl-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 6px 8px; font-size: 12px; font-weight: 700; color: #6B7280;
}
.dl-close {
  border: 0; background: transparent; color: #9CA3AF;
  font-size: 15px; line-height: 1; cursor: pointer; padding: 4px 6px; border-radius: 8px;
}
.dl-close:hover { background: rgba(0, 0, 0, .06); color: #374151; }

.dl-item {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 10px 10px; border: 0; border-radius: 10px; cursor: pointer;
  background: transparent; color: inherit; font-family: inherit; text-align: start;
}
.dl-item:hover:not(:disabled) { background: rgba(255, 69, 0, .09); }
.dl-item:active:not(:disabled) { background: rgba(255, 69, 0, .16); }
.dl-item:disabled { opacity: .55; cursor: not-allowed; }

.dl-icon {
  flex: 0 0 auto; display: grid; place-items: center;
  width: 40px; height: 28px; border-radius: 7px;
  font-size: 10.5px; font-weight: 800; letter-spacing: .4px; color: #fff;
}
.is-pdf { background: #E14434; }
.is-docx { background: #2B579A; }
.is-html { background: #E34F26; }
.is-md { background: #4B5563; }
.is-txt { background: #6B7280; }

.dl-text { display: flex; flex-direction: column; line-height: 1.35; }
.dl-label { font-size: 14.5px; font-weight: 700; color: #111827; }
.dl-hint { font-size: 11.5px; color: #6B7280; }

.dl-msg { margin: 8px 0 0; font-size: 12.5px; }
.dl-msg.is-ok { color: #15803d; }
.dl-msg.is-error { color: #dc2626; }

/* على الهاتف: لوحة سفلية كاملة العرض */
.dl-menu.is-sheet {
  inset-inline: 12px; left: 12px; right: 12px; width: auto;
  bottom: calc(12px + env(safe-area-inset-bottom, 0px));
  top: auto; border-radius: 18px;
  padding: 8px 8px calc(12px + env(safe-area-inset-bottom, 0px));
  max-height: calc(100dvh - 32px);
  overflow-y: auto;
}
.dl-menu.is-sheet .dl-item { padding: 13px 10px; }
.dl-menu.is-sheet .dl-label { font-size: 15px; }
</style>
