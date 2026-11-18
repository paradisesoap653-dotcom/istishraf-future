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
            <span class="badge success">{{ $t('common.completed') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">{{ $t('step2.simInstanceDesc') }}</p>

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
          <p class="description">{{ $t('step2.generateAgentPersonaDesc') }}</p>

          <div v-if="profiles.length > 0" class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ profiles.length }}</span>
              <span class="stat-label">{{ $t('step2.currentAgentCount') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ expectedTotal || '-' }}</span>
              <span class="stat-label">{{ $t('step2.expectedAgentTotal') }}</span>
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
      </div>

      <!-- Step 05: 准备完成 -->
      <div class="step-card" :class="{ 'active': phase >= 4 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">05</span>
            <span class="step-title">{{ $t('step2.setupComplete') }}</span>
          </div>
          <div class="step-status">
            <span v-if="isReady" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else class="badge processing">{{ $t('step1.inProgress') }}</span>
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
            
            <!-- زر المحاكاة مفعل دائماً بمجرد الاستجابة أو اكتمال البيانات -->
            <button 
              class="action-btn primary"
              :disabled="!isReady && phase < 1"
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
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
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

const phase = ref(1)
const taskId = ref(null)
const prepareProgress = ref(0)
const profiles = ref([])
const expectedTotal = ref(null)
const isReady = ref(false)

let pollTimer = null

const addLog = (msg) => {
  emit('add-log', msg)
}

const handleStartSimulation = () => {
  emit('next-step', {})
}

const startPrepareSimulation = async () => {
  if (!props.simulationId) return
  
  addLog(t('log.preparingSimEnv'))
  emit('update-status', 'processing')
  
  try {
    const res = await prepareSimulation({
      simulation_id: props.simulationId,
      use_llm_for_profiles: true,
      parallel_profile_count: 5
    })
    
    if (res.success && res.data) {
      taskId.value = res.data.task_id
      if (res.data.already_prepared) {
        phase.value = 4
        isReady.value = true
        emit('update-status', 'completed')
        return
      }
      startPolling()
    }
  } catch (err) {
    addLog('تنبيه أثناء تهيئة البيئة: ' + err.message)
  }
}

const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  
  // الاستعلام كل ثانيتين لتحديث نسبة التقدم والمراحل بسرعة
  pollTimer = setInterval(async () => {
    try {
      const res = await getPrepareStatus({
        task_id: taskId.value,
        simulation_id: props.simulationId
      })
      
      if (res.success && res.data) {
        const data = res.data
        prepareProgress.value = data.progress || 0
        
        // تحديث الفازات بناءً على النسبة
        if (prepareProgress.value > 25 && prepareProgress.value <= 50) phase.value = 2
        else if (prepareProgress.value > 50 && prepareProgress.value <= 75) phase.value = 3
        else if (prepareProgress.value > 75 || data.status === 'completed' || data.status === 'ready') {
          phase.value = 4
          isReady.value = true
          emit('update-status', 'completed')
          clearInterval(pollTimer)
        }
      }
      
      // جلب البروفايلات في الخلفية
      const profRes = await getSimulationProfilesRealtime(props.simulationId)
      if (profRes.success && profRes.data) {
        profiles.value = profRes.data.profiles || []
      }
    } catch (e) {
      console.warn(e)
    }
  }, 2000)
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
  startPrepareSimulation()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.env-setup-panel { height: 100%; display: flex; flex-direction: column; background: #FAFAFA; }
.scroll-container { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 20px; }
.step-card { background: #FFF; border-radius: 8px; padding: 20px; border: 1px solid #EAEAEA; }
.step-card.active { border-color: #FF5722; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.badge.success { background: #E8F5E9; color: #2E7D32; }
.badge.processing { background: #FF5722; color: #FFF; }
.badge.pending { background: #F5F5F5; color: #999; }
.action-btn.primary { background: #000; color: #FFF; padding: 12px 24px; border-radius: 6px; cursor: pointer; border: none; }
.action-btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }
.action-btn.secondary { background: #F5F5F5; color: #333; padding: 12px 24px; border-radius: 6px; cursor: pointer; border: none; }
.action-group.dual { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
.system-logs { background: #000; color: #DDD; padding: 16px; font-family: monospace; }
.log-content { height: 80px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
</style>
