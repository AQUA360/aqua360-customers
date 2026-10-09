<script setup>
import { useI18n } from 'vue-i18n';
import { ref } from 'vue';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const { t, locale } = useI18n();
const showLanguages = ref(false);

const switchLanguage = (newLocale) => {
  locale.value = newLocale;
  localStorage.setItem('preferred_language', newLocale);
  showLanguages.value = false;
};

const toggleLanguages = () => {
  showLanguages.value = !showLanguages.value;
};

const languages = AVAILABLE_LANGUAGES;

</script>

<template>
  <div class="relative">
    <!-- Gear button -->
    <button @click="toggleLanguages"
      class="p-2 bg-white rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2"
      :title="t('common.language')">
      <!-- <Icon name="fa6-solid:language" class="w-5 h-5 text-gray-600" /> -->
      <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z">
        </path>
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z">
        </path>
      </svg>
      <span class="text-sm font-medium text-gray-700 uppercase">{{ locale }}</span>
      <svg class="w-4 h-4 text-gray-400 transition-transform" :class="{ 'rotate-180': showLanguages }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
      </svg>
    </button>

    <!-- Language buttons (shown when gear is clicked) -->
    <div v-if="showLanguages"
      class="absolute top-full right-0 mt-2 bg-white rounded-lg shadow-lg border p-2 flex flex-col space-y-1 z-10">
      <button v-for="lang in languages" :key="lang.code" @click="switchLanguage(lang.code)" :class="[
        'px-3 py-2 rounded text-sm font-medium transition-colors text-left w-full',
        locale === lang.code
          ? 'bg-sky-500 text-white'
          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
      ]">
        {{ t(lang.name) }}
      </button>
    </div>
  </div>
</template>