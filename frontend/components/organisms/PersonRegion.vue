<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import PersonDetail from '../molecules/PersonDetail.vue';
import CommitmentDepositRegion from './CommitmentDepositRegion.vue';
import PersonContractsList from '../molecules/PersonContractsList.vue';
import VulnerabilityRequestList from '../molecules/VulnerabilityRequestList.vue';
import VulnerabilityRequestIndividualEdit from './VulnerabilityRequestIndividualEdit.vue';
import CommunicationMiniDetail from '../molecules/CommunicationMiniDetail.vue';
import CommunicationRegion from './CommunicationRegion.vue';
import AddNewCall from '../molecules/AddNewCall.vue';
// Importar el component SupplyPointRegion per a la subregion
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import PiggyBankRegion from './PiggyBankRegion.vue';
import { usePermissions } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';
import AddPiggyBankBalance from '../molecules/AddPiggyBankBalance.vue';
import MassiveInvoiceDownload from './MassiveInvoiceDownload.vue';
import InvoiceMiniDetail from '../molecules/InvoiceMiniDetail.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import PersonChangeHistory from '../molecules/PersonChangeHistory.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion']);
const { permissions, loading } = usePermissions();
const router = useRouter();
const { $PersonApiService, $PersonAddressApiService, $PersonContactApiService, $PersonBankApiService, $InvoiceApiService } = useNuxtApp();
const pending = ref(true);
const reload = ref(false);
const error = ref(null);
const data = ref(null);
const activeTab = ref('observations');
const SubRegion = ref(props.isSubRegionOpen);
const vulnerabilityRequestNumber = ref(0)
const modificationsCount = ref(0);

const important_observations = ref([])
const show_important_observations = ref(false)

const totalObservations = ref(0);
const callRegisterNumber = ref(0);
const new_call = ref(null);

const objectPermissions = ref(null);

const loadedTabs = ref(new Set(['observations']));
const addresses = ref([]);
const contacts = ref([]);
const banks = ref([]);
const invoices = ref([]);
const invoicesPagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  isFiltered: true,
});

const getInvoices = async (page = 1) => {
  const res = await $InvoiceApiService.getAll(
    '', [], page,
    null, false, null,
    true, null, null,
    null, null, [],
    null, [], null,
    null, props.id
  );
  invoices.value = res.results;
  invoicesPagination.value.page = page;
  invoicesPagination.value.total = res.count || 0;
  invoicesPagination.value.totalPages = Math.ceil((res.count || 0) / invoicesPagination.value.perPage);
}

const onInvoicesPageChange = (newPage) => {
  getInvoices(newPage);
}

const loadTabData = async (tab) => {
  if (loadedTabs.value.has(tab)) return;

  try {
    if (tab === 'address') {
      const res = await $PersonAddressApiService.getAll(props.id);
      addresses.value = res.results;
    } else if (tab === 'contact') {
      const res = await $PersonContactApiService.getAll(props.id);
      contacts.value = res.results;
    } else if (tab === 'payment_methods') {
      const res = await $PersonBankApiService.getAll(props.id);
      banks.value = res.results;
    }
    await getInvoices();
    // CommunicationMiniDetail handle its own load
    // ObservationList handle its own load
    // CallRegisterList handle its own load
    // VulnerabilityRequestList handle its own load
    // PersonChangeHistory handle its own load

    loadedTabs.value.add(tab);
  } catch (err) {
    console.error(`Error loading tab ${tab}:`, err);
  }
}

const updateVulnerabilityRequestCount = (num) => {
  vulnerabilityRequestNumber.value = num;
}

const updateObservationCount = (num) => {
  totalObservations.value = num;
}

const updateCallRegisterCount = (num) => {
  callRegisterNumber.value = num;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $PersonApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async (load = true) => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = load;

  try {
    const result = await $PersonApiService.getDetail(props.id);
    console.log('result', result);
    result.contracts_count = (result.contracts_holder_count || 0) + (result.contracts_owner_count || 0) + (result.contracts_tenant_count || 0);
    data.value = result;

    important_observations.value = result.important_observations;

    // Reset loaded tabs on new person
    loadedTabs.value = new Set();

    // Initial load for active tab
    nextTick(() => {
      loadTabData(activeTab.value);
    });

  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  await getData();
  if (important_observations?.value?.length > 0) {
    show_important_observations.value = true
  }
  closeSubRegion();
  setActiveTab('contracts');
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
    if (important_observations?.value?.length > 0) {
      show_important_observations.value = true
    }
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    pending.value = false;
  }
});

const handleChange = async (reload = false) => {
  let currentTab = activeTab.value;
  setActiveTab(null);
  await getData(true);
  setActiveTab(currentTab);
  closeSubRegion();
}

const startCall = async (item) => {
  new_call.value = {
    contact: item,
    contract: null,
  };
}

const handleNewCall = () => {
  new_call.value = null;
  handleChange();
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

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const edit = function () {
  return navigateTo('/contract/persons/edit/' + props.id);
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
  if (tab) loadTabData(tab);
}

const addWalletBalance = () => {
  showDetail('AddPiggyBankBalance', props.id);
}

const newCommunication = () => {
  return navigateTo({
    path: '/communication/communications/add',
    query: {
      step: 1,
      person_id: props.id,
    }
  })
}
</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error"
      class="flex flex-col items-center justify-center h-full min-h-[400px] text-center p-6 bg-red-50 rounded-xl m-4 border border-red-100">
      <Icon name="fa6-solid:circle-exclamation" class="text-red-400 text-5xl mb-4" />
      <p class="text-red-800 font-semibold mb-2">Error: {{ error.message }}</p>
      <button @click="getData"
        class="bg-white px-6 py-2 rounded-full shadow-sm border border-red-200 text-red-600 hover:bg-red-50 transition-colors font-medium">
        {{ $t('common.load_again') }}
      </button>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">

      <div v-if="show_important_observations"
        class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
          <button @click="show_important_observations = false"
            class="absolute top-4 right-4 text-gray-500 hover:text-gray-700">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>
          <div class="text-center">
            <div class="mb-4">
              <Icon name="fa6-solid:circle-exclamation" class="text-yellow-500 text-4xl mb-3" />
              <!-- <h2 class="text-xl font-bold text-gray-800 mb-2">{{ $t('Observacions importants') }}</h2> -->
            </div>
            <div class="bg-yellow-50 p-4 rounded-lg text-left max-h-[60vh] overflow-y-auto">
              <ul class="list-disc list-inside space-y-2">
                <li v-for="observation in important_observations" :key="observation.id" class="text-gray-700">
                  {{ observation.observation }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div v-if="new_call" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-auto relative">
          <AddNewCall :data="new_call" @exit="handleNewCall" />
        </div>
      </div>

      <div v-if="show_important_observations || new_call"
        class="fixed inset-0 bg-black bg-opacity-50 h-[150vh] z-20 flex items-center justify-center">
      </div>

      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('person') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption @click="edit">
            <Icon name="fa6-solid:user-pen" class="display-inline mr-2" />
            {{ t('common.modify') }} {{ t('person') }}
          </DropdownOption>
          <DropdownOption @click="newCommunication">
            <Icon name="fa6-solid:envelope" class="display-inline mr-2" />
            {{ t('customer_service_block.new_comm') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.add')} ${t('contract_block.balance')}`" @click="addWalletBalance"
            :disabled="!data.piggy_bank">
            <Icon name="fa6-solid:wallet" class="display-inline mr-2" />
            {{ t('common.add') }} {{ t('contract_block.balance') }}
          </DropdownOption>
          <DropdownOption :name="`${t('common.massive_invoice_download')}`" @click="showDetail('MassiveInvoiceDownload', null)"
            :disabled="!data.piggy_bank">
            <Icon name="fa6-solid:download" class="display-inline mr-2" />
            {{ t('common.massive_invoice_download') }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>

        <PersonDetail :id="props.id" :data="data" @show-detail="showDetail" :isSubRegion="props.isSubRegion" />


        <AtomsTabs>
          <li class="me-2">
            <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }"
              aria-current="page">
              <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />{{ $t("common.observations") }} ({{
                data.observations_count || 0 }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_call_register" @click.prevent="setActiveTab('call_register')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'call_register', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'call_register' }">
              <Icon name="fa6-solid:phone" class="display-inline mr-2" /> {{ $t("contract_block.call_register") }} ({{
                data.call_register_count || 0 }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_contracts" @click.prevent="setActiveTab('contracts')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'contracts', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'contracts' }"
              aria-current="page">
              <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />{{ $t("common.contracts") }} ({{
                (data.contracts_count || 0) }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_payment_methods" @click.prevent="setActiveTab('payment_methods')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'payment_methods', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'payment_methods' }">
              <Icon name="fa6-solid:credit-card" class="display-inline mr-2" /> {{ $t("common.bank_data") }} ({{
                data.banks_count || 0 }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_address" @click.prevent="setActiveTab('address')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'address', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'address' }">
              <Icon name="fa6-solid:address-card" class="display-inline mr-2" /> {{ $t("address_block.addresses") }} ({{
                data.addresses_count || 0 }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_contact" @click.prevent="setActiveTab('contact')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'contact', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'contact' }">
              <Icon name="fa6-solid:address-book" class="display-inline mr-2" /> {{ $t("common.contact") }} ({{
                data.contacts_count || 0 }})
            </a>
          </li>
          <li v-if="permissions?.permissions?.view_billing" class="me-2">
            <a href="#tab_invoices" @click.prevent="setActiveTab('invoices')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'invoices', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'invoices' }">
              <Icon name="fa6-solid:envelope" class="display-inline mr-2" />
              {{ $t("invoices") }} ({{ invoicesPagination.total || invoices?.length || 0 }})
            </a>
          </li>
          <li v-if="permissions?.permissions?.view_customer_service" class="me-2">
            <a href="#tab_communication" @click.prevent="setActiveTab('communication')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'communication', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'communication' }">
              <Icon name="fa6-solid:envelope" class="display-inline mr-2" />
              {{ $t("common.comms") }} ({{ data.communications_count || 0 }})
            </a>
          </li>
          <!-- <li class="me-2">
            <a href="#tab_piggy_banks" @click.prevent="setActiveTab('piggy_banks')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'piggy_banks', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'piggy_banks' }">
              <Icon name="fa6-solid:piggy-bank" class="display-inline mr-2" />
              {{ $t("payment") }} ({{ data.piggy_banks?.length || 0 }})
            </a>
          </li> -->
          <li class="me-2" v-if="data.is_juridic">
            <a href="#tab_cnae" @click.prevent="setActiveTab('cnae')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'cnae', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'cnae' }">
              <Icon name="fa6-solid:industry" class="display-inline mr-2" /> {{ $t("contract_block.cnae") }} ({{
                data.cnaes?.length ||
                0 }})
            </a>
          </li>
          <li class="me-2" v-if="!data.is_juridic">
            <a href="#tab_vulnerability" @click.prevent="setActiveTab('vulnerability')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'vulnerability', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'vulnerability' }">
              <Icon name="fa6-solid:shield-halved" class="display-inline mr-2" />
              {{ $t("contract_block.short_vulnerability_req") }} ({{ vulnerabilityRequestNumber || 0 }})
            </a>
          </li>
          <li class="me-2" v-if="data.deliquency">
            <a href="#tab_deliquency" @click.prevent="setActiveTab('deliquency')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'deliquency', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'deliquency' }">
              <Icon name="fa-solid:user-slash" class="display-inline mr-2" /> {{ $t("contract_block.deliquency") }}
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_modifications" @click.prevent="setActiveTab('modifications')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'modifications', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'modifications' }">
              <Icon name="fa6-solid:address-card" class="display-inline mr-2" /> {{ $t("common.modifications") }} ({{ modificationsCount || 0 }})
            </a>
          </li>
        </AtomsTabs>


        <div id="cluster_tabpanels">

          <section v-if="activeTab === 'call_register'" role="tabpanel" id="tab_call_register"
            class="bg-white antialiased">
            <MoleculesCallRegisterList v-if="data" @update:count="updateCallRegisterCount" :reload="reload"
              :person_id="props.id" :max_height="'65vh'">
            </MoleculesCallRegisterList>
          </section>

          <section v-if="activeTab === 'piggy_banks'" role="tabpanel" id="tab_piggy_banks"
            class="bg-white antialiased py-3">
            <div v-if="data.piggy_banks && data.piggy_banks.length != 0"
              class="m-4 rounded-md border border-gray-300 divide-y">
              <div class="group grid grid-cols-2 divide-x text-sm leading-4 ">
                <span class="p-2 pl-3 text-slate-600"> {{ t('contract') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('common.total') }} </span>
              </div>
              <div v-for="item in data.piggy_banks"
                class="group grid grid-cols-2 divide-x text-sm leading-4 transition-all duration-100">
                <div class="footering text-slate-500 p-2 w-full">
                  <div v-if="!props.isSubRegion" class="flex items-center gap-5">
                    <button @click="showDetail('ContractRegion', item.contract_id)"
                      class="text-start text-sky-500 underline hover:text-sky-600 hover:no-underline">
                      {{ item.contract_token }}</button>

                    <button @click="showDetail('PiggyBankRegion', item.id)"
                      class="text-start text-sky-500 underline flex items-center gap-1 hover:text-sky-600">
                      <Icon name="fa6-solid:piggy-bank" />
                    </button>
                  </div>
                  <span v-else>{{ item.contract_token }}</span>
                </div>
                <div class="footering text-slate-500 p-2 w-full">
                  {{ formatMoneyWithCurrency(item.amount) }}
                </div>
              </div>
            </div>
          </section>

          <section v-if="activeTab === 'contracts'" role="tabpanel" id="tab_contracts"
            class="bg-white antialiased py-3">
            <div>
              <PersonContractsList :personId="props.id" :isSubRegion="props.isSubRegion" @show-detail="showDetail" />
            </div>

            <div v-if="(data.contracts_count === 0)" class="footering text-slate-500 p-2">
              {{ t('common.no_records') }}
            </div>
          </section>
          <section v-if="activeTab === 'observations'" role="tabpanel" id="tab_observations"
            class="bg-white antialiased py-3">
            <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount" :reload="reload"
              parent_entity="person" url_entity="person" :id="props.id" module="coredata" :allow_mark="true">
            </MoleculesObservationList>
          </section>
          <section v-if="activeTab === 'payment_methods'" role="tabpanel" id="tab_payment_methods"
            class="bg-white antialiased py-3">
            <div v-if="banks && banks.length != 0" class="m-4 rounded-md border border-gray-300 divide-y bg-white">
              <div class="group grid grid-cols-[100px,2fr,1fr,1fr,1fr] divide-x text-sm leading-4 ">
                <span class="p-2 pl-3 flex items-center text-slate-600"> {{ t('default') }} </span>
                <span class="p-2 pl-3 flex items-center text-slate-600"> {{ t('common.iban') }} </span>
                <span class="p-2 pl-3 flex items-center text-slate-600"> {{ t('contract_block.holder') }} </span>
                <span class="p-2 pl-3 flex items-center text-slate-600"> {{ t('common.person_id') }} </span>
                <span class="p-2 pl-3 flex items-center text-slate-600"> {{ t('common.role') }} </span>
              </div>
              <div v-for="item in banks"
                class="group grid grid-cols-[100px,2fr,1fr,1fr,1fr] divide-x text-sm leading-4 transition-all duration-100"
                :class="{ 'opacity-50': !item.is_active }">
                <div class="p-2 text-slate-800">
                  <input type="radio" name="default_bank" class="ml-2" :value="item.id" :checked="item.is_default"
                    :disabled="true" />
                </div>
                <div class="footering text-slate-500 p-2">
                  <AtomsIBAN :value="item.iban" />
                </div>
                <div class="relative group footering text-slate-500 p-2 w-full">
                  {{ item.name }}
                </div>
                <div class="relative group footering text-slate-500 p-2 w-full">
                  {{ item.dni }}
                </div>
                <div class="relative group footering text-slate-500 p-2 w-full">
                  {{ item.role }}
                </div>
              </div>
            </div>
            <div v-else class="footering text-slate-500 p-2">
              {{ t('No hi ha dades bancàries') }}
            </div>
          </section>
          <section v-if="activeTab === 'address'" role="tabpanel" id="tab_address" class="bg-white antialiased py-3">
            <div v-if="addresses && addresses?.filter(a => a.is_active).length > 0"
              class="m-4 rounded-md border border-gray-300 divide-y bg-white">
              <div class="group grid grid-cols-[100px,2fr,1fr] divide-x text-sm leading-4 ">
                <span class="p-2 pl-3 text-slate-600"> {{ t('contract_block.billing_address') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('address_block.address') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t("contract_block.attention_to") }} </span>
              </div>
              <div v-for="item in addresses"
                class="group grid grid-cols-[100px,2fr,1fr] divide-x text-sm leading-4 transition-all duration-100">
                <div v-if="item.is_active" class="p-2 text-slate-800">
                  <input type="radio" name="billing" class="ml-2" :value="item.address?.id" :checked="item.is_billing"
                    :disabled="true" />
                </div>
                <div v-if="item.is_active" class="relative group footering text-slate-500 p-2 w-full">
                  {{ item.address?.address_complete }} - {{ item.address?.postal_code }}, {{ item.address?.province_name
                  }}
                </div>
                <div v-if="item.is_active" class="relative group footering text-slate-500 p-2 w-full">
                  {{ item.attention_to }}
                </div>
              </div>
            </div>
            <div v-else class="footering text-slate-500 p-2">
              {{ t('common.no_records') }}
            </div>
          </section>
          <section v-if="activeTab === 'contact'" role="tabpanel" id="tab_contact" class="bg-white antialiased py-3">
            <div v-if="contacts && contacts.length != 0"
              class="m-4 rounded-md border border-gray-300 divide-y bg-white">
              <div class="group grid grid-cols-[100px,1fr,1fr,1fr] divide-x text-sm leading-4 ">
                <span class="p-2 pl-3 text-slate-600"> {{ t('default') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('common.tlf') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('common.email') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('common.role') }} </span>
              </div>
              <div v-for="item in contacts"
                class="group grid grid-cols-[100px,1fr,1fr,1fr] divide-x text-sm leading-4 transition-all duration-100">
                <div class="p-2 text-slate-800">
                  <input type="radio" name="default" class="ml-2" :value="item.id" :checked="item.is_default"
                    :disabled="true" />
                </div>
                <div class="relative group footering text-slate-500 p-2 w-full">
                  <button @click="startCall(item)" class="text-sky-500 underline hover:no-underline">{{ item.phone
                  }}</button>
                </div>
                <div class="relative group footering text-slate-500 p-2 w-full">
                  <a :href="'mailto:' + item.email" class="text-sky-500 underline hover:no-underline">{{ item.email
                  }}</a>
                </div>
                <div class="relative group footering text-slate-500 p-2 w-full">
                  {{ item.role }}
                </div>
              </div>
            </div>
            <div v-else class="footering text-slate-500 p-2">
              {{ t('common.no_records') }}
            </div>
          </section>
          <section v-if="data.is_juridic" v-show="activeTab === 'cnae'" role="tabpanel" id="tab_cnae"
            class="bg-white antialiased py-3">
            <div v-if="data.cnaes && data.cnaes.length != 0"
              class="m-4 rounded-md border border-gray-300 divide-y bg-white">
              <div class="group grid grid-cols-[1fr,3fr] divide-x text-sm leading-4">
                <span class="p-2 pl-3 text-slate-600"> {{ t('common.code') }} </span>
                <span class="p-2 pl-3 text-slate-600 flex items-center"> {{ t('common.description') }} </span>
              </div>
              <div v-for="item in data.cnaes"
                class="group grid grid-cols-[1fr,3fr] divide-x text-sm leading-4 transition-all duration-100">
                <div class="relative group footering text-slate-500 p-2 w-full">
                  {{ item.cnae.token }}
                </div>
                <div class="relative group footering text-slate-500 p-2 w-full">
                  {{ item.cnae.description }}
                </div>
              </div>
            </div>
            <div v-else class="footering text-slate-500 p-2">
              {{ t('common.no_records') }}
            </div>
          </section>

          <section v-if="activeTab === 'vulnerability'" role="tabpanel" id="tab_vulnerability"
            class="bg-white antialiased p-3">
            <VulnerabilityRequestList :person_id="props.id" :isSubRegion="isSubRegion" @show-detail="showDetail"
              @update:count="updateVulnerabilityRequestCount" />
          </section>

          <section v-if="activeTab === 'invoices'" role="tabpanel" id="tab_invoices" class="bg-white antialiased">
            <section class="mb-10 mt-2">
              <InvoiceMiniDetail :item="invoices" @show-detail="showDetail" :isSubRegion="isSubRegion" />
              <div class="border-t border-gray-100 p-2" v-if="invoicesPagination.totalPages > 1">
                <Pagination :pagination="invoicesPagination" @update:page="onInvoicesPageChange" />
              </div>
              </section>
          </section>


          <section v-if="activeTab === 'communication' && permissions?.permissions?.view_customer_service"
            role="tabpanel" id="tab_communication" class="bg-white antialiased p-3">
            <CommunicationMiniDetail :person_ids="[props.id]" @show-detail="showDetail" :max_height="'60vh'" />
          </section>

          <section v-if="data.deliquency" v-show="activeTab === 'deliquency'" role="tabpanel" id="tab_deliquency"
            class="bg-white antialiased p-3">
            <div class="p-2 mt-2 border-b border-slate-300">
              <div class="grid grid-cols-2 gap-3">
                <FieldDetail :label='$t("contract_block.debt_last_date")'
                  :value="data.deliquency.last_debt_data ? formatDate(data.deliquency.last_debt_data) : '-'">
                </FieldDetail>
                <div class="flex items-center ml-2 text-slate-500">
                  <input v-model="data.deliquency.is_debtor" type="checkbox" id="is_debtor" name="is_debtor"
                    class="checkbox" :disabled="true" />
                  <label for="is_debtor" class="ml-2"> {{ t('contract_block.debtor') }}</label>
                </div>
                <FieldDetail :label='$t("common.total")'
                  :value="data.deliquency.debt_amount ? formatMoneyWithCurrency(data.deliquency.debt_amount) : '-'">
                </FieldDetail>
              </div>
            </div>
          </section>

          <section v-if="activeTab === 'modifications'" role="tabpanel" id="tab_modifications"
            class="bg-white antialiased">
            <PersonChangeHistory :person_id="props.id" :person_token="data.token" :canChange="objectPermissions?.can_change"
              @update:count="(n) => modificationsCount = n" />
          </section>

        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <OrganismsSupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true"></OrganismsSupplyPointRegion>
        <OrganismsContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true"></OrganismsContractRegion>
        <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'" :id="regionDetailId"
          :isSubRegion="true"></CommitmentDepositRegion>
        <PiggyBankRegion
          v-if="showRegionDetailComponent === 'PiggyBankRegion' || showRegionDetailComponent === 'PersonPiggyBankRegion'"
          :id="regionDetailId" :isSubRegion="true" :isPerson="showRegionDetailComponent === 'PersonPiggyBankRegion'"
          :canChange="objectPermissions?.can_change">
        </PiggyBankRegion>
        <VulnerabilityRequestIndividualEdit v-if="showRegionDetailComponent === 'VulnerabilityRequestRegion'"
          :vulnerability_id="regionDetailId" :isSubRegion="true"></VulnerabilityRequestIndividualEdit>
        <CommunicationRegion v-if="showRegionDetailComponent === 'CommunicationRegion'" :id="regionDetailId"
          :isSubRegion="true" @changed="handleChange"></CommunicationRegion>
        <AddPiggyBankBalance v-if="showRegionDetailComponent === 'AddPiggyBankBalance'"
          :personId="parseInt(regionDetailId)" :data="data.piggy_bank" @change="handleChange" @close="closeSubRegion" />
        <MassiveInvoiceDownload v-if="showRegionDetailComponent === 'MassiveInvoiceDownload'"
          :person_id="parseInt(props.id)" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId" :isSubRegion="true"
          @close-subregion="closeSubRegion" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>