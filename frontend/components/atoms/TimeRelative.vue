<script setup>
// TimeRelative.vue
import { ref, computed } from 'vue';
import { onMounted } from 'vue';
// import '@github/time-elements/dist/relative-time-element.js';
import '@github/time-elements';
const { t, locale } = useI18n();

const props = defineProps({
    datetime: String,
    class: String
});

onMounted(() => {
    getLanguage();
});

const getLanguage = () => {
  if (process.client) {
    const savedLanguage = localStorage.getItem('preferred_language');
    if (savedLanguage && ['ca', 'es'].includes(savedLanguage)) {
      locale.value = savedLanguage;
    }
  }
}

watch(locale, (newLocale) => {
  getLanguage();
})
</script>
<template>
<ClientOnly>
<relative-time :datetime=props.datetime tense="past" format="relative" class="" :lang="locale">{{ props.datetime }}</relative-time>
</ClientOnly>
</template>



