<template>
  <div
    v-if="pullDistance > 8 || refreshing"
    class="ptr-indicator"
    :style="{ transform: `translate(-50%, ${Math.min(pullDistance, 76)}px)` }"
  >
    <span class="ptr-spinner" :class="{ spinning: refreshing || pullDistance >= THRESHOLD }">↻</span>
    <span class="ptr-text">
      {{ refreshing ? 'جاري تحديث الصفحة...' : (pullDistance >= THRESHOLD ? 'أفلت للتحديث الآن' : 'اسحب لأسفل للتحديث') }}
    </span>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const THRESHOLD = 72
const pullDistance = ref(0)
const refreshing = ref(false)

let startY = 0
let startX = 0
let tracking = false

const scrolledAncestor = (el) => {
  for (let node = el; node && node !== document.body; node = node.parentElement) {
    if (node.scrollTop > 2 && /(auto|scroll)/.test(getComputedStyle(node).overflowY)) return true
  }
  return false
}

const isIgnoredTarget = (el) => {
  if (!el || !el.closest) return false
  return Boolean(
    el.closest('.graph-container') ||
    el.closest('textarea') ||
    el.closest('input') ||
    el.closest('.auth-backdrop') ||
    el.closest('.settings-backdrop') ||
    el.closest('.pwa-modal-backdrop')
  )
}

const onTouchStart = (e) => {
  if (refreshing.value) return
  if (window.scrollY > 4) {
    tracking = false
    return
  }
  if (e.touches.length !== 1 || isIgnoredTarget(e.target) || scrolledAncestor(e.target)) {
    tracking = false
    return
  }
  startY = e.touches[0].clientY
  startX = e.touches[0].clientX
  tracking = true
}

const onTouchMove = (e) => {
  if (!tracking || refreshing.value) return
  if (window.scrollY > 4) {
    tracking = false
    pullDistance.value = 0
    return
  }
  if (e.touches.length !== 1 || scrolledAncestor(e.target)) {
    tracking = false
    pullDistance.value = 0
    return
  }
  const deltaY = e.touches[0].clientY - startY
  const deltaX = e.touches[0].clientX - startX
  if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 15) {
    tracking = false
    pullDistance.value = 0
    return
  }
  if (deltaY > 12) {
    pullDistance.value = Math.min(95, (deltaY - 12) * 0.55)
  } else {
    pullDistance.value = 0
  }
}

const onTouchEnd = () => {
  if (!tracking || refreshing.value) return
  tracking = false
  if (pullDistance.value >= THRESHOLD) {
    refreshing.value = true
    pullDistance.value = 58
    setTimeout(() => {
      window.location.reload()
    }, 220)
  } else {
    pullDistance.value = 0
  }
}

const onTouchCancel = () => {
  tracking = false
  pullDistance.value = 0
}

onMounted(() => {
  window.addEventListener('touchcancel', onTouchCancel, { passive: true })
  window.addEventListener('touchstart', onTouchStart, { passive: true })
  window.addEventListener('touchmove', onTouchMove, { passive: true })
  window.addEventListener('touchend', onTouchEnd, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('touchcancel', onTouchCancel)
  window.removeEventListener('touchstart', onTouchStart)
  window.removeEventListener('touchmove', onTouchMove)
  window.removeEventListener('touchend', onTouchEnd)
})
</script>

<style scoped>
.ptr-indicator {
  position: fixed;
  top: -46px;
  left: 50%;
  z-index: 9999;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 999px;
  background: var(--bg-card, #FFFFFF);
  color: var(--text-primary, #0F172A);
  border: 1.5px solid var(--accent-orange, #FF4500);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  font-size: 0.85rem;
  font-weight: 800;
  pointer-events: none;
  transition: transform 0.12s ease-out;
}

.ptr-spinner {
  display: inline-block;
  color: var(--accent-orange, #FF4500);
  font-size: 1.05rem;
  font-weight: 800;
}

.ptr-spinner.spinning {
  animation: ptr-spin 0.7s linear infinite;
}

@keyframes ptr-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
