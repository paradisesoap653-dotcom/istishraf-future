<template>
  <button type="button" class="nav-back-btn" title="الرجوع للصفحة السابقة" @click="goBack">
    <span class="back-arrow">↩</span>
    <span>رجوع</span>
  </button>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const goBack = () => {
  if (window.history.state && window.history.state.back) {
    router.back()
  } else {
    router.push('/')
  }
}
</script>

<style scoped>
.nav-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  border-radius: 6px;
  border: 1.5px solid var(--border-strong, #94A3B8);
  background: var(--bg-subtle, #F1F5F9);
  color: var(--text-primary, #0F172A);
  font-size: 0.82rem;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-back-btn:hover {
  border-color: var(--accent-orange, #FF4500);
  color: var(--accent-orange, #FF4500);
}

.back-arrow {
  font-size: 0.95rem;
  line-height: 1;
}
</style>
