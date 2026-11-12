import { createI18n } from 'vue-i18n'
import languages from '../../../locales/languages.json'

const localeFiles = import.meta.glob('../../../locales/!(languages).json', { eager: true })

const messages = {}
const rawLocales = {}

for (const path in localeFiles) {
  const key = path.match(/\/([^/]+)\.json$/)[1]
  if (languages[key]) {
    messages[key] = localeFiles[path].default
    rawLocales[key] = { key, label: languages[key].label }
  }
}

// Preserve order from languages.json (Arabic first)
const availableLocales = Object.keys(languages)
  .filter((k) => rawLocales[k])
  .map((k) => rawLocales[k])

export function applyLocaleDirection(key) {
  if (typeof document !== 'undefined') {
    document.documentElement.lang = key
    document.documentElement.dir = key === 'ar' ? 'rtl' : 'ltr'
    const titleMsg = messages[key]?.meta?.title
    if (titleMsg) {
      document.title = titleMsg
    }
  }
}

const savedLocale = (typeof localStorage !== 'undefined' && localStorage.getItem('locale')) || 'ar'
const initialLocale = messages[savedLocale] ? savedLocale : 'ar'
applyLocaleDirection(initialLocale)

const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'ar',
  messages
})

export { availableLocales }
export default i18n
