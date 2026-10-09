<script setup>
import { ca } from 'date-fns/locale';
import { ref, onMounted, nextTick, computed, watch, watchEffect } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';


const { t } = useI18n();
const router = useRouter();
const toast = useToast();
const { $PaymentApiService, $ProductApiService, $ExploitationApiService, $BillingApiService, $ConfigProjectApiService } = useNuxtApp();

const props = defineProps({
    payments: Object,
    loading: Boolean,
});

const pending = ref(true);
const error = ref(null);
const items = ref([]);

const loading_data = ref(false)
const is_commitment = ref(false)
const is_piggy_bank = ref(false)

const filter_origin = ref([]);
const filter_date_start = ref(null)
const filter_date_end = ref(null)
const filter_send_at = ref(null)
const company_banks = ref([])
const exploitations = ref([])
const billings = ref([])

const selectedFilters = ref([]);
const selectedPayments = ref(props.payments || []);
const selectedBank = ref(null)
const selectedExploitation = ref(null)
const selectedBilling = ref(null)
const selectedSendDate = ref(new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])

const consumption_origin_token = ref(null)

const filters = ref({})

const emit = defineEmits(['changed']);

const getData = async () => {
    loading_data.value = true;
    error.value = null;
    if (selectedFilters.value.length == 0 && !is_commitment.value && !is_piggy_bank.value) {
        selectedPayments.value = [];
    }
    emit('changed', selectedPayments.value, selectedFilters.value, filter_date_start.value, filter_date_end.value, selectedBank?.value?.value, true, is_commitment.value, is_piggy_bank.value, selectedExploitation.value?.value, selectedBilling.value?.value, selectedSendDate.value, filter_send_at.value);

    try {
        consumption_origin_token.value = await $ConfigProjectApiService.get('origin_reading_token');
    } catch (err) {
        error.value = err;
    } finally {
        loading_data.value = false;
    }

}

const getExploitations = async () => {
    try {
        const result = await $ExploitationApiService.getData();
        result.results;
        result.results.forEach(exploitation => {
            exploitations.value.push({
                value: exploitation.id,
                label: exploitation.name,
                company: exploitation.company.id
            })
        })
        exploitations.value.unshift({
            value: null,
            label: `--`,
        })
        if (exploitations.value.length === 1) {
            selectedExploitation.value = { value: exploitations.value[0].value, label: exploitations.value[0].label, company: exploitations.value[0].company }
        }
        getCompanyBanks()
    } catch (err) {
        error.value = err;
    }
}

const getBillings = async () => {
    try {
        const result = await $BillingApiService.getAll();
        result.results.forEach(billing => {
            billings.value.push({
                value: billing.id,
                label: billing.name,
            })
        })
        billings.value.unshift({
            value: null,
            label: `--`,
        })
    } catch (err) {
        error.value = err;
    }
}

const getCompanyBanks = async () => {
    try {

        const result = await $ExploitationApiService.getCompanyBanks(selectedExploitation?.value?.company || '');
        company_banks.value = [];
        result.results.forEach(bank => {
            if (company_banks.value.find(c => c.value == bank.id)) return
            let bank_name = bank.bank.name + ' - ' + bank.swift
            company_banks.value.push({
                value: bank.id,
                label: bank.is_sepa ? bank_name + ' - (SEPA)' : bank_name,
            })
            if (bank.is_sepa) {
                selectedBank.value = { value: bank.id, label: bank_name + ' - (SEPA)', company: bank.company.id }
            }
        })


    } catch (err) {
        error.value = err;
    }
}

const getFilterOrigin = async () => {
    error.value = null;
    try {
        filter_origin.value = [];
        const result = await $ProductApiService.getOrigins();
        filter_origin.value = result.results

    } catch (err) {
        error.value = err;
    }
}


const typeClicked = (async (payment) => {
    if (!selectedExploitation.value && !selectedBilling.value) {
        toast.warning(t('billing_block.error_select_exploitation'))
        return;
    }
    pending.value = true;
    /* is_commitment.value = false
    is_piggy_bank.value = false */
    if (selectedFilters.value.includes(payment.id)) {
        var index = selectedFilters.value.indexOf(payment.id);
        if (index > -1) {
            selectedFilters.value.splice(index, 1);
        }
    } else {
        selectedFilters.value.push(payment.id)
    }


    try {
        await getData();
    } catch (e) {
        console.error(e)
    } finally {
        pending.value = false;
    }

})

const commitmentClicked = async () => {
    pending.value = true;
    is_commitment.value = !is_commitment.value
    /* is_piggy_bank.value = false
    selectedFilters.value = [] */
    try {
        await getData();
    } catch (e) {
        console.error(e)
    } finally {
        pending.value = false;
    }
}

const piggyBankClicked = async () => {
    pending.value = true;
    is_piggy_bank.value = !is_piggy_bank.value
    /* is_commitment.value = false
    selectedFilters.value = [] */
    try {
        await getData();
    } catch (e) {
        console.error(e)
    } finally {
        pending.value = false;
    }
}

const updateDate = () => {
    if (selectedFilters.value.length > 0) {
        getData();
    }
}

const updateSelected = async (e) => {
    if (e.entity == 'exploitation') {
        console.log(e.id)
        if (e.id?.value == null) {
            selectedExploitation.value = null;
        } else {
            selectedExploitation.value = e.id;
        }
        await getCompanyBanks()
        if (selectedBank.value) {
            emit('changed', selectedPayments.value, selectedFilters.value, filter_date_start.value, filter_date_end.value, selectedBank?.value?.value, true, is_commitment.value, is_piggy_bank.value, selectedExploitation.value?.value, selectedBilling.value?.value, selectedSendDate.value, filter_send_at.value);
        }
    } else if (e.entity == 'bank') {
        selectedBank.value = e.id;
        if (selectedExploitation.value || selectedBilling.value) {
            emit('changed', selectedPayments.value, selectedFilters.value, filter_date_start.value, filter_date_end.value, selectedBank?.value?.value, true, is_commitment.value, is_piggy_bank.value, selectedExploitation.value?.value, selectedBilling.value?.value, selectedSendDate.value, filter_send_at.value);
        }
    } else if (e.entity == 'billing') {
        selectedBilling.value = e.id;
        if (e.id?.value == null) {
            selectedBilling.value = null;
            if (!selectedExploitation.value) {
                selectedFilters.value = [];
            }
        } else {
            selectedBilling.value = e.id;
            selectedExploitation.value = null;
            selectedFilters.value = [];
            selectedFilters.value.push(filter_origin.value.find(o => o.token == consumption_origin_token.value)?.id);
        }
        emit('changed', selectedPayments.value, selectedFilters.value, filter_date_start.value, filter_date_end.value, selectedBank?.value?.value, true, is_commitment.value, is_piggy_bank.value, selectedExploitation.value?.value, selectedBilling.value?.value, selectedSendDate.value, filter_send_at.value);
    }
}


onMounted(() => {
    getExploitations()
    getBillings()
    getData();
    getFilterOrigin();
    getCompanyBanks();
});

watch(() => props.loading, () => {
    loading_data.value = props.loading;
}, { immediate: true });

watch(() => props.payments, () => {
    selectedPayments.value = props.payments || [];
}, { immediate: true, deep: true })

watch([filter_date_start, filter_date_end, filter_send_at], () => {
    getData();
})




</script>

<template>
    <div id="wrapper" class="p-6 text-gray-800">
        <h2 class="text-2xl font-bold mb-6">
            {{ t("billing_block.invoice_select_title") }}
        </h2>

        <div class="grid grid-cols-2 gap-8">
            <!-- Payment Options -->
            <div class="space-y-3">

                <div v-for="item in filter_origin" :key="item.id" @click="selectedBilling ? null : typeClicked(item)"
                    class="flex items-center justify-between w-56 px-5 py-3 rounded-lg border shadow-sm transition-all duration-200 text-gray-600 bg-gray-50"
                    :class="{
                        'bg-sky-100 text-sky-600 font-semibold': selectedFilters.includes(item.id),
                        'cursor-not-allowed opacity-70': selectedBilling,
                        'cursor-pointer hover:bg-sky-100 hover:text-sky-600 hover:shadow-md': !selectedBilling,
                    }">

                    <span
                        :class="{ 'ml-[15px] font-semibold text-sky-500 hover:text-sky-700 hover:font-bold': selectedFilters.includes(item.id) }"
                        class="px-1 text-nowrap transition-all duration-200">{{ item.name }}</span>

                    <span
                        :class="{ 'ml-[15px] font-semibold text-sky-500 hover:text-sky-700 hover:font-bold': selectedFilters.includes(item.id) }">
                        <Icon name="fa6-solid:angles-right" class="text-[13px]" />
                    </span>
                </div>
                <div @click="selectedBilling ? null : commitmentClicked()"
                    class="flex items-center justify-between w-56 px-5 py-3 rounded-lg border shadow-sm transition-all duration-200 text-gray-600 bg-gray-50"
                    :class="{
                        'bg-sky-100 text-sky-600 font-semibold': is_commitment,
                        'cursor-not-allowed opacity-70': selectedBilling,
                        'cursor-pointer hover:bg-sky-100 hover:text-sky-600 hover:shadow-md': !selectedBilling,
                    }">
                    <!-- <div 
                    class="flex items-center justify-between w-56 px-5 py-3 rounded-lg border shadow-sm transition-all duration-200 text-gray-600 bg-gray-50 opacity-50 cursor-not-allowed"> -->
                    <span
                        :class="{ 'ml-[15px] font-semibold text-sky-500 hover:text-sky-700 hover:font-bold': is_commitment }"
                        class="px-1 text-nowrap transition-all duration-200">{{ t('claim_block.commitment') }}</span>

                    <span
                        :class="{ 'ml-[15px] font-semibold text-sky-500 hover:text-sky-700 hover:font-bold': is_commitment }">
                        <Icon name="fa6-solid:angles-right" class="text-[13px]" />
                    </span>
                </div>
                <!-- <div @click="piggyBankClicked()"
                    class="flex items-center justify-between w-56 px-5 py-3 rounded-lg border cursor-pointer shadow-sm transition-all duration-200 text-gray-600 bg-gray-50 hover:bg-sky-100 hover:text-sky-600 hover:shadow-md"
                    :class="{ 'bg-sky-100 text-sky-600 font-semibold': is_piggy_bank }">
                    <span
                        :class="{ 'ml-[15px] font-semibold text-sky-500 hover:text-sky-700 hover:font-bold': is_piggy_bank }"
                        class="px-1 text-nowrap transition-all duration-200">{{ t('Retorn de saldo') }}</span>

                    <span
                        :class="{ 'ml-[15px] font-semibold text-sky-500 hover:text-sky-700 hover:font-bold': is_piggy_bank }">
                        <Icon name="fa6-solid:angles-right" class="text-[13px]" />
                    </span>
                </div> -->
                <div>

                </div>
            </div>

            <!-- Payment Details -->
            <div class="space-y-4">
                <!-- Configuration Section -->
                <div class="bg-white rounded-lg p-4 border border-gray-200 shadow-sm space-y-4">
                    <!-- Compact Summary Row -->
                    <div class="flex items-center gap-4 pb-3 border-b border-gray-100">
                        <div class="flex items-center gap-2 min-w-[140px]">
                            <span class="text-sm font-medium text-gray-500">{{ $t('billing_block.selected_payments') }}:</span>
                            <span v-if="!loading_data" class="text-lg font-bold text-sky-600">
                                {{ selectedPayments ? selectedPayments.length : 0 }}
                            </span>
                            <Icon v-if="!loading_data && selectedPayments?.length == 0" 
                                name="fa6-solid:circle-exclamation" 
                                :title="t('common.no_data_found')"
                                class="text-orange-500 text-sm" />
                            <Icon v-if="loading_data" name="fa6-solid:spinner" class="animate-spin text-sky-500" />
                        </div>
                        <!-- <div class="flex items-center gap-2 flex-1">
                            <span class="text-sm font-medium text-gray-500">{{ $t('common.remittance_date') }} <span class="text-red-500">*</span></span>
                            <AtomsInputDate v-model="selectedSendDate" class="flex-1" @update:modelValue="updateDate()" />
                        </div> -->
                    </div>

                    <!-- Exploitation & Billing -->
                    <div class="grid grid-cols-[120px,1fr] gap-x-3 gap-y-2.5 items-center">
                        <span class="text-sm font-medium text-gray-600">{{ $t('exploitation') }}</span>
                        <v-select 
                            class="w-full required" 
                            :disabled="exploitations.length < 2"
                            :model-value="selectedExploitation"
                            @update:modelValue="updateSelected({ entity: 'exploitation', id: $event })"
                            :options="exploitations"
                        />
                        
                        <span class="text-sm font-medium text-gray-600">{{ $t('billing') }}</span>
                        <v-select 
                            class="w-full required" 
                            :disabled="billings.length == 0"
                            :model-value="selectedBilling"
                            @update:modelValue="updateSelected({ entity: 'billing', id: $event })"
                            :options="billings"
                        />
                    </div>

                    <div class="border-t border-gray-100"></div>

                    <!-- Payment Range -->
                    <div>
                        <h3 class="text-[10px] font-semibold text-gray-500 uppercase  mb-2">
                            {{ $t('common.select') }} {{ $t('common.send_date_expected').toLowerCase() }} ({{ $t('invoice') }})
                        </h3>
                        <div class="grid grid-cols-[120px,1fr] gap-x-3 items-center">
                            <span class="text-sm font-medium text-gray-600">{{ $t('common.date') }}</span>
                            <AtomsInputDate v-model="filter_send_at" class="w-full" @update:modelValue="updateDate()" />
                        </div>
                    </div>
                    
                    <div class="border-t border-gray-100"></div>

                    <div>
                        <h3 class="text-[10px] font-semibold text-gray-500 uppercase  mb-2">
                            {{ $t('billing_block.payment_range') }}
                        </h3>
                        <div class="grid grid-cols-[120px,1fr] gap-x-3 items-center">
                            <span class="text-sm font-medium text-gray-600">{{ $t('common.from') }}</span>
                            <AtomsInputDate v-model="filter_date_start" class="w-full" @update:modelValue="updateDate()" />
                            
                            <span class="text-sm font-medium text-gray-600">{{ $t('common.to') }}</span>
                            <AtomsInputDate v-model="filter_date_end" class="w-full" @update:modelValue="updateDate()" />
                        </div>
                    </div>

                    <div class="border-t border-gray-100"></div>

                    <!-- Bank Selection -->
                    <div>
                        <h3 class="text-[10px] font-semibold text-gray-500 uppercase  mb-2">
                            {{ $t('common.select') }} {{ $t('common.bank') }}
                        </h3>
                        <div class="grid grid-cols-[120px,1fr] gap-3 items-center">
                            <span class="text-sm font-medium text-gray-600">{{ $t('common.bank') }}</span>
                            <v-select 
                                class="w-full required" 
                                :model-value="selectedBank"
                                @update:modelValue="updateSelected({ entity: 'bank', id: $event })"
                                :options="company_banks"
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
