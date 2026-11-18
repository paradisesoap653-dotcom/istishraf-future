
<template>
  <div class="report-container">
    <!-- رأس التقرير وأزرار الإجراءات (تحميل + السيناريو المقارن) -->
    <div class="report-header-actions">
      <div class="report-id-badge">ID: report_2e391d727313</div>
      
      <div class="buttons-group">
        <!-- زر السيناريو المقارن الاستثنائي -->
        <button class="action-btn compare-btn" @click="$emit('open-scenario-compare')">
          ⚡ سيناريو مقارن (استثنائي)
        </button>
        
        <button class="action-btn download-btn">
          📥 تحميل التقرير
        </button>
      </div>
    </div>

    <!-- شريط منصات التواصل مع دعم السحب الأفقي الكامل للهواتف -->
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

    <!-- محتوى التقرير الأساسي -->
    <div class="report-content-body">
      <h2>تقرير توقعات مستقبلية: انتشار منصة التجارة الإلكترونية عبر جميع طبقات المجتمع</h2>
      <p class="report-desc">
        تظهر المحاكاة أن استراتيجية الإعلان المتكاملة التي تجمع بين التسويق عبر المؤثرين، والجوائز القابلة للتبادل، والتكامل مع الموردين، أدت إلى انتشار واسع للمنصة وتبنيها من قبل التجار، الموردين، المعلنين، والعملاء، مع ظهور تأثيرات شبكة قوية وتحديات تنظيمية.
      </p>
    </div>
  </div>
</template>

<script setup>
defineEmits(['open-scenario-compare'])
</script>

<style scoped>
.report-container {
  padding: 16px;
  background: #FFF;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.report-header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.report-id-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #64748B;
  background: #F1F5F9;
  padding: 4px 8px;
  border-radius: 4px;
}

.buttons-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* تنسيق زر السيناريو المقارن الاستثنائي */
.action-btn.compare-btn {
  background: #FF5722 !important;
  color: #FFF !important;
  font-weight: 600;
  font-size: 13px;
  padding: 10px 16px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: opacity 0.2s;
}

.action-btn.compare-btn:hover {
  opacity: 0.85;
}

.action-btn.download-btn {
  background: #F97316;
  color: #FFF;
  font-weight: 600;
  font-size: 13px;
  padding: 10px 16px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
}

/* شريط منصات التواصل مع دعم السحب الأفقي الكامل للهواتف */
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
  flex: 0 0 auto !important;
  min-width: 130px !important;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
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
}

.platform-stats {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #64748B;
}

.report-content-body h2 {
  font-size: 18px;
  color: #0F172A;
  margin-bottom: 12px;
  line-height: 1.4;
}

.report-desc {
  font-size: 14px;
  color: #334155;
  line-height: 1.7;
  margin: 0;
  text-align: justify;
}
</style>
