<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import ClaimRequestDetail from '../molecules/ClaimRequestDetail.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '../molecules/ChangeStatus.vue';
import ExploitationRegion from '../organisms/ExploitationRegion.vue';
import ContractRegion from './ContractRegion.vue';
import ContractRequestRegion from './ContractRequestRegion.vue';
import SupplyPointRegion from './SupplyPointRegion.vue';
import PersonRegion from './PersonRegion.vue';
import ContractMiniDetail from '../molecules/ContractMiniDetail.vue';
import InvoiceMiniDetail from '../molecules/InvoiceMiniDetail.vue';
import ClaimRequestContractChange from '../atoms/ClaimRequestContractChange.vue';
import ClaimStepRegion from './ClaimStepRegion.vue';


const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed']);
const router = useRouter();
const { $ClaimRequestApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const SubRegion = ref(props.isSubRegionOpen);
const activeTab = ref('contracts');

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const token_pending = ref(null)
const token_accepted = ref(null)
const token_cancelled = ref(null)
const token_step_vulnerable = ref(null)


const getData = async () => {
  pending.value = true;
  error.value = null;

  try {
    token_pending.value = await $ConfigProjectApiService.get('claim_request_status_pending_token');
    token_accepted.value = await $ConfigProjectApiService.get('claim_request_status_accepted_token');
    token_cancelled.value = await $ConfigProjectApiService.get('claim_request_status_cancelled_token');
    token_step_vulnerable.value = await $ConfigProjectApiService.get('claim_step_vulnerability_request_token');
    const result = await $ClaimRequestApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

getData();

const onClickCheck = async () => {
  //TODO: CAN THE MANAGEMENT BE MODIFIED?
}

const goNextClaimStep = async () => {
  let response = await $ClaimRequestApiService.updateClaimRequestNextStep(data.value.id)
  refresh()
}

const refresh = async () => {
  getData()
  emit('changed')
}

const acceptClaim = async () => {
  let save_data = {
    id: props.id,
    status_token: token_accepted.value
  }

  let response = await $ClaimRequestApiService.save(save_data)
  refresh()
}

const denyClaim = async () => {
  let save_data = {
    id: props.id,
    status_token: token_cancelled.value
  }

  let response = await $ClaimRequestApiService.save(save_data)
  refresh()
}

const downloadClaimExcel = async () => {
  try {
    let response = await $ClaimRequestApiService.getClaimExcelFile(props.id);
    const utf8BOM = "\uFEFF";
    const csvData = utf8BOM + response;

    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;

    let filename = `${data.value.token}.csv`;
    a.download = filename;

    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error(err);
  }
};


const downloadClaimLetters = async () => {
  try {
    let response = await $ClaimRequestApiService.downloadClaimDocument(props.id);
    const blob = new Blob([response], { type: 'application/pdf' });

    const url = window.URL.createObjectURL(blob);
    //get todays date in string with the format YYYYMMDD without '-' or '_'
    
    const date = new Date();
    const today = date.getFullYear().toString() + 
                      String(date.getMonth() + 1).padStart(2, '0') + 
                      String(date.getDate()).padStart(2, '0');
    const a = document.createElement('a');
    a.href = url;
    a.download = `${data.value.step.document_type.token}${today}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error(err);
  }
}

const updateSubRegion = function () {
  getData();
  closeSubRegion();
  emit('changed')
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

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}


</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('billing_block.non_payment') }}
        </H1Region>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <ClaimRequestDetail @show-detail="showDetail" @change="updateSubRegion()" :id="props.id" :data="data"
          :isSubRegion="isSubRegion" />
        <AtomsTabs>

          <li class="me-2">
            <a href="#tab_contracts" @click.prevent="setActiveTab('contracts')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'contracts', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'contracts' }">
              <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />
              {{ $t("common.contracts") }}
            </a>
          </li>

          <li class="me-2">
            <a href="#tab_invoices" @click.prevent="setActiveTab('invoices')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'invoices', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'invoices' }">
              <Icon name="fa6-solid:file-invoice" class="display-inline mr-2" />
              {{ $t("invoices") }}
            </a>
          </li>

          <li class="me-2">
            <a href="#tab_contract_change" @click.prevent="setActiveTab('contract_change')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'contract_change', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'contract_change' }">
              <Icon name="fa6-regular:square-minus" class="display-inline mr-2" />
              {{ $t("common.changes") }}
            </a>
          </li>

        </AtomsTabs>
        <div id="contract_tabpanels">
          <section v-show="activeTab === 'contracts'" role="tabpanel" id="tab_contracts"
            class="bg-white antialiased py-3 h-[50vh] overflow-y-auto border-b rounded">
            <div v-if="data.contracts.length > 0" class="">
              <ContractMiniDetail :item="data.contracts" @show-detail="showDetail" />
            </div>
            <hr v-if="data.contract_requests.length > 0" class="mt-10 opacity-0" />
            <div v-if="data.contract_requests.length > 0">
              <span class="text-slate-500 font-semibold">
                {{ t('contract_requests') }}
              </span>
              <ContractMiniDetail :item="data.contract_requests" @show-detail="showDetail" :is_request="true" />
            </div>
            <div v-if="data.contracts.length == 0 && data.contract_requests.length == 0">
              <span class="text-gray-700 mt-1 font-medium italic text-sm bg-yellow-100 rounded-md px-2 py-1">
                {{ t('common.no_data_found') }}
              </span>
            </div>
          </section>

          <section v-show="activeTab === 'invoices'" role="tabpanel" id="tab_invoices"
            class="bg-white antialiased py-3 h-[50vh] overflow-y-auto border-b rounded">
            <div v-if="data.invoices.length > 0">
              <InvoiceMiniDetail :item="data.invoices" @show-detail="showDetail" />
            </div>
            <div v-else>
              <span class="text-gray-700 mt-1 font-medium italic text-sm bg-yellow-100 rounded-md px-2 py-1">
                {{ t('common.no_data_found') }}
              </span>
            </div>
          </section>

          <section v-show="activeTab === 'contract_change'" role="tabpanel" id="tab_contract_change"
            class="bg-white antialiased py-3">
            <ClaimRequestContractChange :id="data.id" :object="data" />
          </section>
        </div>
      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- SUBREGIONS AQUI -->
        <ExploitationRegion v-if="showRegionDetailComponent === 'ExploitationRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ContractRequestRegion v-if="showRegionDetailComponent === 'ContractRequestRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <PersonRegion v-if="showRegionDetailComponent === 'PersonRegion'" :id="regionDetailId" :isSubRegion="true" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true" />
        <ClaimStepRegion v-if="showRegionDetailComponent === 'ClaimStepRegion'" :id="regionDetailId"
          :isSubRegion="true" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
