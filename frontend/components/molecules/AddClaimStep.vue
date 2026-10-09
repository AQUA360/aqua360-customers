<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import H1 from '~/components/atoms/H1.vue';
import ClaimStepPriceRatesRegion from '~/components/organisms/ClaimStepPriceRatesRegion.vue';
import _ from 'lodash';
const { t } = useI18n();
const { $ClaimRequestApiService, $ConfiglistApiService } = useNuxtApp();

const props = defineProps({
  id: Number,
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['change']);

const token = ref('')
const name = ref('')
const next_step = ref(null)
const duration_days = ref(null)
const duration_type = ref('WORK')
const description = ref('')
const price_rates = ref([])
const price_rate_ids = ref([])
const template = ref(null)

const selectedOrderType = ref(null)
const selectedDocumentType = ref(null)

const orderTypes = ref([])
const documentTypes = ref([])

const SubRegion = ref(props.isSubRegionOpen);

const attemptedSave = ref(false);
const saving = ref(false);

const showRegion = ref(false);
const isPriceRatesOpen = ref(false);
const isPriceRateSubRegionOpen = ref(false);

const billingTypes = ref([
  { value: 'contract', label: t('common.contract'), description: t('claim_block.contract_application') },
  { value: 'invoice', label: t('invoice'), description: t('claim_block.invoice_application') },
])
const selectedBillingType = ref('invoice');
const groupedPayments = ref(false)

const getData = async () => {
  attemptedSave.value = false;
  saving.value = false;
  if (props.id != null) {
    try {
      const response = await $ClaimRequestApiService.getClaimRequestStepTemplateDetail(props.id);
      token.value = response.token;
      name.value = response.name;
      next_step.value = { 'name': response.next_step_name, 'id': response.next_step_id };
      duration_days.value = response.duration;
      duration_type.value = response.duration_type;
      selectedOrderType.value = response.order_type ? { code: response.order_type.id, label: response.order_type.name } : orderTypes.value[0];
      selectedDocumentType.value = response.document_type ? { code: response.document_type.id, label: response.document_type.name } : documentTypes.value[0];
      description.value = response.description;
      price_rates.value = response.price_rates || [];
      price_rate_ids.value = price_rates.value.map(item => item.id);
      template.value = response.template;
      selectedBillingType.value = response.billing_type || 'invoice';
      groupedPayments.value = response.group_payments || false;
    } catch (error) {
      console.error(error)
    }
  }
}

const getOrderTypes = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('order/order-type');
    response.results.forEach(item => {
      orderTypes.value.push({
        label: item.name,
        code: item.id
      })
    })
    orderTypes.value.unshift(
      {
        label: t("order_block.no_action_assigned"),
        code: 'null',
      }
    );
  } catch (error) {
    console.error(error)
  }
}
const getDocumentTypes = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('claimrequest/claim-document-type/');
    response.results.forEach(item => {
      documentTypes.value.push({
        label: item.name,
        code: item.id
      })
    })
    documentTypes.value.unshift(
      {
        label: t("common.no_doc_type"),
        code: 'null',
      }
    );
  } catch (error) {
    console.error(error)
  }
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'order_type':
      selectedOrderType.value = event;
      break;
    case 'document_type':
      selectedDocumentType.value = event;
      break;
    default:
      null;
      break;
  }
}

const isValid = () => {
  if (name.value == '') return false;
  if (token.value == '') return false;
  if (duration_days.value == null) return false;

  return true;
}

const save = async () => {
  if (isValid()) {
    saving.value = true;
    try {
      let order_id = selectedOrderType?.value?.code != "null" ? selectedOrderType?.value?.code : null;
      let document_id = selectedDocumentType?.value?.code != "null" ? selectedDocumentType?.value?.code : null;

      const selectedOptions = {
        id: props.id ? props.id : null,
        name: name.value,
        token: token.value,
        duration: duration_days.value,
        description: description.value,
        duration_type: duration_type.value,
        order_type: order_id || null,
        document_type: document_id || null,
        price_rates: price_rate_ids.value,
        template: template.value,
        billing_type: selectedBillingType.value,
        group_payments: groupedPayments.value,
      };

      let response = await $ClaimRequestApiService.saveClaimStepTemplate(selectedOptions);

      emit('change');
    } catch (error) {
      console.error(error);
    } finally {
      saving.value = false;
    }

  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isPriceRateSubRegionOpen.value = false;
    isPriceRatesOpen.value = false;
  }
}

const showPriceRates = () => {
  isPriceRatesOpen.value = true;
  toggleRegion(true);
}

const handleSubRegionEvent = (event) => {
  isPriceRateSubRegionOpen.value = event;
}

const updatePriceRates = (selected) => {
  price_rates.value = selected;
  price_rate_ids.value = selected.map(item => item.id);
}

onMounted(async () => {
  await getOrderTypes()
  await getDocumentTypes()
  getData()
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
  getData();
  if (!newValue) {
    toggleRegion(false);
  }
});

watch(() => props.id, (newValue) => {
  getData();
});

</script>

<template>
  <div class="region__content">
    <div>
      <H1>{{ props.id ? `${$t('common.modify')} ${t('billing_block.step')}` : $t('billing_block.new_step') }}</H1>
      <div class="row grid grid-cols-2 gap-3 mt-2">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identification') }} * </label>
          <input required type="text" v-model="token" class="input" :disabled="props.id"
            :class="{ 'invalid': attemptedSave && token == '' }" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }} * </label>
          <input required type="text" v-model="name" :class="{ 'invalid': attemptedSave && name == '' }"
            class="input" />
        </div>


        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.duration') }} * </label>
          <div class="grid grid-cols-[60px,1fr] gap-3">
            <input required type="number" v-model="duration_days"
              :class="{ 'invalid': attemptedSave && duration_days == '' }" class="input" />
            <div class="flex items-center p-2">
              <label class="mr-4">
                <input type="radio" v-model="duration_type" value="WORK" @change="fieldChanged" /> {{ t('common.work')
                }}
              </label>
              <label>
                <input type="radio" v-model="duration_type" value="NATURAL" @change="fieldChanged" /> {{
                  t('common.natural')
                }}
              </label>
            </div>
          </div>
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.next_step') }}</label>
          <!-- TODO: SELECCIONAR CONSULTAR, EDITAR I CREAR NOU PAS EN CAS DE SER PROCESSOS MÉS FLEXIBLES -->
          <p class="py-2 px-4 bg-slate-100 text-slate-400 text-sm border border-slate-300 rounded-lg w-full">
            {{ next_step?.name ? next_step.name : t('billing_block.no_next_step') }}
          </p>
        </div>

        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('billing_block.send_doc') }}</label>
          <v-select class="block w-full mr-1 custom-select" :model-value="selectedDocumentType"
            @update:modelValue="updateSelect($event, 'document_type')" :options="documentTypes" />

        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.work_order') }}</label>
          <v-select class="block w-full mr-1 custom-select" :model-value="selectedOrderType"
            @update:modelValue="updateSelect($event, 'order_type')" :options="orderTypes" />
        </div>

      </div>

      <div class="mb-4 mt-4">
        <label class="flex text-sm font-medium text-slate-500 mb-3 gap-2">
          <span>{{ $t('common.price_rates') }} ({{ price_rates.length }})</span>
        </label>
        <div class="pl-3 pr-3">
          <div class="mb-2 grid grid-cols-2 gap-3">
            <div v-for="item in price_rates" :key="item.id" class="mb-1">
              <Icon name="fa6-solid:cube" class="text-slate-500" />
              &nbsp;<span class="font-semibold">{{ item.name }}</span> - {{ item.product_name || item.product?.name ||
                t('pricing_block.no_product') }}
            </div>
          </div>
          <button class="button-default-xs" @click="showPriceRates">
            <Icon name="fa-solid:plus" class="text-slate-500 mr-1" />
            {{ $t('common.add') }}/{{ $t('common.modify') }}
          </button>
        </div>
      </div>

      <div v-if="price_rates.length > 0" class="mb-4 -mt-2 p-3 pt-1 bg-sky-100/70 rounded-lg">
        <label class="block text-sm font-medium text-slate-500 mb-2">
          {{ $t('pricing_block.price_rates_application') }}
        </label>
        <div class="grid grid-cols-2 gap-3">
          <div v-for="item in billingTypes" :key="item.value">
            <label>
              <input type="radio" :value="item.value" v-model="selectedBillingType" />
              {{ item.label }}
            </label>
            <p class="text-xs text-slate-400">{{ item.description }}</p>
          </div>
        </div>
      </div>

      <div class="mb-4">
        <label class="flex items-center gap-x-2 text-slate-500">
          <input type="checkbox" v-model="groupedPayments" />
          {{ t('claim_block.group_price_rates_with_invoice') }}
        </label>
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.description') }}</label>
        <textarea name="description" id="description" cols="30" rows="5" v-model="description"
          class="w-full border border-slate-300 rounded-md p-2 focus:outline-none focus:border-primary"></textarea>
      </div>


      <!-- <hr /> -->
      <div class="flex flex-row-reverse mt-4">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div>

    </div>
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-[60] w-[95%] overflow-y-auto overflow-x-hidden"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
        'w-1/2': !isPriceRateSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div v-if="isPriceRatesOpen" class="px-10">
        <ClaimStepPriceRatesRegion v-model="price_rate_ids" :isSubRegionOpen="isPriceRateSubRegionOpen"
          :priceRates="price_rates" @change="updatePriceRates" @show-subregion="handleSubRegionEvent" />
      </div>
    </div>
  </div><!-- end wrapper -->
</template>