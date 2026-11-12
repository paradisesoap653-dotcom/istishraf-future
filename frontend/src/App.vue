<template>
  <router-view />
</template>

<script setup>
import './store/theme'
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
html[data-theme="dark"] .step-label {
  color: var(--text-primary) !important;
}

html[data-theme="dark"] .panel-wrapper,
html[data-theme="dark"] .project-card,
html[data-theme="dark"] .auth-card,
html[data-theme="dark"] .api-modal-card,
html[data-theme="dark"] .pwa-modal-card {
  background-color: var(--bg-card) !important;
  border-color: var(--border-frame) !important;
  color: var(--text-primary) !important;
}

html[data-theme="dark"] .card-title,
html[data-theme="dark"] .auth-title,
html[data-theme="dark"] .modal-title {
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

/* Responsive headers & split views on mobile screens */
@media (max-width: 900px) {
  .app-header {
    height: auto !important;
    min-height: 56px;
    flex-wrap: wrap;
    padding: 8px 14px !important;
    gap: 8px;
  }

  .header-right {
    flex-wrap: wrap;
    gap: 8px !important;
  }

  .content-area {
    flex-direction: column !important;
    height: auto !important;
    min-height: calc(100vh - 64px);
    overflow-y: auto !important;
  }

  .panel-wrapper.left,
  .panel-wrapper.right {
    width: 100% !important;
    min-height: 440px;
    opacity: 1 !important;
    transform: none !important;
  }
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
