export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.directive('no-dash', {
    mounted(el) {
      let isUpdating = false;
      el.addEventListener('input', () => {
        if (isUpdating) return;
        isUpdating = true;
        el.value = el.value.replace('-', '');
        // Manually trigger an input event to update v-model
        el.dispatchEvent(new Event('input'));
        isUpdating = false;
      });
    }
  });
});