<script setup>
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import ContractDetail from '~/components/molecules/ContractDetail.vue';
import BankDetail from '~/components/molecules/BankDetail.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonBankSelect from '~/components/molecules/PersonBankSelect.vue';
import CompanyBankSelect from '~/components/molecules/CompanyBankSelect.vue';
import AddAddress from '~/components/molecules/AddAddress.vue';
import AddContracts from '~/components/molecules/AddContracts.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import SelectPaymentType from '~/components/molecules/SelectPaymentType.vue';

const route = useRoute()
const router = useRouter()
const { $ContractApiService, $ConfiglistApiService, $GeneralPaymentApiService, $GeneralInvoiceApiService, $PersonApiService, $PersonAddressApiService, $ExploitationApiService } = useNuxtApp();
const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);

const showRegionComponent = ref(null);
const showRegionComponentDetail = ref(null);
const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const contract_id = ref(route.params.id)
const general_invoice_id = ref(route.query.id)
const pending = ref(true);
const loading = ref(false);
const loading_all = ref(false);
const saving = ref(false);

const contract = ref(null);
const general_invoice = ref(null);
const general_invoice_contracts = ref([]);
const persons = ref([]);

const paymentTypeOptionsById = ref({});

const onPaymentTypesLoaded = ({ byId }) => {
    paymentTypeOptionsById.value = byId;
};
const selectedPaymentMethod = ref(null);

const selectedBillingAddress = ref(null);
const selectedContactAddress = ref(null);
const selectedBankDebit = ref(null);
const selectedCompanyBankDebit = ref(null);

const companyBanks = ref([]);
const localCompany = ref(null);

const resolvedCompany = computed(() => {
  if (localCompany.value) {
    return {
      ...localCompany.value,
      company_banks: companyBanks.value?.length ? companyBanks.value : localCompany.value.company_banks
    };
  }
  let comp = contract.value?.company || contract.value?.exploitation?.company;
  if (comp && typeof comp === 'object') {
    return {
      ...comp,
      company_banks: companyBanks.value?.length ? companyBanks.value : comp.company_banks
    };
  }
  if (companyBanks.value?.length) {
    return {
      name: t('company'),
      company_banks: companyBanks.value
    };
  }
  return null;
});

const is_electronic_invoice = ref(false);
const accounting_office = ref(null)
const managing_body = ref(null)
const processing_unit = ref(null)
const command = ref(null)
const record = ref(null)

const addressOptions = ref([]);


const fillPaymentFields = (payment) => {
    selectedPaymentMethod.value = payment?.type?.id;
    selectedBankDebit.value = payment?.IBAN;
    selectedCompanyBankDebit.value = payment?.company_iban || null;
    accounting_office.value = payment?.accounting_office;
    managing_body.value = payment?.managing_body;
    processing_unit.value = payment?.processing_unit;
    command.value = payment?.command;
    record.value = payment?.record;
    if (accounting_office.value || managing_body.value || processing_unit.value) {
        is_electronic_invoice.value = true;
    }
}

const getData = async (load = true) => {
    pending.value = load;
    let fullContract = null;
    try {
        persons.value = [];
        const data = await $ContractApiService.getMinimalDetail(contract_id.value);
        contract.value = data;

        if (general_invoice_id.value && general_invoice_id.value != '') {
            const response = await $GeneralInvoiceApiService.getDetail(general_invoice_id.value);
            general_invoice.value = response;

            general_invoice_contracts.value = response.contracts;
            selectedBillingAddress.value = response.address_billing?.id || null;
            selectedContactAddress.value = response.address_contact?.id || null;
            fillPaymentFields(response.payment);
        } else {
            general_invoice_contracts.value.push(contract.value);

            // New group: start from the addresses and payment of the contract we group from.
            // Values are copied; saving creates a new payment, the contract's own is left untouched.
            const detail = await $ContractApiService.getDetail(contract_id.value);
            fullContract = detail?.results ? detail.results[0] : detail;
            selectedBillingAddress.value = fullContract?.address_billing?.id || null;
            selectedContactAddress.value = fullContract?.address_contact?.id || null;
            fillPaymentFields(fullContract?.payment);
        }

        fillAddressOptions();

        // Resolució multinivell extrema de la companyia i els seus bancs
        let compId = (typeof contract.value?.company === 'object' ? contract.value?.company?.id : contract.value?.company) ||
                     (typeof contract.value?.exploitation?.company === 'object' ? contract.value?.exploitation?.company?.id : contract.value?.exploitation?.company);

        if (!compId && contract_id.value) {
            try {
                if (!fullContract) {
                    const detail = await $ContractApiService.getDetail(contract_id.value);
                    fullContract = detail?.results ? detail.results[0] : detail;
                }
                const cr = fullContract;
                let cc = cr?.company;
                if (!cc) {
                    let explId = typeof cr?.exploitation === 'object' ? cr?.exploitation?.id : cr?.exploitation;
                    if (!explId) {
                        const spExpl = cr?.supply_point_default?.exploitation || cr?.supply_point?.exploitation;
                        explId = typeof spExpl === 'object' ? spExpl?.id : spExpl;
                    }
                    if (explId) {
                        try {
                            const explDetail = await $ExploitationApiService.getDetail(explId);
                            cc = explDetail?.company || explDetail?.results?.[0]?.company;
                        } catch(e) {
                            console.error(e);
                        }
                    }
                }
                compId = typeof cc === 'object' ? cc?.id : cc;
            } catch(err) {
                console.error(err);
            }
        }
        if (!compId) {
            const lsComp = typeof window !== 'undefined' ? localStorage.getItem('company') : null;
            if (lsComp && lsComp !== 'undefined' && lsComp !== 'null') {
                compId = parseInt(lsComp, 10);
            }
        }
        if (!compId) {
            try {
                const compsResp = await $ExploitationApiService.getCompanies();
                if (compsResp?.results?.length > 0) {
                    compId = compsResp.results[0].id;
                }
            } catch(e) {
                console.error(e);
            }
        }

        if (compId) {
            try {
                try {
                    const compResp = await $ExploitationApiService.getCompany(compId);
                    if (compResp) {
                        localCompany.value = compResp;
                    }
                } catch(e) {
                    console.error(e);
                }
                const banksResp = await $ExploitationApiService.getCompanyBanks(compId);
                companyBanks.value = banksResp?.results || banksResp || [];

                if (companyBanks.value?.length === 1 && paymentTypeOptionsById.value[selectedPaymentMethod.value]?.token === 'BANK_TRANSFER' && !selectedCompanyBankDebit.value) {
                    selectedCompanyBankDebit.value = companyBanks.value[0];
                }
            } catch(e) {
                console.error(e);
            }
        }
    } catch (error) {
        console.error(error);
    } finally {
        pending.value = false;
    }
}

const fillAddressOptions = async (load = true) => {
    loading.value = load;
    let newAddressOptions = {};
    let newPersons = [];
    let added = [];
    var keys = ['holder_id', 'owner_id', 'tenant_id']

    for (const key of keys) {
        for (const invoice_contract of general_invoice_contracts.value) {

            if (invoice_contract[key]) {
                const targetId = Number(invoice_contract[key]);
                const existingIds = newPersons.length > 0 ? newPersons.map(p => Number(p.id)) : [];

                if (existingIds.includes(targetId)) {
                    continue;
                }
                if (newPersons.map(p => p.id).includes(invoice_contract[key])) {
                    continue;
                }
                let person = await $PersonApiService.getDetail(invoice_contract[key]);
                newPersons.push(person);
                added = added.concat(fillAddressFromPerson(person, newAddressOptions));
            }
        }
    }
    addressOptions.value = newAddressOptions;
    persons.value = newPersons;
    loading.value = false;
}

const fillAddressFromPerson = (person, targetOptions = null) => {
    var addresses = [];
    const options = targetOptions || addressOptions.value;

    if (person) {
        options[person.full_name] = [];
        if (person.addresses) {
            person.addresses.forEach((person_address) => {

                options[person.full_name].push({
                    value: person_address.id,
                    label: person_address.address_complete
                });
                addresses.push(person_address.id);
            });

            if (person.addresses.length == 0) {
                options[person.full_name].push({
                    value: "",
                    label: `(${t("address_block.no_address")})`
                });
            }
        }
    }

    return addresses;
};

const onAddBillingAddressSaved = async (address) => {
    var person_address = {
        person: contract.value.holder_id,
        address: address.id,
        is_billing: true,
    }
    var person_address = await $PersonAddressApiService.save(person_address);
    fillAddressOptions();
    selectedBillingAddress.value = person_address.id;

    closeAllRegions();
};

const onAddContactAddressSaved = async (address) => {
    var person_address = {
        person: contract.value.holder_id,
        address: address.id,
        is_billing: false,
    }
    var person_address = await $PersonAddressApiService.save(person_address);
    fillAddressOptions();
    selectedContactAddress.value = person_address.id;

    closeAllRegions();
};

const onPersonBankSelected = (bank) => {
    selectedBankDebit.value = bank;
    closeAllRegions();
};

const onCompanyBankSelected = (bank) => {
    selectedCompanyBankDebit.value = bank;
    closeAllRegions();
};

const onSelectPaymentMethod = () => {
    selectedBankDebit.value = null;
    selectedCompanyBankDebit.value = null;
    if (paymentTypeOptionsById.value[selectedPaymentMethod.value]?.token === 'BANK_TRANSFER') {
        if (companyBanks.value?.length === 1) {
            selectedCompanyBankDebit.value = companyBanks.value[0];
        } else if (companyBanks.value?.length > 1) {
            showDetail('CompanyBankSelect', null);
        }
    }
};

const onContractSelected = async (contract) => {
    if (general_invoice_contracts.value.map(c => c.id).includes(contract.id)) {
        general_invoice_contracts.value = general_invoice_contracts.value.filter(c => c.id !== contract.id);
        return;
    }
    try {
        const new_contract = await $ContractApiService.getMinimalDetail(contract.id);
        general_invoice_contracts.value.push(new_contract);
        fillAddressOptions(false);
    } catch (error) {
        console.error(error);
    }

    //closeAllRegions();
};

const save = async () => {
    if (!isValid()) return;
    if (!confirm(t('confirmation_text_block.confirm_save'))) return;

    saving.value = true;
    try {
        const payment_options = {
            id: general_invoice.value?.payment ? general_invoice.value.payment.id : null,
            iban_id: selectedBankDebit.value ? selectedBankDebit.value.id : null,
            company_iban_id: selectedCompanyBankDebit.value ? selectedCompanyBankDebit.value.id : null,
            type_id: selectedPaymentMethod.value,
            accounting_office: accounting_office.value,
            managing_body: managing_body.value,
            processing_unit: processing_unit.value,
            command: command.value,
            record: record.value,
        }

        const response_payment = await $GeneralPaymentApiService.save(payment_options);
        const data = {
            id: general_invoice_id.value,
            address_billing_id: selectedBillingAddress.value,
            address_contact_id: selectedContactAddress.value,
            payment_id: response_payment.id,
            contract_ids: general_invoice_contracts.value.map(c => c.id),
        }

        const response = await $GeneralInvoiceApiService.save(data);
        general_invoice.value = response;
        if (response) {
            toast.success(t('common.correct_save'));
            return navigateTo({
                path: '/contract/contracts/',
                query: {
                    id: contract.value.id,
                }
            })
        }
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
    }
}

const addAllRelated = async () => {
    try {
        loading_all.value = true;
        const response = await $ContractApiService.getAllByHolder(contract.value.holder_id);
        general_invoice_contracts.value = response;
        fillAddressOptions(false);
    } catch (error) {
        console.error(error);
    } finally {
        loading_all.value = false;
    }
}

const isValid = () => {
    if (
        !selectedBillingAddress.value || selectedBillingAddress.value == '' ||
        !selectedContactAddress.value || selectedContactAddress.value == '' ||
        !selectedPaymentMethod.value || selectedPaymentMethod.value == '' ||
        general_invoice_contracts.value.length == 0
    ) {
        toast.error(t('common.required_fields'));
        return false;
    }
    return true;
}

const showDetail = async (component, id) => {
    await closeAllRegions();
    showRegionComponent.value = component;
    showRegionComponentDetail.value = id;
    showRegion.value = true;
};

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
};

const closeAllRegions = () => {
    showRegionComponent.value = null;
    showRegionComponentDetail.value = null;
    showRegion.value = false;
    isSubRegionOpen.value = false;
};

onMounted(async () => {
    objectPermissions.value = await checkPermission($ContractApiService);
    if (!objectPermissions.value.can_change) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
    await getData()
});

</script>

<template>
    <div v-if="objectPermissions?.can_change" id="wrapper" class="p-4 text-base">
        <div v-if="pending">
            <div class="flex justify-center items-center">
                <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
                <span class="ml-2">{{ $t('common.loading') }}...</span>
            </div>
        </div>
        <div v-else>
            <div class="flex justify-between items-center mb-6">
                <H1>{{ $t(`common.modify`) }} {{ $t(`contract_block.general_invoices`).toLowerCase() }} </H1>
            </div>
            <div class="border-gray-300 my-2">

                <div class="mb-4">
                    <label for="sending_address" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
                        <Icon v-show="selectedBillingAddress" name="fa6-solid:circle-check"
                            class="text-xl text-emerald-600" />
                        <Icon v-show="!selectedBillingAddress" name="fa6-solid:asterisk"
                            class="text-lg text-slate-400" />
                        <span>{{ $t('contract_block.billing_address') }}:</span>
                    </label>

                    <div class="grid grid-cols-[1fr,80px,1fr] gap-3 items-center">
                        <div class="relative">
                            <select v-model="selectedBillingAddress"
                                class="w-full text-base border border-gray-300 rounded p-2" id="sending_address"
                                :class="{ 'opacity-50 cursor-not-allowed': loading }" :disabled="loading">
                                <option value="" selected="selected">
                                    <template v-if="loading">
                                        {{ $t('common.loading') }}...
                                    </template>
                                    <template v-else>
                                        --{{ $t('address_block.select_address') }}
                                    </template>
                                </option>
                                <template v-if="!loading" v-for="(addresses, person) in addressOptions" :key="person">
                                    <optgroup :label="person">
                                        <option v-for="address in addresses" :value="address.value"
                                            :key="address.value">
                                            {{ address.label }}
                                        </option>
                                    </optgroup>
                                </template>
                            </select>
                            <div v-if="loading"
                                class="absolute my-auto right-8 top-1/2 transform -translate-y-1/3 pointer-events-none">
                                <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500" />
                            </div>
                        </div>

                        <span class="text-center"> &mdash; {{ t('common.or') }} &mdash;</span>
                        <ButtonSeleccio @click="showDetail('addBillingAddress', contract.holder_id)" class="py-3">
                            <Icon name="fa-solid:plus" class="text-slate-500" />
                            {{ $t('common.add') }} {{ $t('address_block.address').toLowerCase() }}
                        </ButtonSeleccio>
                    </div>
                </div>
                <div class="mb-4">
                    <label for="contact_address" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
                        <Icon v-show="selectedContactAddress" name="fa6-solid:circle-check"
                            class="text-xl text-emerald-600" />
                        <Icon v-show="!selectedContactAddress" name="fa6-solid:asterisk"
                            class="text-lg text-slate-400" />
                        <span>{{ $t('contract_block.contact_address') }}:</span>
                    </label>

                    <div class="grid grid-cols-[1fr,80px,1fr] gap-3 items-center">
                        <div class="relative">
                            <select v-model="selectedContactAddress"
                                class="w-full text-base border border-gray-300 rounded p-2" id="contact_address"
                                :class="{ 'opacity-50 cursor-not-allowed': loading }" :disabled="loading">
                                <option value="" selected="selected">
                                    <template v-if="loading">
                                        {{ $t('common.loading') }}...
                                    </template>
                                    <template v-else>
                                        --{{ $t('address_block.select_address') }}
                                    </template>
                                </option>
                                <template v-if="!loading" v-for="(addresses, person) in addressOptions" :key="person">
                                    <optgroup :label="person">
                                        <option v-for="address in addresses" :value="address.value"
                                            :key="address.value">
                                            {{ address.label }}
                                        </option>
                                    </optgroup>
                                </template>
                            </select>
                            <div v-if="loading"
                                class="absolute my-auto right-8 top-1/2 transform -translate-y-1/3 pointer-events-none">
                                <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500" />
                            </div>
                        </div>

                        <span class="text-center"> &mdash; {{ t('common.or') }} &mdash;</span>
                        <ButtonSeleccio @click="showDetail('addContactAddress', contract.holder_id)" class="py-3">
                            <Icon name="fa-solid:plus" class="text-slate-500" />
                            {{ $t('common.add') }} {{ $t('address_block.address').toLowerCase() }}
                        </ButtonSeleccio>
                    </div>
                </div>
                <hr class="my-2">
                <div class="grid grid-cols-2 gap-x-3">
                    <div class="mb-4">
                        <SelectPaymentType v-model="selectedPaymentMethod" show-label-icons :model-as-number="true"
                            @change="onSelectPaymentMethod" @loaded="onPaymentTypesLoaded" />
                        <div class="select_bank mt-3"
                            v-if="paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'DIRECT_DEBIT'">
                            <div v-if="selectedBankDebit" class="bg-sky-100 p-4 rounded relative group">
                                <div>
                                    <BankDetail :item="selectedBankDebit" />
                                </div>
                                <button @click="showDetail('PersonBankSelect', null)"
                                    class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                                    <Icon name="fa6-solid:pencil" />
                                </button>
                            </div>

                            <ButtonSeleccio v-else @click="showDetail('PersonBankSelect', null)" class="py-3">
                                <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
                                {{ $t('common.select') }} {{ $t('common.iban') }}
                            </ButtonSeleccio>

                        </div>

                        <div class="select_bank mt-3"
                            v-if="paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'BANK_TRANSFER' && companyBanks.length > 1">
                            <label class="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">{{ $t('common.bank_data') }} ({{ $t('company') }})</label>
                            <div v-if="selectedCompanyBankDebit" class="bg-sky-50 border border-sky-100 p-4 rounded relative group">
                                <div>
                                    <BankDetail :item="selectedCompanyBankDebit" />
                                </div>
                                <button @click="showDetail('CompanyBankSelect', null)"
                                    class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                                    <Icon name="fa6-solid:pencil" />
                                </button>
                            </div>

                            <ButtonSeleccio v-else @click="showDetail('CompanyBankSelect', null)" class="py-3">
                                <Icon name="fa6-regular:hand-pointer" class="text-slate-500" />
                                {{ $t('common.select') }} {{ $t('common.iban') }}
                            </ButtonSeleccio>
                        </div>
                    </div>
                    <div class="ml-3">
                        <div class="flex items-center mt-9 ml-2 text-slate-500">
                            <input v-model="is_electronic_invoice" type="checkbox" id="is_electronic_invoice"
                                name="is_electronic_invoice" class="checkbox" />
                            <label for="is_electronic_invoice" class="ml-2"> {{ t('common.electronic_invoice')
                            }}</label>
                        </div>

                        <div class="select_bank mt-3 max-w-xl" v-if="is_electronic_invoice">
                            <div class="bg-green-50 border border-slate-200 rounded-lg p-4 relative group mb-2">
                                <div class="grid grid-cols-2 gap-3">
                                    <div class="space-y-1">
                                        <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                                            {{ $t('billing_block.accounting_office') }}
                                        </label>
                                        <input type="text" v-model="accounting_office"
                                            class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                                            :placeholder="$t('billing_block.accounting_office')" />
                                    </div>
                                    <div class="space-y-1">
                                        <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                                            {{ $t('billing_block.managing_body') }}
                                        </label>
                                        <input type="text" v-model="managing_body"
                                            class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                                            :placeholder="$t('billing_block.managing_body')" />
                                    </div>
                                    <div class="space-y-1">
                                        <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                                            {{ $t('billing_block.processing_unit') }}
                                        </label>
                                        <input type="text" v-model="processing_unit"
                                            class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                                            :placeholder="$t('billing_block.processing_unit')" />
                                    </div>
                                    <!-- <div class="space-y-1">
                                        <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                                            {{ $t('billing_block.command') }}
                                        </label>
                                        <input type="text" v-model="command"
                                            class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                                            :placeholder="$t('billing_block.command')" />
                                    </div>
                                    <div class="space-y-1 col-span-2">
                                        <label class="block text-xs font-medium text-slate-600 uppercase tracking-wide">
                                            {{ $t('billing_block.record') }}
                                        </label>
                                        <input type="text" v-model="record"
                                            class="w-full text-sm border border-slate-300 rounded-md px-3 py-2"
                                            :placeholder="$t('billing_block.record')" />
                                    </div> -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <hr class="my-2">

                <div class="grid grid-cols-2 gap-x-4" :style="{
                    minHeight: is_electronic_invoice || (paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'DIRECT_DEBIT') ? 'calc(100vh - 750px)' : 'calc(100vh - 550px)',
                    maxHeight: is_electronic_invoice || (paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'DIRECT_DEBIT') ? 'calc(100vh - 750px)' : 'calc(100vh - 550px)',
                }">
                    <div v-if="contract_id && contract_id != ''">
                        <span class="font-medium text-slate-500 text-lg">{{ $t('contract_block.current_contract') }}
                        </span>
                        <ContractDetail :id="parseInt(contract_id)" :isSubRegion="true" :showCommunication="false"
                            :showPayment="false" :reducedDetail="true" class="px-2 py-1 bg-green-100 mt-4" />
                    </div>

                    <div class="space-y-3">
                        <div class="flex items-center justify-between">
                            <span class="font-medium text-slate-500 text-lg">
                                {{ $t('contract_block.grouped_contracts') }} - {{ general_invoice_contracts.length }}
                            </span>
                            <div class="flex items-center gap-1">
                                <abbr :title="t('contract_block.add_all_related')" style="text-decoration: none;">
                                    <button @click="addAllRelated()" :disabled="loading_all"
                                        class="button-default-xs flex items-center gap-1">
                                        <Icon :name="loading_all ? 'fa6-solid:spinner' : 'fa6-solid:check-double'"
                                            :class="loading_all ? 'animate-spin' : 'text-xs'" />
                                        <span>{{ t('common.add') }} {{ t('common.all').toLowerCase() }}</span>
                                    </button>
                                </abbr>

                                <button @click="showDetail('addContract', null)"
                                    class="button-default-xs flex items-center gap-1">
                                    <Icon
                                        :name="general_invoice_contracts.length > 1 ? 'fa6-solid:pencil' : 'fa6-solid:plus'"
                                        class="text-xs" />
                                    <span>{{ general_invoice_contracts.length > 1 ? t('common.modify') : t('common.add')
                                        }}</span>
                                </button>
                            </div>
                        </div>

                        <div class="overflow-y-auto" :style="{
                            maxHeight: is_electronic_invoice || (paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'DIRECT_DEBIT') ? 'calc(100vh - 680px)' : 'calc(100vh - 580px)',
                            minHeight: is_electronic_invoice || (paymentTypeOptionsById[selectedPaymentMethod] && paymentTypeOptionsById[selectedPaymentMethod].token == 'DIRECT_DEBIT') ? 'calc(100vh - 680px)' : 'calc(100vh - 580px)',
                        }">
                            <ul class="space-y-1">
                                <li v-for="invoice_contract in general_invoice_contracts" :key="invoice_contract.id"
                                    class="group relative overflow-hidden rounded-md border transition-all duration-200"
                                    :class="invoice_contract.id == contract.id
                                        ? 'bg-amber-50 border-amber-400'
                                        : 'bg-white border-slate-200 hover:border-sky-400 hover:bg-sky-50'">
                                    <button @click="showDetail('ContractRegion', invoice_contract.id)"
                                        class="w-full flex items-center justify-between gap-3 px-3 py-2 text-left">
                                        <span class="font-semibold text-sm transition-colors" :class="invoice_contract.id == contract.id
                                            ? 'text-amber-700'
                                            : 'text-sky-600 group-hover:text-sky-700'">
                                            {{ invoice_contract.token }}
                                        </span>
                                        <span class="text-sm text-slate-500 truncate">
                                            {{ invoice_contract.supply_point }}
                                        </span>
                                    </button>
                                    <div v-if="invoice_contract.id == contract.id"
                                        class="absolute left-0 top-0 bottom-0 w-1 bg-amber-500"></div>
                                </li>
                                <li v-if="general_invoice_contracts.length == 0"
                                    class="text-sm text-slate-400 text-center py-6">
                                    {{ $t('common.no_records') }}
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>

            </div>
            <!-- <div class="flex flex-row-reverse mt-4 px-4"> -->
            <div class="fixed right-0 bottom-0 border-t border-gray-200 py-4 px-4 shadow-lg bg-white"
                style="width: calc(100% - 250px)">
                <div class="flex flex-row-reverse">
                    <button @click="save" :disabled="saving" class="button-primary flex items-center gap-1">
                        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
                            $t('common.save') }}
                    </button>
                </div>
            </div>
        </div>

        <div role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
            :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeAllRegions()"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <AddAddress v-if="showRegionComponent === 'addContactAddress'"
                    @new-address="onAddContactAddressSaved" />
                <AddAddress v-if="showRegionComponent === 'addBillingAddress'"
                    @new-address="onAddBillingAddressSaved" />
                <PersonBankSelect v-if="showRegionComponent === 'PersonBankSelect'"
                    :title="`${$t('common.select')} ${$t('common.iban')}`" :persons="persons"
                    @selected-item="onPersonBankSelected" />
                <CompanyBankSelect v-if="showRegionComponent === 'CompanyBankSelect'"
                    :title="`${$t('common.select')} ${$t('common.iban')}`" :company="resolvedCompany"
                    @selected-item="onCompanyBankSelected" />
                <AddContracts v-if="showRegionComponent === 'addContract'" :selected_items="general_invoice_contracts"
                    @item-clicked="onContractSelected" :person_ids="persons.map(p => p.id)" />
                <ContractRegion v-if="showRegionComponent === 'ContractRegion'" :id="showRegionComponentDetail"
                    @show-subregion="handleSubRegionEvent" :isSubRegionOpen="isSubRegionOpen" />
            </div>
        </div>
    </div>
</template>