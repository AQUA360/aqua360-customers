<script setup>
import { useI18n } from 'vue-i18n';
import SelectPaymentType from '../molecules/SelectPaymentType.vue';

const { t } = useI18n();

const liquidateOpen = defineModel('liquidateOpen', { type: Boolean, default: false });
const modifyOpen = defineModel('modifyOpen', { type: Boolean, default: false });
const generateProofOpen = defineModel('generateProofOpen', { type: Boolean, default: false });
const selectedPaymentDate = defineModel('selectedPaymentDate', { type: String, default: null });
const selectedDueDate = defineModel('selectedDueDate', { type: String, default: null });
const selectedPaymentMethod = defineModel('selectedPaymentMethod', { type: [String, Number], default: null });
const observation = defineModel('observation', { type: String, default: null });

const props = defineProps({
  joinedPayment: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(['modify-data', 'generate-proof']);
const JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS = [
  'BALANCE',
  'DIRECT_DEBIT',
  'ELECTRONIC_INVOICE',
  'CONFIRMING60',
  'CONFIRMING180',
  'TPV_ONLINE',
];

const saving = ref(false);
const attemptedSave = ref(false);

function closeModals(hide = false) {
  saving.value = true;
  selectedPaymentDate.value = null;
  observation.value = '';
  attemptedSave.value = false;
  if (hide){
    liquidateOpen.value = false;
    modifyOpen.value = false;
    generateProofOpen.value = false;
  }
}


const saveModify = (paying = false) => {
  attemptedSave.value = true;
  if (
    (!selectedPaymentMethod || selectedPaymentMethod == '') &&
    (!selectedPaymentDate || selectedPaymentDate == '')
  ) return;
  
  if (!confirm(t('confirmation_text_block.confirm_modify'))) return;
  emit('modify-data', selectedPaymentDate.value && paying ? selectedPaymentDate.value : null);
  closeModals();
}

const generateProof = () => {
  if (!selectedPaymentDate.value || selectedPaymentDate.value == '') return;
  emit('generate-proof');
}

watch([liquidateOpen, modifyOpen, generateProofOpen], () => {
  if (liquidateOpen.value || modifyOpen.value || generateProofOpen.value) {
    saving.value = false;
  }
});

</script>

<template>
  <div>
    <div v-if="liquidateOpen || modifyOpen" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto"
      @click="closeModals(true)">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative" @click.stop>
        <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700" @click="closeModals(true)">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>

        <div v-if="liquidateOpen">
          <div>
            <label class="block font-medium text-slate-500">{{ t('billing_block.payment_date') }}</label>
            <div class="pb-4 rounded-lg text-left max-h-[60vh] overflow-y-auto">
              <AtomsInputDate v-model="selectedPaymentDate" label="" class="mb-2" :disabled="saving"
                :invalid="attemptedSave && (selectedPaymentDate == null || selectedPaymentDate == '') && !saving" />
            </div>
            <SelectPaymentType v-model="selectedPaymentMethod" :exclude-tokens="JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS"
              :invalid="attemptedSave && !selectedPaymentMethod && !saving"
              select-class="w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-700"
              select-wrapper-class="max-w-xl" :model-as-number="true" />
          </div>
          <div class="flex justify-end mt-2">
            <button type="button" class="button-primary flex items-center gap-x-2"
              :disabled="!selectedPaymentDate || !selectedPaymentMethod || selectedPaymentMethod == '' || saving"
              @click="saveModify(true)">
              <Icon name="fa6-solid:spinner" class="animate-spin" v-if="saving" />
              {{ saving ? $t('common.loading') : $t('common.save') }}
            </button>
          </div>
        </div>


        <div v-if="modifyOpen">
          <h2 class="text-lg font-semibold text-slate-800 pr-8 mb-4">
            {{ t('common.modify') }}
          </h2>
          <SelectPaymentType v-model="selectedPaymentMethod" :exclude-tokens="JOINED_PAYMENT_EXCLUDED_TYPE_TOKENS"
            :invalid="attemptedSave && !selectedPaymentMethod && !saving" 
            select-class="w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-700"
            select-wrapper-class="max-w-xl" :model-as-number="true" />
          <AtomsInputDate v-model="selectedDueDate" :label="t('common.due_date')" class="my-2" :disabled="saving"
            :invalid="attemptedSave && (selectedDueDate == null || selectedDueDate == '') && !saving" />
          <div class="flex justify-end mt-2">
            <button type="button" class="button-primary flex items-center gap-x-2"
              :disabled="(!selectedPaymentMethod || selectedPaymentMethod == '') && (!selectedPaymentDate || selectedPaymentDate == '') || saving"
              @click="saveModify">
              <Icon name="fa6-solid:spinner" class="animate-spin" v-if="saving" />
              {{ saving ? $t('common.loading') : $t('common.save') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="generateProofOpen" class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto"
      @click="closeModals(true)">
      <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative" @click.stop>
        <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700" @click="closeModals(true)">
          <Icon name="fa6-solid:xmark" class="text-xl" />
        </button>
        <h2 class="text-lg font-semibold text-slate-800 pr-8 mb-4">
          {{ t('billing_block.payment_proof') }}
        </h2>
        <label class="block font-medium text-slate-500">{{ t('billing_block.payment_date') }}</label>
        <AtomsInputDate v-model="selectedPaymentDate" label="" class="mb-2" :disabled="saving"
          :invalid="attemptedSave && (selectedPaymentDate == null || selectedPaymentDate == '') && !saving" />
        <label class="block font-medium text-slate-500">{{ t('common.observation') }}</label>
        <textarea name="observation" id="observation" cols="30" rows="2" v-model="observation"
          class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
        <div class="flex justify-end mt-2">
          <button type="button" class="button-primary flex items-center gap-x-2"
            :disabled="!selectedPaymentDate || selectedPaymentDate == '' || saving" @click="generateProof">
            {{ $t('common.generate') }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="modifyOpen || liquidateOpen || generateProofOpen"
      class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-20 flex items-center justify-center" />
  </div>
</template>
