export default defineNuxtPlugin((nuxtApp) => {
    nuxtApp.vueApp.directive('format-route-code', {
        mounted(el) {
            let value = el.innerText
            let formattedValue = value
            if (value && value.length === 14) {
                formattedValue = `${value.slice(0, 3)}-${value.slice(3, 8)}/${value.slice(8, 10)}/${value.slice(10, 12)}-${value.slice(12)}`;
            }
            el.innerText = formattedValue
      }
    });
  });