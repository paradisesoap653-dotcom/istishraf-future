<template>
  <div class="interaction-container">
    <!-- شريط منصات التواصل مع دعم السحب الأفقي السلس -->
    <div class="platforms-scroll-container">
      <div 
        v-for="platform in platformsList" 
        :key="platform.id" 
        class="platform-card-item"
      >
        <span class="platform-dot" :style="{ background: platform.color }"></span>
        <span class="platform-name">{{ platform.label }}</span>
        <span class="platform-stats">الجولة {{ platform.currentRound }}/{{ platform.totalRounds }}</span>
      </div>
    </div>

    <!-- أزرار التحكم والتفاعل وتوليد التقرير -->
    <div class="action-panel">
      <button 
        class="action-btn primary generate-report-btn"
        @click="handleGenerateReport"
      >
        توليد التقرير ➔
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['generate-report', 'next-step'])

// قائمة المنصات الافتراضية لضمان ظهور السحب الأفقي
const platformsList = ref([
  { id: 'facebook', label: 'فيسبوك', color: '#1877F2', currentRound: 5, totalRounds: 5 },
  { id: 'reddit', label: 'ريديت', color: '#FF4500', currentRound: 5, totalRounds: 5 },
  { id: 'twitter', label: 'تويتر (إكس)', color: '#1DA1F2', currentRound: 5, totalRounds: 5 },
  { id: 'tiktok', label: 'تيك توك', color: '#000000', currentRound: 5, totalRounds: 5 },
  { id: 'whatsapp', label: 'واتساب', color: '#25D366', currentRound: 5, totalRounds: 5 }
])

const handleGenerateReport = () => {
  // تفعيل حدث توليد التقرير والانتقال بسلاسة دون تعليق
  emit('generate-report')
}
</script>

<style scoped>
.interaction-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: #FAFAFA;
}

/* إصلاح شريط منصات التواصل ليدعم السحب الأفقي بسلاسة تامة */
.platforms-scroll-container {
  display: flex;
  overflow-x: auto;
  gap: 12px;
  padding-bottom: 8px;
  width: 100%;
  -webkit-overflow-scrolling: touch;
  scroll-behavior: smooth;
}

.platforms-scroll-container::-webkit-scrollbar {
  height: 6px;
}

.platforms-scroll-container::-webkit-scrollbar-thumb {
  background: #CBD5E1;
  border-radius: 3px;
}

.platform-card-item {
  flex: 0 0 auto;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 12px 16px;
  min-width: 140px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}

.platform-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-bottom: 4px;
}

.platform-name {
  font-size: 13px;
  font-weight: 600;
  color: #1E293B;
}

.platform-stats {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #64748B;
}

/* تفعيل زر توليد التقرير وضمان استجابته للضغط الفوري */
.action-panel {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.action-btn.primary, button.generate-report-btn {
  background: #000 !important;
  color: #FFF !important;
  font-size: 14px;
  font-weight: 600;
  padding: 14px 24px;
  border-radius: 8px;
  border: none;
  cursor: pointer !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  width: 100%;
  text-align: center;
  transition: opacity 0.2s ease;
}

.action-btn.primary:hover, button.generate-report-btn:hover {
  opacity: 0.85 !important;
}
</style>
