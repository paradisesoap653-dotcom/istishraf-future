<template>
  <div class="simulation-interaction-container" style="padding: 20px; background: #fff;">
    <div style="margin-bottom: 20px; color: #333; font-weight: bold;">
      اكتملت الجولات بنجاح. يمكنك الانتقال للتقرير الآن.
    </div>
    
    <!-- زر توليد التقرير المرتبط مباشرة بحدث الانتقال -->
    <button 
      @click="forceNextStep"
      style="width: 100%; background: #000; color: #fff; padding: 16px; border-radius: 8px; font-size: 16px; font-weight: bold; border: none; cursor: pointer;"
    >
      توليد التقرير ➔
    </button>
  </div>
</template>

<script setup>
import { defineEmits } from 'vue'

const emit = defineEmits(['generate-report', 'next-step', 'update-status'])

const forceNextStep = () => {
  // إطلاق كافة الأحداث المحتملة لضمان انتقال التطبيق للخطوة التالية فوراً
  emit('generate-report')
  emit('next-step')
  emit('update-status', 'completed')
}
</script>
