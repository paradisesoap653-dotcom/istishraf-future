<template>
  <div class="scenario-compare">
    <button class="scn-trigger" type="button" @click="open = true">
      <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 3v18h18"></path>
        <path d="M7 15l4-6 4 3 4-7"></path>
      </svg>
      <span>سيناريو مقارن</span>
    </button>

    <Teleport to="body">
      <div v-if="open" class="scn-overlay" @click.self="close">
        <div class="scn-sheet" dir="rtl">
          <div class="scn-head">
            <span class="scn-title">سيناريو مقارن</span>
            <button class="scn-x" type="button" @click="close" aria-label="إغلاق">✕</button>
          </div>

          <!-- شاشة الإعداد -->
          <div v-if="!result" class="scn-body">
            <p class="scn-hint">
              عدّل افتراضًا واحدًا (مثل العمولة أو السعر) وسنعيد تشغيل جولات قصيرة على
              <b>نفس الوكلاء</b>، ثم نقارن النتيجة بالأصل — بلا إعادة محاكاة كاملة.
            </p>

            <label class="scn-label">ما التغيير المطلوب؟</label>
            <textarea
              v-model="change"
              class="scn-text"
              rows="3"
              maxlength="400"
              placeholder="مثال: خفض العمولة من 10% إلى 5%"
            ></textarea>

            <label class="scn-label">عدد الجولات</label>
            <div class="scn-rounds">
              <button
                v-for="n in [1, 2, 3]"
                :key="n"
                type="button"
                class="scn-round-btn"
                :class="{ active: rounds === n }"
                @click="rounds = n"
              >{{ n }}</button>
            </div>

            <button class="scn-run" type="button" :disabled="busy || !change.trim()" @click="run">
              <span v-if="busy" class="scn-spin"></span>
              {{ busy ? 'جارٍ تشغيل السيناريو…' : 'شغّل السيناريو' }}
            </button>
            <p v-if="busy" class="scn-wait">قد يستغرق من ٢٠ إلى ٩٠ ثانية. لا تغلق الصفحة.</p>
            <p v-if="error" class="scn-err">{{ error }}</p>
          </div>

          <!-- شاشة النتيجة -->
          <div v-else class="scn-body">
            <p class="scn-change-tag">التغيير: <b>{{ result.change }}</b></p>

            <div class="scn-table">
              <div class="scn-row scn-row--head">
                <span>المؤشر</span><span>الأصل</span><span>السيناريو</span><span>الفرق</span>
              </div>
              <div v-for="row in rows" :key="row.label" class="scn-row">
                <span class="scn-name">{{ row.label }}</span>
                <span class="scn-num">{{ row.before }}</span>
                <span class="scn-num scn-num--after">{{ row.after }}</span>
                <span class="scn-delta" :class="row.dir">{{ row.delta }}</span>
              </div>
            </div>

            <p class="scn-note">
              الأرقام محسوبة من وقائع المحاكاة نفسها. مؤشر النبرة تقريبي بحسب الكلمات.
            </p>

            <div v-if="result.analysis" class="scn-analysis">
              <div class="scn-analysis-head">قراءة تحليلية <span>(استنتاج)</span></div>
              <p>{{ result.analysis }}</p>
            </div>

            <div class="scn-actions">
              <a
                v-for="f in formats"
                :key="f.id"
                class="scn-dl"
                :href="downloadUrl(f.id)"
                target="_blank"
                rel="noopener"
              >{{ f.label }}</a>
            </div>

            <div class="scn-actions">
              <button class="scn-again" type="button" @click="reset">سيناريو آخر</button>
              <button class="scn-close2" type="button" @click="close">إغلاق</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { runReportScenario, getScenarioDownloadUrl } from '../api/report'

const props = defineProps({
  reportId: { type: String, required: true }
})

const open = ref(false)
const change = ref('')
const rounds = ref(2)
const busy = ref(false)
const error = ref('')
const result = ref(null)

const formats = [
  { id: 'pdf', label: 'PDF' },
  { id: 'docx', label: 'Word' },
  { id: 'md', label: 'Markdown' }
]

const rows = computed(() => {
  if (!result.value) return []
  const b = result.value.baseline || {}
  const s = result.value.scenario || {}

  const build = (label, key, suffix = '') => {
    const before = Number(b[key] ?? 0)
    const after = Number(s[key] ?? 0)
    const diff = Math.round((after - before) * 10) / 10
    return {
      label,
      before: before + suffix,
      after: after + suffix,
      delta: (diff > 0 ? '+' : '') + diff + suffix,
      dir: diff > 0 ? 'up' : diff < 0 ? 'down' : 'flat'
    }
  }

  return [
    build('عدد التفاعلات', 'interactions'),
    build('المنشورات', 'posts'),
    build('التعليقات', 'comments'),
    build('الوكلاء المشاركون', 'agents'),
    build('نبرة مؤيدة', 'support_pct', '٪'),
    build('نبرة متحفظة', 'skeptic_pct', '٪')
  ]
})

const downloadUrl = (format) =>
  getScenarioDownloadUrl(props.reportId, result.value?.scenario_id, format)

const run = async () => {
  if (busy.value || !change.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    const res = await runReportScenario(props.reportId, {
      change: change.value.trim(),
      rounds: rounds.value
    })
    const data = res && (res.data || null)
    if (!data || !data.baseline) {
      throw new Error((res && res.error) || 'لم تصل نتيجة من الخادم')
    }
    result.value = data
  } catch (err) {
    const msg = err?.response?.data?.error || err?.message || 'تعذر تشغيل السيناريو'
    error.value = msg
  } finally {
    busy.value = false
  }
}

const reset = () => {
  result.value = null
  error.value = ''
}

const close = () => {
  open.value = false
  busy.value = false
  error.value = ''
  result.value = null
}
</script>

<style scoped>
.scn-trigger {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 9px 14px; border-radius: 12px; cursor: pointer;
  border: 1px solid var(--border-frame, #CBD5E1);
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0F172A);
  font-family: inherit; font-size: 14px; font-weight: 700;
  transition: border-color .15s ease, transform .12s ease;
}
.scn-trigger:hover { border-color: var(--accent-orange, #FF4500); transform: translateY(-1px); }

.scn-overlay {
  position: fixed; inset: 0; z-index: 9990;
  background: rgba(10, 15, 30, .45);
  display: flex; align-items: center; justify-content: center;
  padding: 16px;
}

.scn-sheet {
  width: min(560px, 100%); max-height: 90vh; overflow-y: auto;
  background: var(--bg-card, #fff); color: var(--text-primary, #0F172A);
  border-radius: 18px; padding: 16px 16px 20px;
  box-shadow: 0 24px 60px rgba(6, 12, 24, .35);
  font-family: 'Fustat', 'Inter', system-ui, sans-serif;
}

.scn-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.scn-title { font-size: 17px; font-weight: 800; }
.scn-x { border: 0; background: transparent; font-size: 17px; color: var(--text-muted, #94A3B8); cursor: pointer; padding: 4px 6px; border-radius: 8px; }
.scn-x:hover { background: rgba(0, 0, 0, .06); }

.scn-body { display: flex; flex-direction: column; gap: 10px; }
.scn-hint { font-size: 13px; line-height: 1.85; color: var(--text-secondary, #475569); margin: 0 0 4px; }

.scn-label { font-size: 12.5px; font-weight: 700; color: var(--text-secondary, #475569); }

.scn-text {
  width: 100%; border-radius: 12px; padding: 10px 12px;
  border: 1px solid var(--border-frame, #CBD5E1);
  background: var(--bg-subtle, #F8FAFC); color: var(--text-primary, #0F172A);
  font-family: inherit; font-size: 14px; line-height: 1.7; resize: vertical;
}
.scn-text:focus { outline: none; border-color: var(--accent-orange, #FF4500); }

.scn-rounds { display: flex; gap: 8px; }
.scn-round-btn {
  width: 42px; height: 36px; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--border-frame, #CBD5E1);
  background: var(--bg-card, #fff); color: var(--text-secondary, #475569);
  font-family: inherit; font-weight: 700;
}
.scn-round-btn.active {
  background: var(--accent-orange, #FF4500); border-color: var(--accent-orange, #FF4500); color: #fff;
}

.scn-run {
  margin-top: 6px; padding: 12px 16px; border-radius: 12px; border: 0;
  background: linear-gradient(180deg, #FF5A17, #E63C00); color: #fff;
  font-family: inherit; font-size: 15px; font-weight: 800; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
}
.scn-run:disabled { opacity: .55; cursor: not-allowed; }

.scn-spin {
  width: 15px; height: 15px; border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, .45); border-top-color: #fff;
  animation: scnspin .8s linear infinite;
}
@keyframes scnspin { to { transform: rotate(360deg); } }

.scn-wait { font-size: 12.5px; color: var(--text-muted, #64748B); margin: 0; text-align: center; }
.scn-err { font-size: 13px; color: #DC2626; margin: 4px 0 0; line-height: 1.7; }

.scn-change-tag { font-size: 13.5px; color: var(--text-secondary, #475569); margin: 0; line-height: 1.7; }

.scn-table { border: 1px solid var(--border-frame, #E5E7EB); border-radius: 12px; overflow: hidden; }
.scn-row {
  display: grid; grid-template-columns: 1.5fr .8fr .9fr .7fr;
  gap: 6px; padding: 9px 10px; font-size: 12.5px;
  border-bottom: 1px solid var(--border-frame, #EEF2F7);
  align-items: center;
}
.scn-row:last-child { border-bottom: 0; }
.scn-row--head {
  background: var(--bg-subtle, #F8FAFC); font-weight: 800; font-size: 12px;
  color: var(--text-secondary, #475569);
}
.scn-name { color: var(--text-secondary, #475569); }
.scn-num { text-align: center; font-variant-numeric: tabular-nums; }
.scn-num--after { font-weight: 800; }
.scn-delta { text-align: center; font-weight: 800; font-variant-numeric: tabular-nums; }
.scn-delta.up { color: #059669; }
.scn-delta.down { color: #DC2626; }
.scn-delta.flat { color: var(--text-muted, #94A3B8); }

.scn-note { font-size: 11.5px; color: var(--text-muted, #94A3B8); margin: 0; line-height: 1.7; }

.scn-analysis {
  border-inline-start: 3px solid var(--accent-orange, #FF4500);
  background: var(--bg-subtle, #F8FAFC);
  padding: 10px 12px; border-radius: 0 10px 10px 0;
}
.scn-analysis-head { font-size: 12.5px; font-weight: 800; margin-bottom: 4px; }
.scn-analysis-head span { font-weight: 500; color: var(--text-muted, #94A3B8); }
.scn-analysis p { margin: 0; font-size: 13px; line-height: 1.9; color: var(--text-secondary, #475569); white-space: pre-wrap; }

.scn-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.scn-dl {
  flex: 1 1 30%; text-align: center; text-decoration: none;
  padding: 9px 10px; border-radius: 10px;
  border: 1px solid var(--border-frame, #CBD5E1);
  color: var(--text-primary, #0F172A); font-size: 12.5px; font-weight: 700;
  background: var(--bg-card, #fff);
}
.scn-dl:hover { border-color: var(--accent-orange, #FF4500); }

.scn-again {
  flex: 1; padding: 10px; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--border-frame, #CBD5E1); background: transparent;
  color: var(--text-secondary, #475569); font-family: inherit; font-size: 13px; font-weight: 700;
}
.scn-close2 {
  flex: 1; padding: 10px; border-radius: 10px; border: 0; cursor: pointer;
  background: var(--accent-orange, #FF4500); color: #fff;
  font-family: inherit; font-size: 13px; font-weight: 800;
}

@media (max-width: 600px) {
  .scn-overlay { align-items: flex-end; padding: 0; }
  .scn-sheet { width: 100%; border-radius: 18px 18px 0 0; max-height: 92vh; padding: 14px 13px calc(18px + env(safe-area-inset-bottom, 0px)); }
  .scn-row { grid-template-columns: 1.4fr .75fr .85fr .65fr; font-size: 12px; padding: 8px 8px; }
}
</style>
