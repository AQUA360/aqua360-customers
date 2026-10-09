<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';

const props = defineProps({
  request: Object,
  step: Object,
  isFirstStep: {
    type: Boolean,
    default: false
  },
  isLastStep: {
    type: Boolean,
    default: false
  },
  selectedContracts: {
    type: Array,
    default: () => []
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['changed', 'previous-step', 'next-step', 'show-contracts', 'update:selectedContracts', 'show-terminations']);
const { $ClaimRequestApiService, $ConfiglistApiService } = useNuxtApp();

const saving = ref(false);
const contracts = ref([]);
const selectedContracts = ref([]);
const terminationTypes = ref([]);
const cancellationDate = ref('');
const cancellationReason = ref('');
const observations = ref('');

const atCurrentStep = computed(() => {
  return props.request.current_step?.id === props.step.id;
});

// Carregar els tipus de baixa
const loadTerminationTypes = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('contract/contract-termination-request-type');
    terminationTypes.value = response.results || [];
  } catch (error) {
    console.error('Error loading termination types:', error);
    toast.error(t('common.error_load'));
  }
};

// Carregar els contractes
const loadContracts = async () => {
  try {
    const response = await $ClaimRequestApiService.getContracts(props.request.id);
    contracts.value = response.results || [];
  } catch (error) {
    console.error('Error loading contracts:', error);
    toast.error(t('common.error_load'));
  }
};

// Comptadors computats
const activeContractsCount = computed(() => {
  return contracts.value.filter(c => !c.is_terminated).length;
});

const terminatedContractsCount = computed(() => {
  return props.request?.contract_termination_requests?.length || 0;
});

const selectedContractsCount = computed(() => {
  return props.selectedContracts.length;
});

// Watch per actualitzar els contractes seleccionats locals quan canvien les props
watch(() => props.selectedContracts, (newValue) => {
  selectedContracts.value = [...newValue];
}, { immediate: true, deep: true });

const handleShowContracts = async () => {
  try {
    await loadContracts();
    emit('show-contracts', contracts.value);
  } catch (error) {
    console.error('Error showing contracts:', error);
    toast.error(t('common.error_load'));
  }
};

const handleShowTerminations = () => {
  emit('show-terminations');
};

// Afegim un watch per debugar els canvis
/* watch(selectedContracts, (newValue) => {
  console.log('selectedContracts ha canviat:', newValue);
}, { deep: true }); */

const handleSubmit = async () => {
  if (!cancellationDate.value) {
    toast.error(t('warning_block.no_termination_date_warning'));
    return;
  }

  if (!cancellationReason.value) {
    toast.error(t('warning_block.no_termination_reason_warning'));
    return;
  }

  if (selectedContracts.value.length === 0) {
    toast.error(t('warning_block.warning_select_contract'));
    return;
  }

  if (!confirm(t('confirmation_text_block.confirm_terminate_contracts'))) return;

  
  saving.value = true;
  try {
    const data = {
      request_id: props.request.id,
      contracts: selectedContracts.value,
      cancellation_date: cancellationDate.value,
      cancellation_reason: cancellationReason.value,
      observations: observations.value
    };

    const response = await $ClaimRequestApiService.submitMassiveTerminationContract(data);

    if (response.terminations && response.terminations.length > 0) {
      toast.success((`${t('informative_block.info_termination_orders')}: ${response.terminations.length}`));
    } else {
      toast.error(t('common.error_save'));
    }

    await $ClaimRequestApiService.save({
      id: props.request.id,
      end_step_date: new Date().toISOString()
    });

    emit('changed');
  } catch (error) {
    toast.error(t('common.error_save'));
    console.error(error);
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  await loadTerminationTypes();
  await loadContracts();
});
</script>

<template>
  <div class="space-y-6 py-3">
    
    <div class="flex justify-between">
      <div>
        <h3 class="text-lg font-semibold">{{ $t('common.terminate') }}</h3>
        <p class="text-gray-600">{{ $t('claim_block.mng_mass_termination') }}</p>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <abbr class="italic" :title="$t('informative_block.info_start_vul_req')">
          {{ $t('common.start_date') }}: 
          {{ step?.action_date_at ? formatDate(step.action_date_at) : '-' }}
        </abbr>
        <abbr class="italic" :title="step?.step_template.duration + ' ' + step?.step_template.duration_type + ' ' + $t('date.days')">
          {{ $t('common.end_date') }}: 
          {{ step?.due_date ? formatDate(step.due_date) : '-' }}
        </abbr>
        <abbr class="italic">
          {{ $t('common.completion_date') }}: 
          {{ step?.end_step_date ? formatDate(step.end_step_date) : '-' }}
        </abbr>
      </div>
    </div>

    <!-- Secció de contractes -->
    <fieldset class="bg-white p-4 rounded-lg shadow">
      <legend class="flex items-center space-x-2">
        <span class="flex items-center justify-center w-6 h-6 rounded-full bg-gray-400 text-white font-medium">1</span>
        <h4 class="font-medium p-0 m-0">{{ $t('contract_block.affected_contracts') }}</h4>
      </legend>

      <div class="grid grid-cols-2 gap-4 mb-4">
        <div class="flex items-center space-x-2">
          <span class="font-medium">{{ $t('contract_block.active_contracts') }}:</span>
          <span class="text-blue-600 font-bold">{{ activeContractsCount }}</span>
        </div>
        <div class="flex items-center space-x-2">
          <span class="font-medium">{{ $t('common.contract_terminations') }}:</span>
          <button 
            @click="handleShowTerminations"
            class="text-red-600 font-bold hover:text-red-800 hover:underline"
            :title="`${$t('common.show')} ${$t('common.contract_terminations')}`"
          >
            {{ terminatedContractsCount }}
          </button>
        </div>
      </div>

      <div class="mb-4">
        <button @click="handleShowContracts" class="button-default">
          {{ $t('contract_block.selected_contracts') }}: {{ selectedContractsCount }}
        </button>
      </div>
    </fieldset>

    <!-- Secció de baixa -->
    <fieldset class="bg-white p-4 rounded-lg shadow">
      <legend class="flex items-center space-x-2">
        <span class="flex items-center justify-center w-6 h-6 rounded-full bg-gray-400 text-white font-medium">2</span>
        <h4 class="font-medium p-0 m-0">{{ $t('claim_block.start_termination') }}</h4>
      </legend>

      <form @submit.prevent="handleSubmit" class="space-y-4" v-if="selectedContractsCount > 0">
        <div v-if="selectedContractsCount > 0" class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <Icon name="fa6-solid:triangle-exclamation" class="h-5 w-5 text-yellow-400" />
            </div>
            <div class="ml-3">
              <p class="text-sm text-yellow-700">
                {{ $t('common.caution') }}, {{ $t('informative_block.info_terminate_contracts') }} {{ selectedContractsCount }}
              </p>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="flex flex-col space-y-2">
            <label for="cancellation_date" class="font-medium">{{ $t('common.termination_date') }}</label>
            <input type="date" id="cancellation_date" v-model="cancellationDate"
              class="border border-gray-300 rounded p-2" required />
          </div>

          <div class="flex flex-col space-y-2">
            <label for="cancellation_reason" class="font-medium">{{ $t('order_block.reason') }}</label>
            <select id="cancellation_reason" v-model="cancellationReason" class="border border-gray-300 rounded p-2"
              required>
              <option value="">{{ $t('common.select') }} {{ $t('order_block.reason') }}</option>
              <option v-for="type in terminationTypes" :key="type.id" :value="type.id">
                {{ type.name }}
              </option>
            </select>
          </div>
        </div>

        <div class="flex flex-col space-y-2">
          <label for="observations" class="font-medium">{{ $t('common.observations') }}</label>
          <textarea id="observations" v-model="observations" rows="3" class="border border-gray-300 rounded p-2"
            :placeholder="`${$t('common.add')} ${$t('common.observations')}...`"></textarea>
        </div>

        <div class="flex justify-start">
          <button type="submit" :disabled="saving || selectedContractsCount === 0 || !atCurrentStep" class="button-primary">
            <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin mr-2" />
            {{ $t('claim_block.start_termination') }}
          </button>
        </div>
      </form>
      <div v-else>
        <p class="text-gray-600">{{ $t('common.no_data') }}</p>
      </div>
    </fieldset>

    <div v-if="!atCurrentStep" class="text-sm text-amber-500 text-bold">
      {{ $t('claim_block.info_at_current_step') }}
    </div>

    <slot name="footer" />

  </div>
</template>