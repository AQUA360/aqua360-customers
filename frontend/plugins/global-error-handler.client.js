// plugins/global-error-handler.client.js
// Catches errors that never go through api-manager.js: Vue render/lifecycle
// errors and unhandled promise rejections. Logs full context and shows a
// generic toast so failures are never silent.
import { defineNuxtPlugin } from '#app'
import { useToast } from 'vue-toastification'

export default defineNuxtPlugin(nuxtApp => {
  const toast = useToast()

  nuxtApp.hook('vue:error', (error, instance, info) => {
    logError('Vue error', error, { component: instance?.$options?.name, info })
    toast.error('An unexpected error occurred.')
  })

  nuxtApp.hook('app:error', (error) => {
    logError('App error', error)
    toast.error('An unexpected error occurred.')
  })

  window.addEventListener('unhandledrejection', (event) => {
    logError('Unhandled promise rejection', event.reason)
    toast.error('An unexpected error occurred.')
  })
})
