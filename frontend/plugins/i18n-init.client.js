export default defineNuxtPlugin((nuxtApp) => {
  const { $i18n } = nuxtApp;
  const config = useRuntimeConfig();
  
  // Check localStorage first, then fall back to defaultLocale from config
  const savedLanguage = localStorage.getItem('preferred_language');
  const validLocales = ['ca', 'es', 'gl', 'en'];
  
  if (savedLanguage && validLocales.includes(savedLanguage)) {
    $i18n.locale.value = savedLanguage;
  } else if (config.public.defaultLocale) {
    $i18n.locale.value = config.public.defaultLocale;
  }
});

