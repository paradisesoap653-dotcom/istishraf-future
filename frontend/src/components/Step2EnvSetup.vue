<template>
  <div class="env-setup-panel">
    <div class="scroll-container">
      <!-- Step 01: 模拟实例 -->
      <div class="step-card" :class="{ 'active': phase === 0, 'completed': phase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">{{ $t('step2.simInstanceInit') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 0" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else class="badge processing">{{ $t('step2.initializing') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">
            {{ $t('step2.simInstanceDesc') }}
          </p>

          <div v-if="simulationId" class="info-card">
            <div class="info-row">
              <span class="info-label">Project ID</span>
              <span class="info-value mono">{{ projectData?.project_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Graph ID</span>
              <span class="info-value mono">{{ projectData?.graph_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Simulation ID</span>
              <span class="info-value mono">{{ simulationId }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Task ID</span>
              <span class="info-value mono">{{ taskId || $t('step2.asyncTaskDone') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: 生成 Agent 人设 -->
      <div class="step-card" :class="{ 'active': phase === 1, 'completed': phase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">{{ $t('step2.generateAgentPersona') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 1" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 1" class="badge processing">{{ prepareProgress }}%</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.generateAgentPersonaDesc') }}
          </p>

          <!-- Profiles Stats -->
          <div v-if="profiles.length > 0" class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ profiles.length }}</span>
              <span class="stat-label">{{ $t('step2.currentAgentCount') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ expectedTotal || '-' }}</span>
              <span class="stat-label">{{ $t('step2.expectedAgentTotal') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ totalTopicsCount }}</span>
              <span class="stat-label">{{ $t('step2.relatedTopicsCount') }}</span>
            </div>
          </div>

          <!-- Profiles List Preview -->
          <div v-if="profiles.length > 0" class="profiles-preview">
            <div class="preview-header">
              <span class="preview-title">{{ $t('step2.generatedAgentPersonas') }}</span>
            </div>
            <div class="profiles-list">
              <div 
                v-for="(profile, idx) in profiles" 
                :key="idx" 
                class="profile-card"
                @click="selectProfile(profile)"
              >
                <div class="profile-header">
                  <span class="profile-realname">{{ profile.username || 'Unknown' }}</span>
                  <span class="profile-username">@{{ profile.name || `agent_${idx}` }}</span>
                </div>
                <div class="profile-meta">
                  <span class="profile-profession">{{ profile.profession || $t('step2.unknownProfession') }}</span>
                </div>
                <p class="profile-bio">{{ profile.bio || $t('step2.noBio') }}</p>
                <div v-if="profile.interested_topics?.length" class="profile-topics">
                  <span 
                    v-for="topic in profile.interested_topics.slice(0, 3)" 
                    :key="topic" 
                    class="topic-tag"
                  >{{ topic }}</span>
                  <span v-if="profile.interested_topics.length > 3" class="topic-more">
                    +{{ profile.interested_topics.length - 3 }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: 生成双平台模拟配置 -->
      <div class="step-card" :class="{ 'active': phase === 2, 'completed': phase > 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">{{ $t('step2.dualPlatformConfig') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 2" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 2" class="badge processing">{{ $t('step2.generating') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.dualPlatformConfigDesc') }}
          </p>
          
          <!-- Config Preview -->
          <div v-if="simulationConfig" class="config-detail-panel">
            <!-- 时间配置 -->
            <div class="config-block">
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.simulationDuration') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.total_simulation_hours || '-' }} {{ $t('common.hours') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.roundDuration') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.minutes_per_round || '-' }} {{ $t('common.minutes') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.totalRounds') }}</span>
                  <span class="config-item-value">{{ Math.floor((simulationConfig.time_config?.total_simulation_hours * 60 / simulationConfig.time_config?.minutes_per_round)) || '-' }} {{ $t('common.rounds') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.activePerHour') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.agents_per_hour_min }}-{{ simulationConfig.time_config?.agents_per_hour_max }}</span>
                </div>
              </div>
            </div>

            <!-- 平台配置 -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">{{ $t('step2.recommendAlgoConfig') }}</span>
              </div>
              <p v-if="researchSummary" class="research-line">
                <span class="research-badge">بحث الويب</span>
                {{ researchSummary }}
              </p>
              <div class="platforms-grid">
                <div v-for="card in platformCards" :key="card.platform" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">
                      <span class="platform-dot" :style="{ background: card.color }"></span>
                      {{ card.label }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 04: 初始激活编排 -->
      <div class="step-card" :class="{ 'active': phase === 3, 'completed': phase > 3 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">04</span>
            <span class="step-title">{{ $t('step2.initialActivation') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 3" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 3" class="badge processing">{{ $t('step2.orchestrating') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.initialActivationDesc') }}
          </p>
        </div>
      </div>

      <!-- Step 05: 准备完成 -->
      <div class="step-card" :class="{ 'active': phase === 4 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">05</span>
            <span class="step-title">{{ $t('step2.setupComplete') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase >= 4" class="badge processing">{{ $t('step1.inProgress') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/start</p>
          <p class="description">{{ $t('step2.setupCompleteDesc') }}</p>
          
          <div class="action-group dual">
            <button 
              class="action-btn secondary"
              @click="$emit('go-back')"
            >
              ← {{ $t('step2.backToGraphBuild') }}
            </button>
            <button 
              class="action-btn primary"
              :disabled="phase < 4"
              @click="handleStartSimulation"
            >
              {{ $t('step2.startDualWorldSim') }} ➝
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- System Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SYSTEM DASHBOARD</span>
        <span class="log-id">{{ simulationId || 'NO_SIMULATION' }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { entityTypeLabel, registerOntology } from '../utils/ontologyLabels'
import { platformLabel, platformColor, PLATFORM_FORMS } from '../utils/platformLabels'
import {
  prepareSimulation,
  getPrepareStatus,
  getSimulationProfilesRealtime,
  getSimulationConfigRealtime
} from '../api/simulation'

const { t } = useI18n()

const props = defineProps({
  simulationId: String,
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

const phase = ref(0)
const taskId = ref(null)
const prepareProgress = ref(0)
const currentStage = ref('')
const profiles = ref([])
const expectedTotal = ref(null)
const simulationConfig = ref(null)
const researchSummary = ref('')
const useCustomRounds = ref(false)
const customMaxRounds = ref(12)

watch(() => props.projectData?.ontology, (value) => {
  registerOntology(value)
}, { immediate: true })

const platformCards = computed(() => {
  const config = simulationConfig.value
  if (!config) return []
  const fromServer = config.platform_configs
  const entries = []
  if (fromServer && typeof fromServer === 'object') {
    for (const key of Object.keys(fromServer)) {
      entries.push({ platform: key, ...fromServer[key] })
    }
  }
  return entries.map((item) => ({
    ...item,
    label: platformLabel(item.platform),
    color: platformColor(item.platform),
    forms: PLATFORM_FORMS[item.platform] || []
  }))
})

const totalTopicsCount = computed(() => {
  return profiles.value.reduce((sum, p) => sum + (p.interested_topics?.length || 0), 0)
})

const addLog = (msg) => {
  emit('add-log', msg)
}

const handlePrepareFailure = (message) => {
  stopAllPolling()
  addLog(t('log.prepareFailedWithError', { error: message || t('common.unknownError') }))
  emit('update-status', 'error')
}

const handleStartSimulation = () => {
  const params = useCustomRounds.value ? { maxRounds: customMaxRounds.value } : {}
  emit('next-step', params)
}

// دمج المؤقتات في مؤقت ذكي موحد لمنع البطء والضغط على الشبكة
let mainSyncTimer = null

const startUnifiedPolling = () => {
  if (mainSyncTimer) return
  mainSyncTimer = setInterval(async () => {
    await pollPrepareStatusAndData()
  }, 4000) // تمديد الفترة الزمنية إلى 4 ثوانٍ لراحة المعالج ومنع التعليق
}

const stopAllPolling = () => {
  if (mainSyncTimer) {
    clearInterval(mainSyncTimer)
    mainSyncTimer = null
  }
}

const startPrepareSimulation = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    emit('update-status', 'error')
    return
  }
  
  phase.value = 1
  addLog(t('log.simInstanceCreated', { id: props.simulationId }))
  addLog(t('log.preparingSimEnv'))
  emit('update-status', 'processing')
  
  try {
    const res = await prepareSimulation({
      simulation_id: props.simulationId,
      use_llm_for_profiles: true,
      parallel_profile_count: 5
    })
    
    if (res.success && res.data) {
      if (res.data.already_prepared) {
        addLog(t('log.detectedExistingPrep'))
        await loadPreparedData()
        return
      }
      
      taskId.value = res.data.task_id
      if (res.data.expected_entities_count) {
        expectedTotal.value = res.data.expected_entities_count
      }
      
      // بدء المزامنة الموحدة السريعة
      startUnifiedPolling()
    } else {
      addLog(t('log.prepareFailed', { error: res.error || t('common.unknownError') }))
      emit('update-status', 'error')
    }
  } catch (err) {
    addLog(t('log.prepareException', { error: err.message }))
    emit('update-status', 'error')
  }
}

const pollPrepareStatusAndData = async () => {
  if (!taskId.value && !props.simulationId) return
  
  try {
    // جلب الحالة والبروفايل دفعة واحدة بكفاءة عالية
    const [statusRes, profilesRes, configRes] = await Promise.all([
      getPrepareStatus({ task_id: taskId.value, simulation_id: props.simulationId }),
      getSimulationProfilesRealtime(props.simulationId),
      getSimulationConfigRealtime(props.simulationId)
    ])

    if (profilesRes.success && profilesRes.data) {
      profiles.value = profilesRes.data.profiles || []
      if (profilesRes.data.total_expected) {
        expectedTotal.value = profilesRes.data.total_expected
      }
    }

    if (statusRes.success && statusRes.data) {
      const data = statusRes.data
      prepareProgress.value = data.progress || 0
      
      if (data.status === 'completed' || data.status === 'ready' || data.already_prepared) {
        addLog(t('log.prepareComplete'))
        stopAllPolling()
        phase.value = 4
        emit('update-status', 'completed')
      } else if (data.status === 'failed') {
        handlePrepareFailure(data.error)
      }
    }

    if (configRes.success && configRes.data?.config_generated) {
      simulationConfig.value = configRes.data.config
      phase.value = 4
      emit('update-status', 'completed')
    }
  } catch (err) {
    console.warn('تحديث بيانات البيئة:', err)
  }
}

const loadPreparedData = async () => {
  phase.value = 4
  emit('update-status', 'completed')
}

const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

onMounted(() => {
  if (props.simulationId) {
    addLog(t('log.step2Init'))
    startPrepareSimulation()
  }
})

onUnmounted(() => {
  stopAllPolling()
})
</script>

<style scoped>
/* التنسيقات العامة للوحة التهيئة السريعة */
.env-setup-panel { height: 100%; display: flex; flex-direction: column; background: #FAFAFA; }
.scroll-container { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 20px; }
.step-card { background: #FFF; border-radius: 8px; padding: 20px; border: 1px solid #EAEAEA; }
.step-card.active { border-color: #FF5722; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.badge.success { background: #E8F5E9; color: #2E7D32; }
.badge.processing { background: #FF5722; color: #FFF; }
.badge.pending { background: #F5F5F5; color: #999; }
.action-btn.primary { background: #000; color: #FFF; padding: 12px 24px; border-radius: 6px; cursor: pointer; border: none; }
.action-btn.secondary { background: #F5F5F5; color: #333; padding: 12px 24px; border-radius: 6px; cursor: pointer; border: none; }
.action-group.dual { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
.system-logs { background: #000; color: #DDD; padding: 16px; font-family: monospace; }
.log-content { height: 80px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
</style>
