import { useToast } from 'vue-toastification';
export default defineNuxtPlugin((nuxtApp) => {
    nuxtApp.vueApp.directive('validate-email', {
      mounted(el) {
        el.addEventListener('blur', () => {
            let email = el.value
            if (email && email.length > 0) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
                const isValidEmail = emailRegex.test(email)
                if (!isValidEmail) {
                    el.value = ''
                    const toast = useToast();
                    toast.error('És necessari indicar un email en format example@example.com')
                }
            }
        });
      }
    });
  });