<script setup>
import { ref, watch, computed } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const open = defineModel('open', { type: Boolean, default: false });

const emit = defineEmits(['search']);

const codesText = ref('');
const searching = ref(false);

const parsedCodes = computed(() => {
  const seen = new Set();
  return codesText.value
    .split(/[\n\r]+/)
    .map((line) => line.trim())
    .filter((line) => {
      if (!line || seen.has(line)) return false;
      seen.add(line);
      return true;
    });
});

const codeCount = computed(() => parsedCodes.value.length);

watch(open, (isOpen) => {
  if (!isOpen) {
    codesText.value = '';
    searching.value = false;
  }
});

const handleCancel = () => {
  open.value = false;
};

const handleSearch = () => {
  if (!parsedCodes.value.length || searching.value) return;
  searching.value = true;
  emit('search', parsedCodes.value);
};

const setSearching = (value) => {
  searching.value = value;
};

defineExpose({ setSearching });
</script>

<template>
  <Teleport to="body">
    <div v-if="open">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="handleCancel" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" aria-labelledby="meter-lookup-title" @click="handleCancel">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full relative" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" @click="handleCancel">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <h2 id="meter-lookup-title" class="text-lg font-semibold text-slate-800 mb-1 pr-8">
            {{ t('service_block.meter_lookup_title') }}
          </h2>
          <p class="text-sm text-slate-600 mb-4">
            {{ t('service_block.meter_lookup_help') }}
          </p>

          <label class="block text-sm font-medium text-slate-500 mb-1" for="meter-lookup-codes">
            {{ t('service_block.meter_lookup_codes_label') }}
          </label>
          <textarea id="meter-lookup-codes" v-model="codesText" rows="12" spellcheck="false"
            class="w-full rounded border border-slate-300 px-3 py-2 text-sm font-mono text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:border-sky-400 resize-y"
            :placeholder="t('service_block.meter_lookup_codes_placeholder')"
            @keydown.meta.enter="handleSearch" @keydown.ctrl.enter="handleSearch" />

          <p class="mt-1 text-xs text-slate-500">
            {{ t('service_block.meter_lookup_codes_count', { count: codeCount }) }}
          </p>

          <div class="flex justify-end gap-2 mt-6">
            <button type="button" class="button-default" @click="handleCancel" :disabled="searching">
              {{ t('common.cancel') }}
            </button>
            <button type="button" class="button-primary flex items-center gap-2"
              :disabled="!codeCount || searching" @click="handleSearch">
              <Icon :name="searching ? 'fa6-solid:spinner' : 'fa6-solid:magnifying-glass'"
                :class="{ 'animate-spin': searching }" />
              {{ searching ? t('common.loading') + '...' : t('common.search') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
