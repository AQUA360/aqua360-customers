<script setup>
import { useI18n } from 'vue-i18n';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';
import H1Region from '../atoms/H1Region.vue';
import AddBillings from './AddBillings.vue';
import AddClaimRequest from './AddClaimRequest.vue';
import BillingDetail from './BillingDetail.vue';
import ClaimRequestDetail from './ClaimRequestDetail.vue';
import SEPARemittanceDetailMinimal from './SEPARemittanceDetailMinimal.vue';
import SEPARemittanceList from '../organisms/SEPARemittanceList.vue';
import SupplyCutDetail from './SupplyCutDetail.vue';
import AddSupplyCut from './AddSupplyCut.vue';

const { t } = useI18n();

const props = defineProps({
  isSubRegion: false,
  isSubRegionOpen: Boolean,
  reload: {
    type: Boolean,
    default: false
  }
});
const emit = defineEmits(['show-subregion', 'search']);

const { $CommunicationApiService } = useNuxtApp();

const manage_option = ref('billing');
const selected_option_id = ref(null);
const objects = ref([]);

const currentManageOption = computed({
  get: () => manage_option.value,
  set: (value) => {
    if (manage_option.value !== value) {
      selected_option_id.value = null;
      objects.value = [];
    }
    manage_option.value = value;
  }
});

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const SubRegion = ref(false);

const manageOptions = [
  { value: 'billing', name: 'billing' },
  { value: 'claimrequest', name: 'claim_block.claim_payments' },
]

const search = function () {
  emit('search', currentManageOption.value, selected_option_id.value);
}

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  showSubRegion();
}

const itemClicked = function (item) {
  selected_option_id.value = item.id;
  objects.value = [item];
  closeSubRegion();
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

onMounted(() => {
})


</script>
<template>

  <div class="region__content">
    <div class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between items-center mb-4">
        <H1Region>{{ $t('customer_service_block.select_mng') }}</H1Region>
      </div>
      <!-- INFO TEXT -->
      <div
        class="my-5 mx-2 p-3 border-l-2 border-orange-500 rounded bg-orange-50 text-orange-500 grid grid-cols-[auto,1fr] gap-2">
        <div class="flex items-center">
          <Icon name="fa6-solid:info" class="text-orange-500" />
        </div>
        <div>
          <p class="text-sm font-medium">
            {{ t('informative_block.info_mng_select_comms') }}
          </p>
        </div>
      </div>

      <!-- OPTIONS OBJECT SELECT -->
      <div class="my-2">
        <div class="flex items-center gap-2 mb-2">
          <input type="radio" v-model="currentManageOption" value="billing" />
          <abbr :title="t('customer_service_block.include_invoices')">
            <label class="font-medium text-slate-500">{{ t('billing') }}</label>
          </abbr>
        </div>
        <ButtonSeleccio v-if="!selected_option_id || (currentManageOption != 'billing' && selected_option_id)"
          :disabled="currentManageOption != 'billing'" @click="showDetail('BillingForm', selected_option_id)"
          class="py-3 mx-2">
          <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
          {{ $t('reports_block.select_billing') }}
        </ButtonSeleccio>
        <div v-else class="p-3 bg-green-50 m-2 group relative">
          <BillingDetail :id="selected_option_id" />
          <button @click="showDetail('BillingForm', selected_option_id)"
            class="absolute border border-slate-300 top-1 right-1 bg-white h-6 w-6 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-all duration-200 ease">
            <Icon name="fa6-solid:pencil" class="text-slate-500" />
          </button>
        </div>
      </div>
      <div class="my-2">
        <div class="flex items-center gap-2 mb-2">
          <input type="radio" v-model="currentManageOption" value="claimrequest" />
          <abbr :title="t('customer_service_block.include_claim_letter')">
            <label class="font-medium text-slate-500">{{ t('claim_block.claim_payments') }}</label>
          </abbr>
        </div>
        <ButtonSeleccio v-if="!selected_option_id || (currentManageOption != 'claimrequest' && selected_option_id)"
          :disabled="currentManageOption != 'claimrequest'" @click="showDetail('ClaimRequestForm', selected_option_id)"
          class="py-3 mx-2">
          <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
          {{ $t('claim_block.select_claim_payments') }}
        </ButtonSeleccio>
        <div v-else class="p-3 bg-green-50 m-2 group relative">
          <ClaimRequestDetail :id="selected_option_id" :isSubRegion="true" />
          <button @click="showDetail('ClaimRequestForm', selected_option_id)"
            class="absolute border border-slate-300 top-1 right-1 bg-white h-6 w-6 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-all duration-200 ease">
            <Icon name="fa6-solid:pencil" class="text-slate-500" />
          </button>
        </div>
      </div>
      <div class="my-2">
        <div class="flex items-center gap-2 mb-2">
          <input type="radio" v-model="currentManageOption" value="supplycut" />
          <abbr :title="t('common.supply_cuts')">
            <label class="font-medium text-slate-500">{{ t('common.supply_cuts') }}</label>
          </abbr>
        </div>
        <ButtonSeleccio v-if="!selected_option_id || (currentManageOption != 'supplycut' && selected_option_id)"
          :disabled="currentManageOption != 'supplycut'" @click="showDetail('SupplyCutForm', selected_option_id)"
          class="py-3 mx-2">
          <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
          {{ $t('common.select') }} {{ $t('common.supply_cuts') }}
        </ButtonSeleccio>
        <div v-else class="p-3 bg-green-50 m-2 group relative">
          <SupplyCutDetail :id="selected_option_id" />
          <button @click="showDetail('SupplyCutForm', selected_option_id)"
            class="absolute border border-slate-300 top-1 right-1 bg-white h-6 w-6 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-all duration-200 ease">
            <Icon name="fa6-solid:pencil" class="text-slate-500" />
          </button>
        </div>
      </div>
      <hr />
      <div class="my-2">
        <div class="flex items-center gap-2 mb-2">
          <input type="radio" v-model="currentManageOption" value="sepa_payments" />
          <abbr :title="t('common.sepa_managements')">
            <label class="font-medium text-slate-500">{{ t('common.sepa_managements') }}</label>
          </abbr>
        </div>
        <ButtonSeleccio v-if="!selected_option_id || (currentManageOption != 'sepa_payments' && selected_option_id)"
          :disabled="currentManageOption != 'sepa_payments'"
          @click="showDetail('SEPARemittanceForm', selected_option_id)" class="py-3 mx-2">
          <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
          {{ $t('reports_block.select_remittance') }}
        </ButtonSeleccio>
        <div v-else class="p-3 bg-green-50 m-2 group relative">
          <SEPARemittanceDetailMinimal :remittance_id="selected_option_id" :isSubRegion="true" />
          <button @click="showDetail('SEPARemittanceForm', selected_option_id)"
            class="absolute border border-slate-300 top-1 right-1 bg-white h-6 w-6 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-all duration-200 ease">
            <Icon name="fa6-solid:pencil" class="text-slate-500" />
          </button>
        </div>
      </div>
      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button
          @click="search"
          class="button-primary flex items-center gap-2"
          :disabled="!selected_option_id"
        >
          {{ $t('common.accept') }}
        </button>
      </div>
    </div>


    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddBillings v-if="showRegionDetailComponent == 'BillingForm'" :selected_items="objects"
          @item-clicked="itemClicked" :multiple="false" />
        <AddClaimRequest v-if="showRegionDetailComponent == 'ClaimRequestForm'" :selected_items="objects"
          @item-clicked="itemClicked" :multiple="false" :is_comm="true" />
        <AddSupplyCut v-if="showRegionDetailComponent == 'SupplyCutForm'" :selected_items="objects"
          @item-clicked="itemClicked" :multiple="false" />
        <SEPARemittanceList v-if="showRegionDetailComponent == 'SEPARemittanceForm'" :selected_item="selectedRemittance"
          @item-clicked="itemClicked" :allow_select="true" />
      </div>
    </div>
  </div>


</template>