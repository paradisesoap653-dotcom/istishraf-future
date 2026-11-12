<template>
  <PullToRefresh />
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import './store/theme'
import { authState } from './store/auth'
import PullToRefresh from './components/PullToRefresh.vue'

const router = useRouter()
const route = useRoute()

onMounted(() => {
  window.__istishrafHandleBack = () => {
    if (authState.modalOpen) {
      authState.modalOpen = false
      return 'handled'
    }
    if (route.path && route.path !== '/') {
      if (window.history.state && window.history.state.back) {
        router.back()
      } else {
        router.push('/')
      }
      return 'handled'
    }
    return 'exit'
  }
})
</script>

<style>
:root,
html[data-theme="light"] {
  --bg-page: #F6F8FB;
  --bg-card: #FFFFFF;
  --bg-subtle: #F1F5F9;
  --bg-elevated: #F8FAFC;
  --text-primary: #0F172A;
  --text-secondary: #475569;
  --text-muted: #64748B;
  --border-frame: #CBD5E1;
  --border-strong: #94A3B8;
  --accent-orange: #FF4500;
  --card-shadow: 0 4px 18px rgba(15, 23, 42, 0.05);
}

html[data-theme="dark"] {
  --bg-page: #0B0F17;
  --bg-card: #131924;
  --bg-subtle: #1B2434;
  --bg-elevated: #172030;
  --text-primary: #F1F5F9;
  --text-secondary: #CBD5E1;
  --text-muted: #94A3B8;
  --border-frame: #2A364B;
  --border-strong: #3B4B66;
  --accent-orange: #FF5722;
  --card-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);
}

/* Global reset */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  max-width: 100%;
  overflow-x: hidden;
  overscroll-behavior-y: contain;
  -webkit-tap-highlight-color: transparent;
  background-color: var(--bg-page);
  color: var(--text-primary);
  transition: background-color 0.25s ease, color 0.25s ease;
}

#app {
  font-family: 'Fustat', 'IBM Plex Sans Arabic', 'Inter', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--text-primary);
  background-color: var(--bg-page);
  min-height: 100vh;
}

/* خط الفسطاط الرسمي (Fustat & Fustat-EB) لكامل الواجهة العربية */
html[dir="rtl"] #app,
html[dir="rtl"] body,
html[dir="rtl"] .home-container,
html[dir="rtl"] .main-view,
html[dir="rtl"] button,
html[dir="rtl"] input,
html[dir="rtl"] textarea,
html[dir="rtl"] select {
  font-family: 'Fustat', 'IBM Plex Sans Arabic', sans-serif !important;
}

html[dir="rtl"] h1,
html[dir="rtl"] h2,
html[dir="rtl"] h3,
html[dir="rtl"] h4,
html[dir="rtl"] .nav-brand,
html[dir="rtl"] .brand,
html[dir="rtl"] .main-title,
html[dir="rtl"] .section-title,
html[dir="rtl"] .step-title,
html[dir="rtl"] .metric-value,
html[dir="rtl"] .card-title {
  font-family: 'Fustat', sans-serif !important;
  font-weight: 800 !important;
  letter-spacing: 0 !important;
}

html[dir="rtl"] p,
html[dir="rtl"] span,
html[dir="rtl"] button,
html[dir="rtl"] input,
html[dir="rtl"] textarea,
html[dir="rtl"] div {
  letter-spacing: 0 !important;
}

html[dir="rtl"] .pwa-url-display {
  font-family: 'JetBrains Mono', monospace !important;
  letter-spacing: 0.5px !important;
}

html[dir="rtl"] .btn-arrow {
  display: inline-block;
  transform: scaleX(-1);
}

.header-left {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

/* نظام القراءة الليلية الشامل للصفحات الداخلية والبطاقات والنوافذ المنبثقة */
html[data-theme="dark"] .main-view,
html[data-theme="dark"] .process-container,
html[data-theme="dark"] .history-database {
  background-color: var(--bg-page) !important;
  color: var(--text-primary) !important;
}

html[data-theme="dark"] .app-header {
  background-color: var(--bg-card) !important;
  border-bottom-color: var(--border-frame) !important;
  color: var(--text-primary) !important;
}

html[data-theme="dark"] .brand,
html[data-theme="dark"] .status-indicator,
html[data-theme="dark"] .step-label,
html[data-theme="dark"] .step-name {
  color: var(--text-primary) !important;
}

html[data-theme="dark"] .panel-wrapper,
html[data-theme="dark"] .project-card,
html[data-theme="dark"] .auth-card,
html[data-theme="dark"] .api-modal-card,
html[data-theme="dark"] .pwa-modal-card,
html[data-theme="dark"] .graph-panel,
html[data-theme="dark"] .graph-legend {
  background-color: var(--bg-card) !important;
  border-color: var(--border-frame) !important;
  color: var(--text-primary) !important;
}

html[data-theme="dark"] .card-title,
html[data-theme="dark"] .auth-title,
html[data-theme="dark"] .modal-title,
html[data-theme="dark"] .panel-title {
  color: var(--text-primary) !important;
}

html[data-theme="dark"] .card-desc,
html[data-theme="dark"] .auth-subtitle {
  color: var(--text-secondary) !important;
}

html[data-theme="dark"] .card-files-wrapper,
html[data-theme="dark"] input,
html[data-theme="dark"] textarea,
html[data-theme="dark"] select {
  background-color: var(--bg-subtle) !important;
  color: var(--text-primary) !important;
  border-color: var(--border-frame) !important;
}

html[data-theme="dark"] .auth-trigger-btn,
html[data-theme="dark"] .auth-trigger-btn.dark {
  background-color: #FF5722 !important;
  border-color: #FF5722 !important;
  color: #FFFFFF !important;
}

/* تنسيق متجاوب كامل لشاشات الهاتف لمنع أي تداخل في الرأس أو اللوحات */
@media (max-width: 900px) {
  .main-view {
    height: auto !important;
    min-height: 100vh !important;
    overflow-y: visible !important;
  }

  .app-header {
    height: auto !important;
    min-height: 58px;
    flex-wrap: wrap;
    justify-content: space-between;
    padding: 10px 12px !important;
    gap: 10px;
    position: relative !important;
  }

  .header-left {
    order: 1;
  }

  .header-right {
    order: 2;
    flex-wrap: wrap;
    justify-content: center;
    width: 100%;
    gap: 6px !important;
  }

  .header-center {
    position: static !important;
    left: auto !important;
    transform: none !important;
    order: 3;
    width: 100%;
    display: flex;
    justify-content: center;
    padding-top: 4px;
    border-top: 1px solid var(--border-frame);
  }

  .step-divider {
    display: none !important;
  }

  .content-area {
    flex-direction: column !important;
    height: auto !important;
    min-height: calc(100vh - 120px);
    overflow-y: visible !important;
    padding: 8px;
    gap: 12px;
  }

  .panel-wrapper.left,
  .panel-wrapper.right {
    width: 100% !important;
    opacity: 1 !important;
    transform: none !important;
    border: 1.5px solid var(--border-frame) !important;
    border-radius: 12px;
    overflow: hidden;
  }

  .panel-wrapper.mobile-hidden { display: none !important; }
  .panel-wrapper.left { height: 480px !important; flex: none; }
  .panel-wrapper.right { height: auto !important; min-height: 440px; }
  .panel-wrapper.right > * { height: auto !important; min-height: 440px; }
  .panel-wrapper.right .scroll-container { overflow: visible !important; }
  .graph-legend { max-width: calc(100% - 24px); max-height: 115px; overflow: auto; bottom: 12px !important; left: 12px !important; }
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--bg-subtle);
}

::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 4px;
}

button {
  font-family: inherit;
}
</style>
