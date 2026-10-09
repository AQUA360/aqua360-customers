<script setup>
import { ref, computed } from 'vue';
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
  ordersCount: {
    type: Number,
    default: 0
  },
  selectedContracts: {
    type: Array,
    default: () => []
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['changed', 'previous-step', 'next-step', 'show-contracts', 'show-orders']);
const { $OrderApiService, $ClaimRequestApiService } = useNuxtApp();

const saving = ref(false);
const workOrderDate = ref(props.step.action_date_at);
const contracts = ref([]);
const selectedContracts = ref([]);

const selectedContractsCount = computed(() => {
  return props.selectedContracts.length;
});
const atCurrentStep = computed(() => {
  return props.request.current_step?.id === props.step.id;
});

const loadContracts = async () => {
  try {
    const response = await $ClaimRequestApiService.getContracts(props.request.id);
    contracts.value = response.results || [];
  } catch (error) {
    console.error('Error loading contracts:', error);
  }
};

const handleShowContracts = () => {
  loadContracts();
  emit('show-contracts', contracts.value);
};

const handleSubmit = async () => {
  if (!workOrderDate.value) {
    toast.error(t('warning_block.no_order_date_warning'));
    return;
  }

  if(selectedContracts.value.length === 0){
    toast.error(t('warning_block.warning_select_contract'));
    return;
  }

  if (!confirm(t('confirmation_text_block.confirm_create_orders'))) return;
  
  saving.value = true;
  try {
    // Primer actualitzem la data d'execució
    await $ClaimRequestApiService.updateClaimRequestStep({
      id: props.step.id,
      claim_request: props.request.id,
      action_date_at: workOrderDate.value
    });

    // Després creem les ordres
    const data = {
      claim_request: props.request.id,
      contracts: selectedContracts.value,
      date: workOrderDate.value
    };

    const response = await $OrderApiService.postClaimRequestOrder('remove_meter', data);
    
    if (response.message) {
      toast.success(response.message);
    }
    
    emit('changed');
  } catch (error) {
    toast.error(t('common.error_save'));
    console.error(error);
  } finally {
    saving.value = false;
  }
};

watch(() => props.selectedContracts, (newValue) => {
  selectedContracts.value = [...newValue];
}, { immediate: true, deep: true });


</script>

<template>
  <div class="space-y-6 py-3">
    <div class="flex justify-between">
      <div>
        <h3 class="text-lg font-semibold">{{ $t('order_block.remove_meter') }}</h3>
        <p class="text-gray-600">{{ $t('claim_block.mng_remove_meter') }}</p>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <abbr class="italic" :title="`${$t('common.add')} ${$t('common.send_date')}`">
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
      
      <div class="mb-4">
        <button
          @click="handleShowContracts"
          class="button-default"
        >
          {{ $t('common.contracts') }} ({{ selectedContractsCount }})
        </button>
      </div>
    </fieldset>

    <!-- Secció de creació d'ordres -->
    <fieldset class="bg-white p-4 rounded-lg shadow">
      <legend class="flex items-center space-x-2">
        <span class="flex items-center justify-center w-6 h-6 rounded-full bg-gray-400 text-white font-medium">2</span>
        <h4 class="font-medium p-0 m-0">{{ $t('claim_block.mng_remove_meter_title') }}</h4>
      </legend>
      
      <form @submit.prevent="handleSubmit" class="flex gap-2 items-end space-y-4">
        <div class="flex flex-col space-y-2">
          <label for="work_order_date" class="font-medium">{{ $t('common.execution_date') }}</label>
          <input
            type="date"
            id="work_order_date"
            v-model="workOrderDate"
            class="border border-gray-300 rounded p-2"
            required
          />
        </div>

        <div class="flex justify-end">
          <button
            type="submit"
            :disabled="saving || !atCurrentStep"
            class="button-primary"
          >
            <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin mr-2" />
            {{ $t('common.execute') }} {{ $t('common.orders') }} {{ $t('common.and') }} {{ $t('order_block.remove_meter') }}
          </button>
        </div>
      </form>
    </fieldset>

    <!-- Secció de visualització d'ordres -->
    <fieldset class="bg-white p-4 rounded-lg shadow">
      <legend class="flex items-center space-x-2">
        <span class="flex items-center justify-center w-6 h-6 rounded-full bg-gray-400 text-white font-medium">3</span>
        <h4 class="font-medium p-0 m-0">{{ $t('work_orders') }}</h4>
      </legend>
      
      <div class="mb-4">
        <button
          @click="$emit('show-orders', 'remove_meter')"
          class="button-default">
          {{ $t('common.show') }} {{ $t('common.orders') }} ({{ ordersCount }})
        </button>
      </div>
    </fieldset>

    <div v-if="!atCurrentStep" class="text-sm text-amber-500 text-bold">
      {{ $t('claim_block.info_at_current_step') }}
    </div>

    <slot name="footer" />

  </div>
</template> 