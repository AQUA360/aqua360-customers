import { defineNuxtPlugin } from '#app';
import { defineComponent, h, unref } from 'vue';
import VueDatePicker from '@vuepic/vue-datepicker'
import '@vuepic/vue-datepicker/dist/main.css'

// Aquí no se li passava mai res, i la llibreria té tots els textos en anglès per
// defecte: `locale` val 'en-Us' (mesos i dies) i els botons són cadenes a part
// (`selectText` = 'Select', `cancelText` = 'Cancel'), que el locale NO tradueix.
// L'embolcall els omple amb l'idioma actiu d'i18n -- el mateix que ja fa a mà
// components/atoms/DatePicker.vue -- i es refà quan l'usuari canvia d'idioma.
// Qui necessiti valors diferents els pot continuar passant per prop: com que
// `attrs` s'escampa després, sobreescriu aquests valors per defecte.
export default defineNuxtPlugin((nuxtApp) => {
  const LocalizedDatepicker = defineComponent({
    name: 'Datepicker',
    inheritAttrs: false,
    setup(_props, { attrs, slots }) {
      return () => {
        // Es llegeix dins del render perquè no depengui de l'ordre de càrrega dels
        // plugins i perquè el canvi d'idioma torni a pintar el calendari.
        const i18n = nuxtApp.$i18n;
        const locale = unref(i18n?.locale);
        const defaults = {};
        if (locale) defaults.locale = locale;
        if (i18n?.t) {
          defaults.selectText = i18n.t('common.select');
          defaults.cancelText = i18n.t('common.cancel');
        }
        return h(VueDatePicker, { ...defaults, ...attrs }, slots);
      };
    },
  });

  nuxtApp.vueApp.component('Datepicker', LocalizedDatepicker);
});
