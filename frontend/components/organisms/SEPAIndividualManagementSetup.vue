<script setup>
import { ca } from 'date-fns/locale';
import { ref, onMounted, nextTick, computed, watch, watchEffect } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import { useI18n } from 'vue-i18n';
import PaymentDetail from '../molecules/PaymentDetail.vue';
import InvoiceDetail from '../molecules/InvoiceDetail.vue';
import InvoicePaymentDetail from '../molecules/InvoicePaymentDetail.vue';
import CommitmentDepositDetail from '../molecules/CommitmentDepositDetail.vue';

const { t } = useI18n();
const route = useRoute()
const router = useRouter()
const toast = useToast();
const { $PaymentApiService, $ProductApiService, $ExploitationApiService, $InvoiceApiService, $CommitmentDepositApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const invoice = ref(null)
const commitment_deposit = ref(null)
const payment = ref(null)
const payment_id = ref(null)

const company_banks = ref([])
const exploitations = ref([])

const selectedFilters = ref([]);
const selectedPayments = ref([]);
const selectedBank = ref(null)
const selectedExploitation = ref(null)
const selectedSendDate = ref(new Date(Date.now() + 1 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])

const emit = defineEmits(['changed']);


const getData = async () => {
    pending.value = true;
    error.value = null;
    try {
        const data = await $PaymentApiService.getDetail(payment_id.value);
        payment.value = data
        selectedPayments.value = [];
        selectedPayments.value = [payment.value.id]

        if (payment.value.invoice) {
            getInvoice()
        } else if (payment.value.commitment_deposit) {
            getCommitmentDeposit()
        }
    } catch (err) {
        error.value = err;
    } finally {
        pending.value = false;
    }
}

const getInvoice = async () => {
    error.value = null;
    try {
        const data = await $InvoiceApiService.getDetail(payment.value.invoice.id);
        invoice.value = data
        selectedFilters.value = [];
        selectedFilters.value.push(invoice.value.origin.id)
        emit('changed', selectedPayments.value, selectedFilters.value, null, null, selectedBank?.value?.value, false, null, null, null, null, selectedSendDate.value);
    } catch (err) {
        error.value = err;
    }
}

const getCommitmentDeposit = async () => {
    error.value = null;
    try {
        const data = await $CommitmentDepositApiService.getDetail(payment.value.commitment_deposit.id);
        commitment_deposit.value = data
        selectedFilters.value = [];
        emit('changed', selectedPayments.value, selectedFilters.value, null, null, selectedBank?.value?.value, false, null, null, null, null, selectedSendDate.value);
    } catch (err) {
        error.value = err;
    }
}

const getExploitations = async () => {
    try {
        const result = await $ExploitationApiService.getData();
        result.results.forEach(i => {
            exploitations.value.push(
                {
                    value: i.id,
                    label: i.name,
                    company: i.company.id
                })
        })
        //exploitations.value = result.results;
        if (exploitations.value.length === 1) {
            selectedExploitation.value = { value: exploitations.value[0].id, label: exploitations.value[0].name, company: exploitations.value[0].company.id }
        }
        getCompanyBanks()
    } catch (err) {
        error.value = err;
    }
}

const getCompanyBanks = async () => {
    try {
        const result = await $ExploitationApiService.getCompanyBanks(selectedExploitation.value ? selectedExploitation.value.company : '');
        result.results.forEach(bank => {
            company_banks.value.push({
                value: bank.id,
                label: bank.bank.name + ' - ' + bank.swift,
            })
            if (bank.is_sepa) {
                selectedBank.value = { value: bank.id, label: bank.bank.name + ' - ' + bank.swift, company: bank.company.id }
                emit('changed', selectedPayments.value, selectedFilters.value, null, null, selectedBank?.value?.value, false, null, null, null, null, selectedSendDate.value);
            }
        })
    } catch (err) {
        error.value = err;
    }
}



const updateSelected = (e) => {
    if (e.entity == 'exploitation') {
        selectedExploitation.value = e.id;
        getCompanyBanks()
    } else if (e.entity == 'bank') {
        selectedBank.value = e.id;
        emit('changed', selectedPayments.value, selectedFilters.value, null, null, selectedBank?.value?.value, false, null, null, null, null, selectedSendDate.value);
    } else if (e.entity == 'send_date') {
        emit('changed', selectedPayments.value, selectedFilters.value, null, null, selectedBank?.value?.value, false, null, null, null, null, selectedSendDate.value);
    }
}


onMounted(() => {
    checkRouteQuery()
    getExploitations()
    getCompanyBanks()
    getData();
    emit('changed', selectedPayments.value, selectedFilters.value, null, null, selectedBank?.value?.value, false, null, null, null, null, selectedSendDate.value);
});

const checkRouteQuery = () => {
    if (route.query?.action == 'idvMng') {
        if (route.query.payment_id) {
            payment_id.value = parseInt(route.query.payment_id)
        }
    }
}



watch(selectedPayments, () => {
    emit('changed', selectedPayments.value, selectedFilters.value, null, null, selectedBank?.value?.value, false, null, null, null, null, selectedSendDate.value);
})


</script>

<template>
    <div id="wrapper" class="p-6 text-gray-800">
        <h2 class="text-2xl font-bold mb-6">
            {{ t("billing_block.invoice_select_title") }}
        </h2>
        <div class="grid grid-cols-2 gap-8">
            <div class="">
                <details open>
                    <summary class="border-b border-slate-300 p-1 my-2 text-slate-500 font-semibold">{{
                        t("billing_block.payment_info") }}</summary>
                    <div class="bg-sky-50 p-2 rounded-xs">
                        <PaymentDetail v-if="payment" :id="payment_id" :data="payment" :isSubRegion="true"
                            :isPayment="false" />
                    </div>
                </details>
                <details v-if="invoice">
                    <summary class="border-b border-slate-300 p-1 my-2 text-slate-500 font-semibold">{{
                        t("billing_block.invoice_info") }}</summary>
                    <div class="bg-sky-50 p-2 rounded-xs">
                        <InvoiceDetail v-if="invoice" :id="invoice.id" :data="invoice" :isSubRegion="true" />
                    </div>
                </details>
                <details v-if="commitment_deposit">
                    <summary class="border-b border-slate-300 p-1 my-2 text-slate-500 font-semibold">{{
                        t("billing_block.commitment_info") }}</summary>
                    <div class="bg-sky-50 p-2 rounded-xs">
                        <CommitmentDepositDetail :id="commitment_deposit.id" :data="commitment_deposit"
                            :isSubRegion="true" />
                    </div>
                </details>
            </div>

            <div>
                <!-- Date Range Selector -->
                <div class="mt-3">
                    <!-- <span class="text-gray-500 font-medium">{{ $t('common.send_date') }} <span
                            class="text-red-500">*</span></span>
                    <AtomsInputDate v-model="selectedSendDate" class="w-full" @update:modelValue="updateSelected({ entity: 'send_date', date: $event })" /> -->

                    <span class="text-slate-500 font-semibold">{{ $t('common.select') }} {{ $t('common.bank') }}</span>
                    <fieldset class="mt-2">
                        <div class="grid grid-cols-[auto,1fr] gap-4 mt-2 items-center">
                            <span class="text-gray-500 font-medium">{{ $t('exploitation') }}</span>
                            <v-select class="block w-full mr-2 required" :disabled="exploitations.length < 2"
                                :model-value="selectedExploitation"
                                @update:modelValue="updateSelected({ entity: 'exploitation', id: $event })"
                                :options="exploitations"></v-select>
                            <span class="text-gray-500 font-medium">{{ $t('common.bank') }}</span>
                            <v-select class="block w-full mr-2 required" :model-value="selectedBank"
                                @update:modelValue="updateSelected({ entity: 'bank', id: $event })"
                                :options="company_banks"></v-select>
                        </div>
                    </fieldset>
                    <div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.selected {
    margin-left: 15px;
}
</style>
