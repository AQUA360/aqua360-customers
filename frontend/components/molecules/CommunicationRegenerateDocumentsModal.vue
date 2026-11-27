<script setup>
// Regenerar la carta i les factures de les comunicacions d'un procés: de totes o
// només de les pendents d'enviar. Els documents antics queden a l'històric.
const { t } = useI18n();

const props = defineProps({
  show: { type: Boolean, default: false },
  running: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'confirm']);

const onlyPending = ref(true);

watch(() => props.show, (isOpen) => {
  if (isOpen) onlyPending.value = true;
});

const close = () => {
  if (props.running) return;
  emit('close');
};
</script>

<template>
  <div v-if="show">
    <div class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-40" @click="close"></div>

    <div class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto pointer-events-none">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-xl w-full mx-4 my-auto relative pointer-events-auto"
        role="dialog" aria-modal="true" aria-labelledby="communication-regenerate-documents-title">
        <button @click="close" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700" :disabled="running">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>

        <h3 id="communication-regenerate-documents-title" class="text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Icon name="fa6-solid:rotate" class="text-slate-500" />
          {{ t('customer_service_block.regenerate_documents') }}
        </h3>

        <p class="text-sm text-slate-600 mb-5">{{ t('customer_service_block.regenerate_documents_info') }}</p>

        <p class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
          {{ t('customer_service_block.regenerate_documents_which') }}
        </p>
        <div class="space-y-2 mb-5">
          <label class="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input type="radio" name="regenerate-documents-scope" :value="true" v-model="onlyPending" />
            {{ t('customer_service_block.regenerate_documents_pending') }}
          </label>
          <label class="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input type="radio" name="regenerate-documents-scope" :value="false" v-model="onlyPending" />
            {{ t('customer_service_block.regenerate_documents_all') }}
          </label>
        </div>

        <div class="flex justify-end gap-2 border-t border-slate-200 pt-4">
          <button type="button" class="button-secondary" :disabled="running" @click="close">
            {{ t('common.cancel') }}
          </button>
          <button type="button" class="button-primary flex items-center gap-2" :disabled="running"
            @click="emit('confirm', { onlyPending })">
            <Icon v-if="running" name="fa6-solid:spinner" class="animate-spin" />
            <Icon v-else name="fa6-solid:rotate" />
            {{ t('customer_service_block.regenerate_documents') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
