<template>
  <div class="report-download" ref="rootEl">
    <button
      class="dl-trigger"
      type="button"
      :disabled="busy || !reportId"
      :aria-expanded="open ? 'true' : 'false'"
      @click.stop="toggle"
    >
      <svg v-if="!busy" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="7 10 12 15 17 10"></polyline>
        <line x1="12" y1="15" x2="12" y2="3"></line>
      </svg>
      <span v-else class="spinner" aria-hidden="true"></span>
      <span>{{ busy ? 'جارٍ التجهيز…' : 'تحميل التقرير' }}</span>
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    <div v-if="open" class="dl-menu" role="menu">
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

    <p v-if="message" class="dl-msg" :class="error ? 'is-error' : 'is-ok'">{{ message }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import service from '../api'

const props = defineProps({
  reportId: { type: String, required: true },
  fileName: { type: String, default: '' }
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

const toggle = () => {
  if (busy.value) return
  open.value = !open.value
  if (open.value) { message.value = '' }
}

const closeMenu = (event) => {
  if (!rootEl.value) return
  if (!rootEl.value.contains(event.target)) open.value = false
}

onMounted(() => document.addEventListener('click', closeMenu))
onBeforeUnmount(() => document.removeEventListener('click', closeMenu))

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

.dl-trigger {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 9px 14px; border-radius: 12px; cursor: pointer;
  border: 1px solid rgba(255, 69, 0, .35);
  background: linear-gradient(180deg, rgba(255, 69, 0, .12), rgba(255, 69, 0, .05));
  color: inherit; font-family: inherit; font-size: 14px; font-weight: 600;
  transition: transform .12s ease, box-shadow .12s ease, background .12s ease;
}
.dl-trigger:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(255, 69, 0, .18); }
.dl-trigger:disabled { opacity: .6; cursor: not-allowed; }

.spinner {
  width: 15px; height: 15px; border-radius: 50%;
  border: 2px solid rgba(255, 69, 0, .3); border-top-color: #FF4500;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.dl-menu {
  position: absolute; top: calc(100% + 8px); inset-inline-start: 0; z-index: 40;
  min-width: 250px; padding: 6px; border-radius: 14px;
  background: var(--panel-bg, #fff); color: var(--text-primary, #1b1d22);
  border: 1px solid rgba(0, 0, 0, .08);
  box-shadow: 0 18px 45px rgba(10, 15, 30, .18);
  backdrop-filter: blur(6px);
}

.dl-item {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 9px 10px; border: 0; border-radius: 10px; cursor: pointer;
  background: transparent; color: inherit; font-family: inherit; text-align: start;
}
.dl-item:hover:not(:disabled) { background: rgba(255, 69, 0, .09); }
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
.dl-label { font-size: 14px; font-weight: 600; }
.dl-hint { font-size: 11.5px; opacity: .62; }

.dl-msg { margin: 8px 0 0; font-size: 12.5px; }
.dl-msg.is-ok { color: #15803d; }
.dl-msg.is-error { color: #dc2626; }

@media (max-width: 600px) {
  .dl-menu { position: fixed; inset-inline: 12px; top: auto; bottom: 16px; min-width: 0; }
}
</style>
