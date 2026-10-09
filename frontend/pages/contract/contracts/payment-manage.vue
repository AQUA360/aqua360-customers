<script setup>
import H1 from '~/components/atoms/H1.vue';
import Tabs from '~/components/atoms/Tabs.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import PersonRegion from '~/components/organisms/PersonRegion.vue';
import { useToast } from 'vue-toastification';
import { useRouter } from 'vue-router';
import { checkPermission } from '~/middleware/permission';

const toast = useToast();
const router = useRouter();
const { t } = useI18n();
const objectPermissions = ref(null);
const loading = ref(true);
const loading_contracts = ref(false);

const showRegionComponent = ref(null);
const showRegionDetail = ref(null);
const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const found_contracts = ref([]);
const found_persons = ref([]);
const activeResultTab = ref('contracts');
const setActiveResultTab = (tab) => {
    activeResultTab.value = tab;
};
const no_bank_accounts = ref([]);
const no_contracts = ref([]);
const not_existing_contracts = ref([]);
const processed_file = ref(null)
const searched = ref(false)

const { $ContractApiService } = useNuxtApp();

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
}

const openDetail = (component, id) => {
    showRegionComponent.value = component;
    showRegionDetail.value = id;
    showRegion.value = true;
}

const closeRegion = () => {
    showRegion.value = false;
    showRegionComponent.value = null;
    showRegionDetail.value = null;
    isSubRegionOpen.value = false;
}

const getData = async (data, save = false) => {
    if (save) {
        if (!confirm(t('confirmation_text_block.confirm_apply'))) return;
    }
    loading_contracts.value = true;
    try {
        if (data) processed_file.value = data;
        let save_data = {
            file: data,
            save: save,
        };
        const response = await $ContractApiService.processBankChange(save_data);

        found_contracts.value = response.found_contracts;
        found_persons.value = response.found_persons;
        no_bank_accounts.value = response.no_bank_accounts;
        no_contracts.value = response.no_contracts;
        not_existing_contracts.value = response.non_existent_contracts;
        searched.value = true;
        activeResultTab.value = response.found_contracts?.length > 0 ? 'contracts' : 'persons';
        console.log('found_persons', response.found_persons);

        if (save) {
            toast.success(t('common.correct_save'));
            //return router.push(`/contract/contracts/`);
        }

    } catch (error) {
        console.log(error);
    } finally {
        loading_contracts.value = false;
    }
}

onMounted(async () => {
    objectPermissions.value = await checkPermission($ContractApiService);
    if (!objectPermissions.value.can_change) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
    loading.value = false;
});

</script>

<template>
    <div id="wrapper" class="text-base p-4 max-w-full">
        <div class="flex justify-between items-center mb-6">
            <H1>{{ $t(`contract_block.manage_contracts_payment`) }}</H1>
        </div>
        <div class="p-2 border border-slate-200 rounded text-base">
            <div class="m-3 mb-6">
                <h2 class="text-lg font-bold text-slate-800 mb-3">
                    {{ $t(`contract_block.enter_bank_change`) }}
                </h2>

                <div class="grid grid-cols-2 gap-4">
                    <div class="mb-4 px-4 py-2 bg-slate-50 rounded-lg border border-slate-200">
                        <div class="flex items-center gap-2 mb-2">
                            <Icon name="fa6-solid:upload" class="text-sky-600 text-sm" />
                            <span class="text-sm font-medium text-slate-700">{{ t("common.doc") }}</span>
                        </div>
                        <AtomsInputFile @update="getData" :name="'bankFile'" :uploaded="null" :fullWidth="true"
                            class="w-full" />
                    </div>

                </div>
                <div v-if="searched && !loading_contracts && (found_contracts.length > 0 || found_persons.length > 0)">
                    <Tabs class="bg-sky-50 rounded-t-lg">
                        <li class="me-2">
                            <a href="#tab_contracts" @click.prevent="setActiveResultTab('contracts')"
                                :class="{ 'text-sky-600 border-sky-600': activeResultTab === 'contracts', 'hover:text-gray-600 hover:border-gray-300': activeResultTab !== 'contracts' }">
                                <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />
                                {{ t("contract_block.affected_contracts") }}
                                <span v-if="found_contracts.length > 0"
                                    class="ml-1 px-2 py-0.5 bg-green-200 text-green-700 text-xs font-medium rounded">
                                    {{ found_contracts.length }}
                                </span>
                            </a>
                        </li>
                        <li class="me-2">
                            <a href="#tab_persons" @click.prevent="setActiveResultTab('persons')"
                                :class="{ 'text-sky-600 border-sky-600': activeResultTab === 'persons', 'hover:text-gray-600 hover:border-gray-300': activeResultTab !== 'persons' }">
                                <Icon name="fa6-solid:user" class="display-inline mr-2" />
                                {{ t("contract_block.affected_persons") }}
                                <span v-if="found_persons.length > 0"
                                    class="ml-1 px-2 py-0.5 bg-green-200 text-green-700 text-xs font-medium rounded">
                                    {{ found_persons.length }}
                                </span>
                            </a>
                        </li>
                    </Tabs>

                    <section v-show="activeResultTab === 'contracts'" role="tabpanel" id="tab_contracts"
                        class="bg-white border border-slate-200 rounded-lg overflow-hidden">
                        <div class="px-4 py-2 bg-slate-50 border-b border-slate-200">
                            <div class="flex items-center justify-between">
                                <h3 class="text-sm font-semibold text-slate-700">{{
                                    t("contract_block.affected_contracts")
                                }}</h3>
                                <span v-if="found_contracts.length > 0"
                                    class="px-2 py-1 bg-green-100 text-green-700 text-sm font-medium rounded">
                                    {{ found_contracts.length }}
                                </span>
                            </div>
                        </div>
                        <div v-if="found_contracts.length > 0" class="overflow-x-auto max-h-96">
                            <table class="w-full text-sm">
                                <thead class="bg-slate-50 border-b border-slate-200">
                                    <tr>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                            {{ t("contract") }}
                                        </th>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                            {{ t("common.bank") }}
                                        </th>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                            {{ t("common.swift") }}
                                        </th>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                            {{ t("common.account_bank") }}
                                        </th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-100">
                                    <tr v-for="(contract, index) in found_contracts" :key="index"
                                        class="hover:bg-slate-50 transition-colors">
                                        <td class="px-3 py-2">
                                            <button class="text-sky-600 hover:text-sky-800 text-sm underline"
                                                @click="openDetail('ContractRegion', contract.contract_id)">
                                                {{ contract.contract_token || "-" }}
                                            </button>
                                        </td>
                                        <td class="px-3 py-2 text-slate-900 text-sm">
                                            {{ contract.bank_name || "-" }}
                                        </td>
                                        <td class="px-3 py-2 text-slate-900 text-sm">
                                            {{ contract.swift_code || "-" }}
                                        </td>
                                        <td class="px-3 py-2 text-slate-900 text-sm flex items-center gap-x-2">
                                            <AtomsIBAN :value="contract.bank_account" />
                                            <Icon :name="contract.bank_account == contract.current_bank_account ?
                                                'fa6-solid:circle-check' : 'fa6-solid:circle-xmark'" :class="contract.bank_account == contract.current_bank_account ?
                                                'text-green-600' : 'text-red-600'" />
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <div v-else class="px-4 py-8 text-center text-slate-500 text-sm">
                            {{ t("common.no_data") }}
                        </div>
                    </section>

                    <section v-show="activeResultTab === 'persons'" role="tabpanel" id="tab_persons"
                        class="bg-white border border-slate-200 rounded-lg overflow-hidden">
                        <div class="px-4 py-2 bg-slate-50 border-b border-slate-200">
                            <div class="flex items-center justify-between">
                                <h3 class="text-sm font-semibold text-slate-700">{{
                                    t("contract_block.affected_persons")
                                }}</h3>
                                <span v-if="found_persons.length > 0"
                                    class="px-2 py-1 bg-green-100 text-green-700 text-sm font-medium rounded">
                                    {{ found_persons.length }}
                                </span>
                            </div>
                        </div>
                        <div v-if="found_persons.length > 0" class="overflow-x-auto max-h-96">
                            <table class="w-full text-sm">
                                <thead class="bg-slate-50 border-b border-slate-200">
                                    <tr>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                            {{ t("person") }}
                                        </th>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                            {{ t("common.bank") }}
                                        </th>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                            {{ t("common.swift") }}
                                        </th>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                            {{ t("common.account_bank") }}
                                        </th>
                                        <th class="px-3 py-2 text-left text-sm font-medium text-slate-600 uppercase">
                                        </th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-100">
                                    <tr v-for="(person, index) in found_persons" :key="index"
                                        class="hover:bg-slate-50 transition-colors"
                                        :class="{
                                            'bg-yellow-100': person.contract_no_sepa > 0,
                                        }">
                                        <td class="px-3 py-2">
                                            <button class="text-sky-600 hover:text-sky-800 text-sm underline"
                                                @click="openDetail('PersonRegion', person.person_id)">
                                                {{ `${person.person_token} - ${person.person_name}` || "-" }}
                                            </button>
                                        </td>
                                        <td class="px-3 py-2 text-slate-900 text-sm">
                                            {{ person.bank_name || "-" }}
                                        </td>
                                        <td class="px-3 py-2 text-slate-900 text-sm">
                                            {{ person.swift_code || "-" }}
                                        </td>
                                        <td class="px-3 py-2 text-slate-900 text-sm flex items-center gap-x-2">
                                            <AtomsIBAN :value="person.bank_account" />
                                            <Icon :name="person.already_has_bank_account ?
                                                'fa6-solid:circle-check' : 'fa6-solid:circle-xmark'" :class="person.already_has_bank_account ?
                                                'text-green-600' : 'text-red-600'" />
                                        </td>
                                        <td class="px-3 py-2 text-slate-900 text-sm">
                                            <abbr v-if="person.contract_no_sepa > 0" :title="t('informative_block.info_contract_no_sepa')">
                                                <Icon name="fa6-solid:circle-exclamation" class="text-orange-600" />
                                            </abbr>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <div v-else class="px-4 py-8 text-center text-slate-500 text-sm">
                            {{ t("common.no_data") }}
                        </div>
                    </section>

                    <!-- Warning: No Bank Accounts -->
                    <div v-if="no_bank_accounts.length > 0"
                        class="bg-white border border-amber-200 rounded-lg overflow-hidden mt-4">
                        <div class="px-4 py-2 bg-amber-50 border-b border-amber-200">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <Icon name="fa6-solid:triangle-exclamation" class="text-amber-600 text-sm" />
                                    <h3 class="text-sm font-semibold text-amber-800">
                                        {{ t("informative_block.info_no_bank_accounts") }}
                                    </h3>
                                </div>
                                <span class="px-2 py-1 bg-amber-100 text-amber-700 text-sm font-medium rounded">
                                    {{ no_bank_accounts.length }}
                                </span>
                            </div>
                        </div>
                        <div class="overflow-x-auto max-h-60">
                            <div class="divide-y divide-amber-100">
                                <div v-for="(contract, index) in no_bank_accounts" :key="index"
                                    class="px-4 py-2 hover:bg-amber-50 transition-colors">
                                    <span class="text-sm text-slate-700">{{ contract.contract_token }}</span>
                                </div>
                                
                            </div>
                        </div>
                    </div>

                    <!-- Warning: No Contract Token in Line -->
                    <div v-if="no_contracts.length > 0"
                        class="bg-white border border-orange-200 rounded-lg overflow-hidden mt-4">
                        <div class="px-4 py-2 bg-orange-50 border-b border-orange-200">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <Icon name="fa6-solid:circle-exclamation" class="text-orange-600 text-sm" />
                                    <h3 class="text-sm font-semibold text-orange-800">
                                        {{ t("informative_block.info_no_contract_token_line") }}
                                    </h3>
                                </div>
                                <span class="px-2 py-1 bg-orange-100 text-orange-700 text-sm font-medium rounded">
                                    {{ no_contracts.length }}
                                </span>
                            </div>
                        </div>
                        <div class="overflow-x-auto max-h-60">
                            <div class="divide-y divide-orange-100">
                                <div v-for="(contract, index) in no_contracts" :key="index"
                                    class="px-4 py-2 hover:bg-orange-50 transition-colors">
                                    <span class="text-sm text-slate-700 font-mono">{{ contract.line }}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Error: Non-existing Contracts -->
                    <div v-if="not_existing_contracts.length > 0"
                        class="bg-white border border-red-200 rounded-lg overflow-hidden mt-4">
                        <div class="px-4 py-2 bg-red-50 border-b border-red-200">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-2">
                                    <Icon name="fa6-solid:circle-xmark" class="text-red-600 text-sm" />
                                    <h3 class="text-sm font-semibold text-red-800">
                                        {{ t("informative_block.info_not_existing_contracts") }}
                                    </h3>
                                </div>
                                <span class="px-2 py-1 bg-red-100 text-red-700 text-sm font-medium rounded">
                                    {{ not_existing_contracts.length }}
                                </span>
                            </div>
                        </div>
                        <div class="overflow-x-auto max-h-60">
                            <div class="divide-y divide-red-100">
                                <!-- <div v-for="(contract, index) in not_existing_contracts" :key="index"
                                    class="px-4 py-2 hover:bg-red-50 transition-colors">
                                    <span class="text-sm text-slate-700">{{ contract.contract_token }}</span>
                                </div> -->
                                <div class="overflow-x-auto max-h-96">
                                <table class="w-full text-sm">
                                    <thead class="bg-red-50 border-b border-red-200">
                                        <tr>
                                            <th
                                                class="px-3 py-2 text-left text-sm font-medium text-red-600 uppercase">
                                                {{ t("contract") }}
                                            </th>
                                            <th
                                                class="px-3 py-2 text-left text-sm font-medium text-red-600 uppercase">
                                                {{ t("common.bank") }}
                                            </th>
                                            <th
                                                class="px-3 py-2 text-left text-sm font-medium text-red-600 uppercase">
                                                {{ t("common.swift") }}
                                            </th>
                                            <th
                                                class="px-3 py-2 text-left text-sm font-medium text-red-600 uppercase">
                                                {{ t("common.account_bank") }}
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-slate-100">
                                        <tr v-for="(contract, index) in not_existing_contracts" :key="index"
                                            class="hover:bg-slate-50 transition-colors">
                                            <td class="px-3 py-2">
                                                {{ contract.contract_token || "-" }}
                                            </td>
                                            <td class="px-3 py-2 text-slate-900 text-sm">
                                                {{ contract.bank_name || "-" }}
                                            </td>
                                            <td class="px-3 py-2 text-slate-900 text-sm">
                                                {{ contract.swift_code || "-" }}
                                            </td>
                                            <td class="px-3 py-2 text-slate-900 text-sm flex items-center gap-x-2">
                                                <AtomsIBAN v-if="contract.bank_account" :value="contract.bank_account" />
                                                <span v-else>-</span>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                            </div>
                        </div>
                    </div>
                </div>


                <div v-if="loading_contracts" class="text-center py-8">
                    <div class="w-12 h-12 bg-sky-100 rounded-full flex items-center justify-center mx-auto mb-3">
                        <Icon name="fa6-solid:spinner" class="text-sky-600 animate-spin" />
                    </div>
                    <h3 class="text-sm font-semibold text-slate-800 mb-1">
                        {{ t("customer_service_block.in_process") }}
                    </h3>
                    <p class="text-slate-500 text-xs">
                        {{ t("common.loading") }}...
                    </p>
                </div>

            </div>



            <hr />
            <div class="flex justify-end mt-4">
                <div class="flex gap-3">
                    <NuxtLink class="button-default" to="/contract/contracts/">
                        {{ $t('common.exit') }}
                    </NuxtLink>
                    <button @click="getData(processed_file, true)" class="button-secondary">
                        {{ $t('common.save') }}
                    </button>
                </div>
            </div>
        </div>
        <div role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-[60%] z-20"
            :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="closeRegion" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <ContractRegion v-if="showRegionComponent === 'ContractRegion'" :id="showRegionDetail"
                    @show-subregion="handleSubRegionEvent" />
                <PersonRegion v-if="showRegionComponent === 'PersonRegion'" :id="showRegionDetail"
                    @show-subregion="handleSubRegionEvent" />
            </div>
        </div>
    </div>
</template>
