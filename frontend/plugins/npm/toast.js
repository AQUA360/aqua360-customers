// plugins/npm/toast.js
import { defineNuxtPlugin } from '#app'
import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'

export default defineNuxtPlugin((nuxtApp) => {
  const options = {
    // Customize your Toast options here
    // position: POSITION.TOP_RIGHT,
    timeout: 5000,
    closeOnClick: true,
    pauseOnFocusLoss: false,
    pauseOnHover: true,
    draggable: true,
    draggablePercent: 0.6,
    showCloseButtonOnHover: false,
    hideProgressBar: false,
    closeButton: 'button',
    icon: true,
    rtl: false,
    // Cap visible toasts; errors are further limited below so a backend outage
    // (many parallel failed requests) does not flood the screen.
    maxToasts: 3,
    newestOnTop: true,
    filterBeforeCreate: (toast, toasts) => {
      if (toast.type === 'error' && toasts.some((t) => t.type === 'error')) {
        return false;
      }
      return toast;
    },
  }

  // Register the Toast plugin
  nuxtApp.vueApp.use(Toast, options)
})
