<template>
  <button
    type="button"
    class="theme-toggle-btn"
    :title="currentTheme === 'dark' ? 'التبديل للوضع النهاري' : 'التبديل لوضع القراءة الليلية'"
    @click="toggleTheme"
  >
    <span class="theme-icon">{{ currentTheme === 'dark' ? '☀️' : '🌙' }}</span>
    <span class="theme-label">{{ currentTheme === 'dark' ? 'نهاري' : 'ليلي' }}</span>
  </button>
</template>

<script setup>
import { currentTheme, toggleTheme } from '../store/theme'
</script>

<style scoped>
.theme-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--border-strong, #CBD5E1);
  background: var(--bg-subtle, #F1F5F9);
  color: var(--text-primary, #0F172A);
  transition: all 0.2s ease;
}

.theme-toggle-btn:hover {
  border-color: #FF4500;
}

.theme-icon {
  font-size: 0.9rem;
  line-height: 1;
}
</style>
