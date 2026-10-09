export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.directive('click-outside', {
    mounted(el, binding) {
      el.clickOutsideEvent = (event) => {
        // Check if the click is outside the element and its children
        if (!(el === event.target || el.contains(event.target))) {
          binding.value(event); // Call the provided callback
        }
      };
      document.addEventListener('click', el.clickOutsideEvent);
    },
    unmounted(el) {
      // Cleanup the event listener when the element is removed
      document.removeEventListener('click', el.clickOutsideEvent);
    },
  });
});