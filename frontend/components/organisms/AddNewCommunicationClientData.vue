<script setup>
import { useI18n } from 'vue-i18n';
import AppLoading from '../atoms/AppLoading.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import AddContracts from '~/components/molecules/AddContracts.vue';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';
import SelectorType from '../atoms/SelectorType.vue';
import ContractDetail from '../molecules/ContractDetail.vue';

const { t } = useI18n();
const { $ConfiglistApiService, $PersonApiService, $CommunicationApiService, $ContractApiService } = useNuxtApp();

const ELECTRONIC_INVOICE_TOKEN = 'electronic_inv';
const route = useRoute();
const emit = defineEmits(['change', 'ready']);

const loading = ref(false);
const loadingClientData = ref(false);
const loadingCompaniesConfig = ref(false);
const loadingExtraInformation = ref(false);

const companiesConfig = ref([]);
const selectedCompanyConfig = ref(null);
const selectedCompanyConfigEmail = ref(null);
const dueDate = ref(null);
const communicationTypes = ref([]);
const selectedCommunicationTypes = ref([]);
const communicationUseTypes = ref([]);
const selectedCommunicationUseType = ref(null);

const clientSelect = ref('contract');
const selectedPerson = ref(null);
const selectedContract = ref(null);
const contractPersons = ref([]);

const selectedAddress = ref(null);
const selectedAddressId = ref(null);
const selectedEmail = ref(null);
const selectedEmailId = ref(null);
const selectedPhone = ref(null);
const selectedPhoneId = ref(null);
const accountingOffice = ref(null);
const managingBody = ref(null);
const processingUnit = ref(null);

const extraInformationTypes = ref(['NONE', 'INVOICES', 'READINGS']);
const selectedExtraInformation = ref('NONE')
const selectedInvoices = ref([]);
const selectedReadings = ref([]);
const contractInvoices = ref([]);
const contractReadings = ref([]);

const selectedInvoicesContainReadings = computed(() => {
    return selectedInvoices.value.some(invoice => invoice.readings.length > 0);
});
const addReadingsToInvoices = ref(false);


const clientSelectOptions = computed(() => [
    { value: 'person', label: t('person') },
    { value: 'contract', label: t('contract') },
]);

const extraInformationTypeOptions = computed(() => extraInformationTypes.value.map((type) => ({
    value: type,
    label: t(type.toLowerCase()),
})));

const filteredExtraInformationItems = computed(() => {
    if (selectedExtraInformation.value === 'INVOICES') {
        return contractInvoices.value;
    }
    if (selectedExtraInformation.value === 'READINGS') {
        return contractReadings.value;
    }
    return [];
});

const selectedExtraInformationCount = computed(() => {
    if (selectedExtraInformation.value === 'INVOICES') {
        return selectedInvoices.value.length;
    }
    if (selectedExtraInformation.value === 'READINGS') {
        return selectedReadings.value.length;
    }
    return 0;
});

const selectedExtraInformationLabel = computed(() => {
    if (selectedExtraInformation.value === 'INVOICES') {
        return t('billing_block.selected_invoices');
    }
    if (selectedExtraInformation.value === 'READINGS') {
        return t('billing_block.selected_readings');
    }
    return '';
});

const hasElectronicInvoiceType = computed(() =>
    selectedCommunicationTypes.value.some(type => type.token === ELECTRONIC_INVOICE_TOKEN)
);

const requiresInvoicesForElectronicInvoice = computed(() =>
    hasElectronicInvoiceType.value && selectedInvoices.value.length === 0
);

const clientAddresses = ref([]);
const clientEmails = ref([]);
const clientPhones = ref([]);
const clientData = ref(null);

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);
const isSubRegionOpen = ref(false);

const emitChange = () => {
    emit('change', {
        clientData: clientData.value,
        selectedPerson: selectedPerson.value,
        selectedContract: selectedContract.value,
        selectedCompanyConfig: selectedCompanyConfig.value,
        selectedCompanyConfigEmail: selectedCompanyConfigEmail.value,
        selectedCommunicationUseType: selectedCommunicationUseType.value,
        dueDate: dueDate.value,
        selectedCommunicationTypes: selectedCommunicationTypes.value,
        selectedAddress: selectedAddress.value,
        selectedEmail: selectedEmail.value,
        selectedPhone: selectedPhone.value,
        accountingOffice: accountingOffice.value,
        managingBody: managingBody.value,
        processingUnit: processingUnit.value,
        selectedExtraInformation: selectedExtraInformation.value,
        selectedInvoices: selectedInvoices.value,
        selectedReadings: selectedReadings.value,
        addReadingsToInvoices: addReadingsToInvoices.value,
        loadingClientData: loadingClientData.value,
    });
};

const cleanData = (only_contact = false) => {
    selectedExtraInformation.value = 'NONE';
    selectedInvoices.value = [];
    selectedReadings.value = [];
    addReadingsToInvoices.value = false;
    contractInvoices.value = [];
    contractReadings.value = [];
    selectedAddress.value = null;
    selectedAddressId.value = null;
    selectedEmail.value = null;
    selectedEmailId.value = null;
    selectedPhone.value = null;
    selectedPhoneId.value = null;
    accountingOffice.value = null;
    managingBody.value = null;
    processingUnit.value = null;
    clientAddresses.value = [];
    clientEmails.value = [];
    clientPhones.value = [];
    if (only_contact) {
        emitChange();
        return;
    }
    selectedContract.value = null;
    selectedPerson.value = null;
    selectedCommunicationTypes.value = [];
    contractPersons.value = [];
    clientData.value = null;
    emitChange();
};

const getContractData = async (id) => {
    const response = await $ContractApiService.getMinimalDetail(id);
    selectedContract.value = response;
    getContractPersons();
};

const getPersonData = async (id) => {
    const response = await $PersonApiService.getDetail(id);
    selectedPerson.value = response;
    getClientData();
};

const openRegion = (component, id) => {
    closeSubRegion();
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
};

const closeSubRegion = () => {
    showRegionDetailComponent.value = null;
    regionDetailId.value = null;
    isSubRegionOpen.value = false;
};

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
};

const fetchConfigData = async (service, entity, targetArray) => {
    try {
        const data = await $ConfiglistApiService.getAll(service + '/' + entity);
        targetArray.value = [];
        if (data.results) {
            data.results.forEach(item => {
                targetArray.value.push({
                    label: item.name ? item.name : item.token,
                    value: item.id,
                    token: item.token,
                    is_default: item.is_default || false,
                });
            });
        }
    } catch (error) {
        console.error(`Error fetching ${entity}:`, error);
    }
};

const selectCompanyConfig = (company) => {
    selectedCompanyConfig.value = company;
    if (company.company_config_emails.length > 0) {
        if (company.company_config_emails.find(mail => mail.use_type.token === selectedCommunicationUseType.value.token)) {
            selectedCompanyConfigEmail.value = company.company_config_emails.find(email => email.use_type.token === selectedCommunicationUseType.value.token);
        } else {
            selectedCompanyConfigEmail.value = company.company_config_emails.find(email => email.is_default);
        }
    } else {
        selectedCompanyConfigEmail.value = null;
    }
};

const getCompaniesConfig = async () => {
    loadingCompaniesConfig.value = true;
    try {
        const result = await $ConfiglistApiService.getAll('service/company-config');
        companiesConfig.value = [];
        result.results.forEach(company => {
            companiesConfig.value.push({
                label: company.name,
                code: company.id,
                company: company.company,
                company_config_emails: company.company_config_emails,
            });
        });
    } catch (err) {
        console.error(err);
    } finally {
        loadingCompaniesConfig.value = false;
    }
};

const getClientData = async () => {
    loadingClientData.value = true;
    emitChange();
    try {
        await cleanData(true);
        const person_id = selectedPerson.value?.id;
        const response = await $PersonApiService.getDetail(person_id);

        if (response) {
            if (response.addresses && response.addresses.length > 0) {
                response.addresses.forEach((response_address) => {
                    clientAddresses.value.push({
                        value: response_address.id,
                        label: response_address.address_complete,
                    });
                });
            } else if (response.addresses && response.addresses.length == 0) {
                if (clientAddresses.value.length === 0) {
                    clientAddresses.value.push({
                        value: '',
                        label: `(${t('address_block.no_address')})`,
                    });
                }
            }
            if (response.contacts && response.contacts.length > 0) {
                response.contacts.forEach((response_contact) => {
                    if (response_contact.email) {
                        clientEmails.value.push({
                            value: response_contact.id,
                            label: response_contact.email,
                        });
                    }
                    if (response_contact.phone) {
                        clientPhones.value.push({
                            value: response_contact.id,
                            label: response_contact.phone,
                        });
                    }
                });
            } else if (response.contacts && response.contacts.length == 0) {
                clientEmails.value.push({
                    value: '',
                    label: `(${t('common.no_email')})`,
                });
                clientPhones.value.push({
                    value: '',
                    label: `(${t('common.no_tlf')})`,
                });
            }
        }

        if (selectedContract.value && selectedContract.value.prefered_communication_type) {
            if (selectedContract.value.prefered_communication_type?.type == 'DIGITAL') {
                selectedCommunicationTypes.value = [communicationTypes.value.find(type => type.token === "email")];
                selectedEmail.value = selectedContract.value.prefered_communication_type?.value;
                console.log("selectedCommunicationTypes", selectedCommunicationTypes.value)
                console.log("selectedEmail", selectedEmail.value)
            } else {
                selectedCommunicationTypes.value = [communicationTypes.value.find(type => type.token === "letter")];
                selectedAddress.value = selectedContract.value.prefered_communication_type?.value;
            }
        }

        clientData.value = {
            addresses: [...clientAddresses.value],
            emails: [...clientEmails.value],
            phones: [...clientPhones.value],
        };
        getExtraInformation();
    } catch (error) {
        console.error(error);
        clientData.value = null;
    } finally {
        loadingClientData.value = false;
        emitChange();
    }
};

const isContractPersonSelected = (person) => selectedPerson.value?.id === person.id;

const getContractPersons = () => {
    contractPersons.value = [];
    if (!selectedContract.value) return;

    const addPerson = (role, id, token, fullName, vulnerabilityLevel = 0) => {
        if (!id) return;
        contractPersons.value.push({
            id,
            token,
            full_name: fullName,
            role,
            roleLabel: t(`contract_block.${role}`),
            vulnerability_level: vulnerabilityLevel || 0,
        });
    };

    const contract = selectedContract.value;
    addPerson('holder', contract.holder, contract.holder_token, contract.holder_full_name, contract.holder_vulnerability_level);
    addPerson('tenant', contract.tenant, contract.tenant_token, contract.tenant_full_name, contract.tenant_vulnerability_level);
    addPerson('owner', contract.owner, contract.owner_token, contract.owner_full_name, contract.owner_vulnerability_level);

    selectedPerson.value = contractPersons.value[0] ?? null;

    getClientData();
};

const selectContractPerson = (person) => {
    selectedPerson.value = person;
    getClientData();
};

const selectCommunicationType = (type) => {
    if (selectedCommunicationTypes.value.map(t => t.value).includes(type.value)) {
        selectedCommunicationTypes.value = selectedCommunicationTypes.value.filter(t => t.value !== type.value);
    } else {
        selectedCommunicationTypes.value.push(type);
        if (type.token === ELECTRONIC_INVOICE_TOKEN && selectedExtraInformation.value !== 'INVOICES') {
            selectedExtraInformation.value = 'INVOICES';
            selectedReadings.value = [];
        }
    }
    emitChange();
};

const selectClientType = (type) => {
    if (clientSelect.value === type) return;
    clientSelect.value = type;
    cleanData(false);
};

const getExtraInformation = async () => {
    loadingExtraInformation.value = true;
    try {
        const get_data = {
            contract_id: selectedContract.value?.id,
            person_id: selectedContract.value ? null : selectedPerson.value?.id,
        }
        const response = await $CommunicationApiService.getClientData(get_data);
        contractInvoices.value = response.invoices ?? [];
        contractReadings.value = response.readings ?? [];
        
    } catch (error) {
        console.error(error);
    } finally {
        loadingExtraInformation.value = false;
    }
};

const selectExtraInformation = async (type) => {
    if (selectedExtraInformation.value === type) return;
    selectedExtraInformation.value = type;
    selectedInvoices.value = [];
    selectedReadings.value = [];
    addReadingsToInvoices.value = false;
    emitChange();
};

const isExtraInformationSelected = (itemId) => {
    if (selectedExtraInformation.value === 'INVOICES') {
        return selectedInvoices.value.some((invoice) => invoice.id === itemId);
    }
    if (selectedExtraInformation.value === 'READINGS') {
        return selectedReadings.value.some((reading) => reading.id === itemId);
    }
    return false;
};

const toggleExtraInformationSelection = (item) => {
    const targetRef = selectedExtraInformation.value === 'INVOICES' ? selectedInvoices : selectedReadings;
    const alreadySelected = targetRef.value.some((selectedItem) => selectedItem.id === item.id);

    targetRef.value = alreadySelected
        ? targetRef.value.filter((selectedItem) => selectedItem.id !== item.id)
        : [...targetRef.value, item];
    console.log("targetRef", targetRef.value)
    emitChange();
    if (selectedExtraInformation.value === 'INVOICES' && addReadingsToInvoices.value) addSelectedInvoiceReadings();
};

const onContractSelected = async (item) => {
    await cleanData();
    if (selectedContract.value?.id == item.id) {
        selectedContract.value = null;
    } else {
        selectedContract.value = item;
    }
    getContractPersons();
    closeSubRegion();
};

const onPersonSaved = async (item) => {
    await cleanData();
    selectedPerson.value = item;
    selectedContract.value = null;
    closeSubRegion();
    getClientData();
};

const addSelectedInvoiceReadings = () => {
    if (!addReadingsToInvoices.value) return;
    selectedReadings.value = []
    selectedInvoices.value.forEach(invoice => {
        selectedReadings.value.push(
            contractReadings.value.find(reading => invoice.readings.includes(reading.id))
        )
    });
    console.log("selectedReadings", selectedReadings.value)
    emitChange();
}

const reset = () => cleanData(false);

defineExpose({ reset });

watch(selectedPhoneId, (newVal) => {
    if (!newVal) return;
    const phone = clientPhones.value.find((p) => p.value === newVal);
    selectedPhone.value = phone?.label ? phone.label.replace(/\s/g, '') : null;
    emitChange();
});

watch(selectedEmailId, (newVal) => {
    if (!newVal) return;
    const email = clientEmails.value.find((e) => e.value === newVal);
    selectedEmail.value = email?.label ? email.label : null;
    emitChange();
});

watch(selectedAddressId, (newVal) => {
    if (!newVal) return;
    const address = clientAddresses.value.find((a) => a.value === newVal);
    selectedAddress.value = address?.label ? address.label : null;
    emitChange();
});

watch([selectedCompanyConfig, selectedCompanyConfigEmail, selectedCommunicationUseType, dueDate, selectedAddress, selectedEmail, selectedPhone, accountingOffice, managingBody, processingUnit], () => {
    emitChange();
});

onMounted(async () => {
    loading.value = true;
    try {
        await fetchConfigData('communication', 'message-type', communicationTypes);
        await fetchConfigData('communication', 'communication-use-type', communicationUseTypes);
        selectedCommunicationUseType.value = communicationUseTypes.value.find(type => type.is_default) || null;
        await getCompaniesConfig();
        if (route.query?.contract_id) {
            await getContractData(route.query.contract_id);
        }
        if (route.query?.person_id) {
            await getPersonData(route.query.person_id);
        }
        emitChange();
    } finally {
        loading.value = false;
        emit('ready');
    }
});
</script>

<template>
    <div class="space-y-5 p-2">
        <AppLoading v-if="loading" />

        <template v-else>
            <section class="space-y-3 rounded-lg border border-slate-200 bg-slate-50/60 p-4">
                <section class="space-y-3">
                    <div class="space-y-2">
                        <section class="w-full grid grid-cols-[2fr,1fr] gap-4">
                            <div>
                                <SelectorType :options="clientSelectOptions" :model-value="clientSelect"
                                    @select="selectClientType" class="mb-3" />

                                <ButtonSeleccio v-if="!selectedPerson && !selectedContract"
                                    @click="openRegion(clientSelect === 'contract' ? 'AddContracts' : 'PersonSearch', null)"
                                    class="flex max-w-xl items-center gap-2 rounded-lg border border-slate-300 bg-white text-sm font-medium text-slate-700">
                                    <Icon name="fa6-solid:hand-pointer" class="text-slate-500" />
                                    {{ $t('common.add') }} {{ clientSelect === 'contract' ? $t('contract') :
                                        $t('person') }}
                                </ButtonSeleccio>

                                <div v-if="selectedPerson && !selectedContract"
                                    class="relative max-w-xl rounded-xl border border-slate-300 bg-green-50 px-4 py-2 text-sm text-slate-700 shadow-sm h-fit">
                                    <div class="flex items-start justify-between gap-3">
                                        <div class="flex items-start gap-3">
                                            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
                                                <Icon name="fa6-solid:circle-check" class="text-lg text-emerald-600" />
                                            </span>
                                            <div class="space-y-1">
                                                <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                                    {{ t('person') }}
                                                </p>
                                                <p class="text-sm font-semibold text-slate-800">
                                                    {{ selectedPerson.full_name }}
                                                </p>
                                                <p class="text-xs text-slate-500">
                                                    {{ t('common.person_id') }}:
                                                    <span class="font-medium text-slate-700">{{ selectedPerson.token
                                                    }}</span>
                                                </p>
                                            </div>
                                        </div>
                                        <AtomsVulnerabilityCheck v-if="selectedPerson.vulnerability_level > 0"
                                            :vulnerability_level="selectedPerson.vulnerability_level" />
                                    </div>
                                    <div v-if="selectedPerson.important_observations?.length"
                                        class="mt-2 space-y-1.5 rounded-lg border border-amber-200 bg-amber-50 p-1 px-2">
                                        <p v-for="obs in selectedPerson.important_observations" :key="obs.id"
                                            class="flex items-center gap-2 text-xs font-semibold italic leading-relaxed text-amber-600">
                                            <Icon name="fa6-solid:circle-exclamation" class="text-amber-600" />
                                            {{ obs.observation }}
                                        </p>
                                    </div>
                                    <button @click="cleanData(false)" type="button"
                                        class="absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-md bg-white shadow-sm transition-all duration-200 hover:bg-red-50 hover:shadow-md">
                                        <Icon name="fa6-solid:xmark" class="text-slate-500 hover:text-slate-700" />
                                    </button>
                                </div>

                                <div v-if="selectedContract" class="space-y-3">
                                    <div class="relative max-w-xl">
                                        <button @click="cleanData(false)" type="button"
                                            class="absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-md bg-white shadow-sm transition-all duration-200 hover:bg-red-50 hover:shadow-md">
                                            <Icon name="fa6-solid:xmark" class="text-slate-500 hover:text-slate-700" />
                                        </button>
                                        <ul class="space-y-2" role="listbox" :aria-label="t('person')">
                                            <li v-for="person in contractPersons" :key="person.id" role="option"
                                                :aria-selected="isContractPersonSelected(person)">
                                                <button type="button" @click="selectContractPerson(person)"
                                                    class="w-full rounded-xl border border-slate-300 px-4 py-2 text-left text-sm text-slate-700 shadow-sm transition-colors"
                                                    :class="isContractPersonSelected(person)
                                                        ? 'bg-green-50'
                                                        : 'bg-white hover:bg-green-50/40'">
                                                    <div class="flex items-start justify-between gap-3">
                                                        <div class="flex items-center gap-3">
                                                            <span
                                                                class="flex h-5 w-5 shrink-0 items-center justify-center">
                                                                <Icon class="text-lg transition-all duration-300"
                                                                    :name="isContractPersonSelected(person) ? 'fa6-solid:circle' : 'fa6-regular:circle'"
                                                                    :class="isContractPersonSelected(person) ? 'text-emerald-600' : 'text-slate-300'" />
                                                            </span>
                                                            <div class="space-y-1">
                                                                <p
                                                                    class="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                                                    {{ person.roleLabel }}
                                                                </p>
                                                                <p class="text-sm font-semibold text-slate-800">{{
                                                                    person.full_name }}</p>
                                                                <p class="text-xs text-slate-500">
                                                                    {{ t('common.person_id') }}:
                                                                    <span class="font-medium text-slate-700">{{
                                                                        person.token }}</span>
                                                                </p>
                                                            </div>
                                                        </div>
                                                        <AtomsVulnerabilityCheck v-if="person.vulnerability_level > 0"
                                                            :vulnerability_level="person.vulnerability_level" />
                                                    </div>
                                                </button>
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                            </div>

                            <aside class="flex items-end w-full">
                                <div class="w-full">
                                    <div>
                                        <label class="block font-medium text-slate-500 mb-2">
                                            {{ t('customer_service_block.sender_company') }}<span
                                                class="text-red-500">*</span>
                                        </label>
                                        <v-select class="block w-full mr-2 required"
                                            :disabled="loadingCompaniesConfig || companiesConfig.length == 0"
                                            :model-value="selectedCompanyConfig"
                                            @update:modelValue="selectCompanyConfig"
                                            :options="companiesConfig" />
                                    </div>
                                    <div>
                                        <label class="block font-medium text-slate-500 mb-2">
                                            {{ t('service_block.config_mail_sender') }}<span
                                                class="text-red-500">*</span>
                                        </label>
                                        <v-select class="block w-full mr-2 required"
                                            :disabled="!selectedCompanyConfig || !selectedCompanyConfig?.company_config_emails || selectedCompanyConfig?.company_config_emails.length == 0"
                                            :model-value="selectedCompanyConfigEmail"
                                            @update:modelValue="selectedCompanyConfigEmail = $event; emitChange()"
                                            :options="selectedCompanyConfig?.company_config_emails || []" />
                                    </div>
                                    <div class="mt-2 grid grid-cols-2 gap-2">
                                        <div>
                                            <label class="block font-medium text-slate-500 mb-2">
                                                {{ t('common.use_type') }}<span class="text-red-500">*</span>
                                            </label>
                                            <v-select class="block w-full mr-2 required"
                                                :disabled="communicationUseTypes.length == 0"
                                                :model-value="selectedCommunicationUseType"
                                                @update:modelValue="selectedCommunicationUseType = $event; emitChange()"
                                                :options="communicationUseTypes" />
                                        </div>
                                        <div>
                                            <AtomsInputDate v-model="dueDate" class="w-full"
                                                :label="$t('common.send_date')" :required="true" />
                                        </div>
                                    </div>
                                </div>
                            </aside>

                            <details v-if="selectedContract" class="group w-full col-span-2">
                                <summary
                                    class="flex cursor-pointer list-none items-center justify-between rounded-lg border border-gray-200 bg-white p-3 shadow-sm transition-colors hover:bg-gray-50">
                                    <div class="flex items-center gap-2 font-semibold text-slate-700">
                                        <Icon name="fa6-solid:file-contract" class="text-sky-500" />
                                        {{ t('contract') }}
                                    </div>
                                    <div class="flex items-center gap-3 text-sm text-gray-500">
                                        <span
                                            class="rounded border border-sky-100 bg-sky-50 px-2 py-1 font-medium text-sky-700">
                                            {{ selectedContract.token }}
                                        </span>
                                        <span v-if="selectedContract.holder_full_name"
                                            class="hidden rounded border border-gray-100 bg-gray-50 px-2 py-1 sm:inline">
                                            {{ selectedContract.holder_full_name }}
                                        </span>
                                        <Icon name="fa6-solid:chevron-down"
                                            class="transition-transform group-open:rotate-180" />
                                    </div>
                                </summary>
                                <div class="rounded-b-lg border-x border-b border-gray-200">
                                    <fieldset class="bg-sky-50 px-3 py-1">
                                        <ContractDetail :id="selectedContract.id" :reducedDetail="true"
                                            :isSubRegion="true" :showPayment="false" :showCommunication="false"
                                            :showImportantObservations="true" :canChange="false" />
                                    </fieldset>
                                </div>
                            </details>
                        </section>
                    </div>
                </section>
            </section>

            <hr class="my-2">

            <section class="space-y-3">
                <div class="flex flex-wrap items-center gap-1.5">
                    <button v-for="type in communicationTypes" :key="type.value" type="button"
                        @click="selectCommunicationType(type)"
                        class="rounded-md border px-2.5 py-1 text-xs transition-all duration-300 font-medium" :class="{
                            'bg-white text-slate-600 border-slate-300 hover:bg-sky-100 hover:border-sky-100': !selectedCommunicationTypes.map(t => t.value).includes(type.value),
                            'bg-sky-500 text-white border-sky-500 hover:bg-sky-800 hover:border-sky-800': selectedCommunicationTypes.map(t => t.value).includes(type.value),
                        }">
                        {{ type.label }}
                    </button>
                </div>
                <div class="space-y-1.5">
                    <div v-if="selectedCommunicationTypes.length === 0"
                        class="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
                        {{ t('customer_service_block.select_communication_channel') }}
                    </div>

                    <section v-if="selectedCommunicationTypes.map(t => t.token).includes('letter')"
                        class="rounded-lg border border-sky-200 bg-white/70 p-2.5 transition-all duration-300"
                        :class="{ 'opacity-50 pointer-events-none border-slate-200': !selectedCommunicationTypes.map(t => t.token).includes('letter') }">
                        <div class="mb-1.5 flex items-center justify-between transition-all duration-300 gap-2"
                            :class="{ 'text-sky-400': selectedCommunicationTypes.map(t => t.token).includes('letter'), 'text-slate-400': !selectedCommunicationTypes.map(t => t.token).includes('letter') }">
                            <p class="text-xs font-semibold uppercase tracking-wide">{{ $t('common.address') }}</p>
                            <Icon name="ph:map-pin-duotone" class="text-lg" />
                        </div>
                        <div class="grid gap-2 text-slate-600 md:grid-cols-[minmax(0,1fr),220px]">
                            <input type="text" v-model="selectedAddress"
                                class="input h-9 rounded-lg border-slate-300 text-sm"
                                :disabled="!selectedCommunicationTypes.map(t => t.token).includes('letter')"
                                :placeholder="$t('customer_service_block.select_address')" aria-label="Address input" />
                            <select v-model="selectedAddressId"
                                class="h-9 w-full rounded-lg border border-slate-300 bg-white px-2.5 text-sm text-slate-700 focus:border-slate-500 focus:outline-none"
                                :disabled="!selectedCommunicationTypes.map(t => t.token).includes('letter')"
                                id="contact_address">
                                <option value="" selected="selected">--{{ $t('customer_service_block.select_address') }}
                                </option>
                                <option v-for="address in clientAddresses" :value="address.value" :key="address.value">
                                    {{ address.label }}
                                </option>
                            </select>
                        </div>
                    </section>

                    <section v-if="selectedCommunicationTypes.map(t => t.token).includes('email')"
                        class="rounded-lg border border-sky-200 bg-white/70 p-2.5 transition-all duration-300"
                        :class="{ 'opacity-50 pointer-events-none border-slate-200': !selectedCommunicationTypes.map(t => t.token).includes('email') }">
                        <div class="mb-1.5 flex items-center justify-between transition-all duration-300 gap-2"
                            :class="{ 'text-sky-400': selectedCommunicationTypes.map(t => t.token).includes('email'), 'text-slate-400': !selectedCommunicationTypes.map(t => t.token).includes('email') }">
                            <p class="text-xs font-semibold uppercase tracking-wide">{{ $t('common.email_long') }}</p>
                            <Icon name="ph:envelope-duotone" class="text-lg" />
                        </div>
                        
                        <div class="grid gap-2 text-slate-600 md:grid-cols-[minmax(0,1fr),220px]">
                            <input type="text" v-model="selectedEmail" @input="selectedEmailId = null; emitChange()"
                                :disabled="!selectedCommunicationTypes.map(t => t.token).includes('email')"
                                v-validate-email class="input h-9 rounded-lg border-slate-300 text-sm"
                                :placeholder="$t('customer_service_block.select_email')" aria-label="Email input" />
                            <select v-model="selectedEmailId"
                                :disabled="!selectedCommunicationTypes.map(t => t.token).includes('email')"
                                class="h-9 w-full rounded-lg border border-slate-300 bg-white px-2.5 text-sm text-slate-700 focus:border-slate-500 focus:outline-none"
                                id="contact_email">
                                <option value="" selected="selected">--{{ $t('customer_service_block.select_email') }}
                                </option>
                                <option v-for="email in clientEmails" :value="email.value" :key="email.value">
                                    {{ email.label }}
                                </option>
                            </select>
                        </div>
                    </section>

                    <section v-if="selectedCommunicationTypes.map(t => t.token).includes('electronic_inv')"
                        class="rounded-lg border border-sky-200 bg-white/70 p-2.5 transition-all duration-300"
                        :class="{ 'opacity-50 pointer-events-none border-slate-200': !selectedCommunicationTypes.map(t => t.token).includes('electronic_inv') }">
                        <div class="mb-1.5 flex items-center justify-between transition-all duration-300 gap-2"
                            :class="{ 'text-sky-400': selectedCommunicationTypes.map(t => t.token).includes('electronic_inv'), 'text-slate-400': !selectedCommunicationTypes.map(t => t.token).includes('electronic_inv') }">
                            <p class="text-xs font-semibold uppercase tracking-wide">{{ $t('common.electronic_invoice')
                            }}</p>
                            <Icon name="fa6-solid:file-invoice" class="text-lg" />
                        </div>
                        <div class="grid gap-2 text-slate-600 grid-cols-3">
                            <input type="text" v-model="accountingOffice"
                                :disabled="!selectedCommunicationTypes.map(t => t.token).includes('electronic_inv')"
                                class="input h-9 rounded-lg border-slate-300 text-sm"
                                :placeholder="$t('billing_block.short_accounting_office')"
                                aria-label="Accounting office" />
                            <input type="text" v-model="managingBody"
                                :disabled="!selectedCommunicationTypes.map(t => t.token).includes('electronic_inv')"
                                class="input h-9 rounded-lg border-slate-300 text-sm"
                                :placeholder="$t('billing_block.short_managing_body')" aria-label="Managing body" />
                            <input type="text" v-model="processingUnit"
                                :disabled="!selectedCommunicationTypes.map(t => t.token).includes('electronic_inv')"
                                class="input h-9 rounded-lg border-slate-300 text-sm"
                                :placeholder="$t('billing_block.short_processing_unit')" aria-label="Processing unit" />
                        </div>
                    </section>
                </div>
            </section>

            <hr class="my-2">

            <section class="space-y-3">
                <p v-if="hasElectronicInvoiceType && selectedExtraInformation === 'INVOICES' && requiresInvoicesForElectronicInvoice"
                    class="text-xs font-medium text-amber-600">
                    {{ t('billing_block.no_selected_invoices') }}
                </p>
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <SelectorType :options="clientSelect === 'contract' ? extraInformationTypeOptions : extraInformationTypeOptions.filter(type => type.value !== 'READINGS')"
                        :model-value="selectedExtraInformation" @select="selectExtraInformation" />
                    <div class="flex min-h-[2.25rem] flex-wrap items-center justify-end gap-x-3 gap-y-1">
                        <label v-if="selectedInvoicesContainReadings"
                            class="inline-flex cursor-pointer select-none items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
                            <input type="checkbox" v-model="addReadingsToInvoices" @change="addSelectedInvoiceReadings()"
                                class="h-3.5 w-3.5 shrink-0 rounded border-slate-300 text-sky-600 focus:ring-sky-500" />
                            <span>{{ t('billing_block.add_readings_to_invoices') }}</span>
                        </label>
                        <p v-if="selectedExtraInformation !== 'NONE'" class="text-sm font-medium text-slate-600 text-right">
                            {{ selectedExtraInformationLabel }}:
                            <span class="text-sky-600">{{ selectedExtraInformationCount }}</span>
                        </p>
                    </div>
                </div>

                <div v-if="selectedExtraInformation !== 'NONE'" class="space-y-3">
                    <AppLoading v-if="loadingExtraInformation" />

                    <div v-else-if="filteredExtraInformationItems.length === 0"
                        class="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
                        {{ t('common.no_data') }}
                    </div>

                    <ul v-else class="max-h-80 overflow-y-auto" role="listbox"
                        :aria-label="selectedExtraInformationLabel">
                        <li v-for="item in filteredExtraInformationItems" :key="item.id" role="option"
                            :aria-selected="isExtraInformationSelected(item.id)"
                            class="border-t border-slate-200 last:border-b-0">
                            <button type="button" @click="toggleExtraInformationSelection(item)"
                                class="w-full px-4 py-3 text-left text-sm text-slate-700 transition-colors"
                                :class="isExtraInformationSelected(item.id)
                                    ? 'bg-yellow-50' : 'bg-white hover:bg-slate-50'">
                                <div class="flex items-center gap-3">
                                    <span class="flex h-5 w-5 shrink-0 items-center justify-center self-center">
                                        <Icon class="text-lg transition-all duration-300"
                                            :name="isExtraInformationSelected(item.id) ? 'fa6-solid:circle-check' : 'fa6-regular:circle'"
                                            :class="isExtraInformationSelected(item.id) ? 'text-amber-500' : 'text-slate-300'" />
                                    </span>

                                    <div class="min-w-0 flex-1 space-y-1">
                                        <template v-if="selectedExtraInformation === 'INVOICES'">
                                            <div class="flex flex-wrap justify-between items-center gap-2">
                                                <p class="text-sm font-semibold text-slate-800">
                                                    {{ item.serie_final}} - 
                                                    <span class="text-slate-500 font-medium">{{ item.title_final }}</span>
                                                </p>
                                                <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                                            </div>
                                            <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
                                                <span v-if="item.issue_date">{{ t('billing_block.issue_date') }}: {{ formatDate(item.issue_date) }}</span>
                                                <span v-if="item.due_date">{{ t('common.due_date') }}: {{ formatDate(item.due_date) }}</span>
                                                <span v-if="item.total_final">{{ t('common.total') }}: {{ formatMoneyWithCurrency(item.total_final) }}</span>
                                            </div>
                                        </template>

                                        <template v-else>
                                            <div class="flex flex-wrap gap-x-4 gap-y-1">
                                                <span v-if="item.reading_date" class="font-semibold text-slate-800">
                                                    {{ t('billing_block.reading_date') }}: {{ formatDate(item.reading_date) }}
                                                </span>
                                                <span v-if="item.reading_value" class="font-semibold text-slate-800">
                                                    {{ t('reading') }}: {{ parseInt(item.reading_value) }}
                                                </span>
                                                <span v-if="item.calculated_value" class="font-semibold text-slate-800">
                                                    {{ t('billing_block.consumption') }}: {{ parseInt(item.calculated_value) }}
                                                </span>
                                            </div>
                                            <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                                                <span v-if="item.meter_code">{{ t('meter') }}: {{ item.meter_code }}</span>
                                            </div>
                                            <p v-if="item.alert_notes" class="text-xs font-medium text-amber-600">
                                                {{ item.alert_notes }}
                                            </p>
                                        </template>
                                    </div>
                                </div>
                            </button>
                        </li>
                    </ul>
                </div>

            </section>

        </template>

        <div role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
            :class="{ 'translate-x-0': showRegionDetailComponent, 'translate-x-[2000px]': !showRegionDetailComponent, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeSubRegion()"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <PersonSearch v-if="showRegionDetailComponent === 'PersonSearch'" :id="regionDetailId"
                    :allowCreate="false" @show-subregion="handleSubRegionEvent" @saved="onPersonSaved" />
                <AddContracts v-if="showRegionDetailComponent === 'AddContracts'" :multiple="false"
                    :selected_items="[selectedContract]" @item-clicked="onContractSelected" />
            </div>
        </div>
    </div>
</template>
