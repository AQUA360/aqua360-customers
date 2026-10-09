<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const { t } = useI18n();

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  label: {
    type: String,
    default: null,
  },
  multiline: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['update:modelValue']);

const usedLanguages = computed(() => props.modelValue.map((row) => row.language));

const availableLanguagesFor = (row) => AVAILABLE_LANGUAGES.filter(
  (lang) => lang.code === row.language || !usedLanguages.value.includes(lang.code)
);

const canAddTranslation = computed(() => props.modelValue.length < AVAILABLE_LANGUAGES.length);

const addTranslation = () => {
  const nextLanguage = AVAILABLE_LANGUAGES.find((lang) => !usedLanguages.value.includes(lang.code));
  if (!nextLanguage) return;
  emit('update:modelValue', [...props.modelValue, { language: nextLanguage.code, name: '' }]);
};

const updateRow = (index, changes) => {
  const rows = props.modelValue.map((row, i) => (i === index ? { ...row, ...changes } : row));
  emit('update:modelValue', rows);
};

const removeRow = (index) => {
  emit('update:modelValue', props.modelValue.filter((_, i) => i !== index));
};
</script>

<template>
  <div class="mb-4">
    <label class="block text-sm font-medium text-slate-500 mb-2">{{ label || t('common.translations') }}</label>

    <div v-for="(row, index) in modelValue" :key="index"
      class="grid gap-2 mb-2" :class="multiline ? 'grid-cols-[9rem_1fr_1.5rem] items-start' : 'grid-cols-[9rem_1fr_1.5rem] items-center'">
      <select class="input" :value="row.language" @change="updateRow(index, { language: $event.target.value })">
        <option v-for="lang in availableLanguagesFor(row)" :key="lang.code" :value="lang.code">
          {{ t(lang.name) }}
        </option>
      </select>
      <textarea v-if="multiline" rows="4" class="input" :value="row.name"
        @input="updateRow(index, { name: $event.target.value })"></textarea>
      <input v-else type="text" class="input" :value="row.name"
        @input="updateRow(index, { name: $event.target.value })" />
      <button type="button" class="text-slate-400 hover:text-red-500 px-1" :title="t('common.delete')"
        @click="removeRow(index)">
        <Icon name="fa6-solid:xmark" />
      </button>
    </div>

    <button v-if="canAddTranslation" type="button"
      class="flex items-center gap-1 text-sm text-sky-600 hover:text-sky-800" @click="addTranslation">
      <Icon name="fa6-solid:plus" class="text-xs" />
      {{ t('common.add_translation') }}
    </button>
  </div>
</template>
