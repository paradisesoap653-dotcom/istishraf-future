<template>
  <div v-if="!isNativeApp" class="pwa-install-wrapper">
    <button
      type="button"
      class="pwa-trigger-btn"
      :class="{ dark: dark, installed: isStandalone }"
      @click="handleTrigger"
    >
      <span class="pwa-icon">📲</span>
      <span class="pwa-text">{{ isStandalone ? $t('pwa.installedBadge') : $t('nav.installApp') }}</span>
    </button>

    <Teleport to="body">
      <div v-if="showModal" class="pwa-modal-backdrop" @click.self="showModal = false">
        <div class="pwa-modal-card">
          <div class="pwa-modal-header">
            <div>
              <h3 class="pwa-modal-title">{{ $t('pwa.modalTitle') }}</h3>
              <p class="pwa-modal-subtitle">{{ $t('pwa.modalSubtitle') }}</p>
            </div>
            <button type="button" class="pwa-close-btn" @click="showModal = false">×</button>
          </div>

          <div class="pwa-modal-body">
            <!-- Direct native install if browser supports beforeinstallprompt -->
            <div v-if="canDirectInstall" class="pwa-direct-box">
              <button type="button" class="pwa-primary-btn" @click="installNow">
                📲 {{ $t('pwa.directInstallBtn') }}
              </button>
            </div>

            <!-- Helpful standalone tab / copy link bar (especially useful when inside an iframe preview) -->
            <div class="pwa-link-box">
              <p class="pwa-hint-text">{{ $t('pwa.openNewTabHint') }}</p>
              <div class="pwa-link-actions">
                <a :href="appUrl" target="_blank" rel="noopener" class="pwa-action-btn primary">
                  ↗ {{ $t('pwa.openInBrowserBtn') }}
                </a>
                <button type="button" class="pwa-action-btn" @click="copyUrl">
                  {{ copied ? '✓ ' + $t('pwa.linkCopied') : '🔗 ' + $t('pwa.copyLinkBtn') }}
                </button>
              </div>
              <div class="pwa-url-display" dir="ltr">{{ appUrl }}</div>
            </div>

            <div class="pwa-guides-grid">
              <div class="pwa-guide-card">
                <div class="guide-badge android">Android</div>
                <h4>{{ $t('pwa.androidTitle') }}</h4>
                <ol>
                  <li>{{ $t('pwa.androidStep1') }}</li>
                  <li>{{ $t('pwa.androidStep2') }}</li>
                  <li>{{ $t('pwa.androidStep3') }}</li>
                </ol>
              </div>

              <div class="pwa-guide-card">
                <div class="guide-badge ios">iOS / iPhone</div>
                <h4>{{ $t('pwa.iosTitle') }}</h4>
                <ol>
                  <li>{{ $t('pwa.iosStep1') }}</li>
                  <li>{{ $t('pwa.iosStep2') }}</li>
                  <li>{{ $t('pwa.iosStep3') }}</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineProps({
  dark: {
    type: Boolean,
    default: false
  }
})

const showModal = ref(false)
const canDirectInstall = ref(false)
const isStandalone = ref(false)
const isNativeApp = ref(false)
const copied = ref(false)
const appUrl = ref('')

const syncPromptState = () => {
  canDirectInstall.value = Boolean(window.__pwaDeferredPrompt)
  isStandalone.value =
    window.matchMedia?.('(display-mode: standalone)')?.matches ||
    window.navigator?.standalone === true
}

const handleTrigger = async () => {
  appUrl.value = window.location.origin
  syncPromptState()
  if (window.__pwaDeferredPrompt) {
    await installNow()
  } else {
    showModal.value = true
  }
}

const installNow = async () => {
  const promptEvent = window.__pwaDeferredPrompt
  if (!promptEvent) {
    showModal.value = true
    return
  }
  promptEvent.prompt()
  const choice = await promptEvent.userChoice
  if (choice?.outcome === 'accepted') {
    window.__pwaDeferredPrompt = null
    canDirectInstall.value = false
    showModal.value = false
  }
}

const copyUrl = async () => {
  try {
    await navigator.clipboard.writeText(appUrl.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2200)
  } catch {
    copied.value = false
  }
}

onMounted(() => {
  appUrl.value = window.location.origin
  if (
    (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform()) ||
    navigator.userAgent.includes('IstishrafNative')
  ) {
    isNativeApp.value = true
  }
  syncPromptState()
  window.addEventListener('mirofish-pwa-ready', syncPromptState)
  window.addEventListener('mirofish-pwa-installed', syncPromptState)
})

onUnmounted(() => {
  window.removeEventListener('mirofish-pwa-ready', syncPromptState)
  window.removeEventListener('mirofish-pwa-installed', syncPromptState)
})
</script>

<style scoped>
.pwa-trigger-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #FF4500;
  background: #FF4500;
  color: #FFFFFF;
  transition: opacity 0.2s, transform 0.15s;
}

.pwa-trigger-btn:hover {
  opacity: 0.9;
}

.pwa-trigger-btn.installed {
  background: #10B981;
  border-color: #10B981;
}

.pwa-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 3000;
}

.pwa-modal-card {
  background: #FFFFFF;
  color: #111111;
  width: 100%;
  max-width: 680px;
  max-height: 90vh;
  overflow-y: auto;
  border-radius: 10px;
  border: 2px solid #000000;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
}

.pwa-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid #EAEAEA;
  background: #FAFAFA;
}

.pwa-modal-title {
  font-size: 1.15rem;
  font-weight: 700;
  margin-bottom: 4px;
}

.pwa-modal-subtitle {
  font-size: 0.88rem;
  color: #555;
}

.pwa-close-btn {
  background: none;
  border: none;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  color: #444;
  padding: 0 4px;
}

.pwa-modal-body {
  padding: 20px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.pwa-direct-box {
  display: flex;
}

.pwa-primary-btn {
  width: 100%;
  padding: 12px 18px;
  background: #FF4500;
  color: #FFF;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
}

.pwa-link-box {
  background: #F7F7F8;
  border: 1px solid #E2E2E5;
  border-radius: 8px;
  padding: 14px 16px;
}

.pwa-hint-text {
  font-size: 0.86rem;
  color: #333;
  line-height: 1.6;
  margin-bottom: 12px;
}

.pwa-link-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
}

.pwa-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 6px;
  border: 1px solid #222;
  background: #FFF;
  color: #111;
  font-size: 0.84rem;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
}

.pwa-action-btn.primary {
  background: #000;
  color: #FFF;
}

.pwa-url-display {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  color: #555;
  background: #FFF;
  border: 1px dashed #CCC;
  padding: 6px 10px;
  border-radius: 4px;
  word-break: break-all;
}

.pwa-guides-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 14px;
}

.pwa-guide-card {
  border: 1px solid #E5E5E5;
  border-radius: 8px;
  padding: 16px;
  background: #FFF;
}

.guide-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.guide-badge.android {
  background: #DCFCE7;
  color: #166534;
}

.guide-badge.ios {
  background: #E0E7FF;
  color: #1E40AF;
}

.pwa-guide-card h4 {
  font-size: 0.95rem;
  margin-bottom: 10px;
}

.pwa-guide-card ol {
  padding-inline-start: 18px;
  font-size: 0.85rem;
  color: #444;
  line-height: 1.75;
}

@media (max-width: 640px) {
  .pwa-text {
    font-size: 0.76rem;
  }
}
</style>
