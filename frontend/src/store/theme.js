import { ref } from 'vue'

const getInitialTheme = () => {
  if (typeof window === 'undefined') return 'light'
  const saved = localStorage.getItem('istishraf_theme')
  if (saved === 'dark' || saved === 'light') return saved
  return 'light'
}

export const currentTheme = ref(getInitialTheme())

export const applyTheme = (theme) => {
  const next = theme === 'dark' ? 'dark' : 'light'
  currentTheme.value = next
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', next)
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('istishraf_theme', next)
  }
}

export const toggleTheme = () => {
  applyTheme(currentTheme.value === 'dark' ? 'light' : 'dark')
}

if (typeof document !== 'undefined') {
  applyTheme(currentTheme.value)
}
