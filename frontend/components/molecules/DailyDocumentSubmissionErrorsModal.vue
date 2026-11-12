<script setup>
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const open = defineModel('open', { type: Boolean, default: false });

const props = defineProps({
  errorCount: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits(['confirm', 'cancel']);

function close() {
  open.value = false;
}

function handleCancel() {
  close();
  emit('cancel');
}

function handleConfirm() {
  close();
  emit('confirm');
}

function handleBackdropClick() {
  handleCancel();
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="handleBackdropClick" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" aria-labelledby="daily-doc-submission-errors-title" @click="handleBackdropClick">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full relative border-2 border-red-400" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" @click="handleCancel">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <div class="flex items-start gap-3 mb-4 pr-6">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 text-red-600">
              <Icon name="fa6-solid:triangle-exclamation" class="text-lg" />
            </div>
            <div class="min-w-0">
              <p id="daily-doc-submission-errors-title" class="text-lg font-semibold text-red-700">
                {{ t('statistics_block.submission_errors_modal_title') }}
              </p>
              <p class="mt-1 text-sm text-slate-600 leading-relaxed">
                {{ t('statistics_block.submission_errors_modal_body', { count: errorCount }) }}
              </p>
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <button type="button" class="button-default" @click="handleCancel">
              {{ t('statistics_block.submission_errors_modal_dismiss') }}
            </button>
            <button type="button" class="button-primary" @click="handleConfirm">
              {{ t('statistics_block.submission_errors_modal_confirm') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
