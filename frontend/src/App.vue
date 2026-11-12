<template>
  <router-view />
</template>

<script setup>
// Vue Router manages all views
</script>

<style>
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
}

#app {
  font-family: 'Space Grotesk', 'JetBrains Mono', 'Noto Sans SC', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #000000;
  background-color: #ffffff;
}

/* Native Arabic Typography & RTL Fixes */
html[dir="rtl"] #app,
html[dir="rtl"] body,
html[dir="rtl"] .home-container,
html[dir="rtl"] .main-view {
  font-family: 'IBM Plex Sans Arabic', 'Tajawal', 'Space Grotesk', sans-serif !important;
}

html[dir="rtl"] h1,
html[dir="rtl"] h2,
html[dir="rtl"] h3,
html[dir="rtl"] h4,
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

html[dir="rtl"] .nav-brand,
html[dir="rtl"] .brand {
  font-family: 'Tajawal', 'IBM Plex Sans Arabic', sans-serif !important;
  font-weight: 800 !important;
  letter-spacing: 0 !important;
}

html[dir="rtl"] .hero-left {
  padding-right: 0 !important;
  padding-left: 48px !important;
}

html[dir="rtl"] .btn-arrow {
  display: inline-block;
  transform: scaleX(-1);
}

/* Responsive headers & split views on mobile screens */
@media (max-width: 900px) {
  html[dir="rtl"] .hero-left {
    padding-left: 0 !important;
  }

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
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #000000;
}

::-webkit-scrollbar-thumb:hover {
  background: #333333;
}

button {
  font-family: inherit;
}
</style>
