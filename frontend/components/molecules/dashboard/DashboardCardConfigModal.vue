<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

// Configuració d'una card: mida i les opcions de l'esquema que defineix el backend.
const open = defineModel('open', { type: Boolean, default: false });
const props = defineProps({
  item: { type: Object, default: null },
  card: { type: Object, default: null },
});
const emit = defineEmits(['save']);

const { t } = useI18n();

const size = ref('md');
const config = ref({});

watch(open, (isOpen) => {
  if (!isOpen || !props.item) return;
  size.value = props.item.size;
  config.value = { ...(props.item.config || {}) };
});

const save = () => {
  emit('save', { ...props.item, size: size.value, config: { ...config.value } });
  open.value = false;
};
</script>

<template>
  <Teleport to="body">
    <div v-if="open && item && card">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="open = false" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" @click="open = false">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full relative" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" @click="open = false">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
          <p class="text-base font-semibold text-slate-700 mb-4 pr-8">
            {{ t('home_dashboard.configure') }}: {{ t(`home_dashboard.cards.${item.key}.title`) }}
          </p>

          <label class="block text-sm font-medium text-slate-500 mb-1">{{ t('home_dashboard.size') }}</label>
          <div class="flex gap-2 mb-4">
            <button v-for="option in card.sizes" :key="option" type="button"
              class="px-3 py-1 text-sm rounded-md border"
              :class="size === option ? 'border-sky-500 bg-sky-50 text-sky-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50'"
              @click="size = option">
              {{ t(`home_dashboard.sizes.${option}`) }}
            </button>
          </div>

          <div v-for="option in card.config_schema" :key="option.name" class="mb-4">
            <template v-if="option.type === 'select'">
              <label class="block text-sm font-medium text-slate-500 mb-1">{{ t(`home_dashboard.config.${option.name}.label`) }}</label>
              <select v-model="config[option.name]" class="input w-full">
                <option v-for="choice in option.options" :key="choice.value" :value="choice.value">
                  {{ t(`home_dashboard.config.${option.name}.${choice.value}`) }}
                </option>
              </select>
            </template>
            <label v-else-if="option.type === 'boolean'" class="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
              <input v-model="config[option.name]" type="checkbox" />
              {{ t(`home_dashboard.config.${option.name}.label`) }}
            </label>
          </div>

          <div class="flex justify-end gap-2 mt-4">
            <button type="button" class="button-default" @click="open = false">{{ t('common.cancel') }}</button>
            <button type="button" class="button-primary" @click="save">{{ t('common.save') }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
