import ca from './locales/ca'
import es from './locales/es'
import gl from './locales/gl'
import en from './locales/en'

export default defineI18nConfig(() => ({
    missingWarn: false,
    legacy: false,
    locale: 'ca',
    fallbackLocale: 'ca',
    messages: {
      ca,
      es,
      gl,
      en
    }
  }))