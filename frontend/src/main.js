import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import i18n from './i18n'

// Capture PWA install prompt globally so components can trigger native install
if (typeof window !== 'undefined') {
  window.__pwaDeferredPrompt = null
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    window.__pwaDeferredPrompt = e
    window.dispatchEvent(new CustomEvent('mirofish-pwa-ready'))
  })
  window.addEventListener('appinstalled', () => {
    window.__pwaDeferredPrompt = null
    window.dispatchEvent(new CustomEvent('mirofish-pwa-installed'))
  })

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch((err) => {
        console.warn('SW registration skipped:', err)
      })
    })
  }
}

const app = createApp(App)

app.use(router)
app.use(i18n)

app.mount('#app')
