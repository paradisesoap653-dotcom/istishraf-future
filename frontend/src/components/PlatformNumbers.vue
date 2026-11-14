<template>
  <section class="pnums" :class="{ 'pnums--open': open }">
    <button type="button" class="pnums-head" @click="open = !open">
      <span class="pnums-title">أرقامك الحقيقية <span class="pnums-opt">(اختياري)</span></span>
      <span class="pnums-hint">{{ savedSummary ? 'محفوظة ✓ اضغط للتعديل' : 'اضغط هنا واكتب أرقامك' }}</span>
      <span class="pnums-caret">{{ open ? '▲' : '▼' }}</span>
    </button>

    <div v-if="open" class="pnums-body">
      <p class="pnums-note">
        ما تكتبه هنا يُعامل <b>مدخلًا</b> لا افتراضًا: تُوزَّن به أفعال المحاكاة بين
        المنصّات، ويُذكر في «الافتراضات وحدود الثقة». اترك أي خانة لا تعرفها فارغة.
      </p>

      <div v-if="loading" class="pnums-status">جارٍ التحميل…</div>
      <div v-else-if="loadError" class="pnums-status pnums-status--err">{{ loadError }}</div>

      <template v-else>
        <div v-for="group in fields" :key="group.platform" class="pnums-group">
          <div class="pnums-platform">{{ group.label }}</div>
          <div class="pnums-row" v-for="field in group.fields" :key="field.key">
            <label :for="`${group.platform}-${field.key}`">{{ field.label }}</label>
            <input
              :id="`${group.platform}-${field.key}`"
              type="number"
              inputmode="numeric"
              min="0"
              :placeholder="field.hint"
              v-model="form[group.platform][field.key]"
              @input="persistDraft"
            />
          </div>
        </div>

        <p v-if="error" class="pnums-status pnums-status--err">{{ error }}</p>
        <div class="pnums-actions">
          <button type="button" class="pnums-save" :disabled="saving" @click="save">
            {{ saving ? 'جارٍ الحفظ…' : (error ? 'أعد المحاولة' : 'احفظ الأرقام') }}
          </button>
          <button type="button" class="pnums-clear" :disabled="saving" @click="clear">امسح الكل</button>
        </div>
        <p v-if="draftSaved" class="pnums-draft">مسودة أرقامك محفوظة في هذا الجهاز، فلن تفقدها إن أعدت المحاولة.</p>

        <p v-if="savedSummary" class="pnums-saved">
          <b>محفوظ:</b> {{ savedSummary }}
        </p>
        <div v-if="shareChips.length" class="pnums-chips">
          <span class="pnums-chip" v-for="chip in shareChips" :key="chip">{{ chip }}</span>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getPlatformInputs, savePlatformInputs } from '../api/simulation'

const props = defineProps({
  simulationId: { type: String, required: true }
})

const PLATFORM_LABELS = {
  facebook: 'فيسبوك',
  whatsapp: 'واتساب',
  tiktok: 'تيك توك',
  twitter: 'تويتر',
  reddit: 'ريديت'
}

const open = ref(true)  // تُفتح للمستخدم الجديد؛ وبعد الحفظ تُطوى تلقائيًا
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const loadError = ref('')
const fields = ref([])
const form = reactive({})
const savedSummary = ref('')
const shareChips = ref([])
const draftSaved = ref(false)
const draftKey = () => `istishraf_pnums_draft_${props.simulationId}`

const ensureGroups = (list) => {
  list.forEach((group) => {
    if (!form[group.platform]) form[group.platform] = {}
    group.fields.forEach((field) => {
      if (form[group.platform][field.key] === undefined) form[group.platform][field.key] = ''
    })
  })
}

const applyWeights = (weights) => {
  shareChips.value = Object.entries(weights || {})
    .filter(([, value]) => Number(value) > 0)
    .map(([key, value]) => `${PLATFORM_LABELS[key] || key} ${Math.round(Number(value) * 100)}٪`)
}

const load = async () => {
  if (!props.simulationId) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPlatformInputs(props.simulationId)
    const data = res?.data || res || {}
    fields.value = data.fields || []
    ensureGroups(fields.value)
    const inputs = data.inputs || {}
    Object.keys(inputs).forEach((platform) => {
      Object.entries(inputs[platform] || {}).forEach(([key, value]) => {
        form[platform][key] = value
      })
    })
    savedSummary.value = data.summary || ''
    applyWeights(data.weights)
    // إن كانت الأرقام محفوظة سابقًا نطوي البطاقة حتى لا تحتل الشاشة كلها
    if (savedSummary.value) open.value = false
    else {
      // لم تُحفظ أرقام: استعد المسودة المحلية إن وُجدت
      try {
        const draft = JSON.parse(localStorage.getItem(draftKey()) || 'null')
        if (draft && typeof draft === 'object') {
          Object.entries(draft).forEach(([platform, values]) => {
            if (!form[platform]) form[platform] = {}
            Object.entries(values || {}).forEach(([key, value]) => { form[platform][key] = value })
          })
          draftSaved.value = true
        }
      } catch (err) { /* تجاهل */ }
    }
  } catch (err) {
    loadError.value = 'تعذر تحميل الأرقام المحفوظة.'
  } finally {
    loading.value = false
  }
}

const persistDraft = () => {
  try {
    const payload = collect()
    if (Object.keys(payload).length) {
      localStorage.setItem(draftKey(), JSON.stringify(payload))
    }
  } catch (err) {
    /* التخزين المحلي قد يكون معطّلًا؛ لا نعطّل الحفظ بسبب ذلك */
  }
}

const collect = () => {
  const out = {}
  Object.entries(form).forEach(([platform, values]) => {
    const kept = {}
    Object.entries(values).forEach(([key, value]) => {
      const number = Number(value)
      if (value !== '' && Number.isFinite(number) && number > 0) kept[key] = number
    })
    if (Object.keys(kept).length) out[platform] = kept
  })
  return out
}

const describeError = (err) => {
  const status = err?.response?.status
  const serverMsg = err?.response?.data?.error
  if (status === 401) return 'انتهت صلاحية الجلسة. سجّل الدخول من جديد ثم أعد المحاولة.'
  if (status === 404) return 'هذا المشروع غير متاح للحساب الحالي.'
  if (status === 400 && serverMsg) return serverMsg
  if (status >= 500) {
    return `خطأ في الخادم أثناء الحفظ (${status})${serverMsg ? ': ' + serverMsg : ''}. أرقامك باقية هنا — اضغط «أعد المحاولة».`
  }
  if (!status) return 'لم يصل الطلب إلى الخادم (شبكة أو حجب). أرقامك باقية هنا — اضغط «أعد المحاولة».'
  return `تعذّر الحفظ (${status})${serverMsg ? ': ' + serverMsg : ''}`
}

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    const res = await savePlatformInputs(props.simulationId, collect())
    const data = res?.data || res || {}
    savedSummary.value = data.summary || ''
    applyWeights(data.weights)
    draftSaved.value = false
    try { localStorage.removeItem(draftKey()) } catch (err) { /* تجاهل */ }
  } catch (err) {
    console.error('platform-inputs save failed:', err?.response?.status, err?.message)
    persistDraft()
    draftSaved.value = true
    error.value = describeError(err)
  } finally {
    saving.value = false
  }
}

const clear = async () => {
  Object.keys(form).forEach((platform) => {
    Object.keys(form[platform]).forEach((key) => {
      form[platform][key] = ''
    })
  })
  await save()
}

onMounted(load)
</script>

<style scoped>
.pnums {
  margin: 0 0 12px;
  border: 1px solid var(--border-frame, #e5e7eb);
  border-inline-start: 4px solid #1f6feb;
  border-radius: 14px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, .06);
  background: var(--surface, #fff);
  overflow: hidden;
}
.pnums-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 11px 14px;
  background: transparent;
  border: 0;
  cursor: pointer;
  font-family: inherit;
  text-align: right;
}
.pnums-title { font-weight: 700; font-size: 14px; color: var(--text-primary, #0f172a); }
.pnums-opt { font-weight: 400; font-size: 12px; color: var(--text-secondary, #64748b); }
.pnums-hint { margin-inline-start: auto; font-size: 12px; color: var(--text-secondary, #64748b); }
.pnums-caret { font-size: 10px; color: var(--text-secondary, #64748b); }
.pnums-body { padding: 0 14px 14px; }
.pnums-note {
  margin: 0 0 12px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--text-secondary, #475569);
  background: var(--surface-muted, #f8fafc);
  border-radius: 10px;
  padding: 9px 11px;
}
.pnums-group { margin-bottom: 10px; }
.pnums-platform {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
  color: var(--text-primary, #0f172a);
}
.pnums-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.pnums-row label { flex: 1 1 auto; font-size: 12.5px; color: var(--text-secondary, #475569); }
.pnums-row input {
  flex: 0 0 44%;
  min-width: 110px;
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  text-align: left;
  border: 1px solid var(--border-frame, #dbe2ea);
  border-radius: 9px;
  background: var(--surface, #fff);
  color: var(--text-primary, #0f172a);
}
.pnums-actions { display: flex; gap: 8px; margin-top: 10px; }
.pnums-save {
  flex: 1 1 auto;
  padding: 10px 14px;
  border: 0;
  border-radius: 10px;
  background: #1f6feb;
  color: #fff;
  font-family: inherit;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
}
.pnums-save:disabled { opacity: .6; cursor: default; }
.pnums-clear {
  padding: 10px 14px;
  border: 1px solid var(--border-frame, #dbe2ea);
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary, #475569);
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
}
.pnums-status { font-size: 12.5px; color: var(--text-secondary, #475569); padding: 6px 0; }
.pnums-status--err { color: #b42318; }
.pnums-saved {
  margin: 10px 0 6px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--text-primary, #0f172a);
  word-break: break-word;
}
.pnums-draft { margin: 6px 0 0; font-size: 11.5px; color: var(--text-secondary, #64748b); }
.pnums-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.pnums-chip {
  font-size: 11.5px;
  padding: 4px 9px;
  border-radius: 999px;
  background: #eef4ff;
  color: #1f4fa8;
}
@media (max-width: 600px) {
  .pnums-row { flex-wrap: wrap; }
  .pnums-row input { flex: 1 1 100%; min-width: 0; }
}
</style>
