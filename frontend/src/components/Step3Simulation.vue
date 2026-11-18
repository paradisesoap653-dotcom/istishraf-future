<template>
  <div class="simulation-interaction-container">
    <!-- حاوية منصات التواصل المستقلة مع السحب الأفقي -->
    <div class="platforms-scroll-wrapper">
      <div class="platforms-scroll-container">
        <div class="platform-card-item">
          <span class="platform-dot" style="background: #1877F2;"></span>
          <span class="platform-name">فيسبوك</span>
          <span class="platform-stats">الجولة 5/5</span>
        </div>
        <div class="platform-card-item">
          <span class="platform-dot" style="background: #FF4500;"></span>
          <span class="platform-name">ريديت</span>
          <span class="platform-stats">الجولة 5/5</span>
        </div>
        <div class="platform-card-item">
          <span class="platform-dot" style="background: #1DA1F2;"></span>
          <span class="platform-name">تويتر (إكس)</span>
          <span class="platform-stats">الجولة 5/5</span>
        </div>
        <div class="platform-card-item">
          <span class="platform-dot" style="background: #000000;"></span>
          <span class="platform-name">تيك توك</span>
          <span class="platform-stats">الجولة 5/5</span>
        </div>
        <div class="platform-card-item">
          <span class="platform-dot" style="background: #25D366;"></span>
          <span class="platform-name">واتساب</span>
          <span class="platform-stats">الجولة 5/5</span>
        </div>
      </div>
    </div>

    <!-- حاوية زر التقرير ومنطقة الإجراءات منفصلة تماماً -->
    <div class="action-panel-section">
      <div class="completion-notice">
        اكتملت الجولات بنجاح. يمكنك الانتقال للتقرير الآن.
      </div>
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
import { defineEmits } from 'vue'

const emit = defineEmits(['generate-report', 'next-step', 'update-status'])

const handleGenerateReport = () => {
  emit('generate-report')
  emit('next-step')
  emit('update-status', 'completed')
}
</script>

<style scoped>
.simulation-interaction-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: #FAFAFA;
  width: 100%;
  box-sizing: border-box;
}

/* فصل حاوية المنصات لتعمل بسلاسة دون تداخل */
.platforms-scroll-wrapper {
  width: 100%;
  overflow: hidden;
}

.platforms-scroll-container {
  display: flex !important;
  overflow-x: auto !important;
  flex-wrap: nowrap !important;
  gap: 12px !important;
  padding-bottom: 8px !important;
  width: 100% !important;
  -webkit-overflow-scrolling: touch !important;
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
  flex: 0 0 130px !important;
  min-width: 130px !important;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  box-sizing: border-box;
}

.platform-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-bottom: 2px;
}

.platform-name {
  font-size: 13px;
  font-weight: 600;
  color: #1E293B;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.platform-stats {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #64748B;
}

/* فصل منطقة الأزرار وتأمين عملها بمعزل عن المنصات */
.action-panel-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  box-sizing: border-box;
}

.completion-notice {
  font-size: 13px;
  color: #047857;
  background: #ECFDF5;
  padding: 10px 14px;
  border-radius: 6px;
  text-align: center;
  font-weight: 500;
  border: 1px solid #A7F3D0;
  width: 100%;
  box-sizing: border-box;
}

.action-btn.primary, button.generate-report-btn {
  background: #000 !important;
  color: #FFF !important;
  font-size: 15px;
  font-weight: 600;
  padding: 16px 24px;
  border-radius: 8px;
  border: none;
  cursor: pointer !important;
  opacity: 1 !important;
  pointer-events: auto !important;
  width: 100%;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  box-sizing: border-box;
}

.action-btn.primary:hover, button.generate-report-btn:hover {
  opacity: 0.85 !important;
}
</style>
