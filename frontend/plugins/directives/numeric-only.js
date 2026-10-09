export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.directive('numeric-only', {
    mounted(el, binding) {
      const allowSigned = !!binding.modifiers.signed;
      let isUpdating = false;
      el.addEventListener('input', () => {
        if (isUpdating) return;
        isUpdating = true;
        const hasLeadingMinus = allowSigned && el.value.trim().startsWith('-');
        let value = el.value.replace(/[^\d.]/g, '').replace(/(\..*?)\..*/g, '$1');
        if (hasLeadingMinus) value = `-${value}`;
        el.value = value;
        // Manually trigger an input event to update v-model
        el.dispatchEvent(new Event('input'));
        isUpdating = false;
      });
    }
  });
});