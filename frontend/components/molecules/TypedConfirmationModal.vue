<script setup>
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const open = defineModel('open', { type: Boolean, default: false });

const props = defineProps({
  message: {
    type: String,
    required: true,
  },
  expectedPhrase: {
    type: String,
    required: true,
  },
  instruction: {
    type: String,
    default: null,
  },
  confirmLabel: {
    type: String,
    default: null,
  },
  cancelLabel: {
    type: String,
    default: null,
  },
  isImportant: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['confirm', 'cancel']);

const userInput = ref('');
const attempted = ref(false);

const instructionText = computed(() =>
  props.instruction ?? t('confirmation_text_block.typed_confirm_instruction'),
);

const isPhraseMatch = computed(
  () => userInput.value.trim() === props.expectedPhrase.trim(),
);

const showMismatch = computed(() => attempted.value && !isPhraseMatch.value);

function resetState() {
  userInput.value = '';
  attempted.value = false;
}

watch(open, (isOpen) => {
  if (!isOpen) resetState();
});

function close() {
  open.value = false;
}

function handleCancel() {
  close();
  emit('cancel');
}

function handleConfirm() {
  attempted.value = true;
  if (!isPhraseMatch.value) return;
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
        aria-modal="true" aria-labelledby="typed-confirm-title" @click="handleBackdropClick">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full relative" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="cancelLabel ?? t('common.cancel')" @click="handleCancel">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <p id="typed-confirm-title" class="leading-relaxed "
          :class="isImportant ? 'text-red-700 font-semibold' : 'text-slate-600 font-medium'">
            {{ message }}
          </p>
          <hr class="my-2">
          <p class="text-sm text-slate-600 mb-2">
            {{ instructionText }}
          </p>

          <p class="mb-3 rounded-md bg-slate-100 px-3 py-2 font-mono text-sm font-semibold text-slate-800 select-all">
            {{ expectedPhrase }}
          </p>

          <label class="block text-sm font-medium text-slate-500 mb-1">
            {{ t('confirmation_text_block.typed_confirm_input_label') }}
          </label>
          <input v-model="userInput" type="text" autocomplete="off" spellcheck="false"
            class="w-full rounded border px-3 py-2 text-sm text-slate-700 focus:outline-none"
            :class="showMismatch ? 'border-red-500' : 'border-slate-300'" :placeholder="expectedPhrase"
            @keyup.enter="handleConfirm" />

          <p v-if="showMismatch" class="mt-1 text-sm text-red-600">
            {{ t('confirmation_text_block.typed_confirm_mismatch') }}
          </p>

          <div class="flex justify-end gap-2 mt-6">
            <button type="button" class="button-default disabled:cursor-not-allowed" :disabled="!isPhraseMatch"
              @click="handleConfirm">
              {{ confirmLabel ?? t('common.confirm') }}
            </button>
            <button type="button" class="button-primary" @click="handleCancel">
              {{ cancelLabel ?? t('common.cancel') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
