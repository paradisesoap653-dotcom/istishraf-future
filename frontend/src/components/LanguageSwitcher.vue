<template>
  <div class="language-switcher" :class="{ dark: dark }" ref="switcherRef">
    <button class="switcher-trigger" @click="toggleDropdown" type="button">
      <span>🌐 {{ currentLabel }}</span>
      <span class="caret">{{ open ? '▲' : '▼' }}</span>
    </button>
    <ul v-if="open" class="switcher-dropdown">
      <li
        v-for="loc in availableLocales"
        :key="loc.key"
        class="switcher-option"
        :class="{ active: loc.key === locale }"
        @click="switchLocale(loc.key)"
      >
        {{ loc.label }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { availableLocales, applyLocaleDirection } from '@/i18n/index.js'

defineProps({
  dark: {
    type: Boolean,
    default: false
  }
})

const { locale } = useI18n()
const open = ref(false)
const switcherRef = ref(null)

const currentLabel = computed(() => {
  const found = availableLocales.find(l => l.key === locale.value)
  return found ? found.label : locale.value
})

const toggleDropdown = () => {
  open.value = !open.value
}

const switchLocale = (key) => {
  locale.value = key
  localStorage.setItem('locale', key)
  applyLocaleDirection(key)
  open.value = false
}

const onClickOutside = (e) => {
  if (switcherRef.value && !switcherRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  applyLocaleDirection(locale.value)
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
.language-switcher {
  position: relative;
  display: inline-block;
  font-family: inherit;
}

.switcher-trigger,
.language-switcher.dark .switcher-trigger {
  background: var(--bg-subtle, #F1F5F9);
  color: var(--text-primary, #0F172A);
  border: 1px solid var(--border-strong, #CBD5E1);
  padding: 5px 11px;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  border-radius: 6px;
  transition: border-color 0.2s, background 0.2s;
}

.switcher-trigger:hover,
.language-switcher.dark .switcher-trigger:hover {
  border-color: #FF4500;
}

.switcher-trigger:hover {
  border-color: #666;
}

.caret {
  font-size: 0.6rem;
}

.switcher-dropdown {
  position: absolute;
  top: 100%;
  inset-inline-end: 0;
  margin-top: 4px;
  background: #FFFFFF;
  border: 1px solid #DDD;
  border-radius: 4px;
  list-style: none;
  padding: 4px 0;
  min-width: 130px;
  z-index: 1200;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.14);
}

.switcher-option {
  padding: 7px 14px;
  font-size: 0.85rem;
  color: #222;
  cursor: pointer;
  white-space: nowrap;
  text-align: start;
  transition: background 0.15s;
}

.switcher-option:hover {
  background: #F4F4F4;
}

.switcher-option.active {
  color: #FF4500;
  font-weight: 700;
}
</style>
