<template>
  <div class="home-container">
    <!-- الشريط العلوي المؤطّر -->
    <nav class="navbar">
      <div class="nav-brand">
        <span class="brand-beacon">◈</span>
        <span>استشراف المستقبل</span>
      </div>
      <div class="nav-links">
        <AuthModal :dark="true" />
        <ThemeToggle />
        <PwaInstallButton :dark="true" />
        <ApiSettingsModal :dark="true" />
        <LanguageSwitcher :dark="true" />
      </div>
    </nav>

    <div class="main-content">
      <!-- الإطار الرئيسي العلوي: الشعار في الوسط وبحجم أكبر + النص المنسق داخل إطار -->
      <section class="hero-frame-card">
        <div class="tag-row">
          <span class="orange-tag">{{ $t('home.tagline') }}</span>
          <span class="version-pill">{{ $t('home.version') }}</span>
        </div>

        <!-- الشعار الرسمي مكبّر وفي المنتصف -->
        <div class="logo-showcase">
          <div class="logo-medallion">
            <img
              src="../assets/logo/istishraf_hero.png"
              alt="شعار استشراف المستقبل"
              class="hero-logo"
            />
          </div>
        </div>

        <h1 class="main-title">
          {{ $t('home.heroTitle1') }}
          <span class="accent-title">{{ $t('home.heroTitle2') }}</span>
        </h1>

        <!-- صندوق الوصف المؤطّر والمنسق -->
        <div class="hero-desc-frame">
          <p class="hero-desc-text">
            <i18n-t keypath="home.heroDesc" tag="span">
              <template #brand><span class="highlight-bold">{{ $t('home.heroDescBrand') }}</span></template>
              <template #agentScale><span class="highlight-orange">{{ $t('home.heroDescAgentScale') }}</span></template>
              <template #optimalSolution><span class="highlight-code">{{ $t('home.heroDescOptimalSolution') }}</span></template>
            </i18n-t>
          </p>
          <div class="slogan-frame">
            <span class="slogan-text">{{ $t('home.slogan') }}</span>
            <span class="blinking-cursor">_</span>
          </div>
        </div>

        <div class="hero-footer-bar">
          <button type="button" class="scroll-down-btn" @click="scrollToConsole">
            <span>ابدأ الاستشراف الآن</span>
            <span class="down-arrow">↓</span>
          </button>
        </div>
      </section>

      <!-- القسم المزدوج المؤطّر: حالة النظام ومراحل العمل + منصة الرفع والتشغيل -->
      <section ref="consoleSectionRef" class="dashboard-section">
        <!-- اللوحة اليمنى: حالة النظام والمؤشرات ومراحل العمل (كل قسم داخل إطار مستقل) -->
        <div class="left-panel">
          <!-- إطار حالة النظام والمؤشرات -->
          <div class="framed-card status-card">
            <div class="panel-header">
              <span class="status-dot">●</span>
              <span>{{ $t('home.systemStatus') }}</span>
            </div>

            <h2 class="section-title">{{ $t('home.systemReady') }}</h2>
            <p class="section-desc">
              {{ $t('home.systemReadyDesc') }}
            </p>

            <div class="metrics-row">
              <div class="metric-card">
                <div class="metric-value">{{ $t('home.metricLowCost') }}</div>
                <div class="metric-label">{{ $t('home.metricLowCostDesc') }}</div>
              </div>
              <div class="metric-card">
                <div class="metric-value">{{ $t('home.metricHighAvail') }}</div>
                <div class="metric-label">{{ $t('home.metricHighAvailDesc') }}</div>
              </div>
            </div>
          </div>

          <!-- إطار تسلسل مراحل العمل (كل خطوة داخل إطار فرعي أنيق) -->
          <div class="framed-card steps-container">
            <div class="steps-header">
              <span class="diamond-icon">◈</span>
              <span>{{ $t('home.workflowSequence') }}</span>
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step01Title') }}</div>
                  <div class="step-desc">{{ $t('home.step01Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step02Title') }}</div>
                  <div class="step-desc">{{ $t('home.step02Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step03Title') }}</div>
                  <div class="step-desc">{{ $t('home.step03Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step04Title') }}</div>
                  <div class="step-desc">{{ $t('home.step04Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step05Title') }}</div>
                  <div class="step-desc">{{ $t('home.step05Desc') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- اللوحة اليسرى: وحدة رفع الملفات وبدء المحاكاة داخل إطار محكم -->
        <div class="right-panel">
          <div class="framed-card console-box">
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.realitySeed') }}</span>
                <span class="console-meta">{{ $t('home.supportedFormats') }}</span>
              </div>

              <div
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />

                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">{{ $t('home.dragToUpload') }}</div>
                  <div class="upload-hint">{{ $t('home.orBrowse') }}</div>
                </div>

                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="console-divider">
              <span>{{ $t('home.inputParams') }}</span>
            </div>

            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.simulationPrompt') }}</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  :placeholder="$t('home.promptPlaceholder')"
                  rows="5"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">{{ $t('home.engineBadge') }}</div>
              </div>
            </div>

            <div class="console-section btn-section">
              <button
                type="button"
                class="sample-load-btn"
                @click="loadSampleScenario"
                :disabled="loading"
              >
                📄 {{ $t('home.loadSampleBtn') }}
              </button>
              <button
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">{{ $t('home.startEngine') }}</span>
                <span v-else>{{ $t('home.initializing') }}</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- سجل المحاكاة السابقة داخل إطار منظم -->
      <div class="framed-card history-frame-wrapper">
        <HistoryDatabase />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import PwaInstallButton from '../components/PwaInstallButton.vue'
import ApiSettingsModal from '../components/ApiSettingsModal.vue'
import AuthModal from '../components/AuthModal.vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import { authState, openAuthModal } from '../store/auth'

const router = useRouter()
const consoleSectionRef = ref(null)

const formData = ref({
  simulationRequirement: ''
})

const files = ref([])
const loading = ref(false)
const isDragOver = ref(false)
const fileInput = ref(null)

const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

const handleDragOver = () => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = () => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

const removeFile = (index) => {
  files.value.splice(index, 1)
}

const loadSampleScenario = () => {
  const sampleContent = `تقرير إطلاق مبادرة "المدن الذكية والطاقة النظيفة 2027"
تدرس هيئة التطوير الحضري تطبيق نظام نقل كهربائي ذكي مع تعرفة مرنة لأوقات الذروة ودعم مالي للشركات الناشئة في مجال الطاقة الشمسية المنزلية، بمشاركة السكان وأصحاب المتاجر وشركات التوصيل والخبراء الاقتصاديين.`
  const sampleFile = new File([sampleContent], 'مبادرة_النقل_الذكي_2027.txt', { type: 'text/plain' })
  files.value = [sampleFile]
  formData.value.simulationRequirement =
    'توقّع ردود فعل السكان، وأصحاب الأعمال التجارية، وشركات التوصيل، والخبراء الاقتصاديين تجاه تطبيق التعرفة المرنة للنقل الذكي ودعم الطاقة الشمسية خلال أول أسبوعين من الإعلان، وما هي أبرز نقاط الاعتراض والحلول المقترحة.'
}

const scrollToConsole = () => {
  if (consoleSectionRef.value) {
    consoleSectionRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } else {
    window.scrollTo({ top: 650, behavior: 'smooth' })
  }
}

const launchSimulationRoute = () => {
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}

const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  if (!authState.user) {
    openAuthModal(authState.firstUserBecomesAdmin ? 'register' : 'login', () => {
      launchSimulationRoute()
    })
    return
  }
  launchSimulationRoute()
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  background-color: var(--bg-page);
  color: var(--text-primary);
  padding-bottom: 40px;
}

/* شريط التنقل العلوي المؤطّر */
.navbar {
  min-height: 64px;
  background-color: var(--bg-card);
  color: var(--text-primary);
  border-bottom: 2px solid var(--border-frame);
  box-shadow: var(--card-shadow);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 28px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  font-weight: 800;
  font-size: 1.3rem;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
}

.brand-beacon {
  color: var(--accent-orange);
  font-size: 1.35rem;
}

.nav-links {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

/* الحاوية الرئيسية */
.main-content {
  max-width: 1260px;
  margin: 0 auto;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* البطاقات المؤطّرة الموحّدة */
.framed-card,
.hero-frame-card {
  background-color: var(--bg-card);
  border: 1.5px solid var(--border-frame);
  border-radius: 14px;
  box-shadow: var(--card-shadow);
  padding: 28px;
}

/* بطاقة الواجهة الرئيسية (Hero) المتمركزة */
.hero-frame-card {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  overflow: hidden;
  border-top: 4px solid var(--accent-orange);
}

.tag-row {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 22px;
}

.orange-tag {
  background: var(--accent-orange);
  color: #FFFFFF;
  padding: 6px 14px;
  border-radius: 6px;
  font-weight: 800;
  font-size: 0.85rem;
}

.version-pill {
  background: var(--bg-subtle);
  color: var(--text-secondary);
  border: 1px solid var(--border-frame);
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 700;
}

/* الشعار الكبير في المنتصف */
.logo-showcase {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 6px auto 24px;
}

.logo-medallion {
  width: 260px;
  height: 260px;
  border-radius: 50%;
  padding: 12px;
  background: #FFFFFF;
  border: 2px solid var(--border-strong);
  box-shadow: 0 10px 30px rgba(255, 69, 0, 0.14);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.hero-logo {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.main-title {
  font-size: 2.8rem;
  line-height: 1.35;
  font-weight: 800;
  margin: 0 auto 22px;
  color: var(--text-primary);
  max-width: 820px;
}

.accent-title {
  color: var(--accent-orange);
  display: inline-block;
  margin-inline-start: 8px;
}

/* إطار النص التوضيحي المنسق */
.hero-desc-frame {
  max-width: 780px;
  width: 100%;
  background: var(--bg-elevated);
  border: 1.5px solid var(--border-frame);
  border-radius: 12px;
  padding: 20px 22px;
  margin: 0 auto 22px;
  text-align: center;
}

.hero-desc-text {
  font-size: 1.06rem;
  line-height: 1.95;
  color: var(--text-secondary);
  font-weight: 600;
  margin-bottom: 16px;
}

.highlight-bold {
  color: var(--text-primary);
  font-weight: 800;
}

.highlight-orange {
  color: var(--accent-orange);
  font-weight: 800;
}

.highlight-code {
  background: var(--bg-subtle);
  border: 1px solid var(--border-frame);
  padding: 2px 8px;
  border-radius: 5px;
  color: var(--text-primary);
  font-weight: 800;
}

.slogan-frame {
  background: var(--bg-card);
  border: 1px solid var(--border-frame);
  border-inline-start: 4px solid var(--accent-orange);
  border-radius: 8px;
  padding: 12px 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.slogan-text {
  font-size: 1.08rem;
  font-weight: 800;
  color: var(--text-primary);
}

.blinking-cursor {
  color: var(--accent-orange);
  animation: blink 1s step-end infinite;
  font-weight: 800;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.hero-footer-bar {
  display: flex;
  justify-content: center;
}

.scroll-down-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 8px;
  border: 1.5px solid var(--accent-orange);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-weight: 800;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.scroll-down-btn:hover {
  background: var(--accent-orange);
  color: #FFFFFF;
}

.down-arrow {
  color: var(--accent-orange);
  font-weight: 800;
}

.scroll-down-btn:hover .down-arrow {
  color: #FFFFFF;
}

/* القسم المزدوج */
.dashboard-section {
  display: grid;
  grid-template-columns: 1fr 1.15fr;
  gap: 24px;
  align-items: stretch;
}

.left-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.right-panel {
  display: flex;
  flex-direction: column;
}

.panel-header,
.steps-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.88rem;
  font-weight: 800;
  color: var(--text-muted);
  background: var(--bg-subtle);
  border: 1px solid var(--border-frame);
  padding: 5px 12px;
  border-radius: 6px;
  margin-bottom: 14px;
}

.status-dot,
.diamond-icon {
  color: #10B981;
  font-size: 0.95rem;
}

.diamond-icon {
  color: var(--accent-orange);
}

.section-title {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.section-desc {
  color: var(--text-secondary);
  line-height: 1.85;
  font-size: 0.98rem;
  font-weight: 600;
  padding: 12px 14px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-frame);
  border-radius: 8px;
  margin-bottom: 18px;
}

.metrics-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.metric-card {
  background: var(--bg-elevated);
  border: 1.5px solid var(--border-frame);
  border-radius: 10px;
  padding: 16px 14px;
  text-align: center;
}

.metric-value {
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.metric-label {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text-muted);
}

/* خطوات العمل داخل إطارات أنيقة */
.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
  background: var(--bg-elevated);
  border: 1.5px solid var(--border-frame);
  border-radius: 10px;
  transition: border-color 0.2s ease;
}

.workflow-item:hover {
  border-color: var(--accent-orange);
}

.step-num {
  min-width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(255, 69, 0, 0.12);
  border: 1px solid rgba(255, 69, 0, 0.35);
  color: var(--accent-orange);
  font-weight: 800;
  font-size: 0.92rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 800;
  font-size: 1.04rem;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.9rem;
  line-height: 1.7;
  font-weight: 500;
  color: var(--text-secondary);
}

/* صندوق التحكم ورفع الملفات */
.console-box {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 16px;
}

.console-section {
  background: var(--bg-elevated);
  border: 1px solid var(--border-frame);
  border-radius: 10px;
  padding: 18px;
}

.console-section.btn-section {
  background: transparent;
  border: none;
  padding: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 0.85rem;
  font-weight: 800;
  color: var(--text-secondary);
}

.console-meta {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-weight: 600;
}

.upload-zone {
  border: 2px dashed var(--border-strong);
  border-radius: 10px;
  min-height: 175px;
  padding: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.25s ease;
  background: var(--bg-card);
}

.upload-zone:hover,
.upload-zone.drag-over {
  border-color: var(--accent-orange);
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  border: 1.5px solid var(--border-frame);
  background: var(--bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  color: var(--accent-orange);
  font-weight: 800;
  font-size: 1.2rem;
}

.upload-title {
  font-weight: 800;
  font-size: 0.98rem;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.upload-hint {
  font-size: 0.82rem;
  color: var(--text-muted);
  font-weight: 600;
}

.file-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--bg-subtle);
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-frame);
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text-primary);
}

.file-name {
  flex: 1;
  margin: 0 10px;
  word-break: break-all;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.25rem;
  color: var(--text-muted);
}

.console-divider {
  display: flex;
  align-items: center;
  gap: 10px;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-frame);
}

.console-divider span {
  font-size: 0.8rem;
  font-weight: 800;
  color: var(--text-muted);
}

.input-wrapper {
  position: relative;
  border: 1.5px solid var(--border-frame);
  border-radius: 10px;
  background: var(--bg-card);
  overflow: hidden;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 16px 16px 34px;
  font-size: 0.96rem;
  font-weight: 600;
  line-height: 1.75;
  color: var(--text-primary);
  resize: vertical;
  outline: none;
  min-height: 140px;
}

.model-badge {
  position: absolute;
  bottom: 8px;
  left: 12px;
  font-size: 0.74rem;
  font-weight: 700;
  color: var(--text-muted);
  background: var(--bg-subtle);
  padding: 2px 8px;
  border-radius: 4px;
}

.sample-load-btn {
  width: 100%;
  margin-bottom: 12px;
  padding: 12px 16px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1.5px dashed var(--border-strong);
  border-radius: 10px;
  font-size: 0.92rem;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.2s ease;
}

.sample-load-btn:hover {
  border-color: var(--accent-orange);
}

.start-engine-btn {
  width: 100%;
  background: var(--accent-orange);
  color: #FFFFFF;
  border: none;
  border-radius: 10px;
  padding: 18px 22px;
  font-weight: 800;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.25s ease;
}

.start-engine-btn:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.start-engine-btn:disabled {
  background: var(--bg-subtle);
  color: var(--text-muted);
  border: 1.5px solid var(--border-frame);
  cursor: not-allowed;
}

.history-frame-wrapper {
  padding: 18px;
}

/* توافق كامل ومثالي مع شاشات الهواتف */
@media (max-width: 960px) {
  .dashboard-section {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .navbar {
    flex-direction: column;
    align-items: center;
    padding: 12px 14px;
    gap: 10px;
  }

  .nav-links {
    justify-content: center;
    width: 100%;
  }

  .main-content {
    padding: 14px 12px;
    gap: 16px;
  }

  .framed-card,
  .hero-frame-card {
    padding: 18px 14px;
    border-radius: 12px;
  }

  .logo-medallion {
    width: 210px;
    height: 210px;
    padding: 10px;
  }

  .main-title {
    font-size: 1.95rem;
    line-height: 1.4;
  }

  .hero-desc-frame {
    padding: 14px 12px;
  }

  .hero-desc-text {
    font-size: 0.98rem;
    line-height: 1.85;
  }

  .metrics-row {
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .metric-card {
    padding: 12px 8px;
  }

  .metric-value {
    font-size: 1.05rem;
  }
}
</style>
