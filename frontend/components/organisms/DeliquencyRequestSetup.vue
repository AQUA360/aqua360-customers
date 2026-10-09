<script setup>
import { ca } from 'date-fns/locale';
import { useI18n } from 'vue-i18n';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import { useToast } from 'vue-toastification';
import AddContracts from '../molecules/AddContracts.vue';
import AddInvoices from '../molecules/AddInvoices.vue';
import AffectedContracts from '../organisms/AffectedContracts.vue';

const toast = useToast();
const { t } = useI18n();
const { $PaymentApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);

const selectionType = ref('PAYDATE');
const filter_date_start = ref(null)
const filter_date_end = ref(null)
const endowment_date = ref(null)

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);

const selectedContracts = ref([])
const selectedInvoices = ref([])

const affectedContracts = ref([])
const affectedInvoices = ref([])

const emit = defineEmits(['changed']);

const getData = async () => {
  affectedContracts.value = []
  try {
    let request_data = {
      date_start: filter_date_start.value,
      date_end: filter_date_end.value,
      type: selectionType.value,
      fetching: false,
    }
    const parsedStartDate = new Date(filter_date_start.value);
    const parsedEndDate = new Date(filter_date_end.value);
    if ((filter_date_start.value == null || isNaN(parsedStartDate.getTime())) && (filter_date_end.value == null || isNaN(parsedEndDate.getTime()))) return
    let response = await $PaymentApiService.manageDeliquency(request_data)
    affectedContracts.value = response.contract_data
    if (affectedContracts.value.length === 0){
      toast.warning(t("common.no_data_found"), {
        position: "top-right",
        timeout: 2500,
        closeButton: true,
        icon: true,
        rtl: false,
      });
    }

  } catch (err) {
    console.error(err)
  }
}

const openForm = (type) => {
  closeAllRegions();
  showRegionDetailComponent.value = type;
  showRegion.value = true;
};

const onContractSelected = (item) => {
  if (selectedContracts.value.includes(item)) {
    selectedContracts.value = selectedContracts.value.filter(x => x.id !== item.id);
  } else {
    selectedContracts.value.push(item);
  }
  //affectedContracts.value = selectedContracts.value.map(el => el.id)
  affectedContracts.value = []
  selectedContracts.value.forEach(el => {
    affectedContracts.value.push({
      id: el.id,
      token: el.token,
      holder: el.holder_name + ' ' + el.holder_surname,
      holder_token: el.holder_token
    })
  })
};

const onInvoiceSelected = (item) => {
  if (selectedInvoices.value.includes(item)) {
    selectedInvoices.value = selectedInvoices.value.filter(x => x.id !== item.id);
  } else {
    selectedInvoices.value.push(item);
  }
  affectedContracts.value = []
  selectedInvoices.value.forEach(el => {
    if (affectedContracts.value.find(x => x.id == el.contract)) return
    affectedContracts.value.push({
      id: el.contract,
      token: el.contract
    })
  })
  affectedInvoices.value = selectedInvoices.value.map(el => el.id)
};

const closeAllRegions = () => {
  // Tanquem tots els components

  showRegionDetailComponent.value = null;

  // Tanquem region
  showRegion.value = false;
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

onMounted(() => {
  const date = new Date();
  endowment_date.value = date.getFullYear()
});

watch(() => selectionType.value, (newVal) => {
  filter_date_start.value = null
  filter_date_end.value = null
  affectedContracts.value = []
  selectedContracts.value = []
})

watch([affectedContracts, endowment_date], () => {
  let data = {
    contracts: affectedContracts.value,
    endowment_date: endowment_date.value
  }
  emit('changed', data)
})

watch([filter_date_start, filter_date_end], () => {
  getData();
});

</script>

<template>
  <div id="wrapper" class="p-6 text-gray-800">
    <h2 class="text-xl font-semibold mb-4">{{ $t('common.select') }} {{ $t('common.contracts') }} {{ $t('common.and') }} {{ $t('claim_block.affected_invoices') }}</h2>
    <div class="grid grid-cols-2 gap-8">
      <div class="grid grid-cols-2 gap-4">
        <div class="grid grid-rows gap-5 mt-3">
          <label class="flex items-center">
            <input type="radio" value="PAYDATE" v-model="selectionType" class="mr-2">
            {{ $t('billing_block.payment_date') }}
          </label>
          <label class="flex items-center">
            <input type="radio" value="DUEDATE" v-model="selectionType" class="mr-2">
            {{ $t('common.due_date') }}
          </label>
          <label class="flex items-center">
            <input type="radio" value="TERMINATIONDATE" v-model="selectionType" class="mr-2">
            {{ $t('contract_block.termination_end_date') }}
          </label>
          <label class="flex items-center">
            <input type="radio" value="SPCUT" v-model="selectionType" class="mr-2">
            {{ $t('service_block.supply_cut_date') }}
          </label>
          <label class="flex items-center">
            <input type="radio" value="CONTR" v-model="selectionType" class="mr-2">
            {{ $t('common.select') }} {{ $t('common.contracts') }}
          </label>
          <!-- <label class="flex items-center">
            <input type="radio" value="INV" v-model="selectionType" class="mr-2">
            {{ $t('Selecció de factures') }}
          </label> -->
        </div>

      </div>
      <div
        v-if="selectionType == 'PAYDATE' || selectionType == 'DUEDATE' || selectionType == 'TERMINATIONDATE' || selectionType == 'SPCUT'"
        class="mt-6">
        <div class="grid grid-cols-[auto,1fr] gap-4 my-2 items-center">
          <span class="text-gray-500 font-medium">{{ $t('common.from') }}</span>
          <AtomsInputDate v-model="filter_date_start" class="w-full" />
          <span class="text-gray-500 font-medium">{{ $t('common.to') }}</span>
          <AtomsInputDate v-model="filter_date_end" class="w-full" />
        </div>
      </div>

      <div v-else-if="selectionType == 'CONTR' || selectionType == 'INV'" class="mt-6">
        <div>
          <ButtonSeleccio @click="openForm(selectionType)">
            {{ selectionType == 'CONTR' ? `${$t('common.select')} ${$t('common.contracts')}` : `${$t('common.select')} ${$t('invoices')}` }}
          </ButtonSeleccio>
        </div>
      </div>
      <span></span>
      <div class="gap-4 my-2 grid grid-cols-1 items-end justify-items-end">
        <div
          class="flex justify-end mt-8 p-4 bg-gray-100 rounded-md border boder-slate-500 w-full max-w-md">
          <span class="text-gray-700">
            {{ $t("contract_block.affected_contracts") }}: {{ affectedContracts.length }}
          </span>
          <button v-if="affectedContracts.length > 0" @click="openForm('AffectedContractsRegion')"
            class="p-1 px-2 border border-slate-500 rounded-lg hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:eye" />
          </button>
        </div>
        <div class="w-[200px] flex items-center gap-2 mt-2">
          <span class="text-gray-500 font-medium w-[150px]">{{ $t('contract_block.endowment_year') }}</span>
          <input type="number" v-model="endowment_date" class="input text-center w-[80px]" />
        </div>
      </div>

    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[60%]': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddContracts v-if="showRegionDetailComponent === 'CONTR'" :selected_items="selectedContracts"
          @item-clicked="onContractSelected" :multiple="true" />
        <AddInvoices v-if="showRegionDetailComponent === 'INV'" :selected_items="selectedInvoices"
          @item-clicked="onInvoiceSelected" :multiple="true" />
        <AffectedContracts v-if="showRegionDetailComponent === 'AffectedContractsRegion'" :contracts="affectedContracts"
          :contract_tokens="null" @show-subregion="handleSubRegionEvent" />
      </div>
    </div>
  </div>
</template>
