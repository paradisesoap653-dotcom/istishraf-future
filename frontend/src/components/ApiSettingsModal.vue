<template>
  <div v-if="status.can_manage" class="api-settings-wrapper">
    <button
      type="button"
      class="settings-trigger-btn"
      :class="{ dark: dark }"
      @click="openModal"
    >
      <span class="status-led" :class="{ ok: status.configured }"></span>
      <span>⚙️ {{ $t('nav.settings') }}</span>
    </button>

    <Teleport to="body">
      <div v-if="showModal" class="settings-backdrop" @click.self="showModal = false">
        <div class="settings-card">
          <div class="settings-header">
            <div>
              <h3 class="settings-title">{{ $t('settings.title') }}</h3>
              <p class="settings-subtitle">{{ $t('settings.subtitle') }}</p>
            </div>
            <button type="button" class="settings-close" @click="showModal = false">×</button>
          </div>

          <div class="settings-body">
            <div class="status-banner" :class="{ configured: status.configured }">
              <span class="dot">●</span>
              <span>{{ status.configured ? $t('settings.statusConfigured') : $t('settings.statusMissing') }}</span>
            </div>

            <div class="form-group-box">
              <h4>{{ $t('settings.llmSection') }}</h4>
              <label class="field-label">{{ $t('settings.llmApiKey') }}</label>
              <input
                v-model="form.llm_api_key"
                type="password"
                dir="ltr"
                class="field-input"
                :placeholder="status.has_llm_key ? $t('settings.keepExistingHint') : $t('settings.llmApiKeyPlaceholder')"
              />

              <div class="two-cols">
                <div>
                  <label class="field-label">{{ $t('settings.llmBaseUrl') }}</label>
                  <input
                    v-model="form.llm_base_url"
                    type="text"
                    dir="ltr"
                    class="field-input"
                    placeholder="https://api.openai.com/v1"
                  />
                </div>
                <div>
                  <label class="field-label">{{ $t('settings.llmModelName') }}</label>
                  <input
                    v-model="form.llm_model_name"
                    type="text"
                    dir="ltr"
                    class="field-input"
                    placeholder="gpt-4o-mini"
                  />
                </div>
              </div>
            </div>

            <div class="form-group-box">
              <h4>{{ $t('settings.zepSection') }}</h4>
              <label class="field-label">{{ $t('settings.zepApiKey') }}</label>
              <input
                v-model="form.zep_api_key"
                type="password"
                dir="ltr"
                class="field-input"
                :placeholder="status.has_zep_key ? $t('settings.keepExistingHint') : $t('settings.zepApiKeyPlaceholder')"
              />
            </div>

            <div v-if="savedMsg" class="saved-alert">✓ {{ savedMsg }}</div>

            <div class="settings-footer">
              <button type="button" class="cancel-btn" @click="showModal = false">
                {{ $t('common.close') }}
              </button>
              <button type="button" class="save-btn" :disabled="saving" @click="saveSettings">
                {{ saving ? $t('settings.saving') : $t('settings.saveBtn') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import service from '../api/index'

defineProps({
  dark: {
    type: Boolean,
    default: false
  }
})

const { t } = useI18n()
const showModal = ref(false)
const saving = ref(false)
const savedMsg = ref('')

const status = reactive({
  configured: false,
  has_llm_key: false,
  has_zep_key: false,
  can_manage: false
})

const form = reactive({
  llm_api_key: '',
  llm_base_url: 'https://api.openai.com/v1',
  llm_model_name: 'gpt-4o-mini',
  zep_api_key: ''
})

const fetchStatus = async () => {
  try {
    const res = await service.get('/api/config/status')
    if (res?.data) {
      status.configured = res.data.configured
      status.has_llm_key = res.data.has_llm_key
      status.has_zep_key = res.data.has_zep_key
      status.can_manage = Boolean(res.data.can_manage)
      form.llm_base_url = res.data.llm_base_url || 'https://api.openai.com/v1'
      form.llm_model_name = res.data.llm_model_name || 'gpt-4o-mini'
    }
  } catch {
    // ignore transient startup
  }
}

const openModal = async () => {
  savedMsg.value = ''
  await fetchStatus()
  showModal.value = true
}

const saveSettings = async () => {
  saving.value = true
  savedMsg.value = ''
  try {
    const res = await service.post('/api/config/update', {
      llm_api_key: form.llm_api_key,
      llm_base_url: form.llm_base_url,
      llm_model_name: form.llm_model_name,
      zep_api_key: form.zep_api_key
    })
    if (res?.data) {
      status.configured = res.data.configured
      status.has_llm_key = res.data.has_llm_key
      status.has_zep_key = res.data.has_zep_key
      form.llm_api_key = ''
      form.zep_api_key = ''
      savedMsg.value = t('settings.savedSuccess')
    }
  } catch (err) {
    savedMsg.value = err.message || t('common.error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchStatus()
  window.addEventListener('istishraf-auth-changed', fetchStatus)
})

onUnmounted(() => {
  window.removeEventListener('istishraf-auth-changed', fetchStatus)
})
</script>

<style scoped>
.settings-trigger-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid #CCC;
  background: transparent;
  color: #333;
  transition: border-color 0.2s, background 0.2s;
}

.settings-trigger-btn.dark {
  color: #FFFFFF;
  border-color: rgba(255, 255, 255, 0.35);
}

.settings-trigger-btn.dark:hover {
  border-color: #FFFFFF;
  background: rgba(255, 255, 255, 0.08);
}

.status-led {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #F59E0B;
}

.status-led.ok {
  background: #10B981;
}

.settings-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 3000;
}

.settings-card {
  background: #FFF;
  color: #111;
  width: 100%;
  max-width: 620px;
  max-height: 90vh;
  overflow-y: auto;
  border-radius: 10px;
  border: 2px solid #000;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid #EAEAEA;
  background: #FAFAFA;
}

.settings-title {
  font-size: 1.12rem;
  font-weight: 700;
  margin-bottom: 6px;
}

.settings-subtitle {
  font-size: 0.84rem;
  color: #555;
  line-height: 1.6;
}

.settings-close {
  background: none;
  border: none;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  color: #444;
}

.settings-body {
  padding: 20px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 0.86rem;
  font-weight: 600;
  background: #FEF3C7;
  color: #92400E;
}

.status-banner.configured {
  background: #DCFCE7;
  color: #166534;
}

.form-group-box {
  border: 1px solid #E5E5E5;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-group-box h4 {
  font-size: 0.94rem;
  margin-bottom: 2px;
}

.field-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: #444;
  margin-bottom: 4px;
}

.field-input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #CCC;
  border-radius: 5px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.84rem;
}

.field-input:focus {
  outline: none;
  border-color: #000;
}

.two-cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}

.saved-alert {
  padding: 10px 14px;
  background: #DCFCE7;
  color: #166534;
  border-radius: 6px;
  font-size: 0.86rem;
  font-weight: 600;
}

.settings-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

.cancel-btn {
  padding: 9px 16px;
  border: 1px solid #CCC;
  background: #FFF;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
}

.save-btn {
  padding: 9px 20px;
  border: none;
  background: #000;
  color: #FFF;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 700;
}
</style>
